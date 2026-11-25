//! Handwritten bounded P6 pipeline, exact histograms, sampled preview and replay.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::{collections::BTreeMap, fmt::Write, path::Path};

struct Image {
    width: usize,
    height: usize,
    maximum: u16,
    samples: Vec<u16>,
}
fn whitespace(byte: u8) -> bool {
    matches!(byte, 9 | 10 | 11 | 12 | 13 | 32)
}
fn comment_end(data: &[u8], mut at: usize) -> Result<usize> {
    while at < data.len() && !matches!(data[at], 10 | 13) {
        require(at < 65536, "header byte limit")?;
        at += 1;
    }
    Ok(at)
}
fn number(data: &[u8], mut at: usize) -> Result<(usize, usize)> {
    while at < data.len() {
        require(at < 65536, "header byte limit")?;
        if whitespace(data[at]) {
            at += 1;
        } else if data[at] == b'#' {
            at = comment_end(data, at)?;
        } else {
            break;
        }
    }
    let (mut value, mut digits) = (0, 0);
    while at < data.len() && data[at].is_ascii_digit() {
        require(at < 65536 && digits < 5, "numeric token or header limit")?;
        value = value * 10 + usize::from(data[at] - b'0');
        at += 1;
        digits += 1;
    }
    require(
        digits > 0 && at < data.len(),
        "missing or unterminated number",
    )?;
    require(
        whitespace(data[at]) || data[at] == b'#',
        "invalid numeric separator",
    )?;
    Ok((value, at))
}
fn decode(data: &[u8]) -> Result<Image> {
    require(data.len() >= 3 && &data[..2] == b"P6", "expected P6")?;
    require(
        whitespace(data[2]) || data[2] == b'#',
        "missing magic separator",
    )?;
    let (width, at) = number(data, 2)?;
    let (height, at) = number(data, at)?;
    let (maximum, at) = number(data, at)?;
    require(
        (1..=1024).contains(&width) && (1..=1024).contains(&height),
        "image dimension limit",
    )?;
    require(width * height <= 262144, "image pixel limit")?;
    require((1..=65535).contains(&maximum), "Maxval range")?;
    let at = if data[at] == b'#' {
        comment_end(data, at)?
    } else {
        at
    };
    require(
        at < data.len() && whitespace(data[at]),
        "missing raster separator",
    )?;
    let at = at + 1;
    require(at <= 65536, "header byte limit")?;
    let size = if maximum < 256 { 1 } else { 2 };
    require(
        data.len() - at == width * height * 3 * size,
        "raster byte count",
    )?;
    let samples: Vec<u16> = data[at..]
        .chunks_exact(size)
        .map(|bytes| {
            if size == 1 {
                u16::from(bytes[0])
            } else {
                u16::from_be_bytes([bytes[0], bytes[1]])
            }
        })
        .collect();
    require(
        samples.iter().all(|&v| usize::from(v) <= maximum),
        "sample exceeds Maxval",
    )?;
    Ok(Image {
        width,
        height,
        maximum: maximum as u16,
        samples,
    })
}
fn raster(image: &Image) -> Vec<u8> {
    if image.maximum < 256 {
        image.samples.iter().map(|&v| v as u8).collect()
    } else {
        image.samples.iter().flat_map(|v| v.to_be_bytes()).collect()
    }
}
fn encode(image: &Image) -> Vec<u8> {
    let mut data =
        format!("P6\n{} {}\n{}\n", image.width, image.height, image.maximum).into_bytes();
    data.extend(raster(image));
    data
}
fn histogram(image: &Image) -> [Vec<usize>; 3] {
    let mut result = std::array::from_fn(|_| vec![0; usize::from(image.maximum) + 1]);
    for pixel in image.samples.chunks_exact(3) {
        for channel in 0..3 {
            result[channel][usize::from(pixel[channel])] += 1;
        }
    }
    result
}
fn describe(image: &Image, data: &[u8]) -> Value {
    let raster = raster(image);
    let [red, green, blue] = histogram(image);
    json!({"width":image.width,"height":image.height,"maxval":image.maximum,
        "header_bytes":data.len()-raster.len(),"raster_sha256":digest(&raster),
        "file_sha256":digest(data),"histogram":{"red":red,"green":green,"blue":blue}})
}
fn apply(image: &Image, operation: &Value) -> Result<Image> {
    let kind = string(&operation["op"])?;
    let (mut width, mut height) = (image.width, image.height);
    let mut samples = Vec::new();
    if kind == "crop" {
        exact(operation, &["op", "x", "y", "width", "height"])?;
        let (x, y, w, h) = (
            integer(&operation["x"])?,
            integer(&operation["y"])?,
            integer(&operation["width"])?,
            integer(&operation["height"])?,
        );
        require(x >= 0 && y >= 0 && w > 0 && h > 0, "crop range")?;
        require(
            x.checked_add(w).ok_or("integer overflow")? <= image.width as i64
                && y.checked_add(h).ok_or("integer overflow")? <= image.height as i64,
            "crop outside image",
        )?;
        width = w as usize;
        height = h as usize;
        samples.reserve(width * height * 3);
        for row in y as usize..y as usize + height {
            let start = (row * image.width + x as usize) * 3;
            samples.extend_from_slice(&image.samples[start..start + width * 3]);
        }
    } else if kind == "invert" {
        exact(operation, &["op"])?;
        samples = image.samples.iter().map(|&v| image.maximum - v).collect();
    } else {
        require(kind == "threshold", "unknown filter")?;
        exact(operation, &["op", "value", "mode"])?;
        let threshold = integer(&operation["value"])?;
        let mode = string(&operation["mode"])?;
        require(
            (0..=i64::from(image.maximum)).contains(&threshold)
                && matches!(mode, "channel" | "mean"),
            "threshold range or mode",
        )?;
        samples.reserve(image.samples.len());
        for pixel in image.samples.chunks_exact(3) {
            let total: i64 = pixel.iter().map(|&v| i64::from(v)).sum();
            for &value in pixel {
                let white = if mode == "channel" {
                    i64::from(value) >= threshold
                } else {
                    total >= 3 * threshold
                };
                samples.push(if white { image.maximum } else { 0 });
            }
        }
    }
    Ok(Image {
        width,
        height,
        maximum: image.maximum,
        samples,
    })
}
fn panel(image: &Image, left: usize, title: &str) -> Result<String> {
    let (mut width, mut height) = (image.width, image.height);
    if width.max(height) > 128 {
        if width >= height {
            width = 128;
            height = (image.height * 128 / image.width).max(1);
        } else {
            height = 128;
            width = (image.width * 128 / image.height).max(1);
        }
    }
    let mut out = format!("<text x=\"{left}\" y=\"34\" font-size=\"20\">{title}</text>\n<text x=\"{left}\" y=\"58\" fill=\"#64748b\">{} × {} · Maxval {}</text>\n<svg x=\"{left}\" y=\"80\" width=\"256\" height=\"256\" viewBox=\"0 0 {width} {height}\" preserveAspectRatio=\"xMidYMid meet\" shape-rendering=\"crispEdges\">",image.width,image.height,image.maximum);
    for y in 0..height {
        let source_y = (2 * y + 1) * image.height / (2 * height);
        for x in 0..width {
            let source_x = (2 * x + 1) * image.width / (2 * width);
            let offset = (source_y * image.width + source_x) * 3;
            let color: [u32; 3] = std::array::from_fn(|c| {
                (u32::from(image.samples[offset + c]) * 255 + u32::from(image.maximum) / 2)
                    / u32::from(image.maximum)
            });
            write!(out,"\n<rect x=\"{x}\" y=\"{y}\" width=\"1\" height=\"1\" fill=\"#{:02x}{:02x}{:02x}\"/>",color[0],color[1],color[2])?;
        }
    }
    out.push_str("\n</svg>");
    Ok(out)
}
fn preview(original: &Image, filtered: &Image) -> Result<Vec<u8>> {
    Ok(format!("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"600\" height=\"380\" viewBox=\"0 0 600 380\"><rect width=\"600\" height=\"380\" fill=\"#f8fafc\"/><g font-family=\"sans-serif\" fill=\"#253349\">{}{}<text x=\"24\" y=\"365\" font-size=\"12\">Sampled RGB preview · no gamma conversion · full data in PPM/CSV</text></g></svg>\n",panel(original,24,"Original")?,panel(filtered,320,"Filtered")?).into_bytes())
}
fn histogram_csv(original: &Image, filtered: &Image) -> Result<Vec<u8>> {
    let before = histogram(original);
    let after = histogram(filtered);
    let mut out =
        "value,red_input,red_output,green_input,green_output,blue_input,blue_output\n".to_owned();
    for value in 0..=usize::from(original.maximum) {
        let counts = [
            before[0][value],
            after[0][value],
            before[1][value],
            after[1][value],
            before[2][value],
            after[2][value],
        ];
        if counts.iter().any(|&count| count != 0) {
            write!(out, "{value}")?;
            for count in counts {
                write!(out, ",{count}")?;
            }
            out.push('\n');
        }
    }
    Ok(out.into_bytes())
}
fn run() -> Result<()> {
    let request = Document::read(
        absolute(
            &std::env::var("PPM_CONFIG").unwrap_or("ppm-job.json".into()),
            Path::new("."),
        )?,
        65536,
    )?;
    let config = request.json()?;
    let mode = string(&config["mode"])?;
    require(
        integer(&config["version"])? == 1 && matches!(mode, "process" | "verify"),
        "unsupported request version or mode",
    )?;
    exact(
        &config,
        if mode == "process" {
            &["version", "mode", "input", "output", "pipeline"]
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
        if mode == "verify" { 16777216 } else { 2097152 },
    )?;
    let archive = if mode == "verify" {
        document.json()?
    } else {
        Value::Null
    };
    let decoded;
    let source = if mode == "verify" {
        exact(&archive, &["version", "source_hex", "pipeline", "results"])?;
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
    let pipeline = if mode == "verify" {
        &archive["pipeline"]
    } else {
        &config["pipeline"]
    };
    let operations = pipeline.as_array().ok_or("expected JSON array")?;
    require(operations.len() <= 32, "filter count limit")?;
    let original = decode(source)?;
    let mut filtered = None;
    let mut processed = original.width * original.height;
    let mut steps = Vec::new();
    for (index, operation) in operations.iter().enumerate() {
        let current = filtered.as_ref().unwrap_or(&original);
        processed += current.width * current.height;
        require(processed <= 4194304, "processing pixel budget")?;
        let next = apply(current, operation)?;
        steps.push(json!({"index":index,"filter":operation,"width":next.width,"height":next.height,"raster_sha256":digest(&raster(&next))}));
        filtered = Some(next);
    }
    let filtered = filtered.as_ref().unwrap_or(&original);
    let encoded = encode(filtered);
    let results = json!({"input":describe(&original,source),"output":describe(filtered,&encoded),"steps":steps,"processed_pixels":processed});
    if mode == "verify" {
        require(
            canonical(&archive["results"])? == canonical(&results)?,
            "archive differs from recomputed pipeline",
        )?;
    }
    let mut files = BTreeMap::new();
    files.insert("original.ppm".into(), source.to_vec());
    files.insert("filtered.ppm".into(), encoded);
    files.insert("preview.svg".into(), preview(&original, filtered)?);
    files.insert("histogram.csv".into(), histogram_csv(&original, filtered)?);
    files.insert("archive.json".into(),canonical(&json!({"version":1,"source_hex":rt::bytes_hex(source),"pipeline":pipeline,"results":results}))?);
    files.insert(
        "report.json".into(),
        (rt::pretty_view(&json!({"version":1,"mode":mode,"results":results}))? + "\n").into_bytes(),
    );
    files.insert("process.json".into(),canonical(&json!({"version":1,"mode":"process","input":"original.ppm","output":"processed","pipeline":pipeline}))?);
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
    publish(&output, files, &[request, document], "ppm")?;
    println!(
        "{}",
        rt::json_canonical_view(
            &json!({"width":filtered.width,"height":filtered.height,"maxval":filtered.maximum})
        )?
    );
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
