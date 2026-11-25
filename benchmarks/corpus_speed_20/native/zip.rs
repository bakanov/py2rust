//! Independent physical ZIP32 inspection; payloads are never extracted to disk.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::{
    borrow::Cow,
    collections::{BTreeMap, BTreeSet},
    path::Path,
};

fn number(data: &[u8], offset: usize, width: usize) -> Result<usize> {
    let bytes = data
        .get(offset..offset.checked_add(width).ok_or("truncated field")?)
        .ok_or("truncated field")?;
    Ok(bytes
        .iter()
        .enumerate()
        .map(|(shift, &byte)| usize::from(byte) << (shift * 8))
        .sum())
}
struct Limits {
    entries: usize,
    entry_bytes: usize,
    total_bytes: usize,
}
fn limits(value: &Value) -> Result<Limits> {
    exact(value, &["entries", "entry_bytes", "total_bytes"])?;
    let (entries, entry_bytes, total_bytes) = (
        integer(&value["entries"])?,
        integer(&value["entry_bytes"])?,
        integer(&value["total_bytes"])?,
    );
    require((0..=2048).contains(&entries), "entry count limit")?;
    require(
        (0..=16777216).contains(&entry_bytes),
        "entry expansion limit",
    )?;
    require(
        (0..=67108864).contains(&total_bytes),
        "total expansion limit",
    )?;
    Ok(Limits {
        entries: entries as usize,
        entry_bytes: entry_bytes as usize,
        total_bytes: total_bytes as usize,
    })
}
fn decode_name(
    raw: &[u8],
    flags: usize,
    extra: &[u8],
) -> Result<(String, String, Vec<&'static str>)> {
    let mut codes = Vec::new();
    let mut name = if flags & 2048 != 0 {
        match std::str::from_utf8(raw) {
            Ok(s) => s.to_owned(),
            Err(_) => {
                codes.push("name_encoding");
                String::new()
            }
        }
    } else {
        rt::decode_cp437(raw)
    };
    let mut cursor = 0;
    let mut tags = BTreeSet::new();
    while cursor < extra.len() {
        if extra.len() - cursor < 4 || tags.len() >= 256 {
            codes.push("extra_structure");
            break;
        }
        let tag = number(extra, cursor, 2)?;
        let size = number(extra, cursor + 2, 2)?;
        cursor += 4;
        if size > extra.len() - cursor {
            codes.push("extra_structure");
            break;
        }
        if !tags.insert(tag) {
            codes.push("duplicate_extra");
        }
        let value = &extra[cursor..cursor + size];
        cursor += size;
        if tag == 1 {
            codes.push("zip64");
        }
        if tag == 28789 {
            let decoded = (|| -> Result<String> {
                require(
                    size >= 5
                        && value[0] == 1
                        && number(value, 1, 4)? == rt::crc32(raw, 0) as usize,
                    "Unicode path extra",
                )?;
                let decoded = std::str::from_utf8(&value[5..])?;
                require(
                    flags & 2048 == 0 || decoded == name,
                    "conflicting Unicode path",
                )?;
                Ok(decoded.to_owned())
            })();
            match decoded {
                Ok(s) => name = s,
                Err(_) => codes.push("unicode_path_extra"),
            }
        }
    }
    let mut unsafe_path = name.is_empty()
        || name.starts_with('/')
        || name.contains('\\')
        || name.contains(':')
        || name.ends_with("//");
    for part in name.trim_end_matches('/').split('/') {
        if matches!(part, "" | "." | "..") || part.ends_with(' ') || part.ends_with('.') {
            unsafe_path = true;
        }
        let stem = part.split('.').next().unwrap_or("").to_uppercase();
        if matches!(stem.as_str(), "CON" | "PRN" | "AUX" | "NUL")
            || (stem.len() == 4
                && (stem.starts_with("COM") || stem.starts_with("LPT"))
                && (b'1'..=b'9').contains(&stem.as_bytes()[3]))
        {
            unsafe_path = true;
        }
    }
    for character in name.chars() {
        let value = character as u32;
        if value < 32
            || (127..=159).contains(&value)
            || [1564, 8206, 8207, 8232, 8233].contains(&value)
            || (8234..=8238).contains(&value)
            || (8294..=8297).contains(&value)
        {
            unsafe_path = true;
        }
    }
    if unsafe_path {
        codes.push("unsafe_name");
    }
    let key = rt::casefold(&rt::unicode_normalize("NFC", name.trim_end_matches('/'))?);
    Ok((name, key, codes))
}
struct Entry<'a> {
    offset: usize,
    flags: usize,
    method: usize,
    crc: usize,
    compressed: usize,
    expanded: usize,
    name: &'a [u8],
    extra: &'a [u8],
    version: usize,
    made: usize,
    attributes: usize,
    disk: usize,
}
fn ending(data: &[u8]) -> Result<(usize, usize, usize, Vec<&'static str>)> {
    require(data.len() >= 22, "end record missing")?;
    let mut position = None;
    for offset in (data.len().saturating_sub(65557)..=data.len() - 22).rev() {
        if &data[offset..offset + 4] == b"PK\x05\x06"
            && offset + 22 + number(data, offset + 20, 2)? == data.len()
        {
            position = Some(offset);
            break;
        }
    }
    let position = position.ok_or("end record missing")?;
    let count = number(data, position + 10, 2)?;
    let size = number(data, position + 12, 4)?;
    let start = number(data, position + 16, 4)?;
    let mut codes = Vec::new();
    if number(data, position + 4, 2)? != 0
        || number(data, position + 6, 2)? != 0
        || number(data, position + 8, 2)? != count
    {
        codes.push("multi_disk");
    }
    if count == 65535
        || size == 4294967295
        || start == 4294967295
        || (position >= 20 && &data[position - 20..position - 16] == b"PK\x06\x07")
    {
        codes.push("zip64");
    }
    if codes.is_empty() {
        require(
            start <= position && size == position - start,
            "central directory bounds",
        )?;
    }
    Ok((position, start, count, codes))
}
fn central(data: &[u8], cursor: usize, end: usize) -> Result<(Entry<'_>, usize)> {
    require(
        cursor + 46 <= end && data.get(cursor..cursor + 4) == Some(b"PK\x01\x02"),
        "central header",
    )?;
    let names = number(data, cursor + 28, 2)?;
    let extras = number(data, cursor + 30, 2)?;
    let stop = cursor + 46 + names + extras + number(data, cursor + 32, 2)?;
    require(stop <= end, "central variable fields")?;
    Ok((
        Entry {
            offset: number(data, cursor + 42, 4)?,
            flags: number(data, cursor + 8, 2)?,
            method: number(data, cursor + 10, 2)?,
            crc: number(data, cursor + 16, 4)?,
            compressed: number(data, cursor + 20, 4)?,
            expanded: number(data, cursor + 24, 4)?,
            name: &data[cursor + 46..cursor + 46 + names],
            extra: &data[cursor + 46 + names..cursor + 46 + names + extras],
            version: number(data, cursor + 6, 2)?,
            made: number(data, cursor + 4, 2)?,
            attributes: number(data, cursor + 38, 4)?,
            disk: number(data, cursor + 34, 2)?,
        },
        stop,
    ))
}
fn local<'a>(
    data: &'a [u8],
    entry: &Entry<'_>,
    end: usize,
) -> Result<(usize, usize, &'a [u8], Vec<&'static str>)> {
    let start = entry.offset;
    require(
        start + 30 <= end && data.get(start..start + 4) == Some(b"PK\x03\x04"),
        "local header",
    )?;
    let names = number(data, start + 26, 2)?;
    let extras = number(data, start + 28, 2)?;
    let payload = start + 30 + names + extras;
    let mut stop = payload + entry.compressed;
    require(stop <= end, "local data bounds")?;
    let mut codes = Vec::new();
    if &data[start + 30..start + 30 + names] != entry.name {
        codes.push("local_name");
    }
    if number(data, start + 4, 2)? != entry.version
        || number(data, start + 6, 2)? != entry.flags
        || number(data, start + 8, 2)? != entry.method
    {
        codes.push("local_fields");
    }
    let actual = [
        number(data, start + 14, 4)?,
        number(data, start + 18, 4)?,
        number(data, start + 22, 4)?,
    ];
    let expected = [entry.crc, entry.compressed, entry.expanded];
    if entry.flags & 8 != 0 {
        if actual != [0, 0, 0] && actual != expected {
            codes.push("local_sizes");
        }
        require(stop + 12 <= end, "data descriptor bounds")?;
        let signed = &data[stop..stop + 4] == b"PK\x07\x08"
            && [
                number(data, stop, 4)?,
                number(data, stop + 4, 4)?,
                number(data, stop + 8, 4)?,
            ] != expected;
        let descriptor = stop + if signed { 4 } else { 0 };
        require(descriptor + 12 <= end, "data descriptor bounds")?;
        if [
            number(data, descriptor, 4)?,
            number(data, descriptor + 4, 4)?,
            number(data, descriptor + 8, 4)?,
        ] != expected
        {
            codes.push("descriptor");
        }
        stop = descriptor + 12;
    } else if actual != expected {
        codes.push("local_sizes");
    }
    Ok((payload, stop, &data[start + 30 + names..payload], codes))
}
fn inspect(data: &[u8], settings: &Limits) -> Value {
    let mut entries = Vec::new();
    let mut errors = Vec::new();
    let mut seen = BTreeSet::new();
    let mut spans: Vec<(usize, usize)> = Vec::new();
    let (mut budget, mut checked, mut verified, mut declared, mut cursor) =
        (0usize, 0usize, 0usize, 0usize, 0usize);
    let result = (|| -> Result<()> {
        let (end, directory, count, codes) = ending(data)?;
        declared = count;
        for code in codes {
            errors.push(json!({"entry":-1,"offset":end,"code":code}));
        }
        if declared > settings.entries {
            errors.push(json!({"entry":-1,"offset":end,"code":"entry_limit"}));
        }
        cursor = directory;
        if errors.is_empty() {
            for index in 0..declared {
                let (entry, next) = central(data, cursor, end)?;
                let origin = cursor;
                cursor = next;
                let (name, key, mut codes) = decode_name(entry.name, entry.flags, entry.extra)?;
                if !seen.insert(key.clone()) {
                    codes.push("duplicate_name");
                }
                let mode = (entry.attributes >> 16) & 61440;
                if entry.made >> 8 == 3 && ![0, 16384, 32768].contains(&mode) {
                    codes.push("unsafe_type");
                }
                let mut unsupported = false;
                let reserved = if entry.method == 0 { 63478 } else { 63472 };
                if entry.version > 20
                    || ![0, 8].contains(&entry.method)
                    || entry.disk != 0
                    || entry.flags & reserved != 0
                {
                    codes.push("unsupported_entry");
                    unsupported = true;
                }
                if entry.flags & 1 != 0 {
                    codes.push("encrypted");
                    unsupported = true;
                }
                if [entry.compressed, entry.expanded, entry.offset].contains(&4294967295)
                    || codes.contains(&"zip64")
                {
                    codes.push("zip64_entry");
                    unsupported = true;
                }
                let (mut size, mut actual_crc) = (-1i64, -1i64);
                let mut payload_hash = String::new();
                let mut stop = entry.offset;
                let located = (|| -> Result<()> {
                    let (payload, end, extra, local_codes) = local(data, &entry, directory)?;
                    stop = end;
                    codes.extend(local_codes);
                    codes.extend(decode_name(entry.name, entry.flags, extra)?.2);
                    let overlap = spans
                        .iter()
                        .any(|&(start, end)| entry.offset < end && start < stop);
                    if overlap {
                        codes.push("overlap");
                    } else {
                        spans.push((entry.offset, stop));
                    }
                    let compressed = if overlap {
                        &[][..]
                    } else {
                        &data[payload..payload + entry.compressed]
                    };
                    let allowance = settings.entry_bytes.min(settings.total_bytes - budget);
                    if entry.expanded > allowance {
                        codes.push("expanded_limit");
                    } else if !unsupported && !overlap && !codes.contains(&"zip64") {
                        let decoded = (|| -> Result<Cow<'_, [u8]>> {
                            let output = if entry.method == 8 {
                                Cow::Owned(rt::deflate_decompress(compressed, allowance as i64)?)
                            } else {
                                Cow::Borrowed(compressed)
                            };
                            require(output.len() <= allowance, "stored expansion limit")?;
                            Ok(output)
                        })();
                        match decoded {
                            Ok(decoded) => {
                                size = decoded.len() as i64;
                                budget += decoded.len();
                                checked += decoded.len();
                                actual_crc = rt::crc32(&decoded, 0);
                                payload_hash = digest(&decoded);
                                if decoded.len() != entry.expanded {
                                    codes.push("expanded_size");
                                }
                                if actual_crc as usize != entry.crc {
                                    codes.push("crc");
                                }
                                if (name.ends_with('/')
                                    || mode == 16384
                                    || entry.attributes & 16 != 0)
                                    && !decoded.is_empty()
                                {
                                    codes.push("directory_payload");
                                }
                                if decoded.len() == entry.expanded
                                    && actual_crc as usize == entry.crc
                                {
                                    verified += 1;
                                }
                            }
                            Err(_) => {
                                budget += allowance;
                                codes.push("decompression");
                            }
                        }
                    }
                    Ok(())
                })();
                if located.is_err() {
                    codes.push("local_structure");
                }
                codes.sort_unstable();
                codes.dedup();
                for code in &codes {
                    errors.push(json!({"entry":index,"offset":origin,"code":code}));
                }
                entries.push(json!({"index":index,"name":name,"key":key,"name_hex":rt::bytes_hex(entry.name),
                    "central_offset":origin,"local_offset":entry.offset,"end_offset":stop,"flags":entry.flags,
                    "method":entry.method,"compressed":entry.compressed,"expanded":entry.expanded,"crc":entry.crc,
                    "checked_bytes":size,"computed_crc":actual_crc,"sha256":payload_hash,"codes":codes}));
            }
            if cursor != end {
                errors.push(json!({"entry":-1,"offset":cursor,"code":"central_trailing"}));
            }
            spans.sort_unstable();
            let mut covered = 0;
            for (start, end) in &spans {
                if *start != covered {
                    errors
                        .push(json!({"entry":-1,"offset":covered,"code":"unclaimed_local_bytes"}));
                }
                covered = *end;
            }
            if covered != directory {
                errors.push(json!({"entry":-1,"offset":covered,"code":"unclaimed_local_bytes"}));
            }
        }
        Ok(())
    })();
    if result.is_err() {
        errors.push(json!({"entry":-1,"offset":cursor,"code":"archive_structure"}));
    }
    json!({"summary":{"bytes":data.len(),"declared_entries":declared,"entries":entries.len(),"verified_payloads":verified,
        "checked_bytes":checked,"budget_used":budget,"errors":errors.len()},"entries":entries,"errors":errors})
}
fn run() -> Result<i32> {
    let request = Document::read(
        absolute(
            &std::env::var("ZIP_CONFIG").unwrap_or("zip-job.json".into()),
            Path::new("."),
        )?,
        65536,
    )?;
    let config = request.json()?;
    let mode = string(&config["mode"])?;
    require(
        integer(&config["version"])? == 1 && matches!(mode, "inspect" | "verify"),
        "request version or mode",
    )?;
    exact(
        &config,
        if mode == "inspect" {
            &["version", "mode", "input", "output", "limits"]
        } else {
            &["version", "mode", "input", "output"]
        },
    )?;
    let base = request.path.parent().ok_or("missing parent")?;
    let output = absolute(string(&config["output"])?, base)?;
    require(
        !output.exists() && !output.is_symlink(),
        "output already exists",
    )?;
    let document = Document::read(
        absolute(string(&config["input"])?, base)?,
        if mode == "verify" { 67108864 } else { 16777216 },
    )?;
    let archive = if mode == "verify" {
        document.json()?
    } else {
        Value::Null
    };
    let decoded;
    let source = if mode == "verify" {
        exact(&archive, &["version", "source_hex", "limits", "results"])?;
        require(integer(&archive["version"])? == 1, "archive version")?;
        let spelling = string(&archive["source_hex"])?;
        require(spelling.chars().count() <= 33554432, "source byte limit")?;
        decoded = rt::bytes_from_hex(spelling)?;
        require(
            rt::bytes_hex(&decoded) == spelling,
            "expected canonical lowercase hex",
        )?;
        decoded.as_slice()
    } else {
        document.data.as_slice()
    };
    let settings = if mode == "verify" {
        &archive["limits"]
    } else {
        &config["limits"]
    };
    let results = inspect(source, &limits(settings)?);
    if mode == "verify" {
        require(
            canonical(&archive["results"])? == canonical(&results)?,
            "archive findings differ from recomputed inspection",
        )?;
    }
    let archive = canonical(
        &json!({"version":1,"source_hex":rt::bytes_hex(source),"limits":settings,"results":results}),
    )?;
    let mut files = BTreeMap::new();
    files.insert("source.zip".into(), source.to_vec());
    files.insert("entries.json".into(), canonical(&results["entries"])?);
    files.insert(
        "report.json".into(),
        canonical(
            &json!({"version":1,"mode":mode,"results":results,"archive_sha256":digest(&archive)}),
        )?,
    );
    files.insert("archive.json".into(), archive);
    files.insert(
        "report.txt".into(),
        (rt::pretty_view(&results)? + "\n").into_bytes(),
    );
    files.insert("inspect.json".into(),canonical(&json!({"version":1,"mode":"inspect","input":"source.zip","output":"inspected","limits":settings}))?);
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
    publish(&output, files, &[request, document], "zip")?;
    println!("{}", rt::json_canonical_view(&results["summary"])?);
    Ok(if integer(&results["summary"]["errors"])? > 0 {
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
