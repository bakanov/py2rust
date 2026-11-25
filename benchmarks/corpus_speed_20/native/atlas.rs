//! Handwritten first-fit shelf atlas; exact extraction, previews and replay.
//! The P6 decoder follows the handwritten PPM baseline, with sprite-size bounds.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet},
    fmt::Write,
    path::Path,
};

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
        (1..=256).contains(&width) && (1..=256).contains(&height),
        "image dimension limit",
    )?;
    require(width * height <= 65536, "image pixel limit")?;
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
struct Sprite {
    index: usize,
    name: String,
    data: Vec<u8>,
    image: Image,
}
struct Shelf {
    y: usize,
    height: usize,
    used: usize,
}
struct Placement<'a> {
    sprite: &'a Sprite,
    x: usize,
    y: usize,
    shelf: usize,
}
struct Atlas<'a> {
    image: Image,
    placements: Vec<Placement<'a>>,
    results: Value,
}
fn pack<'a>(sprites: &'a [Sprite], settings: &Value) -> Result<Atlas<'a>> {
    exact(
        settings,
        &["width", "max_height", "padding", "order", "background"],
    )?;
    let (width, max_height, padding) = (
        integer(&settings["width"])?,
        integer(&settings["max_height"])?,
        integer(&settings["padding"])?,
    );
    let order = string(&settings["order"])?;
    require(
        (1..=1024).contains(&width)
            && (1..=1024).contains(&max_height)
            && (0..=16).contains(&padding),
        "atlas size or padding range",
    )?;
    require(matches!(order, "height" | "input"), "unknown ordering")?;
    let (width, max_height, padding) = (width as usize, max_height as usize, padding as usize);
    let maximum = sprites[0].image.maximum;
    let background = settings["background"]
        .as_array()
        .ok_or("expected JSON array")?;
    require(background.len() == 3, "background requires RGB triplet")?;
    let mut color = [0; 3];
    for (index, channel) in background.iter().enumerate() {
        let value = integer(channel)?;
        require(
            (0..=i64::from(maximum)).contains(&value),
            "background channel range",
        )?;
        color[index] = value as u16;
    }
    let mut ordered: Vec<_> = sprites.iter().collect();
    if order == "height" {
        ordered.sort_by(|a, b| {
            b.image
                .height
                .cmp(&a.image.height)
                .then_with(|| b.image.width.cmp(&a.image.width))
                .then_with(|| a.name.cmp(&b.name))
        });
    }
    let mut shelves: Vec<Shelf> = Vec::new();
    let mut placements = Vec::with_capacity(sprites.len());
    let (mut height, mut pixels) = (0, 0);
    for sprite in ordered {
        let image = &sprite.image;
        require(image.maximum == maximum, "sprite Maxval mismatch")?;
        pixels += image.width * image.height;
        require(pixels <= 1048576, "combined source pixel limit")?;
        let (pw, ph) = (image.width + 2 * padding, image.height + 2 * padding);
        require(pw <= width, "sprite wider than atlas")?;
        let selected = match shelves
            .iter()
            .position(|s| ph <= s.height && s.used + pw <= width)
        {
            Some(index) => index,
            None => {
                require(height + ph <= max_height, "shelf packing exceeds height")?;
                shelves.push(Shelf {
                    y: height,
                    height: ph,
                    used: 0,
                });
                height += ph;
                shelves.len() - 1
            }
        };
        let shelf = &mut shelves[selected];
        placements.push(Placement {
            sprite,
            x: shelf.used + padding,
            y: shelf.y + padding,
            shelf: selected,
        });
        shelf.used += pw;
    }
    let mut canvas = color.repeat(width * height);
    let mut items = Vec::with_capacity(placements.len());
    for placed in &placements {
        let sprite = placed.sprite;
        let image = &sprite.image;
        for y in 0..image.height {
            let at = ((placed.y + y) * width + placed.x) * 3;
            canvas[at..at + image.width * 3]
                .copy_from_slice(&image.samples[y * image.width * 3..(y + 1) * image.width * 3]);
        }
        items.push(json!({"index":sprite.index,"name":sprite.name,"x":placed.x,"y":placed.y,"width":image.width,
            "height":image.height,"shelf":placed.shelf,"source_sha256":digest(&sprite.data),
            "raster_sha256":digest(&raster(image)),"extracted_sha256":digest(&encode(image))}));
    }
    let shelf_rows: Vec<_> = shelves
        .iter()
        .map(|s| json!({"y":s.y,"height":s.height,"used_width":s.used}))
        .collect();
    let image = Image {
        width,
        height,
        maximum,
        samples: canvas,
    };
    let results = json!({"width":width,"height":height,"maxval":maximum,"source_pixels":pixels,"background_pixels":width*height-pixels,
        "items":items,"shelves":shelf_rows,"atlas_sha256":digest(&encode(&image)),"raster_sha256":digest(&raster(&image))});
    Ok(Atlas {
        image,
        placements,
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
fn preview(atlas: &Atlas<'_>) -> Result<Vec<u8>> {
    let image = &atlas.image;
    let (width, height, maximum) = (image.width, image.height, u32::from(image.maximum));
    let (columns, rows) = (128.min(width), 128.min(height));
    let mut out=format!("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"640\" height=\"480\" viewBox=\"0 0 640 480\">\n<rect width=\"640\" height=\"480\" fill=\"#f8fafc\"/><g font-family=\"sans-serif\" fill=\"#253349\">\n<text x=\"24\" y=\"32\" font-size=\"22\">Sprite atlas</text>\n<text x=\"24\" y=\"57\" font-size=\"14\">{} sprites · {width} × {height} · Maxval {maximum}</text>\n<svg x=\"24\" y=\"80\" width=\"592\" height=\"350\" viewBox=\"0 0 {width} {height}\" preserveAspectRatio=\"xMidYMid meet\" shape-rendering=\"crispEdges\">",atlas.placements.len());
    for y in 0..rows {
        let (top, bottom) = (y * height / rows, (y + 1) * height / rows);
        for x in 0..columns {
            let (left, right) = (x * width / columns, (x + 1) * width / columns);
            let offset = (((top + bottom) / 2) * width + (left + right) / 2) * 3;
            let color: [u32; 3] = std::array::from_fn(|c| {
                (u32::from(image.samples[offset + c]) * 255 + maximum / 2) / maximum
            });
            write!(out,"\n<rect x=\"{left}\" y=\"{top}\" width=\"{}\" height=\"{}\" fill=\"#{:02x}{:02x}{:02x}\"/>",right-left,bottom-top,color[0],color[1],color[2])?;
        }
    }
    for placed in &atlas.placements {
        write!(out,"\n<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"none\" stroke=\"#ffffff\" stroke-width=\"{}\"><title>{}</title></rect>",placed.x,placed.y,placed.sprite.image.width,placed.sprite.image.height,(width.min(height)/256).max(1),escaped(&placed.sprite.name))?;
    }
    out.push_str("\n</svg><text x=\"24\" y=\"460\" font-size=\"12\">Sampled preview · outlines use exact coordinates · full pixels in atlas.ppm</text></g></svg>\n");
    Ok(out.into_bytes())
}
fn extract(image: &Image, placement: &Placement<'_>) -> Image {
    let sprite = &placement.sprite.image;
    let mut samples = Vec::with_capacity(sprite.width * sprite.height * 3);
    for y in placement.y..placement.y + sprite.height {
        let start = (y * image.width + placement.x) * 3;
        samples.extend_from_slice(&image.samples[start..start + sprite.width * 3]);
    }
    Image {
        width: sprite.width,
        height: sprite.height,
        maximum: image.maximum,
        samples,
    }
}
fn bundle(
    mode: &str,
    sprites: &[Sprite],
    settings: &Value,
    atlas: &Atlas<'_>,
) -> Result<BTreeMap<String, Vec<u8>>> {
    let mut files = BTreeMap::new();
    files.insert("atlas.ppm".into(), encode(&atlas.image));
    files.insert("coordinates.json".into(), canonical(&atlas.results)?);
    files.insert("preview.svg".into(), preview(atlas)?);
    let (mut originals, mut extracted, mut archived) = (Vec::new(), Vec::new(), Vec::new());
    for sprite in sprites {
        let filename = format!("original-{}.ppm", sprite.index);
        originals.push(json!({"name":sprite.name,"path":filename}));
        extracted.push(json!({"name":sprite.name,"path":format!("extracted-{}.ppm",sprite.index)}));
        archived.push(json!({"name":sprite.name,"source_hex":rt::bytes_hex(&sprite.data)}));
        files.insert(filename, sprite.data.clone());
    }
    for placed in &atlas.placements {
        files.insert(
            format!("extracted-{}.ppm", placed.sprite.index),
            encode(&extract(&atlas.image, placed)),
        );
    }
    files.insert(
        "sprites.json".into(),
        canonical(&json!({"version":1,"settings":settings,"sprites":originals}))?,
    );
    files.insert(
        "extracted.json".into(),
        canonical(&json!({"version":1,"settings":settings,"sprites":extracted}))?,
    );
    files.insert(
        "archive.json".into(),
        canonical(
            &json!({"version":1,"settings":settings,"sprites":archived,"results":atlas.results}),
        )?,
    );
    files.insert(
        "report.json".into(),
        (rt::pretty_view(&json!({"version":1,"mode":mode,"results":atlas.results}))? + "\n")
            .into_bytes(),
    );
    for (filename, mode, input, output) in [
        ("repack.json", "pack", "sprites.json", "repacked"),
        ("pack-extracted.json", "pack", "extracted.json", "extracted"),
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
            &std::env::var("ATLAS_CONFIG").unwrap_or("atlas-job.json".into()),
            Path::new("."),
        )?,
        65536,
    )?;
    let config = request.json()?;
    exact(&config, &["version", "mode", "input", "output"])?;
    let mode = string(&config["mode"])?;
    require(
        integer(&config["version"])? == 1 && matches!(mode, "pack" | "verify"),
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
            &["version", "settings", "sprites", "results"]
        } else {
            &["version", "settings", "sprites"]
        },
    )?;
    require(
        integer(&definition["version"])? == 1,
        "unsupported project or archive version",
    )?;
    let rows = definition["sprites"]
        .as_array()
        .ok_or("expected JSON array")?;
    require((1..=64).contains(&rows.len()), "sprite count limit")?;
    let base = project.path.parent().unwrap().to_path_buf();
    let mut inputs = vec![request, project];
    let mut sprites = Vec::with_capacity(rows.len());
    let mut names = BTreeSet::new();
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
            require(spelling.chars().count() <= 1048576, "image byte limit")?;
            let data = rt::bytes_from_hex(spelling)?;
            require(
                rt::bytes_hex(&data) == spelling,
                "expected canonical lowercase hex",
            )?;
            data
        } else {
            let document = Document::read(absolute(string(&row["path"])?, &base)?, 524288)?;
            let data = document.data.clone();
            inputs.push(document);
            data
        };
        total_bytes += data.len();
        require(total_bytes <= 8388608, "combined source byte limit")?;
        let name = string(&row["name"])?;
        require(
            (1..=64).contains(&name.chars().count()) && !rt::str_strip(name).is_empty(),
            "sprite name length",
        )?;
        require(
            name.chars()
                .all(|c| c as u32 >= 32 && !(127..=159).contains(&(c as u32))),
            "control in sprite name",
        )?;
        require(names.insert(name.to_owned()), "duplicate sprite name")?;
        let image = decode(&data)?;
        sprites.push(Sprite {
            index: sprites.len(),
            name: name.to_owned(),
            data,
            image,
        });
    }
    let atlas = pack(&sprites, &definition["settings"])?;
    if mode == "verify" {
        require(
            canonical(&definition["results"])? == canonical(&atlas.results)?,
            "archive differs from recomputed atlas",
        )?;
    }
    let summary =
        json!({"sprites":sprites.len(),"width":atlas.image.width,"height":atlas.image.height});
    publish(
        &output,
        bundle(mode, &sprites, &definition["settings"], &atlas)?,
        &inputs,
        "atlas",
    )?;
    println!("{}", rt::json_canonical_view(&summary)?);
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
