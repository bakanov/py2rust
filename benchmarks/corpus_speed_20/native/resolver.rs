//! Handwritten typed resolver baseline. Same DFS order, budgets and conflict records.
//! Supports resolve jobs; verify-lock mode is deliberately outside this benchmark.
mod common;
use common::*;
use serde_json::{json, Value};
use std::{collections::BTreeMap, path::Path};

type Version = [i64; 3];
type Choices = BTreeMap<String, String>;
type Requirements = BTreeMap<String, Requirement>;
#[derive(Clone)]
struct Requirement {
    text: String,
    clauses: Vec<Vec<(String, Version)>>,
}
struct Release {
    text: String,
    version: Version,
    dependencies: Requirements,
}
type Packages = BTreeMap<String, Vec<Release>>;
struct Incoming<'a> {
    from: String,
    requirement: &'a Requirement,
}

fn version(text: &str) -> Result<Version> {
    let parts: Vec<_> = text.split('.').collect();
    require(parts.len() == 3, "invalid version")?;
    let mut result = [0; 3];
    for (i, part) in parts.iter().enumerate() {
        require(
            !part.is_empty()
                && part.len() <= 10
                && part.bytes().all(|b| b.is_ascii_digit())
                && (part.len() == 1 || !part.starts_with('0')),
            "invalid version",
        )?;
        result[i] = part.parse()?;
        require(result[i] <= 2147483647, "version component exceeds 31 bits")?;
    }
    Ok(result)
}
fn requirement(text: &str) -> Result<Requirement> {
    require(
        !text.is_empty()
            && text.len() <= 256
            && text
                .bytes()
                .all(|b| b.is_ascii_digit() || b" .<>=^~|*".contains(&b)),
        "invalid requirement",
    )?;
    let alternatives: Vec<_> = text.split("||").collect();
    require(alternatives.len() <= 4, "too many alternatives")?;
    let mut clauses = Vec::new();
    for alternative in alternatives {
        let terms: Vec<_> = alternative
            .trim()
            .split(' ')
            .filter(|s| !s.is_empty())
            .collect();
        require(
            !terms.is_empty() && terms.len() <= 4,
            "expected one to four terms",
        )?;
        let mut atoms = Vec::new();
        for term in terms {
            if term == "*" {
                continue;
            }
            let op = [">=", "<=", ">", "<", "=", "^", "~"]
                .into_iter()
                .find(|op| term.starts_with(op));
            let lower = version(op.map_or(term, |op| &term[op.len()..]))?;
            match op.unwrap_or("=") {
                op @ ("^" | "~") => {
                    let upper = if op == "^" && lower[0] > 0 {
                        [lower[0] + 1, 0, 0]
                    } else if op == "^" && lower[1] == 0 {
                        [0, 0, lower[2] + 1]
                    } else {
                        [lower[0], lower[1] + 1, 0]
                    };
                    atoms.push((">=".into(), lower));
                    atoms.push(("<".into(), upper));
                }
                op => atoms.push((op.into(), lower)),
            }
        }
        clauses.push(atoms);
    }
    Ok(Requirement {
        text: text.into(),
        clauses,
    })
}
fn package_name(name: &str) -> Result<()> {
    require(
        !name.is_empty()
            && name.len() <= 32
            && name.as_bytes()[0].is_ascii_alphabetic()
            && name
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"_-".contains(&b)),
        "invalid package name",
    )
}
fn requirements(value: &Value, limit: usize) -> Result<Requirements> {
    let object = value.as_object().ok_or("expected dependencies object")?;
    require(object.len() <= limit, "too many dependencies")?;
    object
        .iter()
        .map(|(name, value)| {
            package_name(name)?;
            Ok((name.clone(), requirement(string(value)?)?))
        })
        .collect()
}
fn accepts(candidate: Version, required: &Requirement) -> bool {
    required.clauses.iter().any(|clause| {
        clause.iter().all(|(op, bound)| match op.as_str() {
            ">" => candidate > *bound,
            ">=" => candidate >= *bound,
            "<" => candidate < *bound,
            "<=" => candidate <= *bound,
            _ => candidate == *bound,
        })
    })
}
fn constraints<'a>(
    packages: &'a Packages,
    roots: &'a Requirements,
    choices: &Choices,
) -> BTreeMap<String, Vec<Incoming<'a>>> {
    let mut result: BTreeMap<String, Vec<Incoming>> = BTreeMap::new();
    for (name, requirement) in roots {
        result.entry(name.clone()).or_default().push(Incoming {
            from: "root".into(),
            requirement,
        });
    }
    for (name, selected) in choices {
        let release = packages[name].iter().find(|r| &r.text == selected).unwrap();
        for (dependency, requirement) in &release.dependencies {
            result
                .entry(dependency.clone())
                .or_default()
                .push(Incoming {
                    from: format!("{name}@{selected}"),
                    requirement,
                });
        }
    }
    result
}
fn domain(packages: &Packages, name: &str, required: &[Incoming]) -> Vec<String> {
    packages
        .get(name)
        .into_iter()
        .flatten()
        .filter(|r| required.iter().all(|c| accepts(r.version, c.requirement)))
        .map(|r| r.text.clone())
        .collect()
}
fn conflict(
    packages: &Packages,
    name: &str,
    required: &[Incoming],
    choices: &Choices,
    allowed: &[String],
) -> Value {
    let sources: Vec<_> = required
        .iter()
        .map(|c| json!({"from":c.from,"range":c.requirement.text}))
        .collect();
    let rejected: Vec<_> = packages
        .get(name)
        .into_iter()
        .flatten()
        .filter_map(|r| {
            let failed: Vec<_> = required
                .iter()
                .enumerate()
                .filter(|(_, c)| !accepts(r.version, c.requirement))
                .map(|(i, _)| i)
                .collect();
            (!failed.is_empty()).then(|| json!({"version":r.text,"requirements":failed}))
        })
        .collect();
    let reason = if !packages.contains_key(name) {
        "missing_package"
    } else if choices.contains_key(name) {
        "selected_version"
    } else {
        "no_version"
    };
    json!({"package":name,"reason":reason,"choices":choices,"requirements":sources,"admissible":allowed,"rejected":rejected})
}
fn solve(packages: &Packages, roots: &Requirements, limit: usize, retained: usize) -> Value {
    let mut pending = vec![Choices::new()];
    let (mut visited, mut failed) = (0, 0);
    let mut trace = Vec::new();
    let mut solution = Choices::new();
    let mut status = "unsatisfiable";
    while !pending.is_empty() {
        if visited == limit {
            status = "budget_exhausted";
            break;
        }
        let choices = pending.pop().unwrap();
        visited += 1;
        let required = constraints(packages, roots, &choices);
        let mut selected = String::new();
        let mut options = Vec::new();
        let mut broken = false;
        for (name, required) in &required {
            let allowed = domain(packages, name, required);
            if allowed.is_empty()
                || choices
                    .get(name)
                    .is_some_and(|chosen| !allowed.contains(chosen))
            {
                failed += 1;
                if trace.len() < retained {
                    trace.push(conflict(packages, name, required, &choices, &allowed));
                }
                broken = true;
                break;
            }
            if !choices.contains_key(name) && (selected.is_empty() || allowed.len() < options.len())
            {
                selected = name.clone();
                options = allowed;
            }
        }
        if broken {
            continue;
        }
        if selected.is_empty() {
            status = "resolved";
            solution = choices;
            break;
        }
        for candidate in options {
            let mut branch = choices.clone();
            branch.insert(selected.clone(), candidate);
            pending.push(branch);
        }
    }
    let next = if status == "budget_exhausted" {
        json!(pending.last().unwrap())
    } else {
        Value::Null
    };
    json!({"status":status,"selected":solution,"statistics":{"states":visited,"conflicts":failed,"recorded_conflicts":trace.len(),"pending_states":pending.len()},"conflicts":trace,"next_state":next,"errors":[]})
}
fn run() -> Result<i32> {
    let cwd = std::env::current_dir()?;
    let config = Document::read(
        absolute(
            &std::env::var("RESOLVER_CONFIG").unwrap_or("resolver-job.json".into()),
            &cwd,
        )?,
        65536,
    )?;
    let request = config.json()?;
    exact(
        &request,
        &[
            "version",
            "mode",
            "index",
            "output",
            "roots",
            "max_steps",
            "max_conflicts",
        ],
    )?;
    require(
        request["mode"] == "resolve" && request["version"] == 1,
        "baseline supports version 1 resolve jobs",
    )?;
    let limit = integer(&request["max_steps"])?;
    let retained = integer(&request["max_conflicts"])?;
    require(
        (1..=10000).contains(&limit) && (1..=128).contains(&retained),
        "invalid search budget",
    )?;
    let base = config.path.parent().unwrap();
    let output = absolute(string(&request["output"])?, base)?;
    require(
        std::fs::symlink_metadata(&output).is_err(),
        "output already exists",
    )?;
    let index = Document::read(absolute(string(&request["index"])?, base)?, 524288)?;
    let raw = index.json()?;
    exact(&raw, &["version", "packages"])?;
    require(raw["version"] == 1, "unsupported index")?;
    let entries = raw["packages"].as_object().ok_or("expected packages")?;
    require(entries.len() <= 16, "too many packages")?;
    let mut packages = Packages::new();
    for (name, entries) in entries {
        package_name(name)?;
        let entries = entries.as_array().ok_or("expected releases")?;
        require(entries.len() <= 8, "too many releases")?;
        let mut releases: Vec<Release> = Vec::new();
        for entry in entries {
            exact(entry, &["version", "dependencies"])?;
            let text = string(&entry["version"])?;
            require(
                !releases.iter().any(|r| r.text == text),
                "duplicate version",
            )?;
            releases.push(Release {
                text: text.into(),
                version: version(text)?,
                dependencies: requirements(&entry["dependencies"], 8)?,
            });
        }
        releases.sort_by_key(|r| r.version);
        packages.insert(name.clone(), releases);
    }
    let roots = requirements(&request["roots"], 16)?;
    let outcome = solve(&packages, &roots, limit as usize, retained as usize);
    let status = string(&outcome["status"])?;
    if status == "resolved" {
        let choices: Choices = serde_json::from_value(outcome["selected"].clone())?;
        for (name, required) in constraints(&packages, &roots, &choices) {
            require(
                choices
                    .get(&name)
                    .is_some_and(|c| domain(&packages, &name, &required).contains(c)),
                "internal solution verification failed",
            )?;
        }
    }
    let hash = digest(&index.data);
    let report =
        json!({"version":1,"index_sha256":hash,"roots":request["roots"],"outcome":outcome});
    let mut lines = vec![format!("Package constraint resolver: {status}"),"A conflict explains one branch; retained conflicts are not claimed to be a minimal unsatisfiable core.".into(),py2rust_service_runtime::json_canonical_view(&outcome["statistics"])?];
    for (name, selected) in outcome["selected"].as_object().unwrap() {
        lines.push(format!("{name} = {}", string(selected)?));
    }
    for conflict in outcome["conflicts"].as_array().unwrap() {
        lines.push(format!(
            "Conflict: {}",
            py2rust_service_runtime::json_canonical_view(conflict)?
        ));
    }
    let mut replay = request.clone();
    replay["index"] = json!("index.json");
    replay["output"] = json!("replayed");
    let mut files = BTreeMap::from([
        ("index.json".into(), index.data.clone()),
        ("report.json".into(), canonical(&report)?),
        ("report.txt".into(), (lines.join("\n") + "\n").into_bytes()),
        ("replay.json".into(), canonical(&replay)?),
    ]);
    if status == "resolved" {
        files.insert("lock.json".into(),canonical(&json!({"version":1,"index_sha256":hash,"roots":request["roots"],"packages":outcome["selected"]}))?);
        files.insert("verify.json".into(),canonical(&json!({"version":1,"mode":"verify","index":"index.json","output":"verified","lock":"lock.json"}))?);
    }
    require(
        files.values().map(Vec::len).sum::<usize>() <= 4194304,
        "report bundle exceeds 4 MiB",
    )?;
    publish(Path::new(&output), files, &[config, index], "resolver")?;
    println!("{status}");
    Ok(match status {
        "resolved" => 0,
        "budget_exhausted" => 3,
        _ => 1,
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
