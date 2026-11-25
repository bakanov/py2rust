//! Handwritten schema-driven CSV/JSON conversion and complete rejection reports.
mod common;
mod csv_codec;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::Path,
};
struct Column {
    kind: String,
    nullable: bool,
}
fn rules(config: &Value) -> Result<BTreeMap<String, Column>> {
    let raw = config["columns"].as_array().ok_or("expected array")?;
    require(
        (1..=64).contains(&raw.len()),
        "schema requires 1..64 columns",
    )?;
    let mut columns = BTreeMap::new();
    for value in raw {
        exact(value, &["name", "type", "nullable"])?;
        let name = string(&value["name"])?;
        require(
            !name.is_empty() && name.len() <= 256 && !name.contains('\0'),
            "invalid column name",
        )?;
        require(!columns.contains_key(name), "duplicate schema column")?;
        let kind = string(&value["type"])?;
        require(
            matches!(kind, "string" | "integer" | "number" | "boolean" | "json"),
            "invalid column type",
        )?;
        let nullable = value["nullable"].as_bool().ok_or("expected boolean")?;
        columns.insert(
            name.into(),
            Column {
                kind: kind.into(),
                nullable,
            },
        );
    }
    Ok(columns)
}
fn typed(value: &Value, column: &Column) -> Result<()> {
    if value.is_null() {
        return require(column.nullable, "null is not permitted");
    }
    match column.kind.as_str() {
        "string" => require(value.is_string(), "expected string"),
        "integer" => integer(value).map(|_| ()),
        "number" => require(value.is_number(), "expected number"),
        "boolean" => require(value.is_boolean(), "expected boolean"),
        _ => Ok(()),
    }
}
fn decode(cell: &str, column: &Column) -> Result<Value> {
    if cell == "\\N" {
        typed(&Value::Null, column)?;
        return Ok(Value::Null);
    }
    let value = if cell.starts_with("\\\\") {
        &cell[1..]
    } else {
        cell
    };
    match column.kind.as_str() {
        "string" => return Ok(json!(value)),
        "integer" => return Ok(json!(rt::int_from_decimal(value)?)),
        "number" => require(
            rt::regex_fullmatch(
                r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
                value.trim(),
            )?,
            "expected JSON number",
        )?,
        "boolean" => require(
            matches!(value.trim(), "true" | "false"),
            "expected JSON boolean",
        )?,
        _ => (),
    }
    let parsed = rt::json_loads(value)?;
    typed(&parsed, column)?;
    Ok(parsed)
}
fn encode(value: &Value, column: &Column) -> Result<String> {
    if value.is_null() {
        return Ok("\\N".into());
    }
    let text = if column.kind == "string" {
        string(value)?.into()
    } else {
        rt::json_canonical_view(value)?
    };
    Ok(if text.starts_with('\\') {
        format!("\\{text}")
    } else {
        text
    })
}
fn convert(
    source: &[u8],
    config: &Value,
    columns: &BTreeMap<String, Column>,
    selected: &[String],
) -> Result<(String, Value)> {
    let to_json = string(&config["direction"])? == "csv-to-json";
    let max_rows = integer(&config["max_rows"])? as usize;
    let field_limit = integer(&config["max_field_bytes"])? as usize;
    let delimiter = string(&config["delimiter"])?.chars().next().unwrap();
    let mut header = Vec::new();
    let records: Vec<Value> = if to_json {
        let mut table =
            csv_codec::parse(source, delimiter as u8, max_rows + 1, 64, field_limit)?.into_iter();
        header = table.next().ok_or("CSV header is missing")?;
        let keys: BTreeSet<_> = header.iter().collect();
        require(
            keys.len() == header.len() && keys.into_iter().eq(columns.keys()),
            "CSV header differs from schema",
        )?;
        table.map(|row| json!(row)).collect()
    } else {
        let value = rt::json_loads(std::str::from_utf8(source)?)?;
        let Value::Array(rows) = value else {
            return Err("expected array".into());
        };
        require(rows.len() <= max_rows, "JSON row limit exceeded")?;
        rows
    };
    let mut accepted = Vec::new();
    let mut rejected = Vec::new();
    let mut encoded_rows = Vec::new();
    let csv_header = if to_json {
        String::new()
    } else {
        csv_codec::render_row(selected, delimiter, field_limit)?
    };
    let mut output_bytes = if to_json { 3 } else { csv_header.len() };
    let mut rejection_bytes = 0;
    for (index, raw) in records.iter().enumerate() {
        let mut errors = Vec::new();
        let mut candidate = BTreeMap::new();
        if to_json {
            let cells = raw.as_array().unwrap();
            if cells.len() != header.len() {
                errors.push(json!({"column":"","reason":"row width differs from header"}));
            } else {
                for (name, value) in header.iter().zip(cells) {
                    candidate.insert(name.as_str(), value);
                }
            }
        } else if let Some(object) = raw
            .as_object()
            .filter(|o| o.len() == columns.len() && columns.keys().all(|k| o.contains_key(k)))
        {
            candidate.extend(object.iter().map(|(k, v)| (k.as_str(), v)));
        } else {
            errors.push(json!({"column":"","reason":"record fields differ from schema"}));
        }
        let mut normalized = BTreeMap::new();
        if errors.is_empty() {
            for (name, column) in columns {
                let result = (|| -> Result<Value> {
                    let value = if to_json {
                        decode(string(candidate[name.as_str()])?, column)?
                    } else {
                        let value = candidate[name.as_str()];
                        typed(value, column)?;
                        value.clone()
                    };
                    require(
                        encode(&value, column)?.len() <= field_limit,
                        "formatted field exceeds byte limit",
                    )?;
                    Ok(value)
                })();
                match result {
                    Ok(value) => {
                        normalized.insert(name.as_str(), value);
                    }
                    Err(_) => errors.push(
                        json!({"column":name,"reason":format!("invalid {} value",column.kind)}),
                    ),
                }
            }
        }
        if !errors.is_empty() {
            let rejection = json!({"row":index+1,"input":raw,"errors":errors});
            let rendered = rt::pretty(&rejection)?;
            rejection_bytes += rendered.len() + 4 * rendered.split('\n').count() + 2;
            require(
                rejection_bytes <= 15728640,
                "rejection report exceeds 15 MiB budget",
            )?;
            rejected.push(rejection);
        } else {
            let encoded = if to_json {
                let projected: BTreeMap<_, _> = selected
                    .iter()
                    .map(|name| (name, &normalized[name.as_str()]))
                    .collect();
                rt::json_canonical_view(&json!(projected))?
            } else {
                let row = selected
                    .iter()
                    .map(|name| encode(&normalized[name.as_str()], &columns[name]))
                    .collect::<Result<Vec<_>>>()?;
                csv_codec::render_row(&row, delimiter, field_limit)?
            };
            output_bytes += encoded.len() + usize::from(to_json && !accepted.is_empty());
            require(output_bytes <= 8388608, "converted data exceeds 8 MiB")?;
            accepted.push(index + 1);
            encoded_rows.push(encoded);
        }
    }
    let data = if to_json {
        format!("[{}]\n", encoded_rows.join(","))
    } else {
        csv_header + &encoded_rows.concat()
    };
    require(data.len() <= 8388608, "converted data exceeds 8 MiB")?;
    let report = json!({"direction":config["direction"],"columns":selected,"rows":records.len(),"accepted":accepted.len(),"rejected":rejected.len(),"accepted_rows":accepted,"errors":rejected});
    Ok((data, report))
}
fn publish(output: &Path, filename: &str, data: &str, report: &str) -> Result<()> {
    let parent = output.parent().ok_or("missing parent")?;
    let staging = parent.join(format!(".csv-json-{}", rt::random_token()?));
    fs::create_dir(&staging)?;
    let result = (|| -> Result<()> {
        rt::write_text_atomic(staging.join(filename).to_str().ok_or("invalid path")?, data)?;
        rt::write_text_atomic(
            staging.join("report.json").to_str().ok_or("invalid path")?,
            report,
        )?;
        fs::File::open(&staging)?.sync_all()?;
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
fn run() -> Result<bool> {
    let mode = std::env::var("CONVERT_MODE").unwrap_or_else(|_| "preview".into());
    require(
        matches!(mode.as_str(), "preview" | "convert"),
        "invalid conversion mode",
    )?;
    let configuration = Document::read(
        absolute(
            &std::env::var("CONVERT_CONFIG").unwrap_or_else(|_| "convert.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let config = rt::json_loads(std::str::from_utf8(&configuration.data)?)?;
    exact(
        &config,
        &[
            "input",
            "output",
            "direction",
            "delimiter",
            "columns",
            "select",
            "max_rows",
            "max_field_bytes",
            "max_input_bytes",
        ],
    )?;
    let direction = string(&config["direction"])?;
    require(
        matches!(direction, "csv-to-json" | "json-to-csv"),
        "invalid conversion direction",
    )?;
    require(
        matches!(string(&config["delimiter"])?, "," | ";" | "\t" | "|"),
        "unsupported delimiter",
    )?;
    require(
        (1..=10000).contains(&integer(&config["max_rows"])?),
        "row limit must be 1..10000",
    )?;
    require(
        (1..=65536).contains(&integer(&config["max_field_bytes"])?),
        "field limit must be 1..65536",
    )?;
    let limit = integer(&config["max_input_bytes"])?;
    require(
        (1..=4194304).contains(&limit),
        "input limit must be 1..4 MiB",
    )?;
    let columns = rules(&config)?;
    let mut selected = Vec::new();
    for value in config["select"].as_array().ok_or("expected array")? {
        let name = string(value)?.to_owned();
        require(
            columns.contains_key(&name) && !selected.contains(&name),
            "invalid selected column",
        )?;
        selected.push(name);
    }
    require(!selected.is_empty(), "select at least one column")?;
    let base = configuration.path.parent().ok_or("missing parent")?;
    let output = absolute(string(&config["output"])?, base)?;
    require(
        !output.exists() && !output.is_symlink(),
        "output directory already exists",
    )?;
    let document = Document::read(absolute(string(&config["input"])?, base)?, limit as usize)?;
    std::str::from_utf8(&document.data)?;
    let (data, mut report) = convert(&document.data, &config, &columns, &selected)?;
    let filename = if direction == "csv-to-json" {
        "data.json"
    } else {
        "data.csv"
    };
    report["input_sha256"] = json!(digest(&document.data));
    report["data_sha256"] = json!(digest(data.as_bytes()));
    report["data_file"] = json!(filename);
    let text = rt::pretty(&report)?;
    require(text.len() <= 16777216, "report exceeds 16 MiB")?;
    configuration.unchanged()?;
    document.unchanged()?;
    if mode == "convert" {
        publish(&output, filename, &data, &text)?;
    }
    println!("{text}");
    Ok(integer(&report["rejected"])? > 0)
}
fn main() {
    match run() {
        Ok(rejected) => std::process::exit(i32::from(rejected)),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    }
}
