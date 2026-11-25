//! Handwritten deterministic JSON differences and guarded edits with independent undo.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::Path,
};
fn encoded(value: &Value) -> Result<String> {
    rt::json_canonical_view(value)
}
fn same(left: &Value, right: &Value) -> Result<bool> {
    Ok(encoded(left)? == encoded(right)?)
}
fn hash(value: &Value) -> Result<String> {
    Ok(digest(encoded(value)?.as_bytes()))
}
fn child(path: &str, key: &str) -> String {
    format!("{path}/{}", key.replace('~', "~0").replace('/', "~1"))
}
fn nodes(value: &Value, path: &str, depth: usize, limit: usize) -> Result<usize> {
    require(
        depth <= 24 && path.len() <= 4096,
        "document nesting/path limit exceeded",
    )?;
    let mut count = 1;
    match value {
        Value::Object(values) => {
            for (key, value) in values {
                count += nodes(value, &child(path, key), depth + 1, limit)?;
                require(count <= limit, "document node limit exceeded")?;
            }
        }
        Value::Array(values) => {
            for (index, value) in values.iter().enumerate() {
                count += nodes(value, &child(path, &index.to_string()), depth + 1, limit)?;
                require(count <= limit, "document node limit exceeded")?;
            }
        }
        _ => {}
    }
    Ok(count)
}
fn validate(value: &Value, limit: usize) -> Result<usize> {
    require(encoded(value)?.len() <= 4194304, "document exceeds 4 MiB")?;
    nodes(value, "", 0, limit)
}
fn tokens(path: &str) -> Result<Vec<String>> {
    require(
        path.len() <= 4096 && (path.is_empty() || path.starts_with('/')),
        "invalid pointer",
    )?;
    let mut chars = path.chars();
    while let Some(c) = chars.next() {
        if c == '~' {
            require(
                matches!(chars.next(), Some('0' | '1')),
                "invalid pointer escape",
            )?;
        }
    }
    let parts = if path.is_empty() {
        Vec::new()
    } else {
        path[1..]
            .split('/')
            .map(|s| s.replace("~1", "/").replace("~0", "~"))
            .collect::<Vec<_>>()
    };
    require(parts.len() <= 24, "pointer exceeds 24 levels")?;
    Ok(parts)
}
fn array_index(token: &str, len: usize, insertion: bool) -> Result<usize> {
    require(
        !token.is_empty()
            && token.bytes().all(|b| b.is_ascii_digit())
            && (token == "0" || !token.starts_with('0')),
        "array index must be canonical nonnegative decimal",
    )?;
    let index = token.parse::<i64>()?;
    require(
        if insertion {
            index as u64 <= len as u64
        } else {
            (index as u64) < len as u64
        },
        "array index is out of bounds",
    )?;
    Ok(index as usize)
}
fn differences(
    before: &Value,
    after: &Value,
    path: &str,
    limit: usize,
    result: &mut Vec<Value>,
) -> Result<()> {
    if same(before, after)? {
        return Ok(());
    }
    match (before, after) {
        (Value::Object(left), Value::Object(right)) => {
            let keys: BTreeSet<_> = left.keys().chain(right.keys()).collect();
            for key in keys {
                let following = child(path, key);
                match (left.get(key), right.get(key)) {
                    (None, Some(value)) => result
                        .push(json!({"op":"add","path":following,"before":null,"after":value})),
                    (Some(value), None) => result
                        .push(json!({"op":"remove","path":following,"before":value,"after":null})),
                    (Some(left), Some(right)) => {
                        differences(left, right, &following, limit, result)?
                    }
                    _ => unreachable!(),
                }
                require(result.len() <= limit, "patch change limit exceeded")?;
            }
        }
        (Value::Array(left), Value::Array(right)) => {
            for index in 0..left.len().min(right.len()) {
                differences(
                    &left[index],
                    &right[index],
                    &child(path, &index.to_string()),
                    limit,
                    result,
                )?;
                require(result.len() <= limit, "patch change limit exceeded")?;
            }
            for index in (right.len()..left.len()).rev() {
                result.push(json!({"op":"remove","path":child(path,&index.to_string()),"before":left[index],"after":null}));
                require(result.len() <= limit, "patch change limit exceeded")?;
            }
            for (index, value) in right.iter().enumerate().skip(left.len()) {
                result.push(json!({"op":"add","path":child(path,&index.to_string()),"before":null,"after":value}));
                require(result.len() <= limit, "patch change limit exceeded")?;
            }
        }
        _ => result.push(json!({"op":"replace","path":path,"before":before,"after":after})),
    }
    Ok(())
}
fn difference(before: &Value, after: &Value, limit: usize) -> Result<Value> {
    let mut changes = Vec::new();
    differences(before, after, "", limit, &mut changes)?;
    Ok(
        json!({"version":1,"base_sha256":hash(before)?,"target_sha256":hash(after)?,"changes":changes}),
    )
}
fn validate_patch(
    patch: &Value,
    node_limit: usize,
    change_limit: usize,
) -> Result<Vec<Vec<String>>> {
    exact(
        patch,
        &["version", "base_sha256", "target_sha256", "changes"],
    )?;
    require(
        integer(&patch["version"])? == 1,
        "unsupported patch version",
    )?;
    for key in ["base_sha256", "target_sha256"] {
        let text = string(&patch[key])?;
        require(
            text.len() == 64
                && text
                    .bytes()
                    .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)),
            "invalid document hash",
        )?;
    }
    let changes = patch["changes"]
        .as_array()
        .ok_or("expected changes array")?;
    require(changes.len() <= change_limit, "patch change limit exceeded")?;
    let mut parsed = Vec::with_capacity(changes.len());
    for change in changes {
        exact(change, &["op", "path", "before", "after"])?;
        let op = string(&change["op"])?;
        require(
            matches!(op, "add" | "remove" | "replace"),
            "unsupported patch operation",
        )?;
        let path = string(&change["path"])?;
        parsed.push(tokens(path)?);
        require(
            !path.is_empty() || op == "replace",
            "root permits only replacement",
        )?;
        require(
            op != "add" || change["before"].is_null(),
            "add requires null before placeholder",
        )?;
        require(
            op != "remove" || change["after"].is_null(),
            "remove requires null after placeholder",
        )?;
        validate(&change["before"], node_limit)?;
        validate(&change["after"], node_limit)?;
    }
    Ok(parsed)
}
fn edit(value: &mut Value, parts: &[String], change: &Value) -> Result<()> {
    let op = string(&change["op"])?;
    let Some((token, tail)) = parts.split_first() else {
        require(
            op == "replace" && same(value, &change["before"])?,
            "old value mismatch",
        )?;
        *value = change["after"].clone();
        return Ok(());
    };
    if let Value::Object(object) = value {
        if !tail.is_empty() {
            edit(
                object.get_mut(token).ok_or("missing parent object key")?,
                tail,
                change,
            )?;
        } else if op == "add" {
            require(
                !object.contains_key(token),
                "add would replace an existing object key",
            )?;
            object.insert(token.clone(), change["after"].clone());
        } else {
            require(
                object
                    .get(token)
                    .is_some_and(|v| same(v, &change["before"]).unwrap_or(false)),
                "old value mismatch",
            )?;
            if op == "remove" {
                object.remove(token);
            } else {
                object.insert(token.clone(), change["after"].clone());
            }
        }
    } else {
        let items = value.as_array_mut().ok_or("path traverses a scalar")?;
        let position = array_index(token, items.len(), tail.is_empty() && op == "add")?;
        if !tail.is_empty() {
            edit(&mut items[position], tail, change)?;
        } else if op == "add" {
            items.insert(position, change["after"].clone());
        } else {
            require(
                same(&items[position], &change["before"])?,
                "old value mismatch",
            )?;
            if op == "remove" {
                items.remove(position);
            } else {
                items[position] = change["after"].clone();
            }
        }
    }
    Ok(())
}
fn apply(base: &Value, patch: &Value, node_limit: usize, change_limit: usize) -> Result<Value> {
    let paths = validate_patch(patch, node_limit, change_limit)?;
    require(
        hash(base)? == string(&patch["base_sha256"])?,
        "stale base document",
    )?;
    // One private copy preserves the caller's base on every later guard failure.
    let mut result = base.clone();
    for (change, path) in patch["changes"].as_array().unwrap().iter().zip(paths) {
        edit(&mut result, &path, change)?;
        validate(&result, node_limit)?;
    }
    require(
        hash(&result)? == string(&patch["target_sha256"])?,
        "target document hash mismatch",
    )?;
    require(
        hash(base)? == string(&patch["base_sha256"])?,
        "source value was mutated",
    )?;
    Ok(result)
}
fn reverse(patch: &Value) -> Value {
    let changes: Vec<_> = patch["changes"]
        .as_array()
        .unwrap()
        .iter()
        .rev()
        .map(|change| {
            let op = match change["op"].as_str().unwrap() {
                "add" => "remove",
                "remove" => "add",
                _ => "replace",
            };
            json!({"op":op,"path":change["path"],"before":change["after"],"after":change["before"]})
        })
        .collect();
    json!({"version":1,"base_sha256":patch["target_sha256"],"target_sha256":patch["base_sha256"],"changes":changes})
}
// Match per-file atomic writes (including parent sync), then publish the complete directory.
fn publish_bundle(
    output: &Path,
    files: &BTreeMap<String, String>,
    documents: &[Document],
) -> Result<()> {
    let parent = output.parent().ok_or("missing parent")?;
    let staging = parent.join(format!(".json-patch-{}", rt::random_token()?));
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
fn run() -> Result<()> {
    let mode = std::env::var("PATCH_MODE").unwrap_or_else(|_| "preview".into());
    require(
        matches!(mode.as_str(), "preview" | "write"),
        "invalid patch mode",
    )?;
    let configuration = Document::read(
        absolute(
            &std::env::var("PATCH_CONFIG").unwrap_or_else(|_| "patch-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let config = rt::json_loads(std::str::from_utf8(&configuration.data)?)?;
    let action = string(&config["action"])?;
    require(matches!(action, "diff" | "apply"), "invalid patch action")?;
    let input_name = if action == "diff" { "target" } else { "patch" };
    exact(
        &config,
        &[
            "action",
            "base",
            input_name,
            "output",
            "max_nodes",
            "max_changes",
        ],
    )?;
    let node_limit = integer(&config["max_nodes"])?;
    let change_limit = integer(&config["max_changes"])?;
    require(
        (1..=20000).contains(&node_limit) && (1..=2000).contains(&change_limit),
        "invalid patch limits",
    )?;
    let (node_limit, change_limit) = (node_limit as usize, change_limit as usize);
    let parent = configuration.path.parent().ok_or("missing parent")?;
    let output = absolute(string(&config["output"])?, parent)?;
    require(
        !output.exists() && !output.is_symlink(),
        "output directory already exists",
    )?;
    let original = Document::read(absolute(string(&config["base"])?, parent)?, 4194304)?;
    let incoming = Document::read(
        absolute(string(&config[input_name])?, parent)?,
        if action == "diff" { 4194304 } else { 16777216 },
    )?;
    let base = rt::json_loads(std::str::from_utf8(&original.data)?)?;
    let other = rt::json_loads(std::str::from_utf8(&incoming.data)?)?;
    let before_nodes = validate(&base, node_limit)?;
    let patch = if action == "diff" {
        validate(&other, node_limit)?;
        difference(&base, &other, change_limit)?
    } else {
        other.clone()
    };
    let patch_text = encoded(&patch)? + "\n";
    require(patch_text.len() <= 16777216, "patch exceeds 16 MiB")?;
    let target = apply(&base, &patch, node_limit, change_limit)?;
    if action == "diff" {
        require(
            same(&target, &other)?,
            "generated patch did not reconstruct target",
        )?;
    }
    let undo = reverse(&patch);
    require(
        same(&apply(&target, &undo, node_limit, change_limit)?, &base)?,
        "undo did not reconstruct base",
    )?;
    let mut counts = BTreeMap::from([("add", 0), ("remove", 0), ("replace", 0)]);
    for change in patch["changes"].as_array().unwrap() {
        *counts.get_mut(string(&change["op"])?).unwrap() += 1;
    }
    let report = json!({"action":action,"base_sha256":hash(&base)?,"target_sha256":hash(&target)?,"base_nodes":before_nodes,"target_nodes":validate(&target,node_limit)?,"changes":patch["changes"].as_array().unwrap().len(),"operations":counts});
    let mut files = BTreeMap::from([("report.json".into(), rt::pretty(&report)? + "\n")]);
    if action == "diff" {
        files.insert("patch.json".into(), patch_text);
    } else {
        files.insert("result.json".into(), encoded(&target)?);
        files.insert("undo.json".into(), encoded(&undo)? + "\n");
    }
    require(
        files.values().all(|v| v.len() <= 16777216),
        "output bundle file exceeds 16 MiB",
    )?;
    let documents = [configuration, original, incoming];
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
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
