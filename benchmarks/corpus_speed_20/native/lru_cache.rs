//! Handwritten ordered cache replay with validated, resumable snapshots.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, HashMap},
    fs,
    path::Path,
};
const COUNTERS: [&str; 13] = [
    "steps",
    "gets",
    "hits",
    "misses",
    "puts",
    "overwrites",
    "dropped",
    "deletes",
    "deleted",
    "evictions",
    "resizes",
    "peeks",
    "inspections",
];
fn capacity(v: &Value) -> Result<usize> {
    let n = integer(v)?;
    require((0..=256).contains(&n), "capacity must be 0..256")?;
    Ok(n as usize)
}
fn key(v: &Value) -> Result<&str> {
    let s = string(v)?;
    require(
        (1..=128).contains(&s.len()),
        "key must contain 1..128 UTF-8 bytes",
    )?;
    Ok(s)
}
fn depth(v: &Value, level: usize) -> Result<()> {
    require(level <= 16, "value nesting exceeds 16")?;
    match v {
        Value::Array(a) => {
            for x in a {
                depth(x, level + 1)?;
            }
        }
        Value::Object(o) => {
            for x in o.values() {
                depth(x, level + 1)?;
            }
        }
        _ => (),
    }
    Ok(())
}
fn value_check(v: &Value) -> Result<()> {
    depth(v, 0)?;
    require(
        rt::json_canonical_view(v)?.len() <= 16384,
        "value exceeds 16 KiB",
    )
}
struct Cache {
    capacity: usize,
    values: HashMap<String, (u64, Value)>,
    order: BTreeMap<u64, String>,
    clock: u64,
    stats: BTreeMap<&'static str, i64>,
}
impl Cache {
    fn new(capacity: usize) -> Self {
        Self {
            capacity,
            values: HashMap::new(),
            order: BTreeMap::new(),
            clock: 0,
            stats: COUNTERS.into_iter().map(|s| (s, 0)).collect(),
        }
    }
    fn bump(&mut self, name: &'static str) -> Result<()> {
        let n = self.stats.get_mut(name).unwrap();
        *n = n.checked_add(1).ok_or("integer overflow")?;
        Ok(())
    }
    fn remove(&mut self, name: &str) -> Option<Value> {
        self.values.remove(name).map(|(tick, value)| {
            self.order.remove(&tick);
            value
        })
    }
    fn insert(&mut self, name: String, value: Value) {
        self.clock += 1;
        self.order.insert(self.clock, name.clone());
        self.values.insert(name, (self.clock, value));
    }
    fn entries(&self) -> Value {
        Value::Array(
            self.order
                .values()
                .map(|k| json!({"key":k,"value":self.values[k].1}))
                .collect(),
        )
    }
    fn metrics(&self) -> Result<Value> {
        let rate = if self.stats["gets"] == 0 {
            0.0
        } else {
            rt::int_true_div(self.stats["hits"], self.stats["gets"])?
        };
        Ok(json!({"counters": self.stats, "hit_rate":rate}))
    }
    fn apply(&mut self, command: &Value) -> Result<Value> {
        let op = string(&command["op"])?;
        require(
            matches!(op, "GET" | "PUT" | "DELETE" | "RESIZE" | "PEEK" | "INSPECT"),
            "unknown cache operation",
        )?;
        exact(
            command,
            match op {
                "PUT" => &["op", "key", "value"],
                "RESIZE" => &["op", "capacity"],
                "INSPECT" => &["op"],
                _ => &["op", "key"],
            },
        )?;
        let name = if matches!(op, "GET" | "PUT" | "DELETE" | "PEEK") {
            key(&command["key"])?
        } else {
            ""
        };
        if op == "PUT" {
            value_check(&command["value"])?;
        }
        let size = if op == "RESIZE" {
            capacity(&command["capacity"])?
        } else {
            self.capacity
        };
        self.bump("steps")?;
        let mut event = json!({"step":self.stats["steps"],"op":op});
        let found = self.values.contains_key(name);
        match op {
            "GET" | "PEEK" => {
                event["key"] = json!(name);
                event["hit"] = json!(found);
                event["value"] = self
                    .values
                    .get(name)
                    .map(|(_, v)| v.clone())
                    .unwrap_or(Value::Null);
                if op == "GET" {
                    self.bump("gets")?;
                    self.bump(if found { "hits" } else { "misses" })?;
                    if let Some(value) = self.remove(name) {
                        self.insert(name.into(), value);
                    }
                } else {
                    self.bump("peeks")?;
                }
            }
            "PUT" => {
                self.bump("puts")?;
                let previous = self.remove(name).unwrap_or(Value::Null);
                if found {
                    self.bump("overwrites")?;
                }
                if size > 0 {
                    self.insert(name.into(), command["value"].clone());
                } else {
                    self.bump("dropped")?;
                }
                event["key"] = json!(name);
                event["stored"] = json!(size > 0);
                event["replaced"] = json!(found);
                event["previous"] = previous;
            }
            "DELETE" => {
                self.bump("deletes")?;
                event["value"] = self.remove(name).unwrap_or(Value::Null);
                if found {
                    self.bump("deleted")?;
                }
                event["key"] = json!(name);
                event["deleted"] = json!(found);
            }
            "RESIZE" => {
                self.bump("resizes")?;
                event["capacity"] = json!(size);
            }
            _ => {
                self.bump("inspections")?;
                event["capacity"] = json!(size);
                event["entries"] = self.entries();
                event["stats"] = self.metrics()?;
            }
        }
        if matches!(op, "PUT" | "RESIZE") {
            let mut evicted = Vec::new();
            while self.values.len() > size {
                let name = self.order.first_key_value().unwrap().1.clone();
                let value = self.remove(&name).unwrap();
                evicted.push(json!({"key":name,"value":value}));
                self.bump("evictions")?;
            }
            event["evicted"] = Value::Array(evicted);
        }
        self.capacity = size;
        Ok(event)
    }
    fn save(&self) -> Result<String> {
        let state = json!({"version":1,"capacity":self.capacity,"entries":self.entries(),"stats":self.stats});
        let hash = digest(rt::json_canonical_view(&state)?.as_bytes());
        Ok(rt::json_canonical_view(&json!({"state":state,"sha256":hash}))? + "\n")
    }
    fn restore(envelope: &Value, expected: usize) -> Result<Self> {
        exact(envelope, &["state", "sha256"])?;
        let state = &envelope["state"];
        require(
            digest(rt::json_canonical_view(state)?.as_bytes()) == string(&envelope["sha256"])?,
            "state checksum mismatch",
        )?;
        exact(state, &["version", "capacity", "entries", "stats"])?;
        require(
            integer(&state["version"])? == 1,
            "unsupported cache state version",
        )?;
        let size = capacity(&state["capacity"])?;
        require(
            size == expected,
            "configured capacity differs from saved state",
        )?;
        let mut cache = Self::new(size);
        for entry in state["entries"].as_array().ok_or("expected array")? {
            exact(entry, &["key", "value"])?;
            let name = key(&entry["key"])?;
            require(
                !cache.values.contains_key(name),
                "duplicate saved cache key",
            )?;
            value_check(&entry["value"])?;
            cache.insert(name.into(), entry["value"].clone());
        }
        require(cache.values.len() <= size, "saved cache exceeds capacity")?;
        exact(&state["stats"], &COUNTERS)?;
        for name in COUNTERS {
            let n = integer(&state["stats"][name])?;
            require(n >= 0, "negative saved counter")?;
            cache.stats.insert(name, n);
        }
        let n = |k: &str| cache.stats[k] as i128;
        require(
            n("gets") == n("hits") + n("misses"),
            "inconsistent get counters",
        )?;
        require(n("deleted") <= n("deletes"), "inconsistent delete counters")?;
        require(
            n("overwrites") + n("dropped") <= n("puts"),
            "inconsistent put counters",
        )?;
        require(
            cache.values.len() as i128
                == n("puts") - n("overwrites") - n("dropped") - n("deleted") - n("evictions"),
            "inconsistent saved entry accounting",
        )?;
        require(
            n("steps")
                == ["gets", "puts", "deletes", "resizes", "peeks", "inspections"]
                    .iter()
                    .map(|k| n(k))
                    .sum::<i128>(),
            "inconsistent saved operation count",
        )?;
        Ok(cache)
    }
}
fn run() -> Result<()> {
    let mode = std::env::var("LRU_MODE").unwrap_or_else(|_| "preview".into());
    require(
        matches!(mode.as_str(), "preview" | "write"),
        "invalid LRU mode",
    )?;
    let configuration = Document::read(
        absolute(
            &std::env::var("LRU_CONFIG").unwrap_or_else(|_| "cache-job.json".into()),
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
    let mut cache = Cache::new(capacity(&config["capacity"])?);
    let mut documents = Vec::new();
    let state_path = string(&config["state"])?;
    if !state_path.is_empty() {
        let original = Document::read(absolute(state_path, base)?, 8388608)?;
        cache = Cache::restore(
            &rt::json_loads(std::str::from_utf8(&original.data)?)?,
            cache.capacity,
        )?;
        documents.push(original);
    }
    let trace = Document::read(absolute(string(&config["trace"])?, base)?, 4194304)?;
    let raw = rt::json_loads(std::str::from_utf8(&trace.data)?)?;
    let commands = raw.as_array().ok_or("expected array")?;
    require(commands.len() <= 2000, "trace exceeds 2000 commands")?;
    let before = cache.stats["steps"];
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
    let report = json!({"before_steps":before,"after_steps":cache.stats["steps"],"commands":commands.len(),"capacity":cache.capacity,"entries":cache.entries(),"stats":cache.metrics()?});
    let files = BTreeMap::from([
        ("state.json".into(), state),
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
    let staging = parent.join(format!(".lru-cache-{}", rt::random_token()?));
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
