//! Handwritten bounded redaction; only fixed phase messages escape error boundaries.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde::Serialize;
use serde_json::{json, Value};
use std::{collections::BTreeMap, path::PathBuf};
#[derive(PartialEq)]
enum Component {
    Key(String),
    Index(usize),
}
struct Rule {
    literal: bool,
    pattern: String,
    replacement: String,
}
struct Config {
    input: PathBuf,
    output: PathBuf,
    skip_missing: bool,
    targets: Vec<Vec<Component>>,
    rules: Vec<Rule>,
}
fn load(document: &Document) -> Result<Config> {
    let config = document.json()?;
    exact(
        &config,
        &["version", "input", "output", "missing", "targets", "rules"],
    )?;
    require(integer(&config["version"])? == 1, "unsupported version")?;
    let policy = string(&config["missing"])?;
    require(
        matches!(policy, "skip" | "error"),
        "invalid missing-field policy",
    )?;
    let base = document.path.parent().ok_or("missing parent")?;
    let input = absolute(string(&config["input"])?, base)?;
    let output = absolute(string(&config["output"])?, base)?;
    require(
        input != document.path && !output.exists() && !output.is_symlink(),
        "input/output conflict",
    )?;
    let raw = config["targets"]
        .as_array()
        .ok_or("expected targets array")?;
    require((1..=32).contains(&raw.len()), "expected 1..32 targets")?;
    let mut targets: Vec<Vec<Component>> = Vec::with_capacity(raw.len());
    for value in raw {
        let components = value.as_array().ok_or("expected target path")?;
        require(
            (1..=16).contains(&components.len()),
            "expected 1..16 path components",
        )?;
        let mut path = Vec::with_capacity(components.len());
        for component in components {
            path.push(if let Some(key) = component.as_str() {
                require(key.len() <= 128, "path key too long")?;
                Component::Key(key.into())
            } else {
                let index = integer(component)?;
                require((0..=4095).contains(&index), "invalid array index")?;
                Component::Index(index as usize)
            });
        }
        for previous in &targets {
            let n = previous.len().min(path.len());
            require(previous[..n] != path[..n], "overlapping target paths")?;
        }
        targets.push(path);
    }
    let raw = config["rules"].as_array().ok_or("expected rules array")?;
    require((1..=32).contains(&raw.len()), "expected 1..32 rules")?;
    let mut rules = Vec::with_capacity(raw.len());
    for rule in raw {
        exact(rule, &["kind", "pattern", "replacement"])?;
        let kind = string(&rule["kind"])?;
        require(matches!(kind, "literal" | "regex"), "invalid rule kind")?;
        let pattern = string(&rule["pattern"])?;
        let replacement = string(&rule["replacement"])?;
        require(
            (1..=512).contains(&pattern.len()) && replacement.len() <= 256,
            "rule text limit exceeded",
        )?;
        if kind == "regex" {
            require(!rt::regex_search(pattern, "")?, "regex matches empty input")?;
        }
        rules.push(Rule {
            literal: kind == "literal",
            pattern: pattern.into(),
            replacement: replacement.into(),
        });
    }
    Ok(Config {
        input,
        output,
        skip_missing: policy == "skip",
        targets,
        rules,
    })
}
fn select<'a>(mut value: &'a mut Value, path: &[Component]) -> Result<Option<&'a mut Value>> {
    for component in path {
        let child = match component {
            Component::Key(key) => value
                .as_object_mut()
                .ok_or("expected object at target path")?
                .get_mut(key),
            Component::Index(index) => value
                .as_array_mut()
                .ok_or("expected array at target path")?
                .get_mut(*index),
        };
        let Some(child) = child else {
            return Ok(None);
        };
        value = child;
    }
    require(value.is_string(), "expected string at target")?;
    Ok(Some(value))
}
#[derive(Serialize)]
struct RuleCount {
    index: usize,
    matches: usize,
    matched_fields: usize,
    changed_fields: usize,
}
#[derive(Serialize)]
struct TargetCount {
    index: usize,
    present: usize,
    missing: usize,
    changed: usize,
}
#[derive(Serialize)]
struct Audit {
    version: usize,
    records: usize,
    changed_records: usize,
    selected_fields: usize,
    missing_fields: usize,
    changed_fields: usize,
    matches: usize,
    input_bytes: usize,
    output_bytes: usize,
    rules: Vec<RuleCount>,
    targets: Vec<TargetCount>,
}
fn apply(original: &str, rules: &[Rule], counters: &mut [RuleCount]) -> Result<(String, usize)> {
    require(original.len() <= 65536, "selected field too large")?;
    let mut text = original.to_owned();
    let mut total = 0;
    for (rule, counter) in rules.iter().zip(counters) {
        let (count, removed) = if rule.literal {
            let count = text.match_indices(&rule.pattern).count();
            (count, count * rule.pattern.len())
        } else {
            let matches = rt::regex_findall(&rule.pattern, &text)?;
            (matches.len(), matches.iter().map(String::len).sum())
        };
        require(
            text.len() - removed + count * rule.replacement.len() <= 65536,
            "field expansion limit",
        )?;
        let updated = if rule.literal {
            text.replace(&rule.pattern, &rule.replacement)
        } else {
            rt::regex_replace(&rule.pattern, &rule.replacement, &text)?
        };
        counter.matches += count;
        counter.matched_fields += usize::from(count > 0);
        counter.changed_fields += usize::from(updated != text);
        total += count;
        text = updated;
    }
    Ok((text, total))
}
fn process(config: &Config, data: &[u8]) -> Result<(Vec<u8>, Audit)> {
    let mut audit = Audit {
        version: 1,
        records: 0,
        changed_records: 0,
        selected_fields: 0,
        missing_fields: 0,
        changed_fields: 0,
        matches: 0,
        input_bytes: data.len(),
        output_bytes: 0,
        rules: (0..config.rules.len())
            .map(|index| RuleCount {
                index,
                matches: 0,
                matched_fields: 0,
                changed_fields: 0,
            })
            .collect(),
        targets: (0..config.targets.len())
            .map(|index| TargetCount {
                index,
                present: 0,
                missing: 0,
                changed: 0,
            })
            .collect(),
    };
    let mut output = Vec::new();
    let mut offset = 0;
    while offset < data.len() {
        require(audit.records < 1024, "record count limit")?;
        let window = &data[offset..data.len().min(offset + 65537)];
        let size = window
            .iter()
            .position(|b| *b == b'\n')
            .map_or(window.len(), |i| i + 1);
        require(size <= 65536, "record byte limit")?;
        let mut record = rt::json_loads_unique(std::str::from_utf8(&window[..size])?)?;
        require(record.is_object(), "expected object record")?;
        offset += size;
        let mut changed = false;
        for (path, target) in config.targets.iter().zip(&mut audit.targets) {
            let Some(selected) = select(&mut record, path)? else {
                require(config.skip_missing, "missing required field")?;
                target.missing += 1;
                audit.missing_fields += 1;
                continue;
            };
            let original = selected.as_str().unwrap();
            let (masked, count) = apply(original, &config.rules, &mut audit.rules)?;
            audit.matches += count;
            require(audit.matches <= 1000000, "match count limit")?;
            target.present += 1;
            audit.selected_fields += 1;
            if masked != original {
                *selected = Value::String(masked);
                changed = true;
                target.changed += 1;
                audit.changed_fields += 1;
            }
        }
        let encoded = canonical(&record)?;
        require(
            encoded.len() <= 262144 && output.len() + encoded.len() <= 4194304,
            "output expansion limit",
        )?;
        output.extend(encoded);
        audit.records += 1;
        audit.changed_records += usize::from(changed);
    }
    audit.output_bytes = output.len();
    Ok((output, audit))
}
fn render(data: Vec<u8>, audit: &Audit) -> Result<BTreeMap<String, Vec<u8>>> {
    let mut lines = vec![
        "Structured-log redaction".into(),
        format!("Records: {}", audit.records),
        format!("Changed records: {}", audit.changed_records),
        format!("Matches: {}", audit.matches),
    ];
    for counter in &audit.rules {
        lines.push(format!(
            "Rule {}: {}",
            counter.index,
            rt::json_canonical_view(&serde_json::to_value(counter)?)?
        ));
    }
    for counter in &audit.targets {
        lines.push(format!(
            "Target {}: {}",
            counter.index,
            rt::json_canonical_view(&serde_json::to_value(counter)?)?
        ));
    }
    let mut files: BTreeMap<String, Vec<u8>> = BTreeMap::from([
        ("redacted.jsonl".into(), data),
        (
            "audit.json".into(),
            canonical(&serde_json::to_value(audit)?)?,
        ),
        ("report.txt".into(), (lines.join("\n") + "\n").into_bytes()),
    ]);
    let manifest: BTreeMap<_, _> = files
        .iter()
        .map(|(name, data)| {
            (
                name.clone(),
                json!({"bytes":data.len(),"sha256":digest(data)}),
            )
        })
        .collect();
    files.insert(
        "manifest.json".into(),
        canonical(&json!({"version":1,"files":manifest}))?,
    );
    Ok(files)
}
fn run() -> std::result::Result<(), &'static str> {
    let (document, config) = (|| -> Result<_> {
        let document = Document::read(
            absolute(
                &std::env::var("REDACTOR_CONFIG").unwrap_or_else(|_| "redactor-job.json".into()),
                &std::env::current_dir()?,
            )?,
            65536,
        )?;
        let config = load(&document)?;
        Ok((document, config))
    })()
    .map_err(|_| "Redactor configuration failed")?;
    let (source, data, audit) = (|| -> Result<_> {
        let source = Document::read(config.input.clone(), 4194304)?;
        let (data, audit) = process(&config, &source.data)?;
        Ok((source, data, audit))
    })()
    .map_err(|_| "Redactor input processing failed")?;
    (|| -> Result<()> {
        publish_exact(
            &config.output,
            render(data, &audit)?,
            &[document, source],
            "redactor",
        )?;
        Ok(())
    })()
    .map_err(|_| "Redactor publication failed")?;
    let text = canonical(&serde_json::to_value(audit).map_err(|_| "Redactor publication failed")?)
        .map_err(|_| "Redactor publication failed")?;
    print!(
        "{}",
        std::str::from_utf8(&text).map_err(|_| "Redactor publication failed")?
    );
    Ok(())
}
fn main() {
    if let Err(message) = run() {
        eprintln!("{message}");
        std::process::exit(2);
    }
}
