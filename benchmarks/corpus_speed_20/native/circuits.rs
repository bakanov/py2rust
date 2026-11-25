//! Typed recursive circuit validation and postorder reduction; exact exported audit format.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
struct Node {
    name: String,
    kind: String,
    ohms: f64,
    children: Vec<Node>,
}
struct Equivalent {
    state: &'static str,
    ohms: f64,
}
fn identifier(value: &Value) -> Result<&str> {
    let name = string(value)?;
    require(
        rt::regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name)?,
        "invalid identifier",
    )?;
    Ok(name)
}
fn resistance(value: &Value) -> Result<f64> {
    let spelling = string(value)?;
    require(
        !spelling.is_empty() && spelling.len() <= 64,
        "resistance spelling length limit",
    )?;
    let invalid = "expected zero or finite resistance in 1e-100..1e100 ohms";
    require(rt::regex_fullmatch("[-+0-9_eE.]+", spelling)?, invalid)?;
    let number = rt::float_from_decimal(spelling).map_err(|_| invalid)?;
    let lower = spelling.to_lowercase();
    let mantissa = lower.split('e').next().unwrap().replace('_', "");
    require(
        number.is_finite()
            && (0.0..=1e100).contains(&number)
            && (number == 0.0 || number >= 1e-100)
            && (number != 0.0 || mantissa.trim_matches(['+', '-', '0', '.']).is_empty()),
        invalid,
    )?;
    Ok(if number == 0.0 { 0.0 } else { number })
}
fn parse(value: &Value, depth: usize, seen: &mut BTreeSet<String>) -> Result<Node> {
    require(depth <= 16, "tree depth limit")?;
    require(seen.len() < 256, "tree node limit")?;
    require(
        value.is_object() && value.get("id").is_some() && value.get("kind").is_some(),
        "expected identified node",
    )?;
    let name = identifier(&value["id"])?;
    require(seen.insert(name.to_owned()), "duplicate node identifier")?;
    let kind = string(&value["kind"])?;
    let (ohms, children) = match kind {
        "resistor" => {
            exact(value, &["id", "kind", "ohms"])?;
            (resistance(&value["ohms"])?, vec![])
        }
        "open" | "short" => {
            exact(value, &["id", "kind"])?;
            (0.0, vec![])
        }
        "series" | "parallel" => {
            exact(value, &["id", "kind", "children"])?;
            let branches = value["children"].as_array().ok_or("expected child array")?;
            require(
                (2..=16).contains(&branches.len()),
                "group requires 2..16 children",
            )?;
            let children = branches
                .iter()
                .map(|b| parse(b, depth + 1, seen))
                .collect::<Result<Vec<_>>>()?;
            (0.0, children)
        }
        _ => return Err("unknown node kind".into()),
    };
    Ok(Node {
        name: name.into(),
        kind: kind.into(),
        ohms,
        children,
    })
}
fn measure(value: &Equivalent) -> Value {
    json!({"state":value.state,"ohms":if value.state=="open"{None}else{Some(value.ohms)}})
}
fn compensated(values: &[f64]) -> f64 {
    let (mut total, mut correction) = (0.0, 0.0);
    for value in values {
        let adjusted = value - correction;
        let updated = total + adjusted;
        correction = (updated - total) - adjusted;
        total = updated;
    }
    total
}
fn combine(kind: &str, inputs: &[Equivalent]) -> Result<(Equivalent, &'static str, Value)> {
    if kind == "series" && inputs.iter().any(|e| e.state == "open") {
        return Ok((
            Equivalent {
                state: "open",
                ohms: 0.0,
            },
            "an open branch breaks the series path",
            Value::Null,
        ));
    }
    if kind == "parallel" && inputs.iter().any(|e| e.state == "short") {
        return Ok((
            Equivalent {
                state: "short",
                ohms: 0.0,
            },
            "a short branch bypasses the parallel group",
            Value::Null,
        ));
    }
    let finite: Vec<_> = inputs
        .iter()
        .filter(|e| e.state == "finite")
        .map(|e| e.ohms)
        .collect();
    if finite.is_empty() {
        return Ok(if kind == "series" {
            (
                Equivalent {
                    state: "short",
                    ohms: 0.0,
                },
                "all series branches are shorts",
                Value::Null,
            )
        } else {
            (
                Equivalent {
                    state: "open",
                    ohms: 0.0,
                },
                "all parallel branches are open",
                Value::Null,
            )
        });
    }
    let scale = finite
        .iter()
        .copied()
        .reduce(if kind == "series" { f64::max } else { f64::min })
        .unwrap();
    let terms: Vec<_> = finite
        .iter()
        .map(|v| {
            if kind == "series" {
                v / scale
            } else {
                scale / v
            }
        })
        .collect();
    let total = compensated(&terms);
    let ohms = if kind == "series" {
        scale * total
    } else {
        scale / total
    };
    require(
        (1e-103..=1e103).contains(&ohms),
        "equivalent resistance outside supported range",
    )?;
    Ok((
        Equivalent {
            state: "finite",
            ohms,
        },
        if kind == "series" {
            "scale * sum(R / scale)"
        } else {
            "scale / sum(scale / R)"
        },
        json!({"scale_ohms":scale,"normalized_terms":terms,"normalized_sum":total}),
    ))
}
fn reduce(node: &Node, steps: &mut Vec<Value>) -> Result<Equivalent> {
    let (mut inputs, mut children) = (Vec::new(), Vec::new());
    for child in &node.children {
        let result = reduce(child, steps)?;
        children.push(json!({"id":child.name,"equivalent":measure(&result)}));
        inputs.push(result);
    }
    let (result, rule, arithmetic) =
        if node.kind == "short" || (node.kind == "resistor" && node.ohms == 0.0) {
            (
                Equivalent {
                    state: "short",
                    ohms: 0.0,
                },
                "zero resistance is a short",
                Value::Null,
            )
        } else if node.kind == "resistor" {
            (
                Equivalent {
                    state: "finite",
                    ohms: node.ohms,
                },
                "declared resistance in ohms",
                Value::Null,
            )
        } else if node.kind == "series" || node.kind == "parallel" {
            combine(&node.kind, &inputs)?
        } else {
            (
                Equivalent {
                    state: "open",
                    ohms: 0.0,
                },
                "explicit open circuit",
                Value::Null,
            )
        };
    let mut step =
        json!({"id":node.name,"kind":node.kind,"equivalent":measure(&result),"rule":rule});
    step["children"] = Value::Array(children);
    step["arithmetic"] = arithmetic;
    steps.push(step);
    Ok(result)
}
fn evaluate(row: &Value) -> Result<Value> {
    let mut seen = BTreeSet::new();
    let tree = parse(&row["tree"], 0, &mut seen)?;
    let mut steps = Vec::with_capacity(seen.len());
    let result = reduce(&tree, &mut steps)?;
    let mut value =
        json!({"id":row["id"],"status":"solved","equivalent":measure(&result),"nodes":seen.len()});
    value["steps"] = Value::Array(steps);
    Ok(value)
}
fn label(value: &Value) -> Result<String> {
    Ok(match string(&value["state"])? {
        "open" => "open circuit".into(),
        "short" => "short circuit (0 ohms)".into(),
        _ => rt::json_canonical_view(&value["ohms"])? + " ohms",
    })
}
fn run() -> Result<i32> {
    let request = Document::read(
        absolute(
            &std::env::var("CIRCUIT_CONFIG").unwrap_or("circuit-job.json".into()),
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
    require(mode == "solve" || mode == "verify", "unknown mode")?;
    let base = request.path.parent().unwrap();
    let output = absolute(string(&config["output"])?, base)?;
    require(
        std::fs::symlink_metadata(&output).is_err(),
        "output already exists",
    )?;
    let document = Document::read(
        absolute(string(&config["input"])?, base)?,
        if mode == "verify" { 4194304 } else { 1048576 },
    )?;
    let source = document.json()?;
    exact(
        &source,
        if mode == "verify" {
            &["version", "cases", "results"]
        } else {
            &["version", "cases"]
        },
    )?;
    require(integer(&source["version"])? == 1, "unsupported version")?;
    let rows = source["cases"].as_array().ok_or("expected case array")?;
    require((1..=16).contains(&rows.len()), "case count limit")?;
    let mut seen = BTreeSet::new();
    for row in rows {
        exact(row, &["id", "tree"])?;
        require(
            seen.insert(identifier(&row["id"])?),
            "duplicate case identifier",
        )?;
    }
    let results: Vec<_> = rows
        .iter()
        .map(|row| {
            evaluate(row).unwrap_or_else(
                |e| json!({"id":row["id"],"status":"rejected","reason":e.to_string()}),
            )
        })
        .collect();
    let results = Value::Array(results);
    if mode == "verify" {
        require(
            canonical(&source["results"])? == canonical(&results)?,
            "archive results do not match recomputed reductions",
        )?;
    }
    let mut counts = json!({"solved":0,"rejected":0,"finite":0,"open":0,"short":0});
    for result in results.as_array().unwrap() {
        let status = string(&result["status"])?;
        counts[status] = json!(integer(&counts[status])? + 1);
        if status == "solved" {
            let state = string(&result["equivalent"]["state"])?;
            counts[state] = json!(integer(&counts[state])? + 1);
        }
    }
    let mut lines = vec![
        "Ideal DC series/parallel circuits".into(),
        rt::json_canonical_view(&counts)?,
    ];
    for result in results.as_array().unwrap() {
        let name = string(&result["id"])?;
        if result["status"] == "rejected" {
            lines.push(format!("{name}: rejected: {}", string(&result["reason"])?));
        } else {
            lines.push(format!("{name}: {}", label(&result["equivalent"])?));
            for step in result["steps"].as_array().unwrap() {
                lines.push(format!(
                    "  {} ({}): {}; {}",
                    string(&step["id"])?,
                    string(&step["kind"])?,
                    label(&step["equivalent"])?,
                    string(&step["rule"])?
                ));
            }
        }
    }
    let networks = canonical(&json!({"version":1,"cases":rows}))?;
    let mut archive_value = json!({"version":1,"cases":rows});
    archive_value["results"] = results;
    let archive = canonical(&archive_value)?;
    drop(archive_value);
    let files = BTreeMap::from([
        ("networks.json".into(), networks),
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
            "solve.json".into(),
            canonical(
                &json!({"version":1,"mode":"solve","input":"networks.json","output":"solved"}),
            )?,
        ),
    ]);
    require(
        files.values().all(|data| data.len() <= 4194304),
        "export byte limit",
    )?;
    publish(&output, files, &[request, document], "circuit")?;
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
