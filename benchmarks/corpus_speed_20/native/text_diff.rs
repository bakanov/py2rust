//! Handwritten complete diff-mode job with the same LCS tie rule and context merging.
mod common;
use common::*;
use serde_json::{json, Value};
use std::collections::BTreeMap;
fn lines(data: &[u8]) -> Result<Vec<&str>> {
    require(data.len() <= 65536, "text byte limit exceeded")?;
    let text = std::str::from_utf8(data)?;
    let (mut start, mut offset) = (0, 0);
    let mut result = Vec::new();
    while offset < data.len() {
        let current = data[offset];
        offset += 1;
        if current == 10 || current == 13 {
            if current == 13 && data.get(offset) == Some(&10) {
                offset += 1;
            }
            result.push(&text[start..offset]);
            start = offset;
        }
    }
    if start < data.len() {
        result.push(&text[start..]);
    }
    require(result.len() <= 1024, "text line limit exceeded")?;
    Ok(result)
}
fn identity(data: &[u8]) -> Result<Value> {
    Ok(
        json!({"bytes":data.len(),"lines":lines(data)?.len(),"sha256":digest(data),"ending":if data.ends_with(b"\r\n") {"crlf"} else if data.ends_with(b"\n") {"lf"} else if data.ends_with(b"\r") {"cr"} else {"none"}}),
    )
}
fn align<'a>(before: &[&'a str], after: &[&'a str]) -> Result<Vec<(&'static str, &'a str)>> {
    let width = after.len() + 1;
    let cells = (before.len() + 1) * width;
    require(cells <= 1050625, "alignment cell budget exceeded")?;
    let mut table = vec![0usize; cells];
    for left in (0..before.len()).rev() {
        for right in (0..after.len()).rev() {
            let here = left * width + right;
            table[here] = if before[left] == after[right] {
                table[here + width + 1] + 1
            } else {
                table[here + width].max(table[here + 1])
            };
        }
    }
    let (mut left, mut right) = (0, 0);
    let mut edits = Vec::new();
    while left < before.len() || right < after.len() {
        if left < before.len() && right < after.len() && before[left] == after[right] {
            edits.push((" ", before[left]));
            left += 1;
            right += 1;
        } else if left < before.len()
            && (right == after.len()
                || table[(left + 1) * width + right] >= table[left * width + right + 1])
        {
            edits.push(("-", before[left]));
            left += 1;
        } else {
            edits.push(("+", after[right]));
            right += 1;
        }
    }
    Ok(edits)
}
fn hunks(edits: &[(&str, &str)], context: usize) -> Vec<Value> {
    let mut intervals: Vec<(usize, usize)> = Vec::new();
    let mut old = vec![0];
    let mut new = vec![0];
    for (index, (kind, _)) in edits.iter().enumerate() {
        old.push(old.last().unwrap() + usize::from(*kind != "+"));
        new.push(new.last().unwrap() + usize::from(*kind != "-"));
        if *kind != " " {
            let start = index.saturating_sub(context);
            let end = edits.len().min(index + context + 1);
            if let Some(last) = intervals.last_mut().filter(|(_, end)| start <= *end) {
                last.1 = end;
            } else {
                intervals.push((start, end));
            }
        }
    }
    intervals.into_iter().map(|(start,end)| {
        let operations: Vec<_>=edits[start..end].iter().map(|(kind,text)|json!({"op":kind,"text":text})).collect();
        json!({"old_start":old[start],"old_count":old[end]-old[start],"new_start":new[start],"new_count":new[end]-new[start],"ops":operations})
    }).collect()
}
fn request(mode: &str, output: &str, base: &str, other: &str, context: usize) -> Value {
    let mut value = json!({"version":1,"mode":mode,"output":output,"base":base});
    if mode == "diff" {
        value["target"] = json!(other);
        value["context"] = json!(context);
    } else {
        value["patch"] = json!(other);
    }
    value
}
fn run() -> Result<i32> {
    let config = Document::read(
        absolute(
            &std::env::var("PATCH_CONFIG").unwrap_or("patch-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let value = config.json()?;
    exact(
        &value,
        &["version", "mode", "base", "target", "context", "output"],
    )?;
    require(
        value["version"] == 1 && value["mode"] == "diff",
        "baseline supports version 1 diff jobs",
    )?;
    let context = integer(&value["context"])?;
    require(
        (0..=16).contains(&context),
        "context outside permitted range",
    )?;
    let context = context as usize;
    let parent = config.path.parent().unwrap();
    let output = absolute(string(&value["output"])?, parent)?;
    require(
        std::fs::symlink_metadata(&output).is_err(),
        "output already exists",
    )?;
    let before = Document::read(absolute(string(&value["base"])?, parent)?, 65536)?;
    let after = Document::read(absolute(string(&value["target"])?, parent)?, 65536)?;
    let old_lines = lines(&before.data)?;
    let new_lines = lines(&after.data)?;
    let edits = align(&old_lines, &new_lines)?;
    let hunks = hunks(&edits, context);
    let patch = json!({"version":1,"format":"line-lcs","context":context,"before":identity(&before.data)?,"after":identity(&after.data)?,"hunks":hunks});
    let patch_bytes = canonical(&patch)?;
    let (mut removed, mut added) = (0, 0);
    let mut review = vec!["Line diff: quoted UTF-8 tokens; offsets are zero-based".to_string()];
    for hunk in patch["hunks"].as_array().unwrap() {
        review.push(format!(
            "@@ old {},{} new {},{} @@",
            integer(&hunk["old_start"])?,
            integer(&hunk["old_count"])?,
            integer(&hunk["new_start"])?,
            integer(&hunk["new_count"])?
        ));
        for operation in hunk["ops"].as_array().unwrap() {
            let kind = string(&operation["op"])?;
            removed += usize::from(kind == "-");
            added += usize::from(kind == "+");
            review.push(format!(
                "{kind}{}",
                py2rust_service_runtime::json_canonical_view(&operation["text"])?
            ));
        }
    }
    let statistics = json!({"removed":removed,"added":added,"common":old_lines.len()-removed,"hunks":patch["hunks"].as_array().unwrap().len(),"cells":(old_lines.len()+1)*(new_lines.len()+1)});
    let report = json!({"version":1,"mode":"diff","changed":before.data!=after.data,"before":patch["before"],"after":patch["after"],"patch_sha256":digest(&patch_bytes),"statistics":statistics});
    let files = BTreeMap::from([
        ("base.txt".into(), before.data.clone()),
        ("target.txt".into(), after.data.clone()),
        ("patch.json".into(), patch_bytes),
        ("report.json".into(), canonical(&report)?),
        ("diff.txt".into(), (review.join("\n") + "\n").into_bytes()),
        (
            "apply.json".into(),
            canonical(&request(
                "apply",
                "applied",
                "base.txt",
                "patch.json",
                context,
            ))?,
        ),
        (
            "replay.json".into(),
            canonical(&request(
                "diff",
                "replayed",
                "base.txt",
                "target.txt",
                context,
            ))?,
        ),
        (
            "check-applied.json".into(),
            canonical(&request(
                "diff",
                "checked",
                "applied/result.txt",
                "target.txt",
                context,
            ))?,
        ),
    ]);
    require(
        files.values().all(|data| data.len() <= 1048576),
        "output file budget exceeded",
    )?;
    let changed = before.data != after.data;
    publish(&output, files, &[config, before, after], "patch")?;
    println!(
        "{}",
        py2rust_service_runtime::json_canonical_view(&statistics)?
    );
    Ok(i32::from(changed))
}
fn main() {
    match run() {
        Ok(code) => std::process::exit(code),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    }
}
