//! Handwritten complete common-access-log analysis, with borrowed regex captures.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use regex::Regex;
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Serialize)]
struct Record<'a> {
    host: &'a str,
    ident: &'a str,
    user: &'a str,
    timestamp: String,
    method: &'a str,
    target: &'a str,
    path: &'a str,
    protocol: &'a str,
    status: i64,
    bytes: i64,
    source: &'a str,
    line: usize,
    selected: bool,
}

fn parse<'a>(
    raw: &'a [u8],
    pattern: &Regex,
    source: &'a str,
    line: usize,
) -> std::result::Result<Record<'a>, &'static str> {
    let text = std::str::from_utf8(raw).map_err(|_| "utf8")?;
    if raw.iter().any(|&value| value < 32 || value == 127) {
        return Err("control");
    }
    let captures = pattern.captures(text).ok_or("format")?;
    let group = |index| captures.get(index).unwrap().as_str();
    let month = match group(5) {
        "Jan" => "01",
        "Feb" => "02",
        "Mar" => "03",
        "Apr" => "04",
        "May" => "05",
        "Jun" => "06",
        "Jul" => "07",
        "Aug" => "08",
        "Sep" => "09",
        "Oct" => "10",
        "Nov" => "11",
        "Dec" => "12",
        _ => return Err("timestamp"),
    };
    let offset = group(10);
    let date = format!(
        "{}-{}-{}T{}:{}:{}{}:{}",
        group(6),
        month,
        group(4),
        group(7),
        group(8),
        group(9),
        &offset[..3],
        &offset[3..]
    );
    let timestamp = rt::datetime_iso(&rt::datetime_parse(&date).map_err(|_| "timestamp")?);
    let status: i64 = group(14).parse().map_err(|_| "status")?;
    if !(100..=599).contains(&status) {
        return Err("status");
    }
    if group(15).len() > 4096 {
        return Err("bytes");
    }
    let bytes = if group(15) == "-" {
        0
    } else {
        group(15).parse().map_err(|_| "bytes")?
    };
    let target = group(12);
    Ok(Record {
        host: group(1),
        ident: group(2),
        user: group(3),
        timestamp,
        method: group(11),
        target,
        path: target.split_once('?').map_or(target, |(path, _)| path),
        protocol: group(13),
        status,
        bytes,
        source,
        line,
        selected: false,
    })
}

