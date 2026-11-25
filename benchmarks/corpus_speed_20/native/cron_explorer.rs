//! Handwritten numeric cron parser and bounded UTC calendar exploration.
mod common;
use chrono::Datelike;
use common::*;
use py2rust_service_runtime as rt;
use serde::Serialize;
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet, HashSet},
    path::PathBuf,
};
const NAMES: [&str; 5] = ["minute", "hour", "day_of_month", "month", "day_of_week"];
const LOWS: [i64; 5] = [0, 0, 1, 1, 0];
const HIGHS: [i64; 5] = [59, 23, 31, 12, 7];
#[derive(Serialize)]
struct Field {
    name: &'static str,
    values: BTreeSet<i64>,
    starred: bool,
}
#[derive(Serialize)]
struct Expression {
    fields: Vec<Field>,
    day_rule: &'static str,
    error: String,
    error_field: usize,
    error_column: usize,
}
fn number(text: &str, low: i64, high: i64) -> Result<i64> {
    require(
        (1..=2).contains(&text.len()) && text.bytes().all(|c| c.is_ascii_digit()),
        "expected one or two ASCII digits",
    )?;
    let value = text.parse::<i64>()?;
    require(
        (low..=high).contains(&value),
        &format!("value must be in {low}..{high}"),
    )?;
    Ok(value)
}
fn component(text: &str, low: i64, high: i64) -> Result<BTreeSet<i64>> {
    let pieces: Vec<_> = text.split('/').collect();
    require(pieces.len() <= 2, "expected at most one step separator")?;
    let body = pieces[0];
    let step = if pieces.len() == 2 {
        let step = number(pieces[1], 1, high - low + 1)?;
        require(
            body == "*" || body.contains('-'),
            "steps require a wildcard or range",
        )?;
        step
    } else {
        1
    };
    let (first, last) = if body == "*" {
        (low, high)
    } else {
        let bounds: Vec<_> = body.split('-').collect();
        require(bounds.len() <= 2, "expected a value or ascending range")?;
        let first = number(bounds[0], low, high)?;
        let last = if bounds.len() == 1 {
            first
        } else {
            number(bounds[1], low, high)?
        };
        require(first <= last, "range is descending")?;
        (first, last)
    };
    Ok((first..=last).step_by(step as usize).collect())
}
fn invalid(error: String, field: usize, column: usize) -> Expression {
    Expression {
        fields: Vec::new(),
        day_rule: "",
        error,
        error_field: field,
        error_column: column,
    }
}
fn parse(source: &str) -> Expression {
    let mut tokens: Vec<(String, usize)> = Vec::new();
    let mut token = String::new();
    let mut start = 1;
    for (i, c) in source.chars().enumerate() {
        if c == ' ' || c == '\t' {
            if !token.is_empty() {
                tokens.push((std::mem::take(&mut token), start));
            }
        } else {
            if token.is_empty() {
                start = i + 1;
            }
            token.push(c);
        }
    }
    if !token.is_empty() {
        tokens.push((token, start));
    }
    if tokens.len() != 5 {
        return invalid(
            format!("expected five fields; found {}", tokens.len()),
            (tokens.len() + 1).min(6),
            if tokens.len() > 5 {
                tokens[5].1
            } else {
                source.chars().count() + 1
            },
        );
    }
    let mut fields = Vec::with_capacity(5);
    for (index, (text, column)) in tokens.iter().enumerate() {
        let parts: Vec<_> = text.split(',').collect();
        if parts.len() > 1 && text.contains('*') {
            return invalid(
                "wildcards cannot be combined with a list".into(),
                index + 1,
                *column,
            );
        }
        let mut values = BTreeSet::new();
        let mut offset = *column;
        for part in parts {
            match component(part, LOWS[index], HIGHS[index]) {
                Ok(selected) => values.extend(selected),
                Err(error) => {
                    return invalid(format!("{}: {error}", NAMES[index]), index + 1, offset)
                }
            }
            offset += part.chars().count() + 1;
        }
        if index == 4 && values.remove(&7) {
            values.insert(0);
        }
        fields.push(Field {
            name: NAMES[index],
            values,
            starred: text.starts_with('*'),
        });
    }
    let day_rule = if fields[2].starred || fields[4].starred {
        "and"
    } else {
        "or"
    };
    Expression {
        fields,
        day_rule,
        error: String::new(),
        error_field: 0,
        error_column: 0,
    }
}
struct Job {
    start: rt::DateTime,
    end: rt::DateTime,
    days: i64,
    limit: usize,
    schedules: Vec<Value>,
    output: PathBuf,
}
fn load(document: &Document) -> Result<Job> {
    let value = rt::json_loads(std::str::from_utf8(&document.data)?)?;
    exact(
        &value,
        &["days", "limit", "output", "schedules", "start", "version"],
    )?;
    require(integer(&value["version"])? == 1, "unsupported job version")?;
    let days = integer(&value["days"])?;
    let limit = integer(&value["limit"])?;
    require(
        (1..=3660).contains(&days) && (1..=1000).contains(&limit),
        "days or limit outside bounds",
    )?;
    let start = rt::datetime_parse(string(&value["start"])?)?;
    let end = rt::datetime_add_seconds(&start, days * 86400)?;
    let output = absolute(
        string(&value["output"])?,
        document.path.parent().ok_or("missing parent")?,
    )?;
    require(
        !output.exists() && !output.is_symlink(),
        "output already exists",
    )?;
    let schedules = value["schedules"]
        .as_array()
        .ok_or("expected schedule array")?;
    require(
        (1..=16).contains(&schedules.len()),
        "expected 1..16 schedules",
    )?;
    let mut ids = HashSet::new();
    for entry in schedules {
        exact(entry, &["expression", "id"])?;
        let id = string(&entry["id"])?;
        require(
            rt::regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", id)?,
            "invalid schedule ID",
        )?;
        require(ids.insert(id), "duplicate schedule ID")?;
        require(
            string(&entry["expression"])?.len() <= 256,
            "expression exceeds 256 UTF-8 bytes",
        )?;
    }
    Ok(Job {
        start,
        end,
        days,
        limit: limit as usize,
        schedules: schedules.clone(),
        output,
    })
}
#[derive(Serialize)]
struct Occurrence {
    utc: String,
    weekday: u32,
}
struct Search {
    runs: Vec<Occurrence>,
    more: bool,
    next_omitted: String,
    inspected_days: usize,
}
fn explore(expression: &Expression, job: &Job) -> Result<Search> {
    let midnight = job
        .start
        .date_naive()
        .and_hms_opt(0, 0, 0)
        .unwrap()
        .and_utc();
    let fields = &expression.fields;
    let mut result = Search {
        runs: Vec::new(),
        more: false,
        next_omitted: String::new(),
        inspected_days: 0,
    };
    for offset in 0..=job.days {
        let day = rt::datetime_add_seconds(&midnight, offset * 86400)?;
        if day >= job.end {
            break;
        }
        result.inspected_days += 1;
        let weekday = day.weekday().num_days_from_sunday();
        let date_match = fields[2].values.contains(&(day.day() as i64));
        let weekday_match = fields[4].values.contains(&(weekday as i64));
        let matches = if expression.day_rule == "and" {
            date_match && weekday_match
        } else {
            date_match || weekday_match
        };
        if !fields[3].values.contains(&(day.month() as i64)) || !matches {
            continue;
        }
        for &hour in &fields[1].values {
            for &minute in &fields[0].values {
                let candidate = rt::datetime_add_seconds(&day, hour * 3600 + minute * 60)?;
                if candidate >= job.start && candidate < job.end {
                    let text = rt::datetime_iso(&candidate);
                    if result.runs.len() == job.limit {
                        result.more = true;
                        result.next_omitted = text;
                        return Ok(result);
                    }
                    result.runs.push(Occurrence { utc: text, weekday });
                }
            }
        }
    }
    Ok(result)
}
fn run() -> Result<i32> {
    let document = Document::read(
        absolute(
            &std::env::var("CRON_CONFIG").unwrap_or_else(|_| "cron-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let job = load(&document)?;
    let mut entries = Vec::new();
    let mut errors = 0;
    let mut lines = vec![
        "UTC cron schedules".into(),
        format!(
            "Window: [{}, {})",
            rt::datetime_iso(&job.start),
            rt::datetime_iso(&job.end)
        ),
    ];
    let mut csv = vec!["id,utc,weekday".into()];
    for entry in &job.schedules {
        let id = string(&entry["id"])?;
        let source = string(&entry["expression"])?;
        let expression = parse(source);
        lines.push(format!(
            "\n{id}: {}",
            rt::json_canonical_view(&entry["expression"])?
        ));
        let mut search = Search {
            runs: Vec::new(),
            more: false,
            next_omitted: String::new(),
            inspected_days: 0,
        };
        let status = if !expression.error.is_empty() {
            errors += 1;
            lines.push(format!(
                "  Field {}, column {}: {}",
                expression.error_field, expression.error_column, expression.error
            ));
            "invalid"
        } else {
            search = explore(&expression, &job)?;
            lines.push(format!(
                "  Day-of-month / day-of-week: {}",
                expression.day_rule
            ));
            for field in &expression.fields {
                lines.push(format!(
                    "  {} = {}",
                    field.name,
                    rt::json_canonical_view(&serde_json::to_value(&field.values)?)?
                ));
            }
            for occurrence in &search.runs {
                lines.push(format!("  {}", occurrence.utc));
                csv.push(format!("{id},{},{}", occurrence.utc, occurrence.weekday));
            }
            lines.push(if search.more {
                format!(
                    "  Result limit reached; next omitted run: {}",
                    search.next_omitted
                )
            } else if search.runs.is_empty() {
                "  No runs in the requested window.".into()
            } else {
                "  All runs in the requested window are listed.".into()
            });
            "valid"
        };
        entries.push(json!({"id":id,"expression":source,"explanation":expression,"status":status,"runs":search.runs,"more":search.more,"next_omitted":search.next_omitted,"inspected_days":search.inspected_days}));
    }
    let result = json!({"version":1,"start":rt::datetime_iso(&job.start),"end":rt::datetime_iso(&job.end),"days":job.days,"limit":job.limit,"errors":errors,"schedules":entries});
    let replay = json!({"version":1,"start":rt::datetime_iso(&job.start),"days":job.days,"limit":job.limit,"schedules":job.schedules,"output":"rebuilt"});
    let mut files: BTreeMap<String, Vec<u8>> = BTreeMap::from([
        ("report.json".into(), canonical(&result)?),
        ("report.txt".into(), (lines.join("\n") + "\n").into_bytes()),
        ("schedule.csv".into(), (csv.join("\n") + "\n").into_bytes()),
        ("cron-job.json".into(), canonical(&replay)?),
    ]);
    require(
        files.values().map(Vec::len).sum::<usize>() <= 8388608,
        "schedule bundle exceeds 8 MiB",
    )?;
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
    document.unchanged()?;
    publish_exact(&job.output, files, &[], "cron")?;
    print!("{}", std::str::from_utf8(&canonical(&result)?)?);
    Ok(i32::from(errors > 0))
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
