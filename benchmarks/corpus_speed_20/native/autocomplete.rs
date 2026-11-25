//! Handwritten Unicode trie with owned updates and deterministic ranked suggestions.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::{collections::BTreeMap, fs, path::Path};
fn capacity(v: &Value) -> Result<usize> {
    let n = integer(v)?;
    require((1..=128).contains(&n), "capacity must be 1..128")?;
    Ok(n as usize)
}
fn normalized(v: &Value, allow_empty: bool) -> Result<String> {
    let s = string(v)?;
    require(
        s.chars().count() <= 128 && s.len() <= 512,
        "text exceeds 128 characters or 512 UTF-8 bytes",
    )?;
    let result = rt::casefold(&rt::unicode_normalize("NFKC", s)?);
    require(
        result.chars().count() <= 128 && result.len() <= 512,
        "normalized text exceeds bounds",
    )?;
    require(allow_empty || !result.is_empty(), "term must not be empty")?;
    Ok(result)
}
fn usage(v: &Value) -> Result<i64> {
    let n = integer(v)?;
    require((0..=1000000000).contains(&n), "usage must be 0..1000000000")?;
    Ok(n)
}
struct Term {
    spelling: String,
    uses: i64,
}
struct Node {
    term: Option<Term>,
    children: BTreeMap<char, Node>,
    nodes: usize,
    words: usize,
}
impl Node {
    fn new() -> Self {
        Self {
            term: None,
            children: BTreeMap::new(),
            nodes: 1,
            words: 0,
        }
    }
    fn find(&self, key: &str) -> Option<&Node> {
        let mut node = self;
        for c in key.chars() {
            node = node.children.get(&c)?;
        }
        Some(node)
    }
    fn change(&mut self, key: &[char], term: Option<Term>) {
        if let Some((&c, rest)) = key.split_first() {
            let child = self.children.entry(c).or_insert_with(Node::new);
            // A newly created empty child has not contributed to cached counts yet.
            let old_nodes = if child.words == 0 { 0 } else { child.nodes };
            let old_words = child.words;
            child.change(rest, term);
            let new_words = child.words;
            let new_nodes = if new_words == 0 { 0 } else { child.nodes };
            self.nodes = self.nodes - old_nodes + new_nodes;
            self.words = self.words - old_words + new_words;
            if new_words == 0 {
                self.children.remove(&c);
            }
        } else {
            self.words =
                self.words - usize::from(self.term.is_some()) + usize::from(term.is_some());
            self.term = term;
        }
    }
    fn entry(&self, key: &str) -> Value {
        let term = self.term.as_ref().unwrap();
        json!({"key":key,"term":term.spelling,"uses":term.uses})
    }
    fn collect<'a>(&'a self, prefix: &mut String, out: &mut Vec<(String, &'a Node)>) {
        if self.term.is_some() {
            out.push((prefix.clone(), self));
        }
        for (&c, child) in &self.children {
            let end = prefix.len();
            prefix.push(c);
            child.collect(prefix, out);
            prefix.truncate(end);
        }
    }
    fn entries(&self) -> Value {
        let mut entries = Vec::new();
        self.collect(&mut String::new(), &mut entries);
        Value::Array(entries.into_iter().map(|(k, n)| n.entry(&k)).collect())
    }
}
struct Index {
    capacity: usize,
    steps: i64,
    root: Node,
}
impl Index {
    fn new(capacity: usize) -> Self {
        Self {
            capacity,
            steps: 0,
            root: Node::new(),
        }
    }
    fn summary(&self) -> Value {
        json!({"terms":self.root.words,"nodes":self.root.nodes,"capacity":self.capacity})
    }
    fn suggest(&self, prefix: &str, offset: i64, limit: i64) -> Result<Value> {
        require(
            (0..=128).contains(&offset) && (1..=128).contains(&limit),
            "invalid suggestion pagination",
        )?;
        let mut selected = Vec::new();
        if let Some(node) = self.root.find(prefix) {
            node.collect(&mut prefix.to_owned(), &mut selected);
        }
        selected.sort_by(|(ka, a), (kb, b)| {
            b.term
                .as_ref()
                .unwrap()
                .uses
                .cmp(&a.term.as_ref().unwrap().uses)
                .then_with(|| ka.cmp(kb))
        });
        let count = selected.len();
        let hits: Vec<_> = selected
            .into_iter()
            .skip(offset as usize)
            .take(limit as usize)
            .map(|(k, n)| n.entry(&k))
            .collect();
        Ok(json!({"prefix":prefix,"hits":hits,"count":count,"more":offset+limit<count as i64}))
    }
    fn apply(&mut self, command: &Value) -> Result<Value> {
        let op = string(&command["op"])?;
        require(
            matches!(
                op,
                "PUT" | "HIT" | "GET" | "DELETE" | "SUGGEST" | "EXPORT" | "INSPECT"
            ),
            "unknown autocomplete operation",
        )?;
        require(self.steps < 1000000000, "lifetime command limit reached")?;
        let mut event = json!({"step":self.steps+1,"op":op});
        if matches!(op, "PUT" | "HIT" | "GET" | "DELETE") {
            exact(
                command,
                match op {
                    "PUT" => &["op", "term", "uses"],
                    "HIT" => &["op", "term", "amount"],
                    _ => &["op", "term"],
                },
            )?;
            let key = normalized(&command["term"], false)?;
            let original = self.root.find(&key).filter(|n| n.term.is_some());
            let found = original.is_some();
            event["key"] = json!(key);
            event["found"] = json!(found);
            match op {
                "PUT" => {
                    let uses = usage(&command["uses"])?;
                    let accepted = found || self.root.words < self.capacity;
                    event["accepted"] = json!(accepted);
                    if !accepted {
                        event["reason"] = json!("capacity");
                    } else {
                        self.root.change(
                            &key.chars().collect::<Vec<_>>(),
                            Some(Term {
                                spelling: string(&command["term"])?.into(),
                                uses,
                            }),
                        );
                        event["entry"] = self.root.find(&key).unwrap().entry(&key);
                    }
                }
                "HIT" => {
                    let amount = integer(&command["amount"])?;
                    require(
                        (1..=1000000).contains(&amount),
                        "hit amount must be 1..1000000",
                    )?;
                    if let Some(node) = original {
                        let old = node.term.as_ref().unwrap();
                        let uses = usage(&json!(old.uses + amount))?;
                        let spelling = old.spelling.clone();
                        self.root.change(
                            &key.chars().collect::<Vec<_>>(),
                            Some(Term { spelling, uses }),
                        );
                        event["entry"] = self.root.find(&key).unwrap().entry(&key);
                    }
                }
                "GET" => {
                    event["entry"] = original.map(|n| n.entry(&key)).unwrap_or(Value::Null);
                }
                _ => {
                    if found {
                        self.root.change(&key.chars().collect::<Vec<_>>(), None);
                    }
                }
            }
        } else if op == "SUGGEST" {
            exact(command, &["op", "prefix", "offset", "limit"])?;
            let prefix = normalized(&command["prefix"], true)?;
            event["result"] = self.suggest(
                &prefix,
                integer(&command["offset"])?,
                integer(&command["limit"])?,
            )?;
        } else {
            exact(command, &["op"])?;
            if op == "EXPORT" {
                event["entries"] = self.root.entries();
            } else {
                event["index"] = self.summary();
            }
        }
        require(self.root.nodes <= 8192, "trie exceeds 8192 nodes")?;
        self.steps += 1;
        Ok(event)
    }
    fn save(&self) -> Result<String> {
        let state = json!({"version":1,"capacity":self.capacity,"steps":self.steps,"entries":self.root.entries(),"nodes":self.root.nodes});
        let hash = digest(rt::json_canonical_view(&state)?.as_bytes());
        Ok(rt::json_canonical_view(&json!({"state":state,"sha256":hash}))? + "\n")
    }
    fn restore(envelope: &Value, expected: usize) -> Result<Self> {
        exact(envelope, &["state", "sha256"])?;
        let state = &envelope["state"];
        require(
            string(&envelope["sha256"])? == digest(rt::json_canonical_view(state)?.as_bytes()),
            "snapshot checksum mismatch",
        )?;
        exact(state, &["version", "capacity", "steps", "entries", "nodes"])?;
        require(
            integer(&state["version"])? == 1,
            "unsupported autocomplete version",
        )?;
        let size = capacity(&state["capacity"])?;
        require(
            size == expected,
            "configured capacity differs from saved state",
        )?;
        let mut index = Self::new(size);
        for value in state["entries"].as_array().ok_or("expected array")? {
            exact(value, &["key", "term", "uses"])?;
            let key = normalized(&value["term"], false)?;
            require(
                string(&value["key"])? == key,
                "saved key differs from normalized term",
            )?;
            require(
                !index.root.find(&key).is_some_and(|n| n.term.is_some()),
                "duplicate normalized term",
            )?;
            require(index.root.words < size, "saved trie exceeds capacity")?;
            index.root.change(
                &key.chars().collect::<Vec<_>>(),
                Some(Term {
                    spelling: string(&value["term"])?.into(),
                    uses: usage(&value["uses"])?,
                }),
            );
            require(index.root.nodes <= 8192, "trie exceeds 8192 nodes")?;
        }
        index.steps = integer(&state["steps"])?;
        require(
            (0..=1000000000).contains(&index.steps),
            "invalid step count",
        )?;
        require(
            integer(&state["nodes"])? == index.root.nodes as i64,
            "saved node count differs from rebuilt trie",
        )?;
        Ok(index)
    }
}
fn run() -> Result<()> {
    let mode = std::env::var("AUTOCOMPLETE_MODE").unwrap_or_else(|_| "preview".into());
    require(
        matches!(mode.as_str(), "preview" | "write"),
        "invalid autocomplete mode",
    )?;
    let configuration = Document::read(
        absolute(
            &std::env::var("AUTOCOMPLETE_CONFIG")
                .unwrap_or_else(|_| "autocomplete-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let config = rt::json_loads(std::str::from_utf8(&configuration.data)?)?;
    exact(&config, &["trace", "state", "capacity", "output"])?;
    let base = configuration.path.parent().ok_or("missing parent")?;
    let output = absolute(string(&config["output"])?, base)?;
    require(
        !output.exists() && !output.is_symlink(),
        "output directory already exists",
    )?;
    let mut cache = Index::new(capacity(&config["capacity"])?);
    let mut documents = Vec::new();
    let state_path = string(&config["state"])?;
    if !state_path.is_empty() {
        let original = Document::read(absolute(state_path, base)?, 8388608)?;
        cache = Index::restore(
            &rt::json_loads(std::str::from_utf8(&original.data)?)?,
            cache.capacity,
        )?;
        documents.push(original);
    }
    let trace = Document::read(absolute(string(&config["trace"])?, base)?, 4194304)?;
    let raw = rt::json_loads(std::str::from_utf8(&trace.data)?)?;
    let commands = raw.as_array().ok_or("expected array")?;
    require(commands.len() <= 2000, "trace exceeds 2000 commands")?;
    let before = cache.steps;
    let mut events = String::new();
    for (index, command) in commands.iter().enumerate() {
        let result = (|| -> Result<()> {
            let event = cache.apply(command)?;
            let encoded = rt::json_canonical_view(&event)?;
            require(
                events.len() + encoded.len() + 1 <= 16777216,
                "events exceed 16 MiB",
            )?;
            events.push_str(&encoded);
            events.push('\n');
            Ok(())
        })();
        result.map_err(|e| format!("command {}: {e}", index + 1))?;
    }
    let state = cache.save()?;
    require(state.len() <= 8388608, "state exceeds 8 MiB")?;
    let report = json!({"before_steps":before,"after_steps":cache.steps,"commands":commands.len(),"index":cache.summary()});
    let files = BTreeMap::from([
        ("state.json".into(), state),
        (
            "dictionary.json".into(),
            rt::json_canonical_view(&cache.root.entries())? + "\n",
        ),
        ("events.jsonl".into(), events),
        ("report.json".into(), rt::pretty(&report)? + "\n"),
    ]);
    documents.push(configuration);
    documents.push(trace);
    for doc in &documents {
        doc.unchanged()?;
    }
    if mode == "write" {
        publish_bundle(&output, &files, &documents)?;
    }
    println!("{}", rt::pretty(&report)?);
    Ok(())
}
fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        std::process::exit(2);
    }
}

fn publish_bundle(
    output: &Path,
    files: &BTreeMap<String, String>,
    documents: &[Document],
) -> Result<()> {
    let parent = output.parent().ok_or("missing parent")?;
    let staging = parent.join(format!(".autocomplete-{}", rt::random_token()?));
    fs::create_dir(&staging)?;
    let result = (|| -> Result<()> {
        for (name, text) in files {
            rt::write_text_atomic(staging.join(name).to_str().ok_or("invalid path")?, text)?;
        }
        fs::File::open(&staging)?.sync_all()?;
        for doc in documents {
            doc.unchanged()?;
        }
        rt::rename_no_replace(
            staging.to_str().ok_or("invalid path")?,
            output.to_str().ok_or("invalid path")?,
        )?;
        fs::File::open(parent)?.sync_all()?;
        Ok(())
    })();
    if staging.exists() {
        fs::remove_dir_all(&staging)?;
    }
    result
}
