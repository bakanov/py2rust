//! Handwritten fixed-step RK4 experiment with complete JSON/CSV/SVG publication.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt::Write;

struct Parameters<'a> {
    id: &'a str,
    name: &'a str,
    model: &'a str,
    initial: f64,
    rate: f64,
    capacity: f64,
}
struct Experiment<'a> {
    title: &'a str,
    timestep: f64,
    steps: usize,
    cases: Vec<Parameters<'a>>,
}
fn display(text: &str) -> Result<String> {
    Ok(
        rt::str_split_whitespace_iter(&rt::unicode_normalize("NFKC", text)?)
            .collect::<Vec<_>>()
            .join(" "),
    )
}
fn label(value: &Value, limit: usize) -> Result<&str> {
    let original = string(value)?;
    let shown = display(original)?;
    require(
        (1..=limit).contains(&original.chars().count())
            && (1..=limit).contains(&shown.chars().count()),
        "label character limit",
    )?;
    require(
        shown.chars().all(|c| {
            c >= ' ' && !('\u{7f}'..='\u{9f}').contains(&c) && c != '\u{fffe}' && c != '\u{ffff}'
        }),
        "invalid label character",
    )?;
    Ok(original)
}
fn number(value: &Value, low: f64, high: f64) -> Result<f64> {
    require(value.is_number(), "expected JSON number")?;
    let result = rt::json_float(value)?;
    require(low <= result && result <= high, "number range")?;
    Ok(if result == 0.0 { 0.0 } else { result })
}
fn parse(source: &Value) -> Result<Experiment<'_>> {
    exact(source, &["version", "title", "timestep", "steps", "cases"])?;
    require(
        integer(&source["version"])? == 1,
        "unsupported source version",
    )?;
    let title = label(&source["title"], 100)?;
    let timestep = number(&source["timestep"], 1e-9, 1e6)?;
    let steps = integer(&source["steps"])?;
    require((0..=2048).contains(&steps), "step count limit")?;
    let rows = source["cases"].as_array().ok_or("expected cases array")?;
    require((1..=16).contains(&rows.len()), "case count limit")?;
    let mut seen = BTreeSet::new();
    let mut cases = Vec::new();
    for row in rows {
        exact(row, &["id", "name", "model", "initial", "rate", "capacity"])?;
        let id = string(&row["id"])?;
        require(
            rt::regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", id)? && seen.insert(id),
            "invalid or duplicate identifier",
        )?;
        let name = label(&row["name"], 60)?;
        let model = string(&row["model"])?;
        require(
            model == "exponential" || model == "logistic",
            "unknown growth model",
        )?;
        let initial = number(&row["initial"], 0.0, 1e12)?;
        require(
            initial == 0.0 || initial >= 1e-9,
            "initial population range",
        )?;
        let rate = number(&row["rate"], -1000.0, 1000.0)?;
        require(rate == 0.0 || rate.abs() >= 1e-12, "rate range")?;
        let capacity = if model == "logistic" {
            number(&row["capacity"], 1e-9, 1e12)?
        } else {
            require(
                row["capacity"].is_null(),
                "exponential capacity must be null",
            )?;
            0.0
        };
        cases.push(Parameters {
            id,
            name,
            model,
            initial,
            rate,
            capacity,
        });
    }
    Ok(Experiment {
        title,
        timestep,
        steps: steps as usize,
        cases,
    })
}
fn slope(case: &Parameters<'_>, population: f64, timestep: f64) -> Result<f64> {
    require(
        (0.0..=1e100).contains(&population),
        "population outside numerical domain",
    )?;
    let ratio = if case.model == "logistic" {
        population / case.capacity
    } else {
        0.0
    };
    require(
        case.rate.abs() * timestep * ratio.max(1.0) <= 0.05,
        "timestep too large for current population",
    )?;
    let derivative = case.rate * population;
    Ok(if case.model == "logistic" {
        derivative * (1.0 - ratio)
    } else {
        derivative
    })
}
fn advance(case: &Parameters<'_>, population: f64, h: f64) -> Result<f64> {
    let first = slope(case, population, h)?;
    let second = slope(case, population + h * first / 2.0, h)?;
    let third = slope(case, population + h * second / 2.0, h)?;
    let fourth = slope(case, population + h * third, h)?;
    let result = population + h * (first + 2.0 * second + 2.0 * third + fourth) / 6.0;
    slope(case, result, h)?;
    Ok(if result == 0.0 { 0.0 } else { result })
}
#[derive(Serialize)]
struct Series<'a> {
    id: &'a str,
    name: &'a str,
    model: &'a str,
    values: Vec<f64>,
    initial: f64,
    #[serde(rename = "final")]
    final_value: f64,
    minimum: f64,
    maximum: f64,
    change: f64,
    difference_from_first: f64,
}
#[derive(Serialize)]
struct Summary {
    cases: usize,
    steps: usize,
    points: usize,
    horizon: f64,
}
#[derive(Serialize)]
struct Results<'a> {
    method: &'static str,
    times: Vec<f64>,
    series: Vec<Series<'a>>,
    summary: Summary,
}
fn simulate<'a>(experiment: &Experiment<'a>) -> Result<Results<'a>> {
    let times: Vec<_> = (0..=experiment.steps)
        .map(|i| i as f64 * experiment.timestep)
        .collect();
    let mut series = Vec::new();
    let mut baseline = 0.0;
    for (index, case) in experiment.cases.iter().enumerate() {
        let mut population = case.initial;
        slope(case, population, experiment.timestep)?;
        let mut values = Vec::with_capacity(experiment.steps + 1);
        values.push(population);
        for _ in 0..experiment.steps {
            population = advance(case, population, experiment.timestep)?;
            values.push(population);
        }
        if index == 0 {
            baseline = population;
        }
        let minimum = values.iter().copied().fold(f64::INFINITY, f64::min);
        let maximum = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        series.push(Series {
            id: case.id,
            name: case.name,
            model: case.model,
            values,
            initial: case.initial,
            final_value: population,
            minimum,
            maximum,
            change: population - case.initial,
            difference_from_first: population - baseline,
        });
    }
    let summary = Summary {
        cases: series.len(),
        steps: experiment.steps,
        points: series.len() * times.len(),
        horizon: *times.last().unwrap(),
    };
    Ok(Results {
        method: "rk4",
        times,
        series,
        summary,
    })
}
fn escaped(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}
fn short(value: &str, length: usize) -> String {
    if value.chars().count() <= length {
        value.to_owned()
    } else {
        value.chars().take(length - 3).collect::<String>() + "..."
    }
}
fn render(title: &str, results: &Results<'_>) -> Result<Vec<u8>> {
    let ceiling = results
        .series
        .iter()
        .map(|row| row.maximum)
        .fold(0.0, f64::max);
    let scale = if ceiling > 0.0 { ceiling } else { 1.0 };
    let horizon = results.summary.horizon;
    let duration = if horizon > 0.0 { horizon } else { 1.0 };
    let height = 460 + results.series.len() * 22;
    let colors = [
        "#2678c8", "#cf4a36", "#28834b", "#8c52b8", "#b97808", "#007e87", "#b34e8f", "#515a66",
        "#184b80", "#802e22", "#19542f", "#573374", "#765006", "#004e55", "#713158", "#262d35",
    ];
    let shown = display(title)?;
    let mut lines = vec![
        format!(r#"<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}">"#),
        format!("<title>{}</title>", escaped(&shown)),
        "<desc>Fixed-step RK4 population comparison. Time on the horizontal axis; population on the vertical axis. All series share a linear scale.</desc>".into(),
        r##"<rect width="100%" height="100%" fill="#f7f9fc"/>"##.into(),
        r##"<g font-family="DejaVu Sans, sans-serif" fill="#243145">"##.into(),
        format!(r#"<text x="80" y="36" font-size="18">{}</text>"#, escaped(&short(&shown, 32))),
        r#"<text x="80" y="61" font-size="12">Population · fixed-step RK4 · shared linear scale</text>"#.into(),
        r##"<path d="M80 80 V380 H960" fill="none" stroke="#708095"/>"##.into(),
        format!(r#"<text x="80" y="75" font-size="10">Max: {}</text>"#, rt::json_canonical(&ceiling)?),
        r#"<text x="60" y="384" font-size="12">0</text>"#.into(),
        r#"<text x="80" y="400" font-size="12">0</text>"#.into(),
        format!(r#"<text x="960" y="400" text-anchor="end" font-size="12">{}</text>"#, rt::json_canonical(&horizon)?),
        r#"<text x="520" y="421" text-anchor="middle" font-size="12">Time</text>"#.into(),
    ];
    for (index, row) in results.series.iter().enumerate() {
        let mut points = String::new();
        let mut first_y = 0;
        for (step, (&time, &value)) in results.times.iter().zip(&row.values).enumerate() {
            let x = (80.0 + 880.0 * (time / duration) + 0.5).floor() as i64;
            let y = (80.0 + 300.0 * (1.0 - value / scale) + 0.5).floor() as i64;
            if step == 0 {
                first_y = y;
            } else {
                points.push(' ');
            }
            write!(points, "{x},{y}")?;
        }
        let id = row.id;
        let name = display(row.name)?;
        let color = colors[index];
        lines.push(format!(r#"<polyline id="series-{id}" fill="none" stroke="{color}" stroke-width="2" points="{points}"><title>{}</title></polyline>"#, escaped(&name)));
        lines.push(format!(
            r#"<circle id="start-{id}" cx="80" cy="{first_y}" r="3" fill="{color}"/>"#
        ));
        let label = format!("{id} — {name}");
        lines.push(format!(
            r#"<text x="80" y="{}" font-size="12" fill="{color}"><title>{}</title>{}</text>"#,
            450 + index * 22,
            escaped(&label),
            escaped(&short(&label, 44))
        ));
    }
    lines.push("</g></svg>".into());
    Ok((lines.join("\n") + "\n").into_bytes())
}
fn csv_data(results: &Results<'_>) -> Result<Vec<u8>> {
    let mut text = String::from("id,step,time,population\n");
    for row in &results.series {
        for (index, (&time, &value)) in results.times.iter().zip(&row.values).enumerate() {
            writeln!(
                text,
                "{},{index},{},{}",
                row.id,
                rt::json_canonical(&time)?,
                rt::json_canonical(&value)?
            )?;
        }
    }
    Ok(text.into_bytes())
}
fn run() -> Result<()> {
    let request = Document::read(
        absolute(
            &std::env::var("POPULATION_CONFIG").unwrap_or_else(|_| "population-job.json".into()),
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
    require(mode == "simulate" || mode == "verify", "unknown mode")?;
    let base = request.path.parent().unwrap();
    let output = absolute(string(&config["output"])?, base)?;
    require(
        !output.exists() && !output.is_symlink(),
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
    let experiment = parse(source)?;
    let results = simulate(&experiment)?;
    let summary = serde_json::to_value(&results.summary)?;
    let mut files = BTreeMap::new();
    files.insert("plot.svg".into(), render(experiment.title, &results)?);
    files.insert("series.csv".into(), csv_data(&results)?);
    let results = serde_json::to_value(results)?;
    let encoded_results = canonical(&results)?;
    if mode == "verify" {
        require(
            canonical(&data["results"])? == encoded_results,
            "archive results do not match recomputed population series",
        )?;
    }
    files.insert("series.json".into(), encoded_results);
    files.insert("experiment.json".into(), canonical(source)?);
    let archive = Value::Object(
        [
            ("version".into(), json!(1)),
            ("source".into(), source.clone()),
            ("results".into(), results),
        ]
        .into_iter()
        .collect(),
    );
    let archive = canonical(&archive)?;
    files.insert(
        "report.json".into(),
        canonical(
            &json!({"version":1,"mode":mode,"summary":summary,"archive_sha256":digest(&archive)}),
        )?,
    );
    files.insert("archive.json".into(), archive);
    files.insert(
        "replay.json".into(),
        canonical(
            &json!({"version":1,"mode":"verify","input":"archive.json","output":"replayed"}),
        )?,
    );
    files.insert(
        "simulate.json".into(),
        canonical(
            &json!({"version":1,"mode":"simulate","input":"experiment.json","output":"simulated"}),
        )?,
    );
    require(
        files.values().all(|data| data.len() <= 16777216),
        "export byte limit",
    )?;
    publish(&output, files, &[request, document], "population")?;
    println!("{}", rt::json_canonical_view(&summary)?);
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
