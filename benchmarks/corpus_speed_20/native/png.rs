//! Handwritten bounded PNG chunk inspection; compressed contents stay uninspected.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

fn unsigned(data: &[u8]) -> u32 {
    data.iter()
        .fold(0, |value, byte| value * 256 + u32::from(*byte))
}
fn latin1(data: &[u8]) -> String {
    data.iter().map(|&byte| char::from(byte)).collect()
}
fn utf8(data: &[u8]) -> Result<&str> {
    std::str::from_utf8(data).map_err(|_| "invalid UTF-8 metadata".into())
}
fn keyword(data: &[u8]) -> Result<String> {
    require((1..=79).contains(&data.len()), "keyword length")?;
    require(
        data[0] != 32 && data[data.len() - 1] != 32 && !data.windows(2).any(|pair| pair == b"  "),
        "keyword spacing",
    )?;
    require(
        data.iter().all(|b| (32..=126).contains(b) || *b >= 161),
        "keyword character",
    )?;
    Ok(latin1(data))
}
fn describe(name: &str, data: &[u8], header: &Value, palette: usize) -> Result<Value> {
    match name {
        "IHDR" => {
            require(data.len() == 13, "IHDR length")?;
            let (width, height, depth, color) = (
                unsigned(&data[..4]),
                unsigned(&data[4..8]),
                data[8],
                data[9],
            );
            require(
                (1..=2147483647).contains(&width) && (1..=2147483647).contains(&height),
                "image dimensions",
            )?;
            let allowed: &[u8] = match color {
                0 => &[1, 2, 4, 8, 16],
                2 | 4 | 6 => &[8, 16],
                3 => &[1, 2, 4, 8],
                _ => &[],
            };
            require(allowed.contains(&depth), "color and bit depth combination")?;
            require(
                data[10] == 0 && data[11] == 0 && data[12] <= 1,
                "header methods",
            )?;
            Ok(
                json!({"width":width,"height":height,"bit_depth":depth,"color_type":color,"compression":data[10],"filter":data[11],"interlace":data[12]}),
            )
        }
        "PLTE" => {
            require(
                (3..=768).contains(&data.len()) && data.len() % 3 == 0,
                "palette length",
            )?;
            let entries = data.len() / 3;
            if header.is_object() {
                let color = integer(&header["color_type"])?;
                require(color != 0 && color != 4, "palette forbidden for grayscale")?;
                require(
                    color != 3 || entries <= 1 << integer(&header["bit_depth"])?,
                    "palette exceeds bit depth",
                )?;
            }
            Ok(json!({"entries":entries}))
        }
        "IEND" => {
            require(data.is_empty(), "IEND length")?;
            Ok(json!({}))
        }
        "tRNS" => {
            require(header.is_object(), "header unavailable for transparency")?;
            let color = integer(&header["color_type"])?;
            require(
                [0, 2, 3].contains(&color),
                "transparency forbidden with alpha",
            )?;
            if color == 3 {
                require(
                    !data.is_empty() && data.len() <= palette,
                    "palette transparency length",
                )?;
                return Ok(json!({"alpha":data}));
            }
            require(
                data.len() == if color == 0 { 2 } else { 6 },
                "transparent sample length",
            )?;
            Ok(json!({"samples":data.chunks_exact(2).map(unsigned).collect::<Vec<_>>()}))
        }
        "gAMA" => {
            require(
                data.len() == 4 && (1..=2147483647).contains(&unsigned(data)),
                "gamma value",
            )?;
            Ok(json!({"gamma_times_100000":unsigned(data)}))
        }
        "sRGB" => {
            require(data.len() == 1 && data[0] <= 3, "rendering intent")?;
            Ok(json!({"intent":data[0]}))
        }
        "pHYs" => {
            require(data.len() == 9 && data[8] <= 1, "physical dimensions")?;
            let (x, y) = (unsigned(&data[..4]), unsigned(&data[4..8]));
            require(x <= 2147483647 && y <= 2147483647, "physical density range")?;
            Ok(json!({"x":x,"y":y,"unit":data[8]}))
        }
        "tIME" => {
            require(data.len() == 7, "timestamp length")?;
            let year = unsigned(&data[..2]);
            let (month, day) = (data[2], data[3]);
            let days = [
                31,
                if year % 400 == 0 || (year % 4 == 0 && year % 100 != 0) {
                    29
                } else {
                    28
                },
                31,
                30,
                31,
                30,
                31,
                31,
                30,
                31,
                30,
                31,
            ];
            require(
                (1..=12).contains(&month) && day >= 1 && day <= days[month as usize - 1],
                "calendar date",
            )?;
            require(
                data[4] <= 23 && data[5] <= 59 && data[6] <= 60,
                "timestamp clock",
            )?;
            Ok(
                json!({"year":year,"month":month,"day":day,"hour":data[4],"minute":data[5],"second":data[6]}),
            )
        }
        "tEXt" | "zTXt" | "iTXt" | "iCCP" => {
            let separator = data
                .iter()
                .position(|&b| b == 0)
                .ok_or("missing keyword separator")?;
            let key = keyword(&data[..separator])?;
            let tail = &data[separator + 1..];
            if name == "tEXt" {
                require(!tail.contains(&0), "null in text")?;
                return Ok(json!({"keyword":key,"text":latin1(tail)}));
            }
            if name == "zTXt" || name == "iCCP" {
                require(!tail.is_empty() && tail[0] == 0, "compression method")?;
                return Ok(json!({"keyword":key,"compressed_bytes":tail.len()-1,"decoded":false}));
            }
            require(tail.len() >= 2 && tail[0] <= 1, "international text flags")?;
            let compressed = tail[0] == 1;
            require(!compressed || tail[1] == 0, "compression method")?;
            let end = tail[2..]
                .iter()
                .position(|&b| b == 0)
                .ok_or("missing language separator")?
                + 2;
            let language = &tail[2..end];
            require(language.is_ascii(), "non-ASCII language tag")?;
            let rest = &tail[end + 1..];
            let end = rest
                .iter()
                .position(|&b| b == 0)
                .ok_or("missing translated keyword separator")?;
            let translated = utf8(&rest[..end])?;
            let body = &rest[end + 1..];
            if compressed {
                return Ok(
                    json!({"keyword":key,"language":utf8(language)?,"translated":translated,"compressed_bytes":body.len(),"decoded":false}),
                );
            }
            require(!body.contains(&0), "null in international text")?;
            Ok(
                json!({"keyword":key,"language":utf8(language)?,"translated":translated,"text":utf8(body)?}),
            )
        }
        _ => Ok(json!({"decoded":false})),
    }
}
fn finding(offset: usize, code: &str, detail: &str) -> Value {
    json!({"offset":offset,"code":code,"detail":detail})
}
fn inspect(data: &[u8]) -> Result<Value> {
    let mut chunks = Vec::new();
    let mut errors = Vec::new();
    let mut unchecked = vec![
        "image_data_decompression".to_owned(),
        "pixel_values".to_owned(),
    ];
    let mut header = Value::Null;
    let mut seen = BTreeSet::new();
    let (mut palette, mut idat_bytes, mut metadata_bytes, mut crc_errors) = (0, 0, 0, 0);
    let mut idat_ended = false;
    let mut cursor = 8;
    if !data.starts_with(b"\x89PNG\r\n\x1a\n") {
        errors.push(finding(0, "signature", "invalid PNG signature"));
        cursor = 0;
    } else {
        while cursor < data.len() {
            require(chunks.len() < 4096, "chunk count limit")?;
            if data.len() - cursor < 8 {
                errors.push(finding(
                    cursor,
                    "truncated_header",
                    "incomplete length and type",
                ));
                break;
            }
            let size = unsigned(&data[cursor..cursor + 4]) as usize;
            if size > 2147483647 || size + 12 > data.len() - cursor {
                errors.push(finding(
                    cursor,
                    "chunk_length",
                    "invalid or truncated chunk length",
                ));
                break;
            }
            let raw_type = &data[cursor + 4..cursor + 8];
            let valid = raw_type.iter().all(u8::is_ascii_alphabetic);
            let name = if valid {
                std::str::from_utf8(raw_type).unwrap()
            } else {
                "?"
            };
            let payload = &data[cursor + 8..cursor + 8 + size];
            let stored = unsigned(&data[cursor + 8 + size..cursor + 12 + size]) as i64;
            let computed = rt::crc32(payload, rt::crc32(raw_type, 0));
            let mut codes = Vec::new();
            if !valid || raw_type[2] & 32 != 0 {
                codes.push("chunk_type");
            }
            if stored != computed {
                codes.push("crc");
                crc_errors += 1;
            }
            if chunks.is_empty() && name != "IHDR" {
                codes.push("header_first");
            }
            const SINGLE: &[&str] = &[
                "IHDR", "PLTE", "IEND", "tRNS", "gAMA", "sRGB", "pHYs", "iCCP", "cHRM", "sBIT",
                "bKGD", "hIST", "eXIf", "tIME", "acTL", "cICP", "mDCV", "cLLI",
            ];
            if SINGLE.contains(&name) && seen.contains(name) {
                codes.push("duplicate_chunk");
            }
            const BEFORE_PALETTE: &[&str] = &[
                "gAMA", "sRGB", "iCCP", "cHRM", "sBIT", "cICP", "mDCV", "cLLI",
            ];
            const BEFORE_DATA: &[&str] = &[
                "PLTE", "tRNS", "pHYs", "bKGD", "hIST", "sPLT", "eXIf", "acTL",
            ];
            if (BEFORE_PALETTE.contains(&name) && seen.contains("PLTE"))
                || ((BEFORE_PALETTE.contains(&name) || BEFORE_DATA.contains(&name))
                    && seen.contains("IDAT"))
            {
                codes.push("chunk_order");
            }
            if name == "PLTE" && ["tRNS", "bKGD", "hIST"].iter().any(|n| seen.contains(n)) {
                codes.push("palette_order");
            }
            if name == "IDAT" {
                if idat_ended {
                    codes.push("nonconsecutive_idat");
                }
                if header.is_object() && integer(&header["color_type"])? == 3 && palette == 0 {
                    codes.push("missing_palette");
                }
                idat_bytes += size;
            } else if seen.contains("IDAT") {
                idat_ended = true;
            }
            if valid && raw_type[0] & 32 == 0 && !["IHDR", "PLTE", "IDAT", "IEND"].contains(&name) {
                codes.push("unknown_critical");
            }
            let mut metadata = json!({});
            let decoded = [
                "IHDR", "PLTE", "IEND", "tRNS", "gAMA", "sRGB", "pHYs", "tIME", "tEXt", "zTXt",
                "iTXt", "iCCP",
            ]
            .contains(&name);
            if decoded
                && (["IHDR", "PLTE", "IEND"].contains(&name) || metadata_bytes + size <= 65536)
            {
                metadata_bytes += size;
                match describe(name, payload, &header, palette) {
                    Ok(value) => {
                        metadata = value;
                        if name == "IHDR" && !seen.contains("IHDR") {
                            header = metadata.clone();
                        }
                        if name == "PLTE" {
                            palette = integer(&metadata["entries"])? as usize;
                        }
                    }
                    Err(error) => errors.push(finding(cursor, "metadata", &error.to_string())),
                }
            } else if name != "IDAT" {
                metadata = json!({"decoded":false});
            }
            if name != "IDAT"
                && (!decoded || metadata.get("decoded").is_some())
                && !unchecked.iter().any(|n| n == name)
            {
                unchecked.push(name.to_owned());
            }
            for code in codes {
                errors.push(finding(cursor, code, name));
            }
            chunks.push(json!({"index":chunks.len(),"offset":cursor,"length":size,"type":name,"type_hex":rt::bytes_hex(raw_type),"type_valid":valid,
                "critical":raw_type[0]&32 == 0,"private":raw_type[1]&32 != 0,"safe_to_copy":raw_type[3]&32 != 0,
                "crc_stored":stored,"crc_computed":computed,"crc_ok":stored == computed,"data_sha256":digest(payload),"metadata":metadata}));
            seen.insert(name);
            cursor += size + 12;
            if name == "IEND" {
                break;
            }
        }
        if ["IHDR", "IDAT", "IEND"].iter().any(|n| !seen.contains(n)) {
            errors.push(finding(
                cursor,
                "missing_required_chunk",
                "IHDR, IDAT and IEND required",
            ));
        }
        if seen.contains("IDAT") && idat_bytes == 0 {
            errors.push(finding(
                cursor,
                "empty_image_data",
                "no compressed image bytes",
            ));
        }
        if seen.contains("IEND") && cursor != data.len() {
            errors.push(finding(cursor, "trailing_data", "bytes after IEND"));
        }
    }
    let summary = json!({"bytes":data.len(),"chunks":chunks.len(),"errors":errors.len(),"crc_errors":crc_errors,"idat_bytes":idat_bytes,"scanned_bytes":cursor,"unscanned_bytes":data.len()-cursor});
    Ok(Value::Object(
        [
            ("header".into(), header),
            ("chunks".into(), Value::Array(chunks)),
            ("errors".into(), Value::Array(errors)),
            ("unchecked".into(), json!(unchecked)),
            ("summary".into(), summary),
        ]
        .into_iter()
        .collect(),
    ))
}
fn escaped(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}
fn html(results: &Value) -> Result<Vec<u8>> {
    let mut rows = vec![
        "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>PNG structure report</title>".to_owned(),
        "<style>body{font:15px system-ui;margin:40px;color:#233047;background:#f8fafc}table{border-collapse:collapse;width:100%}td,th{padding:8px;border:1px solid #ccd5df;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}h1{color:#17578e}</style>".into(),
        "<h1>PNG structure report</h1><p>Structural inspection only. Image data and compressed metadata are not decompressed.</p>".into(),
    ];
    for (heading, key) in [
        ("Summary", "summary"),
        ("Image header", "header"),
        ("Findings", "errors"),
        ("Uninspected content", "unchecked"),
    ] {
        rows.push(format!(
            "<h2>{heading}</h2><pre>{}</pre>",
            escaped(&rt::pretty_view(&results[key])?)
        ));
    }
    rows.push("<h2>Chunks</h2><table><tr><th>Index</th><th>Offset</th><th>Type</th><th>Bytes</th><th>CRC</th><th>Metadata</th></tr>".into());
    for chunk in results["chunks"].as_array().ok_or("expected chunks")? {
        let mut line = String::from("<tr>");
        for key in ["index", "offset", "type", "length", "crc_ok"] {
            line.push_str(&format!(
                "<td>{}</td>",
                escaped(&rt::json_canonical_view(&chunk[key])?)
            ));
        }
        line.push_str(&format!(
            "<td><details><summary>Inspect</summary><pre>{}</pre></details></td></tr>",
            escaped(&rt::pretty_view(chunk)?)
        ));
        rows.push(line);
    }
    rows.push("</table></html>".into());
    Ok((rows.join("\n") + "\n").into_bytes())
}
fn run() -> Result<i32> {
    let request = Document::read(
        absolute(
            &std::env::var("PNG_CONFIG").unwrap_or_else(|_| "png-job.json".into()),
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
    require(["inspect", "verify"].contains(&mode), "unknown mode")?;
    let base = request.path.parent().unwrap();
    let output = absolute(string(&config["output"])?, base)?;
    require(
        !output.exists() && !output.is_symlink(),
        "output already exists",
    )?;
    let document = Document::read(
        absolute(string(&config["input"])?, base)?,
        if mode == "verify" { 67108864 } else { 16777216 },
    )?;
    let imported;
    let decoded;
    let source = if mode == "verify" {
        imported = document.json()?;
        exact(&imported, &["version", "source_hex", "results"])?;
        require(
            integer(&imported["version"])? == 1,
            "unsupported archive version",
        )?;
        let spelling = string(&imported["source_hex"])?;
        require(spelling.chars().count() <= 33554432, "source byte limit")?;
        decoded = rt::bytes_from_hex(spelling)?;
        require(
            rt::bytes_hex(&decoded) == spelling,
            "expected canonical lowercase hex",
        )?;
        decoded.as_slice()
    } else {
        imported = Value::Null;
        document.data.as_slice()
    };
    let results = inspect(source)?;
    if mode == "verify" {
        require(
            canonical(&imported["results"])? == canonical(&results)?,
            "archive findings differ from recomputed inspection",
        )?;
    }
    let summary = results["summary"].clone();
    let status = i32::from(integer(&summary["errors"])? > 0);
    let archive = Value::Object(
        [
            ("version".into(), json!(1)),
            ("source_hex".into(), json!(rt::bytes_hex(source))),
            ("results".into(), results),
        ]
        .into_iter()
        .collect(),
    );
    let results = &archive["results"];
    let encoded_archive = canonical(&archive)?;
    let mut files = BTreeMap::new();
    files.insert("image.png".into(), source.to_vec());
    files.insert("chunks.json".into(), canonical(&results["chunks"])?);
    files.insert("report.json".into(),canonical(&json!({"version":1,"mode":mode,"results":results,"archive_sha256":digest(&encoded_archive)}))?);
    files.insert("report.html".into(), html(results)?);
    files.insert("archive.json".into(), encoded_archive);
    files.insert(
        "inspect.json".into(),
        canonical(&json!({"version":1,"mode":"inspect","input":"image.png","output":"inspected"}))?,
    );
    files.insert(
        "replay.json".into(),
        canonical(
            &json!({"version":1,"mode":"verify","input":"archive.json","output":"replayed"}),
        )?,
    );
    require(
        files.values().all(|data| data.len() <= 67108864),
        "export byte limit",
    )?;
    publish(&output, files, &[request, document], "png")?;
    println!("{}", rt::json_canonical_view(&summary)?);
    Ok(status)
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
