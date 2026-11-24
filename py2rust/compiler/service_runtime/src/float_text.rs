//! Python-style shortest finite binary64 display, not JSON canonical formatting.
use crate::{finite, Result};

pub fn float_to_string(value: f64) -> Result<String> {
    finite(value)?;
    // serde_json uses the pinned Ryu implementation for shortest round-trip
    // digits. Rust's Debug formatter differs on some equally short halfway cases.
    let raw = serde_json::to_string(&value)?;
    let (sign, unsigned) = match raw.strip_prefix('-') {
        Some(unsigned) => ("-", unsigned),
        None => ("", raw.as_str()),
    };
    if value == 0.0 {
        return Ok(format!("{sign}0.0"));
    }
    let (mantissa, power) = match unsigned.split_once('e') {
        Some((mantissa, exponent)) => (mantissa, exponent.parse::<i32>()?),
        None => (unsigned, 0),
    };
    let point = mantissa.find('.').unwrap_or(mantissa.len()) as i32;
    let digits: String = mantissa
        .chars()
        .filter(|character| *character != '.')
        .collect();
    let leading = digits.len() - digits.trim_start_matches('0').len();
    let exponent = power + point - leading as i32 - 1;
    let significant = digits.trim_start_matches('0').trim_end_matches('0');
    // All slices are ASCII digits emitted by serde_json, never source UTF-8.
    if !(-4..16).contains(&exponent) {
        let fraction = if significant.len() > 1 {
            format!(".{}", &significant[1..])
        } else {
            String::new()
        };
        return Ok(format!(
            "{}{}{}e{:+03}",
            sign,
            &significant[..1],
            fraction,
            exponent
        ));
    }
    let position = exponent + 1;
    if position <= 0 {
        return Ok(format!(
            "{}0.{}{}",
            sign,
            "0".repeat((-position) as usize),
            significant
        ));
    }
    let position = position as usize;
    if position >= significant.len() {
        return Ok(format!(
            "{}{}{}.0",
            sign,
            significant,
            "0".repeat(position - significant.len())
        ));
    }
    Ok(format!(
        "{}{}.{}",
        sign,
        &significant[..position],
        &significant[position..]
    ))
}
