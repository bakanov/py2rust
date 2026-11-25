//! Handwritten bounded BMP decoding, thumbnails, contact sheets and replay.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::{collections::BTreeMap, path::Path};

struct Source {
    name: String,
    data: Vec<u8>,
}
struct Bitmap {
    width: usize,
    height: usize,
    pixels: Vec<u8>,
    metadata: Value,
}
struct Sheet {
    thumbnails: Vec<Vec<u8>>,
    bitmap: Vec<u8>,
    results: Value,
}
fn unsigned(data: &[u8]) -> usize {
    data.iter()
        .enumerate()
        .map(|(shift, &byte)| usize::from(byte) << (shift * 8))
        .sum()
}
fn signed32(data: &[u8]) -> i64 {
    i64::from(i32::from_le_bytes(data.try_into().unwrap()))
}
fn decode(data: &[u8]) -> Result<Bitmap> {
    require(data.len() >= 26 && &data[..2] == b"BM", "expected BMP file")?;
    require(
        unsigned(&data[2..6]) == data.len() && data[6..10] == [0; 4],
        "file size or reserved fields",
    )?;
    let offset = unsigned(&data[10..14]);
    let dib = unsigned(&data[14..18]);
    require(
        [12, 40, 108, 124].contains(&dib) && data.len() >= 14 + dib,
        "unsupported or truncated DIB header",
    )?;
    let width = if dib == 12 {
        unsigned(&data[18..20]) as i64
    } else {
        signed32(&data[18..22])
    };
    let signed_height = if dib == 12 {
        unsigned(&data[20..22]) as i64
    } else {
        signed32(&data[22..26])
    };
    let height = signed_height.abs();
    require(
        (1..=1024).contains(&width) && (1..=1024).contains(&height) && width * height <= 262144,
        "image dimension or pixel limit",
    )?;
    let (width, height) = (width as usize, height as usize);
    let plane_at = if dib == 12 { 22 } else { 26 };
    require(
        unsigned(&data[plane_at..plane_at + 2]) == 1,
        "expected one plane",
    )?;
    require(
        unsigned(&data[plane_at + 2..plane_at + 4]) == 24,
        "only 24-bit pixels are supported",
    )?;
    let stride = (width * 3 + 3) / 4 * 4;
    let end = offset + stride * height;
    let palette = if dib == 12 {
        0
    } else {
        unsigned(&data[46..50])
    };
    require(
        offset >= 14 + dib + palette * 4 && end <= data.len(),
        "pixel offset or truncated pixel rows",
    )?;
    if dib != 12 {
        require(unsigned(&data[30..34]) == 0, "only BI_RGB is supported")?;
        require(
            [0, stride * height].contains(&unsigned(&data[34..38])),
            "inconsistent image size",
        )?;
    }
    let color_space = if dib >= 108 {
        unsigned(&data[70..74])
    } else {
        0
    };
    let mut profile_bytes = 0;
    if dib == 124 {
        require(unsigned(&data[134..138]) == 0, "reserved V5 field")?;
        if [1279872587, 1296188740].contains(&color_space) {
            let profile = 14 + unsigned(&data[126..130]);
            profile_bytes = unsigned(&data[130..134]);
            require(
                profile >= 14 + dib + palette * 4 && profile_bytes > 0,
                "invalid color profile offset or size",
            )?;
            require(
                profile + profile_bytes <= data.len(),
                "truncated color profile",
            )?;
            require(
                profile + profile_bytes <= offset || profile >= end,
                "color profile overlaps pixels",
            )?;
        }
    }
    let mut pixels = Vec::with_capacity(width * height * 3);
    for y in 0..height {
        let stored_y = if signed_height > 0 { height - 1 - y } else { y };
        let start = offset + stored_y * stride;
        pixels.extend_from_slice(&data[start..start + width * 3]);
    }
    let metadata = json!({"width":width,"height":height,"top_down":signed_height<0,"dib_bytes":dib,
        "pixel_offset":offset,"stride":stride,"palette_entries":palette,"gap_bytes":offset-14-dib,
        "trailing_bytes":data.len()-end,"color_space":color_space,"profile_bytes":profile_bytes,
        "color_management":false,"source_sha256":digest(data),"pixels_sha256":digest(&pixels)});
    Ok(Bitmap {
        width,
        height,
        pixels,
        metadata,
    })
}
fn encode(image: &Bitmap) -> Vec<u8> {
    let stride = (image.width * 3 + 3) / 4 * 4;
    let mut out = vec![0; 54 + stride * image.height];
    out[..2].copy_from_slice(b"BM");
    let size = out.len() as u32;
    out[2..6].copy_from_slice(&size.to_le_bytes());
    out[10..14].copy_from_slice(&54_u32.to_le_bytes());
    out[14..18].copy_from_slice(&40_u32.to_le_bytes());
    out[18..22].copy_from_slice(&(image.width as u32).to_le_bytes());
    out[22..26].copy_from_slice(&(image.height as u32).to_le_bytes());
    out[26..30].copy_from_slice(&[1, 0, 24, 0]);
    out[34..38].copy_from_slice(&((stride * image.height) as u32).to_le_bytes());
    for y in 0..image.height {
        let start = (image.height - 1 - y) * image.width * 3;
        out[54 + y * stride..54 + y * stride + image.width * 3]
            .copy_from_slice(&image.pixels[start..start + image.width * 3]);
    }
    out
}
fn resize(image: &Bitmap, width: usize, height: usize) -> Bitmap {
    let mut pixels = Vec::with_capacity(width * height * 3);
    for y in 0..height {
        let source_y = (2 * y + 1) * image.height / (2 * height);
        for x in 0..width {
            let source_x = (2 * x + 1) * image.width / (2 * width);
            let at = (source_y * image.width + source_x) * 3;
            pixels.extend_from_slice(&image.pixels[at..at + 3]);
        }
    }
    Bitmap {
        width,
        height,
        pixels,
        metadata: Value::Null,
    }
}
fn compose(sources: &[Source], settings: &Value) -> Result<Sheet> {
    exact(
        settings,
        &[
            "box_width",
            "box_height",
            "columns",
            "margin",
            "gap",
            "fit",
            "background",
        ],
    )?;
    let (box_width, box_height, columns, margin, gap) = (
        integer(&settings["box_width"])?,
        integer(&settings["box_height"])?,
        integer(&settings["columns"])?,
        integer(&settings["margin"])?,
        integer(&settings["gap"])?,
    );
    let fit = string(&settings["fit"])?;
    require(
        (1..=256).contains(&box_width)
            && (1..=256).contains(&box_height)
            && (1..=8).contains(&columns),
        "box or column range",
    )?;
    require(
        (0..=32).contains(&margin)
            && (0..=32).contains(&gap)
            && matches!(fit, "contain" | "stretch"),
        "spacing or fit mode",
    )?;
    let background = settings["background"]
        .as_array()
        .ok_or("expected JSON array")?;
    require(background.len() == 3, "background requires RGB triplet")?;
    let mut color = [0; 3];
    for (i, channel) in (0..3).rev().enumerate() {
        let value = integer(&background[channel])?;
        require((0..=255).contains(&value), "background channel range")?;
        color[i] = value as u8;
    }
    let (box_width, box_height, columns, margin, gap) = (
        box_width as usize,
        box_height as usize,
        (columns as usize).min(sources.len()),
        margin as usize,
        gap as usize,
    );
    let rows = (sources.len() + columns - 1) / columns;
    let width = 2 * margin + columns * box_width + (columns - 1) * gap;
    let height = 2 * margin + rows * box_height + (rows - 1) * gap;
    require(
        width <= 4096 && height <= 4096 && width * height <= 2097152,
        "sheet dimension or pixel limit",
    )?;
    let mut canvas = color.repeat(width * height);
    let mut thumbnails = Vec::with_capacity(sources.len());
    let mut items = Vec::with_capacity(sources.len());
    let mut total_pixels = 0;
    for (index, source) in sources.iter().enumerate() {
        let original = decode(&source.data)?;
        total_pixels += original.width * original.height;
        require(total_pixels <= 1048576, "combined source pixel limit")?;
        let (mut tw, mut th) = (box_width, box_height);
        if fit == "contain" {
            if original.width * box_height >= original.height * box_width {
                th = (original.height * box_width / original.width).max(1);
            } else {
                tw = (original.width * box_height / original.height).max(1);
            }
        }
        let thumb = resize(&original, tw, th);
        let left = margin + (index % columns) * (box_width + gap) + (box_width - tw) / 2;
        let top = margin + (index / columns) * (box_height + gap) + (box_height - th) / 2;
        for y in 0..th {
            let start = ((top + y) * width + left) * 3;
            canvas[start..start + tw * 3]
                .copy_from_slice(&thumb.pixels[y * tw * 3..(y + 1) * tw * 3]);
        }
        let data = encode(&thumb);
        items.push(json!({"index":index,"name":source.name,"source":original.metadata,"width":tw,"height":th,
            "left":left,"top":top,"thumbnail_sha256":digest(&data),"pixels_sha256":digest(&thumb.pixels)}));
        thumbnails.push(data);
    }
    let canvas = Bitmap {
        width,
        height,
        pixels: canvas,
        metadata: Value::Null,
    };
    let bitmap = encode(&canvas);
    let results = json!({"width":width,"height":height,"columns":columns,"rows":rows,"source_pixels":total_pixels,
        "items":items,"sheet_sha256":digest(&bitmap),"pixels_sha256":digest(&canvas.pixels)});
    Ok(Sheet {
        thumbnails,
        bitmap,
        results,
    })
}
fn escaped(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}
fn bundle(
    mode: &str,
    sources: &[Source],
    settings: &Value,
    sheet: Sheet,
) -> Result<BTreeMap<String, Vec<u8>>> {
    let mut files = BTreeMap::new();
    files.insert("sheet.bmp".into(), sheet.bitmap);
    let (mut originals, mut thumbnails, mut archived) = (Vec::new(), Vec::new(), Vec::new());
    let mut html=vec![
        "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>BMP contact sheet</title>".to_owned(),
        "<style>body{font:16px system-ui;margin:32px;background:#f8fafc;color:#263449}".into(),
        "img{max-width:100%;image-rendering:pixelated}figure{display:inline-block;vertical-align:top;margin:16px}".into(),
        "figcaption{max-width:256px;overflow-wrap:anywhere}pre{white-space:pre-wrap}</style>".into(),
        "<h1>BMP contact sheet</h1><p>Nearest-neighbor thumbnails. RGB values preserved without color management.</p>".into(),
        "<a href=\"sheet.bmp\"><img src=\"sheet.bmp\" alt=\"Combined contact sheet\"></a><h2>Individual thumbnails</h2>".into(),
    ];
    for (index, (source, thumbnail)) in sources.iter().zip(sheet.thumbnails).enumerate() {
        let original_name = format!("source-{index}.bmp");
        let thumbnail_name = format!("thumbnail-{index}.bmp");
        originals.push(json!({"name":source.name,"path":original_name}));
        thumbnails.push(json!({"name":source.name,"path":thumbnail_name}));
        archived.push(json!({"name":source.name,"source_hex":rt::bytes_hex(&source.data)}));
        html.push(format!("<figure><a href=\"{thumbnail_name}\"><img src=\"{thumbnail_name}\" alt=\"{}\"></a><figcaption>{}</figcaption></figure>",escaped(&source.name),escaped(&source.name)));
        files.insert(original_name, source.data.clone());
        files.insert(thumbnail_name, thumbnail);
    }
    html.push(format!(
        "<h2>Layout</h2><pre>{}</pre></html>",
        escaped(&rt::pretty_view(settings)?)
    ));
    files.insert("index.html".into(), (html.join("\n") + "\n").into_bytes());
    files.insert(
        "project.json".into(),
        canonical(&json!({"version":1,"settings":settings,"images":originals}))?,
    );
    files.insert(
        "thumbnails.json".into(),
        canonical(&json!({"version":1,"settings":settings,"images":thumbnails}))?,
    );
    files.insert(
        "archive.json".into(),
        canonical(
            &json!({"version":1,"settings":settings,"images":archived,"results":sheet.results}),
        )?,
    );
    files.insert(
        "report.json".into(),
        (rt::pretty_view(&json!({"version":1,"mode":mode,"results":sheet.results}))? + "\n")
            .into_bytes(),
    );
    for (filename, mode, input, output) in [
        ("rebuild.json", "build", "project.json", "rebuilt"),
        ("retile.json", "build", "thumbnails.json", "retiled"),
        ("replay.json", "verify", "archive.json", "replayed"),
    ] {
        files.insert(
            filename.into(),
            canonical(&json!({"version":1,"mode":mode,"input":input,"output":output}))?,
        );
    }
    require(
        files.values().all(|data| data.len() <= 33554432),
        "export byte limit",
    )?;
    Ok(files)
}
fn run() -> Result<()> {
    let request = Document::read(
        absolute(
            &std::env::var("BMP_CONFIG").unwrap_or("bmp-job.json".into()),
            Path::new("."),
        )?,
        65536,
    )?;
    let config = request.json()?;
    exact(&config, &["version", "mode", "input", "output"])?;
    let mode = string(&config["mode"])?;
    require(
        integer(&config["version"])? == 1 && matches!(mode, "build" | "verify"),
        "unsupported request version or mode",
    )?;
    let output = absolute(
        string(&config["output"])?,
        request.path.parent().ok_or("missing parent")?,
    )?;
    require(
        !output.exists() && !output.is_symlink(),
        "output already exists",
    )?;
    let project = Document::read(
        absolute(string(&config["input"])?, request.path.parent().unwrap())?,
        if mode == "verify" { 33554432 } else { 65536 },
    )?;
    let definition = project.json()?;
    exact(
        &definition,
        if mode == "verify" {
            &["version", "settings", "images", "results"]
        } else {
            &["version", "settings", "images"]
        },
    )?;
    require(
        integer(&definition["version"])? == 1,
        "unsupported project or archive version",
    )?;
    let rows = definition["images"]
        .as_array()
        .ok_or("expected JSON array")?;
    require((1..=16).contains(&rows.len()), "image count limit")?;
    let base = project.path.parent().unwrap().to_path_buf();
    let mut inputs = vec![request, project];
    let mut sources = Vec::with_capacity(rows.len());
    let mut total_bytes = 0;
    for row in rows {
        exact(
            row,
            if mode == "verify" {
                &["name", "source_hex"]
            } else {
                &["name", "path"]
            },
        )?;
        let data = if mode == "verify" {
            let spelling = string(&row["source_hex"])?;
            require(spelling.chars().count() <= 4194304, "image byte limit")?;
            let data = rt::bytes_from_hex(spelling)?;
            require(
                rt::bytes_hex(&data) == spelling,
                "expected canonical lowercase hex",
            )?;
            data
        } else {
            let document = Document::read(absolute(string(&row["path"])?, &base)?, 2097152)?;
            let data = document.data.clone();
            inputs.push(document);
            data
        };
        total_bytes += data.len();
        require(total_bytes <= 8388608, "combined source byte limit")?;
        let name = string(&row["name"])?;
        require(
            (1..=64).contains(&name.chars().count()) && !rt::str_strip(name).is_empty(),
            "image name length",
        )?;
        require(
            name.chars()
                .all(|c| c as u32 >= 32 && !(127..=159).contains(&(c as u32))),
            "control in image name",
        )?;
        sources.push(Source {
            name: name.to_owned(),
            data,
        });
    }
    let sheet = compose(&sources, &definition["settings"])?;
    if mode == "verify" {
        require(
            canonical(&definition["results"])? == canonical(&sheet.results)?,
            "archive differs from recomputed sheet",
        )?;
    }
    let summary = json!({"images":sources.len(),"width":sheet.results["width"],"height":sheet.results["height"]});
    let files = bundle(mode, &sources, &definition["settings"], sheet)?;
    publish(&output, files, &inputs, "bmp")?;
    println!("{}", rt::json_canonical_view(&summary)?);
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
