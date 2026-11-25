//! Handwritten task dashboard: Unicode cell layout, refresh, signal cleanup and replay.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

fn label(value: &Value, limit: usize) -> Result<&str> {
    let text = string(value)?;
    require(
        !rt::str_split_whitespace_iter(text)
            .collect::<Vec<_>>()
            .is_empty()
            && text.chars().count() <= limit,
        "label length or empty label",
    )?;
    rt::terminal_cells(text)?;
    Ok(text)
}
fn settings(value: &Value) -> Result<()> {
    exact(value, &["columns", "refreshes", "interval_ms"])?;
    let width = integer(&value["columns"])?;
    let count = integer(&value["refreshes"])?;
    let interval = integer(&value["interval_ms"])?;
    require(
        (1..=200).contains(&width)
            && (1..=64).contains(&count)
            && (20..=60000).contains(&interval)
            && count * interval <= 3600000,
        "settings limits",
    )
}
fn snapshot(value: &Value) -> Result<()> {
    exact(value, &["version", "sequence", "title", "tasks"])?;
    require(
        integer(&value["version"])? == 1 && integer(&value["sequence"])? >= 0,
        "snapshot version or sequence",
    )?;
    label(&value["title"], 120)?;
    let tasks = value["tasks"].as_array().ok_or("expected task array")?;
    require(tasks.len() <= 128, "task count limit")?;
    let mut seen = BTreeSet::new();
    for task in tasks {
        exact(task, &["id", "label", "state", "done", "total"])?;
        require(seen.insert(label(&task["id"], 32)?), "duplicate task id")?;
        label(&task["label"], 120)?;
        let state = string(&task["state"])?;
        require(
            ["queued", "running", "done", "failed"].contains(&state),
            "unknown task state",
        )?;
        let done = integer(&task["done"])?;
        let total = integer(&task["total"])?;
        require(
            0 <= done && done <= total && total <= 1000000000,
            "progress range",
        )?;
        require(
            (state != "queued" || done == 0) && (state != "done" || done == total),
            "state progress mismatch",
        )?;
    }
    Ok(())
}
fn empty() -> Value {
    json!({"version":1,"sequence":0,"title":"Waiting for tasks","tasks":[]})
}
fn fit(value: &str, width: usize) -> Result<String> {
    let cells = rt::terminal_cells(value)?;
    let total: usize = cells.iter().map(|(_, size)| *size as usize).sum();
    let budget = if total <= width {
        width
    } else {
        width.saturating_sub(1)
    };
    let mut result = String::new();
    let mut used = 0;
    for (cell, size) in cells {
        let size = size as usize;
        if used + size > budget {
            break;
        }
        result.push_str(&cell);
        used += size;
    }
    if total > width && width > 0 {
        result.push('~');
        used += 1;
    }
    result.extend(std::iter::repeat(' ').take(width - used));
    Ok(result)
}
fn row(task: &Value, width: usize) -> Result<String> {
    let state = string(&task["state"])?;
    let symbol = match state {
        "queued" => ".",
        "running" => ">",
        "done" => "+",
        "failed" => "!",
        _ => return Err("unknown state".into()),
    };
    let total = integer(&task["total"])?;
    let percent = if state == "done" {
        100
    } else if total == 0 {
        -1
    } else {
        integer(&task["done"])? * 100 / total
    };
    let shown = if percent < 0 {
        " --%".into()
    } else {
        fit(&format!("{percent}%"), 4)?
    };
    let label = string(&task["label"])?;
    if width == 1 {
        return Ok(symbol.into());
    }
    if width < 24 {
        return fit(&format!("{symbol} {label}"), width);
    }
    if width < 50 {
        return Ok(format!("{symbol} {shown} {}", fit(label, width - 7)?));
    }
    let size = 20.min(width / 6);
    let filled = if percent < 0 {
        0
    } else {
        percent as usize * size / 100
    };
    let bar = "#".repeat(filled) + &if percent < 0 { "?" } else { "-" }.repeat(size - filled);
    Ok(format!(
        "{} {} {shown} [{bar}] {}",
        fit(string(&task["id"])?, 8)?,
        fit(state, 7)?,
        fit(label, width - size - 25)?
    ))
}
fn frame(
    state: &Value,
    width: usize,
    height: usize,
    index: usize,
    count: usize,
    status: &str,
) -> Result<Vec<String>> {
    let fallback = empty();
    let source = if state.is_null() { &fallback } else { state };
    let tasks = source["tasks"].as_array().ok_or("expected tasks")?;
    let mut counts = BTreeMap::from([("queued", 0), ("running", 0), ("done", 0), ("failed", 0)]);
    for task in tasks {
        *counts
            .get_mut(string(&task["state"])?)
            .ok_or("unknown state")? += 1;
    }
    let mut lines = vec![fit(string(&source["title"])?, width)?];
    if height == 1 {
        return Ok(lines);
    }
    lines.push(fit(
        &format!(
            "{} tasks | {} running | {} done | {} failed",
            tasks.len(),
            counts["running"],
            counts["done"],
            counts["failed"]
        ),
        width,
    )?);
    if height == 2 {
        return Ok(lines);
    }
    if width >= 50 && height >= 5 {
        lines.push(fit("ID       STATE   DONE  PROGRESS / TASK", width)?);
    }
    let visible = tasks.len().min(height.saturating_sub(lines.len() + 1));
    for task in &tasks[..visible] {
        lines.push(row(task, width)?);
    }
    lines.push(fit(
        &format!(
            "{} hidden | frame {index}/{count} | {status}",
            tasks.len() - visible
        ),
        width,
    )?);
    Ok(lines)
}
fn observe(previous: &mut Value, source: &[u8], readable: bool) -> &'static str {
    if !readable {
        return "unreadable";
    }
    let parsed = (|| -> Result<(Value, &'static str)> {
        let current = rt::json_loads_unique(std::str::from_utf8(source)?)?;
        snapshot(&current)?;
        if !previous.is_null() {
            let sequence = integer(&current["sequence"])?;
            let old = integer(&previous["sequence"])?;
            if sequence < old {
                return Ok((Value::Null, "older sequence"));
            }
            if sequence == old {
                return Ok((
                    Value::Null,
                    if rt::json_canonical_view(&current)? == rt::json_canonical_view(previous)? {
                        "unchanged"
                    } else {
                        "conflicting sequence"
                    },
                ));
            }
        }
        Ok((current, "updated"))
    })();
    match parsed {
        Ok((current, status)) => {
            if status == "updated" {
                *previous = current;
            }
            status
        }
        Err(_) => "invalid snapshot",
    }
}
fn event(
    source: &[u8],
    readable: bool,
    state: &Value,
    status: &str,
    dimensions: (usize, usize),
    index: usize,
    count: usize,
) -> Result<Value> {
    let (width, height) = dimensions;
    Ok(
        json!({"source_hex":rt::bytes_hex(source),"readable":readable,"status":status,"columns":width,"rows":height,"lines":frame(state,width,height,index,count,status)?}),
    )
}
fn show(record: &Value, interactive: bool) -> Result<()> {
    let lines: Result<Vec<_>> = record["lines"]
        .as_array()
        .ok_or("expected lines")?
        .iter()
        .map(string)
        .collect();
    let lines = lines?.join(if interactive { "\r\n" } else { "\n" });
    rt::terminal_write(&if interactive {
        format!("\x1b[H\x1b[2J{lines}")
    } else {
        format!("{lines}\n\n")
    })
}
fn watch(path: &Path, options: &Value) -> Result<(Vec<Value>, Value, i64)> {
    let signals = rt::process_pool()?;
    let interactive = rt::terminal_info()["ansi"].as_bool().unwrap();
    let watched = (|| -> Result<(Vec<Value>, Value, i64)> {
        if interactive {
            rt::terminal_write("\x1b[?1049h\x1b[?25l")?;
        }
        let count = integer(&options["refreshes"])? as usize;
        let mut state = Value::Null;
        let mut events = Vec::new();
        for index in 0..count {
            if rt::process_pool_signal(&signals)? != 0 {
                break;
            }
            let (raw, readable) = match Document::read(path.to_owned(), 65536) {
                Ok(document) => (document.data, true),
                Err(_) => (Vec::new(), false),
            };
            let status = observe(&mut state, &raw, readable);
            let info = rt::terminal_info();
            let mut width = integer(&options["columns"])?;
            let mut height = 132;
            if info["isatty"].as_bool().unwrap() {
                width = width.min((integer(&info["columns"])? - 1).max(1));
            }
            if interactive {
                height = height.min((integer(&info["rows"])? - 1).max(1));
            }
            let record = event(
                &raw,
                readable,
                &state,
                status,
                (width as usize, height as usize),
                index + 1,
                count,
            )?;
            show(&record, interactive)?;
            events.push(record);
            if index + 1 < count {
                let mut remaining = integer(&options["interval_ms"])?;
                while remaining > 0 && rt::process_pool_signal(&signals)? == 0 {
                    let delay = remaining.min(20);
                    rt::sleep(delay as f64 / 1000.0)?;
                    remaining -= delay;
                }
            }
        }
        Ok((events, state, rt::process_pool_signal(&signals)?))
    })();
    let restored = if interactive {
        rt::terminal_write("\x1b[?25h\x1b[?1049l")
    } else {
        Ok(())
    };
    rt::process_pool_close(&signals)?;
    restored?;
    watched
}
fn replay(archive: &Value) -> Result<(Value, Vec<Value>, Value, i64)> {
    exact(archive, &["version", "settings", "events", "signal"])?;
    require(integer(&archive["version"])? == 1, "archive version")?;
    let options = &archive["settings"];
    settings(options)?;
    let signal = integer(&archive["signal"])?;
    require([0, 2, 15].contains(&signal), "archive signal")?;
    let count = integer(&options["refreshes"])? as usize;
    let events = archive["events"].as_array().ok_or("expected events")?;
    require(
        events.len() <= count && (events.len() == count || signal != 0),
        "archive frame count",
    )?;
    let mut state = Value::Null;
    for (index, stored) in events.iter().enumerate() {
        exact(
            stored,
            &[
                "source_hex",
                "readable",
                "status",
                "columns",
                "rows",
                "lines",
            ],
        )?;
        let spelling = string(&stored["source_hex"])?;
        require(spelling.chars().count() <= 131072, "snapshot byte limit")?;
        let raw = rt::bytes_from_hex(spelling)?;
        let readable = stored["readable"]
            .as_bool()
            .ok_or("expected readable flag")?;
        require(
            rt::bytes_hex(&raw) == spelling && (readable || raw.is_empty()),
            "archive source encoding",
        )?;
        let width = integer(&stored["columns"])?;
        let height = integer(&stored["rows"])?;
        require(
            (1..=integer(&options["columns"])?).contains(&width) && (1..=132).contains(&height),
            "archive dimensions",
        )?;
        let status = observe(&mut state, &raw, readable);
        let computed = event(
            &raw,
            readable,
            &state,
            status,
            (width as usize, height as usize),
            index + 1,
            count,
        )?;
        require(
            rt::json_canonical_view(&computed)? == rt::json_canonical_view(stored)?,
            "archive differs from recomputed frame",
        )?;
    }
    Ok((options.clone(), events.clone(), state, signal))
}
fn bundle(
    options: Value,
    events: Vec<Value>,
    state: Value,
    signal: i64,
) -> Result<BTreeMap<String, Vec<u8>>> {
    let mut transcript = String::new();
    let mut errors = 0;
    for record in &events {
        if !["updated", "unchanged"].contains(&string(&record["status"])?) {
            errors += 1;
        }
        for line in record["lines"].as_array().ok_or("expected lines")? {
            transcript.push_str(string(line)?);
            transcript.push('\n');
        }
        transcript.push('\n');
    }
    let mut files = BTreeMap::new();
    let fallback = empty();
    files.insert("transcript.txt".into(), transcript.into_bytes());
    files.insert(
        "snapshot.json".into(),
        canonical(if state.is_null() { &fallback } else { &state })?,
    );
    files.insert("watch.json".into(),canonical(&json!({"version":1,"mode":"watch","input":"snapshot.json","output":"watched","columns":options["columns"],"refreshes":options["refreshes"],"interval_ms":options["interval_ms"]}))?);
    files.insert("report.json".into(),(rt::pretty_view(&json!({"version":1,"frames":events.len(),"errors":errors,"signal":signal,"last":state}))?+"\n").into_bytes());
    files.insert(
        "replay.json".into(),
        canonical(
            &json!({"version":1,"mode":"replay","input":"archive.json","output":"replayed"}),
        )?,
    );
    let archive = Value::Object(
        [
            ("version".into(), json!(1)),
            ("settings".into(), options),
            ("events".into(), Value::Array(events)),
            ("signal".into(), json!(signal)),
        ]
        .into_iter()
        .collect(),
    );
    files.insert("archive.json".into(), canonical(&archive)?);
    require(
        files.values().all(|data| data.len() <= 16777216),
        "export byte limit",
    )?;
    Ok(files)
}
fn run() -> Result<i32> {
    let request = Document::read(
        absolute(
            &std::env::var("TASK_DASHBOARD_CONFIG").unwrap_or_else(|_| "tasks-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let config = request.json()?;
    let mode = string(&config["mode"])?;
    require(
        integer(&config["version"])? == 1 && ["watch", "replay"].contains(&mode),
        "request version or mode",
    )?;
    exact(
        &config,
        if mode == "watch" {
            &[
                "version",
                "mode",
                "input",
                "output",
                "columns",
                "refreshes",
                "interval_ms",
            ]
        } else {
            &["version", "mode", "input", "output"]
        },
    )?;
    let path = absolute(string(&config["input"])?, request.path.parent().unwrap())?;
    let output = absolute(string(&config["output"])?, request.path.parent().unwrap())?;
    require(
        output != path && !output.exists() && !output.is_symlink(),
        "output already exists",
    )?;
    let mut inputs = vec![request];
    let (options, events, state, signal) = if mode == "watch" {
        let options = json!({"columns":config["columns"],"refreshes":config["refreshes"],"interval_ms":config["interval_ms"]});
        settings(&options)?;
        let (events, state, signal) = watch(&path, &options)?;
        (options, events, state, signal)
    } else {
        let document = Document::read(path, 16777216)?;
        let restored = replay(&document.json()?)?;
        for record in &restored.1 {
            show(record, false)?;
        }
        inputs.push(document);
        restored
    };
    let errors = events
        .iter()
        .any(|record| !["updated", "unchanged"].contains(&record["status"].as_str().unwrap()));
    publish(
        &output,
        bundle(options, events, state, signal)?,
        &inputs,
        "tasks",
    )?;
    Ok(if mode == "replay" {
        0
    } else if signal != 0 {
        128 + signal as i32
    } else {
        i32::from(errors)
    })
}
fn main() {
    match run() {
        Ok(status) => std::process::exit(status),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    }
}
