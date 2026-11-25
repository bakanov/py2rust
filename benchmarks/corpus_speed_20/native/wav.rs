//! Handwritten bounded RIFF/PCM processing with complete reusable exports.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::fmt::Write;

struct Wave {
    rate: u32,
    samples: Vec<i64>,
    chunks: Vec<Value>,
}
fn u16le(data: &[u8]) -> u16 {
    u16::from_le_bytes(data.try_into().unwrap())
}
fn u32le(data: &[u8]) -> u32 {
    u32::from_le_bytes(data.try_into().unwrap())
}
fn decode(source: &[u8]) -> Result<Wave> {
    require(
        source.len() >= 12 && &source[..4] == b"RIFF" && &source[8..12] == b"WAVE",
        "expected RIFF/WAVE",
    )?;
    require(
        u32le(&source[4..8]) as usize == source.len() - 8,
        "RIFF length differs from file size",
    )?;
    let mut cursor = 12;
    let mut chunks = Vec::new();
    let (mut format, mut audio) = (None, None);
    while cursor < source.len() {
        require(chunks.len() < 1024, "chunk count limit")?;
        require(source.len() - cursor >= 8, "truncated chunk header")?;
        let name = &source[cursor..cursor + 4];
        let size = u32le(&source[cursor + 4..cursor + 8]) as usize;
        let end = cursor + 8 + size;
        require(end + size % 2 <= source.len(), "truncated chunk or padding")?;
        let payload = &source[cursor + 8..end];
        if name == b"fmt " {
            require(format.is_none(), "duplicate format chunk")?;
            format = Some(payload);
        }
        if name == b"data" {
            require(audio.is_none(), "duplicate data chunk")?;
            audio = Some(payload);
        }
        chunks.push(json!({"id_hex":rt::bytes_hex(name),"offset":cursor,"bytes":size,"padding_bytes":size%2,"sha256":digest(payload)}));
        cursor = end + size % 2;
    }
    let format = format.ok_or("format chunk required")?;
    let audio = audio.ok_or("data chunk required")?;
    require(
        format.len() == 16 || format.len() == 18,
        "format chunk must contain 16 or 18 bytes",
    )?;
    require(
        u16le(&format[..2]) == 1 && u16le(&format[2..4]) == 1 && u16le(&format[14..16]) == 16,
        "only mono signed16 integer PCM supported",
    )?;
    let rate = u32le(&format[4..8]);
    require((1..=384000).contains(&rate), "sample rate range")?;
    require(
        u32le(&format[8..12]) == rate * 2 && u16le(&format[12..14]) == 2,
        "inconsistent byte rate or alignment",
    )?;
    require(
        audio.len() % 2 == 0 && audio.len() / 2 <= 262144,
        "sample alignment or count limit",
    )?;
    let samples = audio
        .chunks_exact(2)
        .map(|pair| i16::from_le_bytes(pair.try_into().unwrap()) as i64)
        .collect();
    Ok(Wave {
        rate,
        samples,
        chunks,
    })
}
fn encode(rate: u32, samples: &[i64]) -> Vec<u8> {
    let mut out = Vec::with_capacity(44 + samples.len() * 2);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + samples.len() as u32 * 2).to_le_bytes());
    out.extend_from_slice(b"WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00");
    out.extend_from_slice(&rate.to_le_bytes());
    out.extend_from_slice(&(rate * 2).to_le_bytes());
    out.extend_from_slice(b"\x02\x00\x10\x00data");
    out.extend_from_slice(&(samples.len() as u32 * 2).to_le_bytes());
    for &sample in samples {
        out.extend_from_slice(&(sample as i16).to_le_bytes());
    }
    out
}
fn statistics(samples: &[i64], rate: u32) -> Value {
    let (mut total, mut squares, mut peak) = (0_i64, 0_i64, 0_i64);
    for &value in samples {
        total += value;
        squares += value * value;
        peak = peak.max(value.abs());
    }
    let count = samples.len();
    let denominator = count.max(1) as f64;
    json!({"samples":count,"minimum":samples.iter().min(),"maximum":samples.iter().max(),"peak":peak,"sum":total,"sum_squares":squares,
        "mean":total as f64/denominator,"rms":(squares as f64/denominator).sqrt(),"duration_seconds":count as f64/rate as f64})
}
#[derive(Serialize)]
struct Envelope {
    start: usize,
    end: usize,
    input_min: i64,
    input_max: i64,
    output_min: i64,
    output_max: i64,
}
struct Processed {
    samples: Vec<i64>,
    audio: Vec<u8>,
    results: Value,
    waveform: Vec<Envelope>,
    clipped_low: i64,
    clipped_high: i64,
}
fn process(wave: &Wave, settings: &Value, source_bytes: usize) -> Result<Processed> {
    let method = string(&settings["method"])?;
    let before = statistics(&wave.samples, wave.rate);
    let (numerator, denominator) = if method == "peak" {
        exact(settings, &["method", "target"])?;
        let target = integer(&settings["target"])?;
        require((1..=32767).contains(&target), "peak target range")?;
        let peak = integer(&before["peak"])?;
        if peak == 0 {
            (1, 1)
        } else {
            (target, peak)
        }
    } else {
        require(method == "gain", "unknown gain method")?;
        exact(settings, &["method", "numerator", "denominator"])?;
        let numerator = integer(&settings["numerator"])?;
        let denominator = integer(&settings["denominator"])?;
        require(
            (0..=1000000).contains(&numerator) && (1..=1000000).contains(&denominator),
            "gain ratio range",
        )?;
        (numerator, denominator)
    };
    let (mut clipped_low, mut clipped_high, mut changed) = (0_i64, 0_i64, 0_i64);
    let samples: Vec<_> = wave
        .samples
        .iter()
        .map(|&value| {
            let magnitude = (value.abs() * numerator * 2 + denominator) / (denominator * 2);
            let rounded = if value < 0 { -magnitude } else { magnitude };
            clipped_low += i64::from(rounded < -32768);
            clipped_high += i64::from(rounded > 32767);
            let result = rounded.clamp(-32768, 32767);
            changed += i64::from(result != value);
            result
        })
        .collect();
    let count = samples.len();
    let buckets = count.min(256);
    let waveform: Vec<_> = (0..buckets)
        .map(|bucket| {
            let start = bucket * count / buckets;
            let end = (bucket + 1) * count / buckets;
            let input = &wave.samples[start..end];
            let output = &samples[start..end];
            Envelope {
                start,
                end,
                input_min: *input.iter().min().unwrap(),
                input_max: *input.iter().max().unwrap(),
                output_min: *output.iter().min().unwrap(),
                output_max: *output.iter().max().unwrap(),
            }
        })
        .collect();
    let audio = encode(wave.rate, &samples);
    let results = json!({"sample_rate":wave.rate,"source_bytes":source_bytes,"chunks":wave.chunks,"gain":{"numerator":numerator,"denominator":denominator},
        "input":before,"output":statistics(&samples,wave.rate),"changed_samples":changed,"clipped_low":clipped_low,"clipped_high":clipped_high,"waveform":waveform,"normalized_sha256":digest(&audio)});
    Ok(Processed {
        samples,
        audio,
        results,
        waveform,
        clipped_low,
        clipped_high,
    })
}
fn render(wave: &Wave, processed: &Processed) -> Vec<u8> {
    let count = wave.samples.len();
    let mut rows = vec![
        r#"<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="660" viewBox="0 0 1000 660">"#.into(),
        "<title>WAV level preview</title>".into(),
        "<desc>Input and output minimum/maximum envelopes. Both panels use the full signed16 scale.</desc>".into(),
        r##"<rect width="100%" height="100%" fill="#f7f9fc"/>"##.into(),
        r##"<g font-family="DejaVu Sans, sans-serif" fill="#243145">"##.into(),
        r#"<text x="80" y="32" font-size="22">WAV level preview</text>"#.into(),
        format!(r#"<text x="80" y="56">Samples: {count} · Rate: {} Hz</text>"#, wave.rate),
        format!(r#"<text x="80" y="635">Clamped samples: {}</text>"#, processed.clipped_low + processed.clipped_high),
    ];
    for panel in 0..2 {
        let (label, prefix, color) = if panel == 0 {
            ("Input", "input", "#2678c8")
        } else {
            ("Output", "output", "#d25c32")
        };
        let center = 200 + panel * 280;
        rows.push(format!(
            r#"<text x="80" y="{}" font-size="18">{label}</text>"#,
            center - 112
        ));
        rows.push(format!(
            r##"<path d="M80 {} V{} H960" fill="none" stroke="#708095"/>"##,
            center - 100,
            center + 100
        ));
        rows.push(format!(
            r##"<path d="M80 {center} H960" stroke="#c4cdd7"/>"##
        ));
        rows.push(format!(r#"<text x="15" y="{}">32767</text>"#, center - 95));
        rows.push(format!(
            r#"<text x="15" y="{}">-32768</text>"#,
            center + 100
        ));
        if count == 0 {
            rows.push(format!(
                r#"<text x="460" y="{}">No samples</text>"#,
                center - 10
            ));
        }
        for row in &processed.waveform {
            let (start, end) = (row.start, row.end);
            let x = 80 + (start + end) * 880 / (2 * count);
            let (low, high) = if panel == 0 {
                (row.input_min, row.input_max)
            } else {
                (row.output_min, row.output_max)
            };
            let top = center - (high * 100).div_euclid(32768);
            let bottom = center - (low * 100).div_euclid(32768);
            rows.push(format!(r#"<path class="{prefix}" d="M{x} {top} V{bottom}" stroke="{color}" stroke-width="2" stroke-linecap="round"><title>Samples {start}..{end}: {low}..{high}</title></path>"#));
        }
        rows.push(format!(r#"<text x="80" y="{}">0</text>"#, center + 124));
        rows.push(format!(
            r#"<text x="960" y="{}" text-anchor="end">{count}</text>"#,
            center + 124
        ));
    }
    rows.push("</g></svg>".into());
    (rows.join("\n") + "\n").into_bytes()
}
fn run() -> Result<()> {
    let request = Document::read(
        absolute(
            &std::env::var("WAV_CONFIG").unwrap_or_else(|_| "wav-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let config = request.json()?;
    let mode = string(&config["mode"])?;
    exact(
        &config,
        if mode == "process" {
            &["version", "mode", "input", "output", "settings"]
        } else {
            &["version", "mode", "input", "output"]
        },
    )?;
    require(
        integer(&config["version"])? == 1 && (mode == "process" || mode == "verify"),
        "unsupported request version or mode",
    )?;
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
    let mut archive = Value::Null;
    let decoded;
    let source = if mode == "verify" {
        archive = document.json()?;
        exact(&archive, &["version", "source_hex", "settings", "results"])?;
        require(
            integer(&archive["version"])? == 1,
            "unsupported archive version",
        )?;
        let spelling = string(&archive["source_hex"])?;
        require(spelling.chars().count() <= 4194304, "source byte limit")?;
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
        &archive["settings"]
    } else {
        &config["settings"]
    };
    let wave = decode(source)?;
    let processed = process(&wave, settings, source.len())?;
    if mode == "verify" {
        require(
            canonical(&archive["results"])? == canonical(&processed.results)?,
            "archive differs from recomputed processing",
        )?;
    }
    let summary = json!({"samples":wave.samples.len(),"clipped_low":processed.clipped_low,"clipped_high":processed.clipped_high});
    let mut csv = String::from("sample,input,output\n");
    for (index, (before, after)) in wave.samples.iter().zip(&processed.samples).enumerate() {
        writeln!(csv, "{index},{before},{after}")?;
    }
    let mut files = BTreeMap::new();
    files.insert("waveform.svg".into(), render(&wave, &processed));
    files.insert("samples.csv".into(), csv.into_bytes());
    files.insert("original.wav".into(), source.to_vec());
    files.insert("normalized.wav".into(), processed.audio);
    files.insert(
        "report.json".into(),
        (rt::pretty_view(&json!({"version":1,"mode":mode,"results":processed.results}))? + "\n")
            .into_bytes(),
    );
    let archive = Value::Object(
        [
            ("version".into(), json!(1)),
            ("source_hex".into(), json!(rt::bytes_hex(source))),
            ("settings".into(), settings.clone()),
            ("results".into(), processed.results),
        ]
        .into_iter()
        .collect(),
    );
    files.insert("archive.json".into(), canonical(&archive)?);
    files.insert("process.json".into(),canonical(&json!({"version":1,"mode":"process","input":"original.wav","settings":settings,"output":"processed"}))?);
    files.insert(
        "replay.json".into(),
        canonical(
            &json!({"version":1,"mode":"verify","input":"archive.json","output":"replayed"}),
        )?,
    );
    require(
        files.values().all(|data| data.len() <= 16777216),
        "export byte limit",
    )?;
    publish(&output, files, &[request, document], "wav")?;
    println!("{}", rt::json_canonical_view(&summary)?);
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
