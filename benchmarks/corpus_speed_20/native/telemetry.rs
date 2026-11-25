//! Handwritten telemetry pipeline: typed samples and identical compensated statistics.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

struct Settings {
    window: usize,
    warmup: usize,
    gap_us: i64,
    sigma: f64,
}
struct Sample {
    timestamp: i64,
    utc: String,
    value: f64,
}
#[derive(Default)]
struct Moments {
    count: usize,
    min: f64,
    max: f64,
    mean: f64,
    origin: f64,
    offset: f64,
    variance: f64,
    deviation: f64,
}
fn summed(values: impl IntoIterator<Item = f64>) -> f64 {
    let (mut total, mut correction) = (0.0_f64, 0.0);
    for value in values {
        let updated = total + value;
        correction += if total.abs() >= value.abs() {
            (total - updated) + value
        } else {
            (value - updated) + total
        };
        total = updated;
    }
    total + correction
}
fn calculate(values: &[f64]) -> Moments {
    if values.is_empty() {
        return Moments::default();
    }
    let min = values.iter().copied().reduce(f64::min).unwrap();
    let max = values.iter().copied().reduce(f64::max).unwrap();
    let origin = min / 2.0 + max / 2.0;
    let deltas: Vec<_> = values.iter().map(|v| v - origin).collect();
    let offset = summed(deltas.iter().copied()) / values.len() as f64;
    let variance = summed(deltas.iter().map(|delta| {
        let residual = delta - offset;
        residual * residual
    })) / values.len() as f64;
    let mean = summed(values.iter().copied()) / values.len() as f64;
    Moments {
        count: values.len(),
        min,
        max,
        mean: if mean == 0.0 { 0.0 } else { mean },
        origin,
        offset,
        variance,
        deviation: variance.sqrt(),
    }
}
fn describe(value: &Moments) -> Value {
    if value.count == 0 {
        return json!({"count":0,"minimum":null,"maximum":null,"mean":null,"population_variance":null,"standard_deviation":null,"center":null});
    }
    json!({"count":value.count,"minimum":value.min,"maximum":value.max,"mean":value.mean,"population_variance":value.variance,"standard_deviation":value.deviation,"center":{"origin":value.origin,"mean_offset":value.offset}})
}
fn classify(value: f64, baseline: &Moments, settings: &Settings) -> Value {
    if baseline.count < settings.warmup {
        return json!({"status":"warming","deviation":null,"threshold":null,"z_score":null});
    }
    let difference = (value - baseline.origin) - baseline.offset;
    let difference = if difference == 0.0 { 0.0 } else { difference };
    if baseline.deviation == 0.0 {
        return json!({"status":if difference==0.0 {"within"} else {"constant_shift"},"deviation":difference,"threshold":0.0,"z_score":null});
    }
    let threshold = settings.sigma * baseline.deviation;
    json!({"status":if difference.abs()>threshold {"outlier"} else {"within"},"deviation":difference,"threshold":threshold,"z_score":difference/baseline.deviation})
}
fn number(value: &Value) -> Result<f64> {
    let invalid = "expected zero or finite numeric value with magnitude 1e-100..1e100";
    let parsed = if value.is_number() {
        value.as_f64().ok_or(invalid)?
    } else {
        let text = value.as_str().ok_or(invalid)?;
        require(
            !text.is_empty()
                && text.len() <= 64
                && text
                    .bytes()
                    .all(|b| b.is_ascii_digit() || b"-+_eE.".contains(&b)),
            invalid,
        )?;
        // The shared numeric parser enforces Python-subset underscore rules.
        let parsed = rt::float_from_decimal(text).map_err(|_| invalid)?;
        let lower = text.to_lowercase();
        let mantissa = lower.split('e').next().unwrap().replace('_', "");
        require(
            parsed != 0.0 || mantissa.trim_matches(['+', '-', '0', '.']).is_empty(),
            invalid,
        )?;
        parsed
    };
    require(
        parsed.is_finite() && parsed.abs() <= 1e100 && (parsed == 0.0 || parsed.abs() >= 1e-100),
        invalid,
    )?;
    Ok(if parsed == 0.0 { 0.0 } else { parsed })
}
fn samples(value: &Value) -> Result<Vec<Sample>> {
    let rows = value.as_array().ok_or("expected sample array")?;
    let mut readings = Vec::with_capacity(rows.len());
    for (index, row) in rows.iter().enumerate() {
        exact(row, &["at", "value"])?;
        let invalid = format!("invalid timestamp at sample {index}");
        let text = row["at"]
            .as_str()
            .filter(|s| s.len() <= 40)
            .ok_or(invalid.as_str())?;
        let date = rt::datetime_parse(text).map_err(|_| invalid)?;
        let timestamp = rt::datetime_unix_microseconds(&date);
        if let Some(previous) = readings.last() {
            let previous: &Sample = previous;
            require(
                timestamp > previous.timestamp,
                &format!("timestamps must be strictly increasing at sample {index}"),
            )?;
        }
        readings.push(Sample {
            timestamp,
            utc: rt::datetime_iso(&date),
            value: number(&row["value"])?,
        });
    }
    Ok(readings)
}
fn analyze(name: &str, readings: &[Sample], settings: &Settings) -> Value {
    let (mut values, mut window, mut points, mut gaps) =
        (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    let mut baseline = Moments::default();
    let (mut segment, mut outliers) = (0, 0);
    for (index, sample) in readings.iter().enumerate() {
        let elapsed = if index == 0 {
            0
        } else {
            sample.timestamp - readings[index - 1].timestamp
        };
        let gap = index > 0 && elapsed > settings.gap_us;
        if gap {
            gaps.push(json!({"before_index":index-1,"after_index":index,"elapsed_us":elapsed,"from":readings[index-1].utc,"to":sample.utc}));
            segment += 1;
            window.clear();
            baseline = Moments::default();
        }
        let decision = classify(sample.value, &baseline, settings);
        if decision["status"] == "outlier" || decision["status"] == "constant_shift" {
            outliers += 1;
        }
        let before = json!({"start_index":if baseline.count==0 { None } else { Some(index-baseline.count) },"end_index":if baseline.count==0 { None } else { Some(index-1) },"statistics":describe(&baseline)});
        window.push(sample.value);
        if window.len() > settings.window {
            window.remove(0);
        }
        baseline = calculate(&window);
        let mut point = json!({"index":index,"utc":sample.utc,"timestamp_us":sample.timestamp,"value":sample.value,"segment":segment,"elapsed_us":if index==0 {None} else {Some(elapsed)},"gap":gap,"window":{"start_index":index+1-window.len(),"end_index":index,"statistics":describe(&baseline)}});
        point["baseline"] = before;
        point["decision"] = decision;
        points.push(point);
        values.push(sample.value);
    }
    let mut result = json!({"id":name,"status":"analyzed","samples":readings.len(),"segments":if readings.is_empty() {0} else {segment+1},"outliers":outliers,"first_utc":readings.first().map(|s| &s.utc),"last_utc":readings.last().map(|s| &s.utc),"statistics":describe(&calculate(&values))});
    result["gaps"] = Value::Array(gaps);
    result["points"] = Value::Array(points);
    result
}
fn run() -> Result<i32> {
    let request = Document::read(
        absolute(
            &std::env::var("TREND_CONFIG").unwrap_or("trend-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let config = request.json()?;
    exact(&config, &["version", "mode", "input", "output"])?;
    require(
        integer(&config["version"])? == 1,
        "unsupported request version",
    )?;
    let mode = string(&config["mode"])?;
    require(mode == "analyze" || mode == "verify", "unknown mode")?;
    let base = request.path.parent().unwrap();
    let output = absolute(string(&config["output"])?, base)?;
    require(
        std::fs::symlink_metadata(&output).is_err(),
        "output already exists",
    )?;
    let document = Document::read(
        absolute(string(&config["input"])?, base)?,
        if mode == "verify" { 16777216 } else { 2097152 },
    )?;
    let data = document.json()?;
    let source = if mode == "verify" {
        exact(&data, &["version", "source", "results"])?;
        require(
            integer(&data["version"])? == 1,
            "unsupported archive version",
        )?;
        &data["source"]
    } else {
        &data
    };
    exact(source, &["version", "settings", "series"])?;
    require(
        integer(&source["version"])? == 1,
        "unsupported source version",
    )?;
    let rows = source["series"].as_array().ok_or("expected series array")?;
    require(rows.len() <= 8, "series count limit")?;
    let mut seen = BTreeSet::new();
    let mut count = 0;
    for row in rows {
        exact(row, &["id", "samples"])?;
        let name = string(&row["id"])?;
        require(
            rt::regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name)?,
            "invalid series identifier",
        )?;
        require(seen.insert(name), "duplicate series identifier")?;
        count += row["samples"].as_array().map_or(0, Vec::len);
    }
    require(count <= 4096, "total sample limit")?;
    let raw = &source["settings"];
    exact(raw, &["window", "warmup", "gap_us", "sigma"])?;
    let (window, warmup, gap_us, sigma) = (
        integer(&raw["window"])?,
        integer(&raw["warmup"])?,
        integer(&raw["gap_us"])?,
        number(&raw["sigma"])?,
    );
    require(
        (2..=256).contains(&window) && (2..=window).contains(&warmup),
        "window or warmup limit",
    )?;
    require((1..=86400000000).contains(&gap_us), "gap threshold limit")?;
    require((0.1..=20.0).contains(&sigma), "sigma threshold limit")?;
    let settings = Settings {
        window: window as usize,
        warmup: warmup as usize,
        gap_us,
        sigma,
    };
    let results: Vec<_> = rows
        .iter()
        .map(|row| match samples(&row["samples"]) {
            Ok(samples) => analyze(row["id"].as_str().unwrap(), &samples, &settings),
            Err(error) => json!({"id":row["id"],"status":"rejected","reason":error.to_string()}),
        })
        .collect();
    let results = Value::Array(results);
    if mode == "verify" {
        require(
            canonical(&data["results"])? == canonical(&results)?,
            "archive results do not match recomputed analysis",
        )?;
    }
    let mut counts = json!({"analyzed":0,"rejected":0,"samples":0,"gaps":0,"outliers":0});
    for result in results.as_array().unwrap() {
        let state = string(&result["status"])?;
        counts[state] = json!(integer(&counts[state])? + 1);
        if state == "analyzed" {
            for field in ["samples", "outliers"] {
                counts[field] = json!(integer(&counts[field])? + integer(&result[field])?);
            }
            counts["gaps"] =
                json!(integer(&counts["gaps"])? + result["gaps"].as_array().unwrap().len() as i64);
        }
    }
    let mut lines = vec![
        "Telemetry trends: trailing count windows; population variance".to_owned(),
        rt::json_canonical_view(&counts)?,
    ];
    for result in results.as_array().unwrap() {
        let name = string(&result["id"])?;
        if result["status"] == "rejected" {
            lines.push(format!("{name}: rejected: {}", string(&result["reason"])?));
        } else {
            lines.push(format!(
                "{name}: {} samples; {} outliers; {} gaps; mean {}; variance {}",
                integer(&result["samples"])?,
                integer(&result["outliers"])?,
                result["gaps"].as_array().unwrap().len(),
                rt::json_canonical_view(&result["statistics"]["mean"])?,
                rt::json_canonical_view(&result["statistics"]["population_variance"])?
            ));
        }
    }
    // Move the result tree into the archive after its other consumers finish.
    let mut archive_value = json!({"version":1,"source":source});
    archive_value["results"] = results;
    let archive = canonical(&archive_value)?;
    drop(archive_value);
    let files = BTreeMap::from([
        ("telemetry.json".into(), canonical(source)?),
        (
            "report.json".into(),
            canonical(
                &json!({"version":1,"mode":mode,"summary":counts,"archive_sha256":digest(&archive)}),
            )?,
        ),
        ("archive.json".into(), archive),
        ("report.txt".into(), (lines.join("\n") + "\n").into_bytes()),
        (
            "replay.json".into(),
            canonical(
                &json!({"version":1,"mode":"verify","input":"archive.json","output":"replayed"}),
            )?,
        ),
        (
            "analyze.json".into(),
            canonical(
                &json!({"version":1,"mode":"analyze","input":"telemetry.json","output":"analyzed"}),
            )?,
        ),
    ]);
    require(
        files.values().all(|data| data.len() <= 16777216),
        "export byte limit",
    )?;
    publish(&output, files, &[request, document], "trends")?;
    println!("{}", rt::json_canonical_view(&counts)?);
    Ok(if integer(&counts["rejected"])? > 0 {
        1
    } else {
        0
    })
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
