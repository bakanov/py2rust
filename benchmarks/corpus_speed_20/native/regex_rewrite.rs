//! Handwritten preview planner; shared regex engine preserves Python's anchor rules.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::collections::BTreeSet;

struct Rule<'a> {
    name: &'a str,
    pattern: &'a str,
    replacement: &'a str,
}
fn validate_pattern(pattern: &str) -> Result<()> {
    let bytes = pattern.as_bytes();
    let (mut inside, mut first, mut negate) = (false, false, false);
    let (mut depth, mut index) = (0_i32, 0);
    while index < bytes.len() {
        let character = bytes[index];
        if character == b'\\' {
            index += 1;
            require(index < bytes.len(), "trailing escape")?;
            if bytes[index] == b'x' {
                require(
                    index + 2 < bytes.len()
                        && bytes[index + 1..index + 3]
                            .iter()
                            .all(u8::is_ascii_hexdigit),
                    "invalid hex escape",
                )?;
                index += 2;
            } else {
                require(
                    b"AbBdDsSwWZfnrtv\\.^$*+?{}[]()|-".contains(&bytes[index]),
                    "unsupported escape",
                )?;
            }
            first = false;
            negate = false;
        } else if inside {
            require(character != b'[', "escape literal brackets")?;
            require(
                ![b"&&".as_slice(), b"--", b"~~", b"||"]
                    .contains(&&bytes[index..(index + 2).min(bytes.len())]),
                "class set operations unsupported",
            )?;
            if character == b']' && !first {
                inside = false;
            }
            if character != b'^' || !negate {
                first = false;
            }
            negate = false;
        } else {
            match character {
                b'[' => {
                    inside = true;
                    first = true;
                    negate = true;
                }
                b'{' => {
                    let end = bytes[index + 1..]
                        .iter()
                        .position(|&byte| byte == b'}')
                        .map(|offset| index + 1 + offset)
                        .ok_or("escape literal braces")?;
                    require(
                        rt::regex_fullmatch("[0-9]{1,4}(,[0-9]{0,4})?", &pattern[index + 1..end])?,
                        "invalid repetition",
                    )?;
                    index = end;
                    require(bytes.get(index + 1) != Some(&b'+'), "possessive repetition")?;
                }
                b'}' => return Err("escape literal braces".into()),
                b'*' | b'+' | b'?' => require(
                    !matches!(bytes.get(index + 1), Some(b'+' | b'*')),
                    "stacked repetition",
                )?,
                b'(' => {
                    depth += 1;
                    require(depth <= 32, "group nesting exceeds 32")?;
                }
                b')' => {
                    depth -= 1;
                    require(depth >= 0, "unbalanced group")?;
                }
                _ => {}
            }
        }
        index += 1;
    }
    require(depth == 0 && !inside, "unbalanced structure")
}
fn load_rules(value: &Value) -> Result<Vec<Rule<'_>>> {
    let entries = value.as_array().ok_or("expected rules")?;
    require((1..=32).contains(&entries.len()), "expected 1..32 rules")?;
    let mut names = BTreeSet::new();
    let mut rules = Vec::new();
    for entry in entries {
        exact(entry, &["name", "pattern", "replacement"])?;
        let name = string(&entry["name"])?;
        require(
            rt::regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,63}", name)? && names.insert(name),
            "invalid rule name",
        )?;
        let pattern = string(&entry["pattern"])?;
        let replacement = string(&entry["replacement"])?;
        require(
            (1..=512).contains(&pattern.len()) && !pattern.contains('\0') && pattern.is_ascii(),
            "invalid pattern",
        )?;
        require(
            replacement.len() <= 4096 && !replacement.contains('\0'),
            "invalid replacement",
        )?;
        validate_pattern(pattern)?;
        rt::regex_findall(pattern, "")?;
        rules.push(Rule {
            name,
            pattern,
            replacement,
        });
    }
    Ok(rules)
}
fn transform(mut text: String, rules: &[Rule<'_>]) -> Result<(String, Vec<Value>)> {
    let mut events = Vec::new();
    for rule in rules {
        let matches = rt::regex_findall(rule.pattern, &text)?;
        let removed: usize = matches.iter().map(String::len).sum();
        let expected = text.len() - removed + matches.len() * rule.replacement.len();
        require(expected <= 65536, "replacement exceeds byte limit")?;
        let changed = rt::regex_replace(rule.pattern, rule.replacement, &text)?;
        require(
            changed.len() == expected,
            "replacement byte accounting mismatch",
        )?;
        events.push(json!({"rule":rule.name,"matches":matches.len(),"bytes_before":text.len(),"bytes_after":expected,
            "before_sha256":digest(text.as_bytes()),"after_sha256":digest(changed.as_bytes()),"changed":changed != text}));
        text = changed;
    }
    Ok((text, events))
}
fn run() -> Result<Value> {
    require(
        std::env::var("REWRITE_MODE").unwrap_or_else(|_| "preview".into()) == "preview",
        "native baseline supports preview only",
    )?;
    let config = Document::read(
        absolute(
            &std::env::var("REWRITE_CONFIG").unwrap_or_else(|_| "rewrite-job.json".into()),
            &std::env::current_dir()?,
        )?,
        1048576,
    )?;
    let value = config.json()?;
    exact(&value, &["backup", "files", "rules", "version"])?;
    require(integer(&value["version"])? == 1, "unsupported version")?;
    let rules = load_rules(&value["rules"])?;
    let base = config.path.parent().unwrap();
    let backup = absolute(string(&value["backup"])?, base)?;
    let lock = format!("{}.lock", backup.to_str().ok_or("invalid path")?);
    require(
        std::path::Path::new(&lock) != config.path,
        "lock collides with configuration",
    )?;
    let inputs = value["files"].as_array().ok_or("expected files")?;
    require((1..=64).contains(&inputs.len()), "expected 1..64 files")?;
    let mut paths = vec![config.path.clone()];
    let mut rows = Vec::new();
    let mut count = 0;
    for input in inputs {
        let path = absolute(string(input)?, base)?;
        let name = path.to_str().ok_or("invalid path")?;
        require(
            path != backup && name != lock,
            "input collides with backup or lock",
        )?;
        for previous in &paths {
            require(
                path != *previous && !rt::path_same(name, previous.to_str().unwrap())?,
                "input alias",
            )?;
        }
        if std::path::Path::new(&lock).exists() || std::path::Path::new(&lock).is_symlink() {
            require(!rt::path_same(name, &lock)?, "input aliases lock")?;
        }
        let document = Document::read(path.clone(), 65536)?;
        let metadata = document.metadata();
        require(
            (0..=511).contains(&integer(&metadata["mode"])?),
            "special permissions unsupported",
        )?;
        let text = std::str::from_utf8(&document.data)?;
        require(!text.contains('\0'), "input contains NUL")?;
        let (rewritten, events) = transform(text.to_owned(), &rules)?;
        let changed = document.data != rewritten.as_bytes();
        count += usize::from(changed);
        rows.push(json!({"path":name,"index":rows.len(),"changed":changed,"before_sha256":digest(&document.data),
            "after_sha256":digest(rewritten.as_bytes()),"bytes_before":document.data.len(),"bytes_after":rewritten.len(),
            "preview_before":text.chars().take(160).collect::<String>(),"preview_after":rewritten.chars().take(160).collect::<String>(),
            "mode":metadata["mode"],"mtime_ns":metadata["mtime_ns"],"rules":events}));
        paths.push(path);
    }
    let report = json!({"version":1,"files":rows,"changed":count});
    require(
        rt::json_canonical_view(&report)?.len() <= 1048576,
        "audit exceeds 1 MiB",
    )?;
    Ok(json!({"mode":"preview","report":report}))
}
fn main() {
    match run().and_then(|report| rt::json_canonical_view(&report)) {
        Ok(text) => println!("{text}"),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    }
}