#[derive(Default, Serialize)]
struct PathCount {
    requests: i64,
    bytes: i64,
    errors: i64,
}
#[derive(Default)]
struct Summary<'a> {
    requests: i64,
    bytes: i64,
    client_errors: i64,
    server_errors: i64,
    hosts: BTreeSet<&'a str>,
    statuses: BTreeMap<i64, i64>,
    methods: BTreeMap<&'a str, i64>,
    hours: BTreeMap<String, i64>,
    paths: BTreeMap<&'a str, PathCount>,
    first: Option<String>,
    last: Option<String>,
}
impl<'a> Summary<'a> {
    fn add(&mut self, record: &Record<'a>) -> Result<()> {
        if !record.selected {
            return Ok(());
        }
        self.requests += 1;
        self.bytes = self
            .bytes
            .checked_add(record.bytes)
            .ok_or("selected byte total exceeds signed integer range")?;
        self.client_errors += i64::from((400..500).contains(&record.status));
        self.server_errors += i64::from(record.status >= 500);
        self.hosts.insert(record.host);
        *self.statuses.entry(record.status).or_default() += 1;
        *self.methods.entry(record.method).or_default() += 1;
        *self
            .hours
            .entry(format!("{}:00:00.000000+00:00", &record.timestamp[..13]))
            .or_default() += 1;
        if self
            .first
            .as_ref()
            .map_or(true, |first| &record.timestamp < first)
        {
            self.first = Some(record.timestamp.clone());
        }
        if self
            .last
            .as_ref()
            .map_or(true, |last| &record.timestamp > last)
        {
            self.last = Some(record.timestamp.clone());
        }
        let path = self.paths.entry(record.path).or_default();
        path.requests += 1;
        path.bytes += record.bytes;
        path.errors += i64::from(record.status >= 400);
        Ok(())
    }
    fn finish(self, top: usize) -> Value {
        let mut ranks: Vec<_> = self.paths.iter().collect();
        ranks.sort_by_key(|(path, count)| (-count.requests, **path));
        let top_paths: Vec<_> = ranks.into_iter().take(top).map(|(path, count)| json!({"path":path,"requests":count.requests,"bytes":count.bytes,"errors":count.errors})).collect();
        let statuses: Vec<_> = self
            .statuses
            .into_iter()
            .map(|(status, requests)| json!({"status":status,"requests":requests}))
            .collect();
        let methods: Vec<_> = self
            .methods
            .into_iter()
            .map(|(method, requests)| json!({"method":method,"requests":requests}))
            .collect();
        let hours: Vec<_> = self
            .hours
            .into_iter()
            .map(|(hour, requests)| json!({"hour":hour,"requests":requests}))
            .collect();
        json!({"requests":self.requests,"bytes":self.bytes,"client_errors":self.client_errors,"server_errors":self.server_errors,
            "unique_hosts":self.hosts.len(),"first":self.first,"last":self.last,"statuses":statuses,"methods":methods,"hours":hours,
            "path_count":self.paths.len(),"top_paths":top_paths})
    }
}
fn boundary(value: &Value) -> Result<Option<String>> {
    if value.is_null() {
        Ok(None)
    } else {
        Ok(Some(rt::datetime_iso(&rt::datetime_parse(string(value)?)?)))
    }
}
fn run() -> Result<i32> {
    let mode = std::env::var("ACCESS_MODE").unwrap_or_else(|_| "preview".into());
    require(mode == "preview" || mode == "write", "invalid mode")?;
    let config_path = absolute(
        &std::env::var("ACCESS_CONFIG").unwrap_or_else(|_| "access-job.json".into()),
        &std::env::current_dir()?,
    )?;
    let configuration = Document::read(config_path, 65536)?;
    let config = configuration.json()?;
    exact(&config, &["sources", "start", "end", "top", "output"])?;
    let start = boundary(&config["start"])?;
    let end = boundary(&config["end"])?;
    require(
        start
            .as_ref()
            .zip(end.as_ref())
            .map_or(true, |(a, b)| a <= b),
        "reversed window",
    )?;
    let top = integer(&config["top"])?;
    require((0..=100).contains(&top), "top outside 0..100")?;
    let base = configuration.path.parent().unwrap();
    let output = absolute(string(&config["output"])?, base)?;
    require(
        !output.try_exists()? && !output.is_symlink(),
        "output already exists",
    )?;
    let manifest = Document::read(absolute(string(&config["sources"])?, base)?, 65536)?;
    let sources = manifest.json()?;
    exact(&sources, &["version", "files"])?;
    require(integer(&sources["version"])? == 1, "unsupported version")?;
    let sources = sources["files"].as_array().ok_or("expected source array")?;
    require(sources.len() <= 8, "source count exceeds 8")?;
    let mut names = BTreeSet::new();
    let mut paths = BTreeSet::new();
    let mut documents = Vec::new();
    let mut input_bytes = 0;
    for source in sources {
        exact(source, &["name", "path"])?;
        let name = string(&source["name"])?;
        require(
            (1..=128).contains(&name.chars().count()) && name.len() <= 512 && !name.contains('\0'),
            "invalid source name",
        )?;
        require(names.insert(name), "duplicate source name")?;
        let path = absolute(string(&source["path"])?, manifest.path.parent().unwrap())?;
        require(paths.insert(path.clone()), "duplicate source path")?;
        let document = Document::read(path, 1048576)?;
        input_bytes += document.data.len();
        require(input_bytes <= 4194304, "combined logs exceed 4 MiB")?;
        documents.push(document);
    }
    let pattern = Regex::new(concat!(
        r#"\A([^ "]+) ([^ "]+) ([^ "]+) \[([0-9]{2})/([A-Za-z]{3})/([0-9]{4}):"#,
        r#"([0-9]{2}):([0-9]{2}):([0-9]{2}) ([+-][0-9]{4})\] "#,
        r#""([-!#$%&'*+.^_`|~0-9A-Za-z]+) ([^ "]+) (HTTP/[0-9]\.[0-9])" ([0-9]{3}) (-|[0-9]+)\z"#
    ))?;
    let mut files = BTreeMap::new();
    let mut hashes = BTreeMap::new();
    let mut exported = Vec::new();
    let mut summary = Summary::default();
    let mut valid_lines = Vec::new();
    let mut invalid_lines = Vec::new();
    let (mut count, mut valid, mut malformed, mut record_bytes) = (0, 0, 0, 0);
    for (index, (source, document)) in sources.iter().zip(&documents).enumerate() {
        let name = string(&source["name"])?;
        let filename = format!("source-{index}.log");
        files.insert(filename.clone(), document.data.clone());
        hashes.insert(name, digest(&document.data));
        exported.push(json!({"name":name,"path":filename}));
        // split_inclusive preserves a final bare CR, and omits an invented final empty line.
        for (line, framed) in document
            .data
            .split_inclusive(|&byte| byte == b'\n')
            .enumerate()
        {
            let raw = if let Some(row) = framed.strip_suffix(b"\n") {
                row.strip_suffix(b"\r").unwrap_or(row)
            } else {
                framed
            };
            require(raw.len() <= 8192, "log line exceeds 8192 bytes")?;
            count += 1;
            require(count <= 10000, "log line count exceeds 10000")?;
            match parse(raw, &pattern, name, line + 1) {
                Ok(mut record) => {
                    record.selected = start
                        .as_ref()
                        .map_or(true, |start| &record.timestamp >= start)
                        && end.as_ref().map_or(true, |end| &record.timestamp < end);
                    summary.add(&record)?;
                    let encoded = canonical(&serde_json::to_value(&record)?)?;
                    record_bytes += encoded.len();
                    valid_lines.extend(encoded);
                    valid += 1;
                }
                Err(reason) => {
                    let raw_hex: String = raw.iter().map(|byte| format!("{byte:02x}")).collect();
                    let encoded = canonical(
                        &json!({"source":name,"line":line+1,"reason":reason,"raw_hex":raw_hex}),
                    )?;
                    record_bytes += encoded.len();
                    invalid_lines.extend(encoded);
                    malformed += 1;
                }
            }
            require(record_bytes <= 16777216, "record exports exceed 16 MiB")?;
        }
    }
    let selected = summary.requests;
    let report = json!({"version":1,"window":{"start":start,"end":end},"top":top,"input_sha256":hashes,
        "counts":{"lines":count,"valid":valid,"malformed":malformed,"selected":selected,"filtered":valid-selected},"summary":summary.finish(top as usize)});
    files.insert(
        "sources.json".into(),
        canonical(&json!({"version":1,"files":exported}))?,
    );
    files.insert("report.json".into(), canonical(&report)?);
    files.insert("records.jsonl".into(), valid_lines);
    files.insert("invalid.jsonl".into(), invalid_lines);
    files.insert(
        "summary.txt".into(),
        format!("Access-log analysis\n{}\n", rt::pretty(&report)?).into_bytes(),
    );
    let mut checksums = BTreeMap::new();
    for (name, data) in &files {
        require(data.len() <= 33554432, "output exceeds 32 MiB")?;
        checksums.insert(
            name.clone(),
            json!({"bytes":data.len(),"sha256":digest(data)}),
        );
    }
    files.insert(
        "manifest.json".into(),
        format!("{}\n", rt::pretty(&json!({"version":1,"files":checksums}))?).into_bytes(),
    );
    documents.push(configuration);
    documents.push(manifest);
    for document in &documents {
        document.unchanged()?;
    }
    if mode == "write" {
        publish_exact(&output, files, &documents, "access")?;
    }
    println!("{}", rt::json_canonical_view(&report)?);
    Ok(if malformed == 0 { 0 } else { 1 })
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
