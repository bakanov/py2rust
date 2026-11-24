//! Handwritten baseline: typed JSON decoding, borrowed path splitting, entry updates.
use indexmap::IndexMap;
use serde::{Deserialize, Serialize};
use std::{borrow::Cow, error::Error, fs};

type Result<T> = std::result::Result<T, Box<dyn Error>>;

#[derive(Deserialize)]
struct Event<'a> {
    #[serde(borrow)]
    path: Cow<'a, str>,
    status: i64,
    bytes: i64,
    elapsed_ms: i64,
}

#[derive(Default, Serialize)]
struct Summary {
    requests: i64,
    errors: i64,
    total_bytes: i64,
    max_elapsed_ms: i64,
    routes: IndexMap<String, i64>,
}

fn summarize(text: &str) -> Result<Summary> {
    let mut summary = Summary::default();
    for line in text
        .split('\n')
        .map(str::trim)
        .filter(|line| !line.is_empty())
    {
        let event: Event<'_> = serde_json::from_str(line)?;
        if !event.path.starts_with('/') || !(100..=599).contains(&event.status) {
            return Err("invalid path or HTTP status".into());
        }
        if event.bytes < 0 || event.elapsed_ms < 0 {
            return Err("negative measurement".into());
        }
        let route = event
            .path
            .split_once('?')
            .map_or(event.path.as_ref(), |(path, _)| path);
        let count = summary.routes.entry(route.to_owned()).or_default();
        *count = count.checked_add(1).ok_or("route count overflow")?;
        summary.requests = summary
            .requests
            .checked_add(1)
            .ok_or("request count overflow")?;
        summary.total_bytes = summary
            .total_bytes
            .checked_add(event.bytes)
            .ok_or("byte count overflow")?;
        if event.status >= 400 {
            summary.errors = summary
                .errors
                .checked_add(1)
                .ok_or("error count overflow")?;
        }
        summary.max_elapsed_ms = summary.max_elapsed_ms.max(event.elapsed_ms);
    }
    Ok(summary)
}

fn main() -> Result<()> {
    let path = std::env::var("ACCESS_LOG").unwrap_or_else(|_| "sample.jsonl".to_owned());
    let summary = summarize(&fs::read_to_string(path)?)?;
    println!("{}", serde_json::to_string(&summary)?);
    Ok(())
}
