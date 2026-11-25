//! Handwritten stable composite-key joins with bounded expansion and complete reports.
mod common;
mod csv_codec;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::{
    collections::{BTreeSet, HashMap},
    fs,
    path::Path,
};
fn names(value: &Value) -> Result<Vec<String>> {
    let mut result = Vec::new();
    let mut seen = BTreeSet::new();
    for item in value.as_array().ok_or("expected array")? {
        let name = string(item)?;
        require(
            !name.is_empty() && name.len() <= 256 && !name.contains('\0'),
            "invalid column name",
        )?;
        require(seen.insert(name), "duplicate column name")?;
        result.push(name.into());
    }
    require((1..=64).contains(&result.len()), "require 1..64 columns")?;
    Ok(result)
}
fn delimiter(value: &Value, message: &str) -> Result<char> {
    let s = string(value)?;
    require(matches!(s, "," | ";" | "\t" | "|"), message)?;
    Ok(s.chars().next().unwrap())
}
fn validate(config: &Value) -> Result<()> {
    exact(
        config,
        &[
            "left",
            "right",
            "output",
            "kind",
            "select",
            "delimiter",
            "duplicates",
            "order",
            "max_rows",
            "max_field_bytes",
            "max_input_bytes",
            "max_output_rows",
        ],
    )?;
    require(
        matches!(string(&config["kind"])?, "inner" | "left"),
        "invalid join kind",
    )?;
    require(
        matches!(string(&config["duplicates"])?, "all" | "error"),
        "invalid duplicate policy",
    )?;
    require(
        matches!(string(&config["order"])?, "left" | "key"),
        "invalid output order",
    )?;
    for side in ["left", "right"] {
        exact(&config[side], &["path", "keys", "delimiter"])?;
        names(&config[side]["keys"])?;
        delimiter(&config[side]["delimiter"], "invalid input delimiter")?;
    }
    require(
        config["left"]["keys"].as_array().unwrap().len()
            == config["right"]["keys"].as_array().unwrap().len(),
        "key arity differs",
    )?;
    delimiter(&config["delimiter"], "invalid output delimiter")?;
    for (name, max, message) in [
        ("max_rows", 10000, "row limit must be 1..10000"),
        ("max_field_bytes", 65536, "field limit must be 1..65536"),
        ("max_input_bytes", 4194304, "input limit must be 1..4 MiB"),
        (
            "max_output_rows",
            100000,
            "output row limit must be 1..100000",
        ),
    ] {
        require((1..=max).contains(&integer(&config[name])?), message)?;
    }
    Ok(())
}
struct Table {
    header: Vec<String>,
    rows: Vec<Vec<String>>,
    keys: Vec<usize>,
}
impl Table {
    fn read(doc: &Document, spec: &Value, config: &Value) -> Result<Self> {
        std::str::from_utf8(&doc.data)?;
        let mut rows = csv_codec::parse(
            &doc.data,
            delimiter(&spec["delimiter"], "invalid input delimiter")? as u8,
            integer(&config["max_rows"])? as usize + 1,
            64,
            integer(&config["max_field_bytes"])? as usize,
        )?
        .into_iter();
        let header = names(&json!(rows.next().ok_or("CSV header is required")?))?;
        let keys = names(&spec["keys"])?
            .into_iter()
            .map(|name| {
                header
                    .iter()
                    .position(|x| x == &name)
                    .ok_or_else(|| "join key is missing from header".into())
            })
            .collect::<Result<Vec<_>>>()?;
        let rows: Vec<_> = rows.collect();
        for (index, row) in rows.iter().enumerate() {
            require(
                row.len() == header.len(),
                &format!("CSV row width differs from header at record {}", index + 1),
            )?;
        }
        Ok(Self { header, rows, keys })
    }
    fn key(&self, index: usize) -> Vec<&str> {
        self.keys
            .iter()
            .map(|&k| self.rows[index][k].as_str())
            .collect()
    }
    fn index(&self) -> HashMap<Vec<&str>, Vec<usize>> {
        let mut result: HashMap<_, Vec<_>> = HashMap::new();
        for i in 0..self.rows.len() {
            result.entry(self.key(i)).or_default().push(i);
        }
        result
    }
    fn unmatched(&self, matched: &[bool]) -> Value {
        Value::Array(
            self.rows
                .iter()
                .enumerate()
                .filter(|(i, _)| !matched[*i])
                .map(|(i, row)| json!({"row":i+1,"values":row}))
                .collect(),
        )
    }
}
struct Projection {
    left: bool,
    column: usize,
    alias: String,
}
fn selection(config: &Value, left: &Table, right: &Table) -> Result<Vec<Projection>> {
    let mut selected = Vec::new();
    for item in config["select"].as_array().ok_or("expected array")? {
        exact(item, &["side", "column", "as"])?;
        let side = string(&item["side"])?;
        require(matches!(side, "left" | "right"), "invalid projection side")?;
        let header = if side == "left" {
            &left.header
        } else {
            &right.header
        };
        let name = string(&item["column"])?;
        let column = header
            .iter()
            .position(|k| k == name)
            .ok_or("selected column is missing")?;
        selected.push(Projection {
            left: side == "left",
            column,
            alias: string(&item["as"])?.into(),
        });
    }
    names(&json!(selected
        .iter()
        .map(|p| &p.alias)
        .collect::<Vec<_>>()))?;
    Ok(selected)
}
fn duplicates(index: &HashMap<Vec<&str>, Vec<usize>>) -> Vec<Value> {
    let mut keys: Vec<_> = index.iter().filter(|(_, v)| v.len() > 1).collect();
    keys.sort_by(|(a, _), (b, _)| a.cmp(b));
    keys.into_iter()
        .map(|(key, rows)| json!({"key":key,"rows":rows.iter().map(|i|i+1).collect::<Vec<_>>()}))
        .collect()
}
fn join(
    left: &Table,
    right: &Table,
    selected: &[Projection],
    config: &Value,
) -> Result<(String, Value)> {
    let li = left.index();
    let ri = right.index();
    let ld = duplicates(&li);
    let rd = duplicates(&ri);
    require(
        config["duplicates"] == "all" || (ld.is_empty() && rd.is_empty()),
        "duplicate join key rejected by policy",
    )?;
    let outer = config["kind"] == "left";
    let mut count = 0;
    let mut pairs = 0;
    let mut ml = vec![false; left.rows.len()];
    let mut mr = vec![false; right.rows.len()];
    for (key, rows) in &li {
        let matches = ri.get(key).map(Vec::as_slice).unwrap_or(&[]);
        let n = rows.len() * matches.len();
        pairs += n;
        count += if outer && matches.is_empty() {
            rows.len()
        } else {
            n
        };
        require(
            count <= integer(&config["max_output_rows"])? as usize,
            "join output row limit exceeded",
        )?;
        if !matches.is_empty() {
            for &i in rows {
                ml[i] = true;
            }
            for &i in matches {
                mr[i] = true;
            }
        }
    }
    let mut ordered: Vec<_> = (0..left.rows.len()).collect();
    if config["order"] == "key" {
        ordered.sort_by_cached_key(|&i| left.key(i));
    }
    let header: Vec<_> = selected.iter().map(|p| p.alias.clone()).collect();
    let delimiter = delimiter(&config["delimiter"], "invalid output delimiter")?;
    let mut data = csv_codec::render_row(&header, delimiter, 65536)?;
    let mut append = |i: usize, j: Option<usize>| -> Result<()> {
        let row: Vec<_> = selected
            .iter()
            .map(|p| {
                if p.left {
                    left.rows[i][p.column].clone()
                } else {
                    j.map(|j| right.rows[j][p.column].clone())
                        .unwrap_or_default()
                }
            })
            .collect();
        let line = csv_codec::render_row(&row, delimiter, 65536)?;
        require(
            data.len() + line.len() <= 8388608,
            "join output exceeds 8 MiB",
        )?;
        data.push_str(&line);
        Ok(())
    };
    for i in ordered {
        let key = left.key(i);
        let matches = ri.get(&key).map(Vec::as_slice).unwrap_or(&[]);
        if matches.is_empty() && outer {
            append(i, None)?;
        } else {
            for &j in matches {
                append(i, Some(j))?;
            }
        }
    }
    let report = json!({"kind":config["kind"],"order":config["order"],"columns":header,"left_columns":left.header,"right_columns":right.header,"left_rows":left.rows.len(),"right_rows":right.rows.len(),"output_rows":count,"matched_pairs":pairs,"matched_left":ml.iter().filter(|&&b|b).count(),"matched_right":mr.iter().filter(|&&b|b).count(),"unmatched_left":left.unmatched(&ml),"unmatched_right":right.unmatched(&mr),"duplicate_left":ld,"duplicate_right":rd});
    Ok((data, report))
}
fn run() -> Result<()> {
    let mode = std::env::var("JOIN_MODE").unwrap_or_else(|_| "preview".into());
    require(
        matches!(mode.as_str(), "preview" | "join"),
        "invalid join mode",
    )?;
    let configuration = Document::read(
        absolute(
            &std::env::var("JOIN_CONFIG").unwrap_or_else(|_| "join.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let config = rt::json_loads(std::str::from_utf8(&configuration.data)?)?;
    validate(&config)?;
    let base = configuration.path.parent().ok_or("missing parent")?;
    let output = absolute(string(&config["output"])?, base)?;
    require(
        !output.exists() && !output.is_symlink(),
        "output directory already exists",
    )?;
    let limit = integer(&config["max_input_bytes"])? as usize;
    let left_doc = Document::read(absolute(string(&config["left"]["path"])?, base)?, limit)?;
    let right_doc = Document::read(absolute(string(&config["right"]["path"])?, base)?, limit)?;
    let left = Table::read(&left_doc, &config["left"], &config)?;
    let right = Table::read(&right_doc, &config["right"], &config)?;
    let selected = selection(&config, &left, &right)?;
    let (data, mut report) = join(&left, &right, &selected, &config)?;
    report["left_sha256"] = json!(digest(&left_doc.data));
    report["right_sha256"] = json!(digest(&right_doc.data));
    report["data_sha256"] = json!(digest(data.as_bytes()));
    let text = rt::pretty(&report)?;
    require(text.len() <= 16777216, "join report exceeds 16 MiB")?;
    let documents = [configuration, left_doc, right_doc];
    for doc in &documents {
        doc.unchanged()?;
    }
    if mode == "join" {
        publish(&output, &data, &text, &documents)?;
    }
    println!("{text}");
    Ok(())
}
fn publish(output: &Path, data: &str, report: &str, documents: &[Document]) -> Result<()> {
    let parent = output.parent().ok_or("missing parent")?;
    let staging = parent.join(format!(".csv-join-{}", rt::random_token()?));
    fs::create_dir(&staging)?;
    let result = (|| -> Result<()> {
        rt::write_text_atomic(
            staging.join("joined.csv").to_str().ok_or("invalid path")?,
            data,
        )?;
        rt::write_text_atomic(
            staging.join("report.json").to_str().ok_or("invalid path")?,
            report,
        )?;
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
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
