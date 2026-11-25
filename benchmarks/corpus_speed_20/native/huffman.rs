//! Deterministic canonical Huffman compression, complete write/preview job.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::{
    cmp::Reverse,
    collections::{BTreeMap, BinaryHeap},
};
type Codes = [(u64, u32); 256];
fn frequencies(data: &[u8]) -> [usize; 256] {
    let mut counts = [0; 256];
    for &symbol in data {
        counts[symbol as usize] += 1;
    }
    counts
}
fn lengths(data: &[u8]) -> [u32; 256] {
    let counts = frequencies(data);
    let mut heap = BinaryHeap::new();
    let mut nodes = Vec::new();
    for (symbol, count) in counts.into_iter().enumerate() {
        if count > 0 {
            heap.push(Reverse((count, symbol, nodes.len())));
            nodes.push((Some(symbol), 0, 0));
        }
    }
    while heap.len() > 1 {
        let Reverse(a) = heap.pop().unwrap();
        let Reverse(b) = heap.pop().unwrap();
        heap.push(Reverse((a.0 + b.0, a.1.min(b.1), nodes.len())));
        nodes.push((None, a.2, b.2));
    }
    let mut result = [0; 256];
    if let Some(Reverse((_, _, root))) = heap.pop() {
        let mut pending = vec![(root, 0)];
        while let Some((node, depth)) = pending.pop() {
            if let Some(symbol) = nodes[node].0 {
                result[symbol] = depth.max(1);
            } else {
                pending.push((nodes[node].1, depth + 1));
                pending.push((nodes[node].2, depth + 1));
            }
        }
    }
    result
}
fn codes(widths: &[u32; 256]) -> Result<Codes> {
    let mut ordered: Vec<_> = widths
        .iter()
        .enumerate()
        .filter(|(_, width)| **width > 0)
        .map(|(symbol, width)| (*width, symbol))
        .collect();
    ordered.sort_unstable();
    let (mut code, mut previous) = (0u64, 0);
    let mut result = [(0, 0); 256];
    for &(width, symbol) in &ordered {
        require((1..=32).contains(&width), "invalid codebook entry")?;
        code <<= width - previous;
        require(code < (1u64 << width), "oversubscribed codebook")?;
        result[symbol] = (code, width);
        code += 1;
        previous = width;
    }
    if ordered.len() == 1 {
        require(previous == 1, "single-symbol code must have length one")?;
    } else if ordered.len() > 1 {
        require(code == (1u64 << previous), "incomplete codebook")?;
    }
    Ok(result)
}
fn hash_bytes(data: &[u8]) -> Vec<u8> {
    let hash = digest(data);
    (0..hash.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hash[i..i + 2], 16).unwrap())
        .collect()
}
fn encode(data: &[u8]) -> Result<Vec<u8>> {
    require(data.len() <= 1048576, "original data exceeds 1 MiB")?;
    let codes = codes(&lengths(data))?;
    let mut payload = Vec::new();
    let (mut accumulator, mut held, mut total) = (0u64, 0u32, 0u32);
    for &symbol in data {
        let (code, width) = codes[symbol as usize];
        accumulator = (accumulator << width) | code;
        held += width;
        total += width;
        while held >= 8 {
            held -= 8;
            payload.push(((accumulator >> held) & 255) as u8);
        }
        accumulator &= (1u64 << held) - 1;
    }
    if held > 0 {
        payload.push((accumulator << (8 - held)) as u8);
    }
    let count = codes.iter().filter(|(_, w)| *w > 0).count();
    let mut output = b"PYHF068!".to_vec();
    output.extend_from_slice(&(data.len() as u32).to_be_bytes());
    output.extend_from_slice(&total.to_be_bytes());
    output.extend_from_slice(&(count as u16).to_be_bytes());
    output.extend(hash_bytes(data));
    for (symbol, &(_, width)) in codes.iter().enumerate() {
        if width > 0 {
            output.push(symbol as u8);
            output.push(width as u8);
        }
    }
    output.extend(payload);
    let hash = hash_bytes(&output);
    output.extend(hash);
    Ok(output)
}
struct Block<'a> {
    bits: usize,
    codes: Codes,
    payload: &'a [u8],
}
fn parse(raw: &[u8]) -> Result<Block<'_>> {
    require(
        (82..=4194898).contains(&raw.len()),
        "invalid container size",
    )?;
    require(&raw[..8] == b"PYHF068!", "invalid container magic")?;
    let original = u32::from_be_bytes(raw[8..12].try_into()?) as usize;
    let bits = u32::from_be_bytes(raw[12..16].try_into()?) as usize;
    let count = u16::from_be_bytes(raw[16..18].try_into()?) as usize;
    require(original <= 1048576, "declared output exceeds 1 MiB")?;
    require(count <= 256 && count <= original, "invalid symbol count")?;
    require(
        original <= bits && bits <= original * 32,
        "invalid payload bit count",
    )?;
    let offset = 50 + 2 * count;
    require(
        raw.len() == offset + (bits + 7) / 8 + 32,
        "container length mismatch",
    )?;
    require(
        hash_bytes(&raw[..raw.len() - 32]) == raw[raw.len() - 32..],
        "container checksum mismatch",
    )?;
    let mut widths = [0; 256];
    let mut previous = None;
    for row in raw[50..offset].chunks_exact(2) {
        let symbol = row[0] as usize;
        require(
            previous.is_none_or(|p| symbol > p),
            "codebook symbols must be strictly increasing",
        )?;
        previous = Some(symbol);
        require(row[1] > 0, "invalid codebook entry")?;
        widths[symbol] = row[1] as u32;
    }
    let codes = codes(&widths)?;
    require(
        (original == 0 && count == 0) || (original > 0 && count > 0),
        "missing codebook",
    )?;
    let payload = &raw[offset..raw.len() - 32];
    if bits % 8 != 0 {
        require(
            (payload[payload.len() - 1] & ((1 << (8 - bits % 8)) - 1)) == 0,
            "nonzero padding bits",
        )?;
    }
    Ok(Block {
        bits,
        codes,
        payload,
    })
}
fn statistics(original: &[u8], container: &[u8], block: &Block) -> Value {
    let counts = frequencies(original);
    let mut rows = Vec::new();
    let mut maximum = 0;
    for (symbol, &(code, width)) in block.codes.iter().enumerate() {
        if width > 0 {
            maximum = maximum.max(width);
            rows.push(json!({"symbol":symbol,"frequency":counts[symbol],"length":width,"bits":format!("{code:0width$b}",width=width as usize)}));
        }
    }
    json!({"version":1,"operation":"compress","original_bytes":original.len(),"container_bytes":container.len(),"payload_bits":block.bits,"payload_bytes":block.payload.len(),"padding_bits":block.payload.len()*8-block.bits,"overhead_bytes":82+2*rows.len(),"saved_bytes":original.len()as i64-container.len()as i64,"container_ratio_ppm":if original.is_empty(){None}else{Some(container.len()*1000000/original.len())},"original_sha256":digest(original),"container_sha256":digest(container),"symbols":rows.len(),"maximum_code_length":maximum,"codebook":rows})
}
fn run() -> Result<()> {
    let mode = std::env::var("HUFFMAN_MODE").unwrap_or("preview".into());
    require(mode == "preview" || mode == "write", "invalid Huffman mode")?;
    let config = Document::read(
        absolute(
            &std::env::var("HUFFMAN_CONFIG").unwrap_or("huffman-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let value = rt::json_loads(std::str::from_utf8(&config.data)?)?;
    exact(&value, &["input", "operation", "output"])?;
    require(
        value["operation"] == "compress",
        "baseline supports compression jobs",
    )?;
    let base = config.path.parent().unwrap();
    let output = absolute(string(&value["output"])?, base)?;
    require(
        std::fs::symlink_metadata(&output).is_err(),
        "output directory already exists",
    )?;
    let source = Document::read(absolute(string(&value["input"])?, base)?, 1048576)?;
    let container = encode(&source.data)?;
    let block = parse(&container)?;
    let report = statistics(&source.data, &container, &block);
    let mut files = BTreeMap::from([
        ("archive.phf".into(), container),
        ("report.json".into(), canonical(&report)?),
        (
            "codebook.json".into(),
            (rt::pretty_view(&report["codebook"])? + "\n").into_bytes(),
        ),
    ]);
    let checksums: BTreeMap<_, _> = files
        .iter()
        .map(|(name, data)| (name, json!({"bytes":data.len(),"sha256":digest(data)})))
        .collect();
    files.insert(
        "manifest.json".into(),
        (rt::pretty_view(&json!({"version":1,"files":checksums}))? + "\n").into_bytes(),
    );
    if mode == "write" {
        publish_exact(&output, files, &[config, source], "huffman")?;
    }
    println!("{}", rt::json_canonical_view(&report)?);
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
