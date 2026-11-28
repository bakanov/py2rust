//! HTML5 link extraction and a bounded HTTP(S) URL boundary.
use crate::{Json, Result};
use scraper::{ElementRef, Html, Selector};
use serde_json::json;

pub fn html_links(document: &str, max_links: i64) -> Result<Json> {
    if document.len() > 1_048_576 || !(1..=10_000).contains(&max_links) {
        return Err("invalid HTML document or link limit".into());
    }
    let parsed = Html::parse_document(document);
    let selector = Selector::parse("*").map_err(|_| "invalid internal selector")?;
    let mut base = Json::Null;
    let mut links = Vec::new();
    for element in parsed.select(&selector) {
        if element.value().name.ns.as_ref() != "http://www.w3.org/1999/xhtml"
            || element
                .ancestors()
                .filter_map(ElementRef::wrap)
                .any(|parent| parent.value().name() == "template")
        {
            continue;
        }
        let tag = element.value().name();
        if tag == "base" && base.is_null() {
            if let Some(value) = element.attr("href") {
                base = json!(value);
            }
        }
        let attributes: &[&str] = match tag {
            "a" | "area" | "link" => &["href"],
            "img" | "script" | "iframe" | "audio" | "source" | "input" => &["src"],
            "video" => &["src", "poster"],
            "object" => &["data"],
            _ => &[],
        };
        for attribute in attributes {
            if let Some(value) = element.attr(attribute) {
                if links.len() >= max_links as usize {
                    return Err("HTML link limit exceeded".into());
                }
                links.push(json!({"tag": tag, "attribute": attribute, "value": value}));
            }
        }
    }
    Ok(json!({"base": base, "links": links}))
}

fn validate_reference(value: &str, absolute: bool) -> Result<()> {
    if value.len() > 8192
        || value.starts_with(' ')
        || value.ends_with(' ')
        || value.chars().any(|c| c < ' ' || c == '\u{7f}' || c == '\\')
    {
        return Err("invalid URL characters or length".into());
    }
    let bytes = value.as_bytes();
    for (index, byte) in bytes.iter().enumerate() {
        if *byte == b'%'
            && (index + 2 >= bytes.len()
                || !bytes[index + 1].is_ascii_hexdigit()
                || !bytes[index + 2].is_ascii_hexdigit())
        {
            return Err("invalid URL percent escape".into());
        }
    }
    let scheme_end = value.find(':').filter(|end| {
        *end > 0
            && value.as_bytes()[0].is_ascii_alphabetic()
            && value[..*end]
                .bytes()
                .all(|c| c.is_ascii_alphanumeric() || b"+.-".contains(&c))
    });
    let authority_start = if value.starts_with("//") && !absolute {
        Some(2)
    } else if let Some(end) = scheme_end {
        let prefix = value[..end + 1].to_ascii_lowercase();
        if !["http:", "https:"].contains(&prefix.as_str()) || !value[end + 1..].starts_with("//") {
            return Err("expected an absolute HTTP(S) URL".into());
        }
        Some(end + 3)
    } else if absolute {
        return Err("expected an absolute HTTP(S) URL".into());
    } else {
        None
    };
    if let Some(start) = authority_start {
        let authority = value[start..].split(['/', '?', '#']).next().unwrap_or("");
        let pieces: Vec<_> = authority.split(':').collect();
        if pieces.len() > 2 || pieces[0].is_empty() {
            return Err("expected a DNS name or canonical IPv4 address".into());
        }
        let host = pieces[0].strip_suffix('.').unwrap_or(pieces[0]);
        if host.len() > 253
            || !host.split('.').all(|label| {
                !label.is_empty()
                    && label.len() <= 63
                    && label
                        .bytes()
                        .all(|c| c.is_ascii_alphanumeric() || c == b'-')
                    && !label.starts_with('-')
                    && !label.ends_with('-')
            })
        {
            return Err("invalid URL hostname".into());
        }
        let last = host.rsplit('.').next().unwrap_or("").to_ascii_lowercase();
        if last.bytes().all(|c| c.is_ascii_digit())
            || last
                .strip_prefix("0x")
                .is_some_and(|suffix| suffix.bytes().all(|c| c.is_ascii_hexdigit()))
        {
            host.parse::<std::net::Ipv4Addr>()?;
        }
        if pieces.len() == 2
            && (pieces[1].is_empty()
                || pieces[1].len() > 5
                || !pieces[1].bytes().all(|c| c.is_ascii_digit())
                || pieces[1].parse::<u16>()? == 0)
        {
            return Err("invalid URL port".into());
        }
    }
    Ok(())
}

pub fn url_resolve(base: &str, reference: &str) -> Result<String> {
    validate_reference(base, true)?;
    validate_reference(reference, false)?;
    let mut result = url::Url::parse(base)?.join(reference)?;
    result.set_fragment(None);
    let text = result.as_str().as_bytes();
    let mut output = String::new();
    let mut index = 0;
    while index < text.len() {
        if text[index] == b'%' {
            output.push('%');
            output.push(text[index + 1].to_ascii_uppercase() as char);
            output.push(text[index + 2].to_ascii_uppercase() as char);
            index += 3;
        } else {
            output.push(text[index] as char);
            index += 1;
        }
    }
    if output.len() > 8192 {
        return Err("resolved URL exceeds 8192 bytes".into());
    }
    Ok(output)
}
pub fn url_origin(value: &str) -> Result<String> {
    let value = url::Url::parse(&url_resolve(value, "")?)?;
    Ok(value.origin().ascii_serialization())
}
