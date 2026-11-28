//! Runtime for the opt-in service profile; public functions define its contract.
use chrono::{Datelike, SecondsFormat, TimeDelta, Timelike, Utc};
use serde::Serialize;
use serde_json::Value;
use std::io::Write;
use std::sync::{
    atomic::{AtomicI64, Ordering},
    OnceLock,
};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

pub type Result<T> = std::result::Result<T, Box<dyn std::error::Error + Send + Sync>>;
pub type Json = Value;
pub type DateTime = chrono::DateTime<Utc>;
pub fn ord_text(value: &str) -> Result<i64> {
    let mut characters = value.chars();
    let first = characters
        .next()
        .ok_or("ord requires exactly one character")?;
    if characters.next().is_some() {
        return Err("ord requires exactly one character".into());
    }
    Ok(first as u32 as i64)
}
pub fn ord_bytes(value: &[u8]) -> Result<i64> {
    if value.len() != 1 {
        return Err("ord requires exactly one byte".into());
    }
    Ok(value[0] as i64)
}
mod float_text;
pub use float_text::float_to_string;
mod random;
pub use random::{random_default, random_new, random_random, random_randrange, Random};
mod rational;
pub use rational::{
    rational_add, rational_compare, rational_decimal, rational_denominator, rational_div,
    rational_fixed, rational_mul, rational_new, rational_numerator, rational_sub, Rational,
};
mod compression;
pub use compression::{decode_cp437, deflate_decompress};
mod terminal;
mod terminal_tables;
pub use terminal::{terminal_cells, terminal_info, terminal_write};
mod unique_json;
pub use unique_json::json_loads_unique;
mod timezones;
pub use timezones::{timezone_local, timezone_project};
mod byte_buffers;
pub use byte_buffers::{
    byte_buffer_append, byte_buffer_checked, byte_buffer_copy, byte_buffer_extend,
    byte_buffer_from_ints, byte_buffer_new, byte_value,
};
mod casefold;
pub use casefold::casefold;
mod heaps;
pub use heaps::{heapify, heappop, heappush, heappushpop, heapreplace};
mod sorting;
pub use sorting::{sorted_by_comparable_key, sorted_by_float_key, sorted_by_key};
pub fn unicode_normalize(form: &str, text: &str) -> Result<String> {
    use unicode_normalization::UnicodeNormalization;
    // CPython returns empty input before checking the normalization form.
    if text.is_empty() {
        return Ok(String::new());
    }
    match form {
        "NFC" => Ok(text.nfc().collect()),
        "NFD" => Ok(text.nfd().collect()),
        "NFKC" => Ok(text.nfkc().collect()),
        "NFKD" => Ok(text.nfkd().collect()),
        _ => Err("invalid normalization form".into()),
    }
}
pub fn base64_encode(data: &[u8]) -> Result<String> {
    use base64::Engine;
    if data.len() > 1048576 {
        return Err("codec input exceeds 1 MiB".into());
    }
    Ok(base64::engine::general_purpose::STANDARD.encode(data))
}
pub fn base64_decode(text: &str) -> Result<Vec<u8>> {
    use base64::Engine;
    if text.len() > 1398104 {
        return Err("encoded input exceeds the 1 MiB decoded limit".into());
    }
    let data = base64::engine::general_purpose::STANDARD
        .decode(text)
        .map_err(|_| "expected canonical padded base64")?;
    if data.len() > 1048576 {
        return Err("codec input exceeds 1 MiB".into());
    }
    Ok(data)
}
const fn crc32_table() -> [u32; 256] {
    let mut table = [0u32; 256];
    let mut index = 0;
    while index < table.len() {
        let mut value = index as u32;
        let mut bit = 0;
        while bit < 8 {
            value = if value & 1 != 0 {
                (value >> 1) ^ 0xedb88320
            } else {
                value >> 1
            };
            bit += 1;
        }
        table[index] = value;
        index += 1;
    }
    table
}

pub fn crc32(data: &[u8], value: i64) -> i64 {
    const TABLE: [u32; 256] = crc32_table();
    // Python masks the optional previous checksum to its low 32 bits.
    let mut checksum = !(value as u32);
    for &byte in data {
        checksum = TABLE[((checksum as u8) ^ byte) as usize] ^ (checksum >> 8);
    }
    (!checksum) as i64
}

pub fn struct_pack_float(value: f64) -> Result<Vec<u8>> {
    if !value.is_finite() || value.abs() > f32::MAX as f64 {
        return Err("float does not fit <f".into());
    }
    Ok((value as f32).to_le_bytes().to_vec())
}

pub fn struct_unpack_float(data: &[u8]) -> Result<f64> {
    let bytes: [u8; 4] = data
        .try_into()
        .map_err(|_| "<f requires exactly four bytes")?;
    Ok(f32::from_le_bytes(bytes) as f64)
}

fn struct_integer_fields(format: &str) -> Result<(bool, Vec<(char, usize)>)> {
    let (little, codes) = match format.as_bytes().first() {
        Some(b'<') => (true, &format[1..]),
        Some(b'>') | Some(b'!') => (false, &format[1..]),
        Some(b'@') | Some(b'=') => (cfg!(target_endian = "little"), &format[1..]),
        _ => (cfg!(target_endian = "little"), format),
    };
    let mut fields = Vec::new();
    let mut count = String::new();
    for code in codes.chars() {
        if code.is_ascii_digit() {
            count.push(code);
            continue;
        }
        if !matches!(code, 'b' | 'B' | 'h' | 'H' | 'i' | 'I' | 'q' | 'Q') {
            return Err("unsupported integer struct format".into());
        }
        let repeat = if count.is_empty() {
            1
        } else {
            count.parse::<usize>()?
        };
        fields.extend(std::iter::repeat_n((code, 1), repeat));
        count.clear();
    }
    if !count.is_empty() {
        return Err("incomplete integer struct format".into());
    }
    Ok((little, fields))
}

fn struct_integer_width(code: char) -> usize {
    match code {
        'b' | 'B' => 1,
        'h' | 'H' => 2,
        'i' | 'I' => 4,
        _ => 8,
    }
}

pub fn struct_pack_ints(format: &str, values: &[i64]) -> Result<Vec<u8>> {
    let (little, fields) = struct_integer_fields(format)?;
    if fields.len() != values.len() {
        return Err("integer struct field count does not match arguments".into());
    }
    let mut result = Vec::new();
    for (&value, &(code, _)) in values.iter().zip(&fields) {
        let signed = code.is_ascii_lowercase();
        let width = struct_integer_width(code);
        let valid = if signed {
            let bits = width * 8;
            bits == 64 || value >= -(1_i64 << (bits - 1)) && value < (1_i64 << (bits - 1))
        } else {
            value >= 0 && (width == 8 || (value as u64) < (1_u64 << (width * 8)))
        };
        if !valid {
            return Err("integer does not fit struct field".into());
        }
        let bytes = value.to_le_bytes();
        result.extend_from_slice(if little {
            &bytes[..width]
        } else {
            &bytes[8 - width..]
        });
    }
    Ok(result)
}

pub fn struct_unpack_ints(format: &str, data: &[u8], offset: i64) -> Result<Vec<i64>> {
    let (little, fields) = struct_integer_fields(format)?;
    let mut position = usize::try_from(offset).map_err(|_| "negative struct offset")?;
    let mut result = Vec::new();
    for &(code, _) in &fields {
        let width = struct_integer_width(code);
        let end = position
            .checked_add(width)
            .ok_or("struct offset overflow")?;
        let source = data.get(position..end).ok_or("struct data is too short")?;
        let mut bytes = [0_u8; 8];
        if little {
            bytes[..width].copy_from_slice(source);
        } else {
            bytes[8 - width..].copy_from_slice(source);
        }
        let unsigned = u64::from_le_bytes(bytes);
        let value = if code.is_ascii_lowercase()
            && width < 8
            && source[if little { width - 1 } else { 0 }] & 0x80 != 0
        {
            (unsigned | (!0_u64 << (width * 8))) as i64
        } else {
            unsigned as i64
        };
        result.push(value);
        position = end;
    }
    Ok(result)
}

pub fn heap_float_push<T>(heap: &mut Vec<(f64, i64, T)>, item: (f64, i64, T)) {
    heap.push(item);
    heap.sort_by(|left, right| left.0.total_cmp(&right.0).then(left.1.cmp(&right.1)));
}

pub fn heap_float_pop<T>(heap: &mut Vec<(f64, i64, T)>) -> Result<(f64, i64, T)> {
    if heap.is_empty() {
        return Err("index out of range".into());
    }
    Ok(heap.remove(0))
}

pub fn int_float(value: f64) -> Result<i64> {
    if !value.is_finite() || value < i64::MIN as f64 || value > i64::MAX as f64 {
        return Err("float is outside the integer range".into());
    }
    Ok(value.trunc() as i64)
}

pub fn round_float(value: f64) -> Result<i64> {
    if !value.is_finite() || value < i64::MIN as f64 || value > i64::MAX as f64 {
        return Err("rounded float is outside the integer range".into());
    }
    Ok(value.round_ties_even() as i64)
}

pub fn divmod_int(value: i64, divisor: i64) -> Result<(i64, i64)> {
    if divisor == 0 {
        return Err("integer division or modulo by zero".into());
    }
    let mut quotient = value
        .checked_div(divisor)
        .ok_or("integer division overflow")?;
    let mut remainder = value
        .checked_rem(divisor)
        .ok_or("integer remainder overflow")?;
    if remainder != 0 && (remainder < 0) != (divisor < 0) {
        quotient -= 1;
        remainder += divisor;
    }
    Ok((quotient, remainder))
}

pub fn string_capitalize(value: &str) -> String {
    let mut characters = value.chars();
    let Some(first) = characters.next() else {
        return String::new();
    };
    first
        .to_uppercase()
        .chain(characters.flat_map(char::to_lowercase))
        .collect()
}

pub fn string_remove_prefix(value: &str, prefix: &str) -> String {
    value.strip_prefix(prefix).unwrap_or(value).to_string()
}

pub fn string_remove_suffix(value: &str, suffix: &str) -> String {
    value.strip_suffix(suffix).unwrap_or(value).to_string()
}

pub fn range_values(start: i64, stop: i64, step: i64) -> Result<Vec<i64>> {
    if step == 0 {
        return Err("range() arg 3 must not be zero".into());
    }
    let mut result = Vec::new();
    let mut value = start;
    while step > 0 && value < stop || step < 0 && value > stop {
        result.push(value);
        value = value.checked_add(step).ok_or("range overflow")?;
    }
    Ok(result)
}

pub fn bytes_split(data: &[u8], separator: &[u8], maxsplit: i64) -> Vec<Vec<u8>> {
    if separator.is_empty() || maxsplit == 0 {
        return vec![data.to_vec()];
    }
    let limit = if maxsplit < 0 {
        usize::MAX
    } else {
        maxsplit as usize
    };
    let mut result = Vec::new();
    let mut start = 0;
    while result.len() < limit {
        let Some(relative) = data[start..]
            .windows(separator.len())
            .position(|window| window == separator)
        else {
            break;
        };
        let end = start + relative;
        result.push(data[start..end].to_vec());
        start = end + separator.len();
    }
    result.push(data[start..].to_vec());
    result
}

pub fn decode_latin1(data: &[u8]) -> String {
    data.iter().map(|&byte| char::from(byte)).collect()
}

pub fn decode_ascii(data: &[u8]) -> Result<String> {
    if !data.is_ascii() {
        return Err("invalid ASCII input".into());
    }
    Ok(String::from_utf8(data.to_vec())?)
}

pub fn decode_bytes(data: &[u8], encoding: &str, errors: &str) -> Result<String> {
    if !matches!(errors, "strict" | "replace") {
        return Err("decode errors must be strict or replace".into());
    }
    match encoding {
        "utf-8" | "utf8" => Ok(if errors == "replace" {
            String::from_utf8_lossy(data).into_owned()
        } else {
            String::from_utf8(data.to_vec())?
        }),
        "latin-1" | "latin1" | "iso-8859-1" | "iso8859-1" => Ok(decode_latin1(data)),
        "cp437" | "437" | "ibm437" => Ok(decode_cp437(data)),
        "ascii" => {
            if errors == "replace" {
                Ok(data
                    .iter()
                    .map(|&byte| {
                        if byte < 128 {
                            char::from(byte)
                        } else {
                            '\u{fffd}'
                        }
                    })
                    .collect())
            } else {
                decode_ascii(data)
            }
        }
        "cp1252" | "windows-1252" => {
            const EXTENDED: [char; 32] = [
                '\u{20ac}', '\u{fffd}', '\u{201a}', '\u{192}', '\u{201e}', '\u{2026}', '\u{2020}',
                '\u{2021}', '\u{2c6}', '\u{2030}', '\u{160}', '\u{2039}', '\u{152}', '\u{fffd}',
                '\u{17d}', '\u{fffd}', '\u{fffd}', '\u{2018}', '\u{2019}', '\u{201c}', '\u{201d}',
                '\u{2022}', '\u{2013}', '\u{2014}', '\u{2dc}', '\u{2122}', '\u{161}', '\u{203a}',
                '\u{153}', '\u{fffd}', '\u{17e}', '\u{178}',
            ];
            let mut output = String::new();
            for &byte in data {
                let character = match byte {
                    0x80..=0x9f => EXTENDED[(byte - 0x80) as usize],
                    _ => char::from(byte),
                };
                if character == '\u{fffd}' && errors == "strict" {
                    return Err("invalid CP1252 input".into());
                }
                output.push(character);
            }
            Ok(output)
        }
        _ => Err("unsupported text encoding".into()),
    }
}

pub fn sha1_digest(data: &[u8]) -> Result<Vec<u8>> {
    if data.len() > 1048576 {
        return Err("codec input exceeds 1 MiB".into());
    }
    // This legacy digest is required by protocols such as the WebSocket handshake.
    Ok(
        ring::digest::digest(&ring::digest::SHA1_FOR_LEGACY_USE_ONLY, data)
            .as_ref()
            .to_vec(),
    )
}
pub fn bytes_xor(data: &[u8], key: &[u8]) -> Result<Vec<u8>> {
    if data.len() > 1048576 || key.is_empty() || key.len() > 4096 {
        return Err("XOR requires at most 1 MiB and a 1..4096-byte key".into());
    }
    Ok(data
        .iter()
        .enumerate()
        .map(|(index, value)| value ^ key[index % key.len()])
        .collect())
}
#[inline]
pub fn wrapping_add(left: i64, right: i64) -> i64 {
    left.wrapping_add(right)
}
#[inline]
pub fn wrapping_sub(left: i64, right: i64) -> i64 {
    left.wrapping_sub(right)
}
#[inline]
pub fn wrapping_mul(left: i64, right: i64) -> i64 {
    left.wrapping_mul(right)
}
#[inline]
#[track_caller]
pub fn int_lshift(value: i64, count: i64) -> Result<i64> {
    let location = std::panic::Location::caller();
    if count < 0 {
        return Err("negative shift count".into());
    }
    if value == 0 {
        return Ok(0);
    }
    if count >= 64 {
        return Err(format!("integer overflow: {value} << {count} at {location}").into());
    }
    Ok(i64::try_from((value as i128) << count)
        .map_err(|_| format!("integer overflow: {value} << {count} at {location}"))?)
}
#[inline]
pub fn int_rshift(value: i64, count: i64) -> Result<i64> {
    if count < 0 {
        return Err("negative shift count".into());
    }
    if count >= 64 {
        return Ok(if value < 0 { -1 } else { 0 });
    }
    Ok(value >> count)
}
pub fn int_from_decimal(text: &str) -> Result<i64> {
    if text.len() > 4096 || !text.is_ascii() {
        return Err("decimal input must contain at most 4096 ASCII bytes".into());
    }
    let value = text.trim_matches([' ', '\t', '\n', '\r', '\u{000b}', '\u{000c}']);
    let digits = value.strip_prefix(['+', '-']).unwrap_or(value);
    if digits.is_empty() || !digits.bytes().all(|byte| byte.is_ascii_digit()) {
        return Err("expected signed decimal digits".into());
    }
    Ok(value.parse::<i64>()?)
}
pub fn float_from_decimal(text: &str) -> Result<f64> {
    if text.len() > 4096 || !text.is_ascii() {
        return Err("decimal input must contain at most 4096 ASCII bytes".into());
    }
    let value = text.trim_matches([' ', '\t', '\n', '\r', '\u{000b}', '\u{000c}']);
    // Match Python's decimal spelling, including underscores only between digits.
    // NaN/infinity are outside the finite numeric profile, as are hexadecimal floats.
    static DECIMAL: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    let grammar = DECIMAL.get_or_init(|| {
        regex::Regex::new(r"\A[+-]?(?:[0-9](?:_?[0-9])*(?:\.(?:[0-9](?:_?[0-9])*)?)?|\.[0-9](?:_?[0-9])*)(?:[eE][+-]?[0-9](?:_?[0-9])*)?\z")
            .expect("fixed decimal float grammar")
    });
    if !grammar.is_match(value) {
        return Err("expected finite decimal floating point text".into());
    }
    finite(value.replace('_', "").parse::<f64>()?)
}
pub fn ceil(value: f64) -> Result<i64> {
    let rounded = finite(value)?.ceil();
    if rounded < i64::MIN as f64 || rounded >= -(i64::MIN as f64) {
        return Err("ceiling result is outside signed 64-bit range".into());
    }
    Ok(rounded as i64)
}
pub fn floor(value: f64) -> Result<i64> {
    let rounded = finite(value)?.floor();
    if rounded < i64::MIN as f64 || rounded >= -(i64::MIN as f64) {
        return Err("floor result is outside signed 64-bit range".into());
    }
    Ok(rounded as i64)
}
pub fn math_log(value: f64) -> Result<f64> {
    if finite(value)? <= 0.0 {
        return Err("logarithm requires a positive finite number".into());
    }
    finite(value.ln())
}
pub fn math_sqrt(value: f64) -> Result<f64> {
    if finite(value)? < 0.0 {
        return Err("square root requires a nonnegative finite number".into());
    }
    finite(value.sqrt())
}

pub fn math_isfinite(value: f64) -> bool {
    value.is_finite()
}

pub fn math_sin(value: f64) -> Result<f64> {
    finite(finite(value)?.sin())
}

pub fn math_cos(value: f64) -> Result<f64> {
    finite(finite(value)?.cos())
}

pub fn math_atan2(y: f64, x: f64) -> Result<f64> {
    finite(finite(y)?.atan2(finite(x)?))
}

pub fn math_ldexp(value: f64, exponent: i64) -> Result<f64> {
    let exponent = i32::try_from(exponent)
        .map_err(|_| "floating-point exponent is outside supported range")?;
    finite(finite(value)? * 2.0_f64.powi(exponent))
}
pub fn int_floor_div(left: i64, right: i64) -> Result<i64> {
    if right == 0 {
        return Err("integer division by zero".into());
    }
    let (left, right) = (left as i128, right as i128);
    let mut quotient = left / right;
    let remainder = left % right;
    if remainder != 0 && (remainder < 0) != (right < 0) {
        quotient -= 1;
    }
    Ok(i64::try_from(quotient).map_err(|_| "integer overflow")?)
}
/// Round the exact signed-i64 ratio once, using binary64 ties-to-even.
/// Casting both operands to f64 first can double-round values above 2^53.
pub fn int_true_div(left: i64, right: i64) -> Result<f64> {
    if right == 0 {
        return Err("division by zero".into());
    }
    let sign = u64::from((left < 0) != (right < 0)) << 63;
    let numerator = u128::from(left.unsigned_abs());
    let denominator = u128::from(right.unsigned_abs());
    if numerator == 0 {
        return Ok(f64::from_bits(sign));
    }
    let mut exponent = numerator.ilog2() as i32 - denominator.ilog2() as i32;
    let below_power = if exponent >= 0 {
        numerator < (denominator << exponent)
    } else {
        (numerator << -exponent) < denominator
    };
    if below_power {
        exponent -= 1;
    }
    // Ratios of nonzero i64 magnitudes have exponents in -63..=63. Scaling
    // to a 53-bit significand needs at most 117 bits, so u128 is sufficient.
    let shift = 52 - exponent;
    let (scaled, divisor) = if shift >= 0 {
        (numerator << shift, denominator)
    } else {
        (numerator, denominator << -shift)
    };
    let mut significand = scaled / divisor;
    let twice_remainder = 2 * (scaled % divisor);
    if twice_remainder > divisor || (twice_remainder == divisor && significand & 1 != 0) {
        significand += 1;
    }
    if significand == 1 << 53 {
        significand >>= 1;
        exponent += 1;
    }
    let bits = sign | (((exponent + 1023) as u64) << 52) | ((significand as u64) & ((1 << 52) - 1));
    Ok(f64::from_bits(bits))
}
pub fn float_true_div(left: f64, right: f64) -> Result<f64> {
    finite(left)?;
    finite(right)?;
    if right == 0.0 {
        return Err("float division by zero".into());
    }
    finite(left / right)
}
pub fn int_modulo(left: i64, right: i64) -> Result<i64> {
    if right == 0 {
        return Err("integer modulo by zero".into());
    }
    let divisor = right as i128;
    let mut remainder = (left as i128) % divisor;
    if remainder != 0 && (remainder < 0) != (divisor < 0) {
        remainder += divisor;
    }
    Ok(i64::try_from(remainder)?)
}
pub fn limit_address_space(maximum: i64) -> Result<i64> {
    if !(33554432..=17179869184).contains(&maximum) {
        return Err("address-space limit must be 32 MiB..16 GiB".into());
    }
    #[cfg(unix)]
    {
        let mut limits = libc::rlimit {
            rlim_cur: 0,
            rlim_max: 0,
        };
        // Both calls borrow a valid, initialized rlimit for the current process.
        if unsafe { libc::getrlimit(libc::RLIMIT_AS, &mut limits) } != 0 {
            return Err(std::io::Error::last_os_error().into());
        }
        let desired = libc::rlim_t::try_from(maximum)?;
        if limits.rlim_cur == libc::RLIM_INFINITY || desired < limits.rlim_cur {
            limits.rlim_cur = desired;
            if unsafe { libc::setrlimit(libc::RLIMIT_AS, &limits) } != 0 {
                return Err(std::io::Error::last_os_error().into());
            }
        }
        Ok(i64::try_from(limits.rlim_cur)?)
    }
    #[cfg(not(unix))]
    Err("address-space limits require Unix".into())
}

pub fn process_exit(code: i64) -> Result<()> {
    use std::io::Write;
    std::io::stdout().flush()?;
    std::io::stderr().flush()?;
    std::process::exit(code.rem_euclid(256) as i32);
}
pub enum TryFlow<T> {
    Continue,
    Return(T),
}
pub fn assertion(condition: bool, message: &str) -> Result<()> {
    if condition {
        Ok(())
    } else {
        Err(message.to_string().into())
    }
}
pub fn bytes_from_hex(text: &str) -> Result<Vec<u8>> {
    let source = text.as_bytes();
    let mut output = Vec::new();
    let mut index = 0;
    while index < source.len() {
        // Python allows ASCII whitespace between complete bytes, not nibbles.
        if matches!(source[index], b' ' | b'\t' | b'\n' | b'\r' | 0x0b | 0x0c) {
            index += 1;
            continue;
        }
        let high = (source[index] as char)
            .to_digit(16)
            .ok_or("invalid hex digit")?;
        index += 1;
        let low = (*source.get(index).ok_or("incomplete hex byte")? as char)
            .to_digit(16)
            .ok_or("invalid hex digit")?;
        output.push((high * 16 + low) as u8);
        index += 1;
    }
    Ok(output)
}
pub fn bytes_hex(data: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(data.len() * 2);
    for byte in data {
        output.push(DIGITS[(byte >> 4) as usize] as char);
        output.push(DIGITS[(byte & 15) as usize] as char);
    }
    output
}
pub fn json_contains_string(value: &Json, needle: &str) -> Result<bool> {
    match value {
        Value::Object(object) => Ok(object.contains_key(needle)),
        Value::Array(array) => Ok(array.iter().any(|item| item.as_str() == Some(needle))),
        Value::String(text) => Ok(text.contains(needle)),
        _ => Err("JSON value is not a container".into()),
    }
}
pub fn json_keys(value: &Json) -> Result<Vec<String>> {
    let object = value.as_object().ok_or("expected JSON object")?;
    let mut keys: Vec<_> = object.keys().cloned().collect();
    keys.sort();
    Ok(keys)
}
pub fn json_equal(left: &Json, right: &Json) -> bool {
    fn integer_float(integer: i64, float: f64) -> bool {
        (-9223372036854775808.0..9223372036854775808.0).contains(&float)
            && float.trunc() == float
            && float as i64 == integer
    }
    match (left, right) {
        (Value::Number(a), Value::Number(b)) => match (a.as_i64(), b.as_i64()) {
            (Some(a), Some(b)) => a == b,
            (Some(a), None) => b.as_f64().is_some_and(|b| integer_float(a, b)),
            (None, Some(b)) => a.as_f64().is_some_and(|a| integer_float(b, a)),
            (None, None) => a.as_f64() == b.as_f64(),
        },
        (Value::Array(a), Value::Array(b)) => {
            a.len() == b.len() && a.iter().zip(b).all(|(a, b)| json_equal(a, b))
        }
        (Value::Object(a), Value::Object(b)) => {
            a.len() == b.len()
                && a.iter()
                    .all(|(key, value)| b.get(key).is_some_and(|other| json_equal(value, other)))
        }
        _ => left == right,
    }
}
pub fn json_scalar_compare(left: &Json, right: &Json) -> Result<i64> {
    use std::cmp::Ordering;
    fn integer_float(integer: i64, float: f64) -> Ordering {
        if float < -9223372036854775808.0 {
            Ordering::Greater
        } else if float >= 9223372036854775808.0 {
            Ordering::Less
        } else {
            let order = integer.cmp(&(float as i64));
            if order != Ordering::Equal {
                order
            } else if (integer as f64) < float {
                Ordering::Less
            } else if (integer as f64) > float {
                Ordering::Greater
            } else {
                Ordering::Equal
            }
        }
    }
    let order = match (left, right) {
        (Json::Null, Json::Null) => Ordering::Equal,
        (Json::Bool(a), Json::Bool(b)) => a.cmp(b),
        (Json::String(a), Json::String(b)) => a.cmp(b),
        (Json::Number(a), Json::Number(b)) => match (a.as_i64(), b.as_i64()) {
            (Some(a), Some(b)) => a.cmp(&b),
            (Some(a), None) => integer_float(a, json_float(right)?),
            (None, Some(b)) => integer_float(b, json_float(left)?).reverse(),
            (None, None) => json_float(left)?
                .partial_cmp(&json_float(right)?)
                .ok_or("expected finite JSON numbers")?,
        },
        _ => return Err("expected compatible JSON scalars".into()),
    };
    Ok(match order {
        Ordering::Less => -1,
        Ordering::Equal => 0,
        Ordering::Greater => 1,
    })
}
pub fn json_number_add(left: &Json, right: &Json) -> Result<Json> {
    let a = left.as_number().ok_or("expected JSON numbers")?;
    let b = right.as_number().ok_or("expected JSON numbers")?;
    if let (Some(a), Some(b)) = (a.as_i64(), b.as_i64()) {
        return Ok(Json::from(a.checked_add(b).ok_or("integer overflow")?));
    }
    to_json(&finite(json_float(left)? + json_float(right)?)?)
}
pub fn path_resolve(path: &str) -> Result<String> {
    Ok(std::fs::canonicalize(path)?
        .into_os_string()
        .into_string()
        .map_err(|_| "canonical path is not UTF-8")?)
}
mod filesystem;
mod http;
mod http_dates;
mod markup;
mod parallel;
mod process_pool;
mod processes;
pub use process_pool::{
    process_poll, process_pool, process_pool_close, process_pool_signal, process_signal,
    process_spawn, ProcessPool,
};
mod python_ast;
mod python_identifiers;
mod resources;
mod tcp;
mod udp;
#[cfg(unix)]
mod unix;
pub use filesystem::{
    create_symlink, directory_names, mkdir_new, path_set_metadata, path_stat, read_link,
    rename_no_replace, replace_file,
};
pub use http::{
    http_listen, http_port, http_request, http_serve_json, http_serve_json_timeout, https_listen,
    https_request_ca, web_close, web_open, web_open_ca, web_read, web_request, web_request_ca,
    HttpReader, HttpResponse, HttpServer,
};
pub use http_dates::http_retry_after;
pub use markup::{html_links, url_origin, url_resolve};
pub use parallel::parallel_map;
pub use processes::{process_pipeline, process_run};
mod python_syntax;
pub use python_ast::{python_statement_tree, python_syntax_tree};
pub use resources::{
    file_close, file_lock, file_open, file_read, file_seek, file_size, file_sync, file_truncate,
    file_write, line_close, line_open, line_position, line_read, link_file, path_is_symlink,
    path_name, path_parent, path_same, sha256_digest, sha256_new, sha256_update, sync_directory,
    FileHandle, LineReader, ResourceGuard, Sha256,
};
pub use tcp::{
    int_from_bytes, int_from_bytes_signed, int_to_bytes, tcp_accept_ready, tcp_accept_timeout,
    tcp_close, tcp_close_listener, tcp_connect, tcp_listen, tcp_port, tcp_recv, tcp_recv_ready,
    tcp_select, tcp_send_buffer, tcp_send_ready, tcp_sendall, tcp_set_deadline, tcp_shutdown_write,
    TcpListener, TcpStream,
};
pub use udp::{udp_bind, udp_close, udp_port, udp_recvfrom, udp_sendto, UdpSocket};
#[cfg(unix)]
pub use unix::{
    unix_accept_ready, unix_accept_timeout, unix_close, unix_close_listener, unix_connect,
    unix_listen, unix_recv, unix_recv_ready, unix_select, unix_send_buffer, unix_send_ready,
    unix_sendall, unix_set_deadline, unix_shutdown_write, UnixListener, UnixStream,
};

fn json_check(value: &Value, depth: usize) -> Result<()> {
    if depth > 64 {
        return Err("JSON nesting exceeds 64".into());
    }
    match value {
        Value::Number(n) => {
            // Preserve the original token, so enormous integers cannot silently
            // fall back to floating point during deserialization.
            if n.to_string().contains(['.', 'e', 'E']) {
                if n.as_f64().filter(|v| v.is_finite()).is_none() {
                    return Err("non-finite JSON number".into());
                }
            } else if n.as_i64().is_none() {
                return Err("JSON integers must fit signed 64 bits".into());
            }
        }
        Value::Array(a) => {
            for v in a {
                json_check(v, depth + 1)?;
            }
        }
        Value::Object(o) => {
            for v in o.values() {
                json_check(v, depth + 1)?;
            }
        }
        _ => (),
    }
    Ok(())
}
pub fn json_loads(text: &str) -> Result<Json> {
    let value = unique_json::parse(text, 0, false)?;
    json_check(&value, 0)?;
    Ok(value)
}
/// Transfer existing JSON elements while retaining the normal conversion checks.
pub fn json_from_array(values: Vec<Json>) -> Result<Json> {
    let value = Value::Array(values);
    json_check(&value, 0)?;
    Ok(value)
}
pub fn to_json<T: Serialize + ?Sized>(value: &T) -> Result<Json> {
    let value = serde_json::to_value(value)?;
    json_check(&value, 0)?;
    Ok(value)
}
pub fn json_dumps<T: Serialize + ?Sized>(value: &T) -> Result<String> {
    Ok(serde_json::to_string(&to_json(value)?)?)
}
/// Stable subset JSON for fingerprints; distinct from shortest-display formatting.
/// Finite binary64 values use 17 significant digits and a normalized exponent.
pub fn json_canonical<T: Serialize + ?Sized>(value: &T) -> Result<String> {
    render_json_canonical(&to_json(value)?)
}

/// Validate and render the existing tree without cloning it.
pub fn json_canonical_view(value: &Json) -> Result<String> {
    json_check(value, 0)?;
    render_json_canonical(value)
}

fn render_json_canonical(value: &Json) -> Result<String> {
    fn render(value: &Value, output: &mut String) -> Result<()> {
        match value {
            Value::Number(number) if number.to_string().contains(['.', 'e', 'E']) => {
                let value = number.as_f64().ok_or("expected finite float")?;
                let scientific = format!("{value:.16e}");
                let (mantissa, exponent) =
                    scientific.split_once('e').ok_or("invalid float format")?;
                output.push_str(mantissa.trim_end_matches('0').trim_end_matches('.'));
                output.push('e');
                output.push_str(&exponent.parse::<i32>()?.to_string());
            }
            Value::Number(number) => {
                output.push_str(
                    &number
                        .as_i64()
                        .ok_or("expected signed integer")?
                        .to_string(),
                );
            }
            Value::Array(items) => {
                output.push('[');
                for (index, item) in items.iter().enumerate() {
                    if index != 0 {
                        output.push(',');
                    }
                    render(item, output)?;
                }
                output.push(']');
            }
            Value::Object(items) => {
                output.push('{');
                let mut keys: Vec<_> = items.keys().collect();
                keys.sort();
                for (index, key) in keys.iter().enumerate() {
                    if index != 0 {
                        output.push(',');
                    }
                    output.push_str(&serde_json::to_string(key)?);
                    output.push(':');
                    render(&items[*key], output)?;
                }
                output.push('}');
            }
            _ => output.push_str(&serde_json::to_string(value)?),
        }
        Ok(())
    }
    let mut output = String::new();
    render(value, &mut output)?;
    Ok(output)
}
pub fn pretty<T: Serialize + ?Sized>(value: &T) -> Result<String> {
    Ok(serde_json::to_string_pretty(&to_json(value)?)?)
}
mod json_output;
mod map_positions;
pub use json_output::{json_dumps_view, pretty_view};
pub use map_positions::{cached_map_get, cached_map_insert, cached_map_position};

pub fn json_string_ref(value: &Json) -> Result<&str> {
    Ok(value.as_str().ok_or("expected JSON string")?)
}
pub fn cached_json_string<'a>(
    cache: &'a std::cell::OnceCell<String>,
    value: &Json,
    key: &str,
) -> Result<&'a str> {
    if let Some(text) = cache.get() {
        return Ok(text.as_str());
    }
    // Validate only on the original control-flow path. Failed projections are
    // not cached, so a handler can retry without suppressing checked errors.
    let text = json_string_ref(json_key_ref(value, key)?)?.to_owned();
    let _ = cache.set(text);
    Ok(cache
        .get()
        .expect("projection cache was initialized")
        .as_str())
}
pub fn json_string(value: &Json) -> Result<String> {
    Ok(value.as_str().ok_or("expected JSON string")?.to_string())
}
#[track_caller]
pub fn json_int(value: &Json) -> Result<i64> {
    let location = std::panic::Location::caller();
    Ok(value
        .as_i64()
        .ok_or_else(|| format!("expected JSON integer: {value} at {location}"))?)
}
pub fn json_bool(value: &Json) -> Result<bool> {
    Ok(value.as_bool().ok_or("expected JSON boolean")?)
}
pub fn json_float(value: &Json) -> Result<f64> {
    finite(value.as_f64().ok_or("expected JSON number")?)
}
pub fn json_is_null(value: &Json) -> bool {
    value.is_null()
}
pub fn json_array_ref(value: &Json) -> Result<&[Json]> {
    Ok(value.as_array().ok_or("expected JSON array")?.as_slice())
}
pub fn json_object(value: &Json) -> Result<indexmap::IndexMap<String, Json>> {
    match value {
        Json::Object(entries) => Ok(entries
            .iter()
            .map(|(key, value)| (key.clone(), value.clone()))
            .collect()),
        _ => Err("expected a JSON object".into()),
    }
}

pub fn json_array(value: &Json) -> Result<Vec<Json>> {
    Ok(json_array_ref(value)?.to_vec())
}
pub fn json_get(value: &Json, key: &str, default: &Json) -> Result<Json> {
    Ok(value
        .as_object()
        .ok_or("expected JSON object")?
        .get(key)
        .unwrap_or(default)
        .clone())
}
#[track_caller]
pub fn json_key_ref<'a>(value: &'a Json, key: &str) -> Result<&'a Json> {
    let location = std::panic::Location::caller();
    Ok(value
        .as_object()
        .ok_or("expected JSON object")?
        .get(key)
        .ok_or_else(|| format!("missing JSON key {key:?} at {location}"))?)
}
pub fn json_index_ref(value: &Json, position: i64) -> Result<&Json> {
    let values = value.as_array().ok_or("expected JSON array")?;
    Ok(&values[index(values.len(), position)?])
}
pub fn json_key(value: &Json, key: &str) -> Result<Json> {
    Ok(json_key_ref(value, key)?.clone())
}
pub fn json_index(value: &Json, position: i64) -> Result<Json> {
    Ok(json_index_ref(value, position)?.clone())
}

pub fn clamp_index(length: usize, index: i64) -> usize {
    let adjusted = if index < 0 {
        length as i64 + index
    } else {
        index
    };
    adjusted.max(0).min(length as i64) as usize
}

#[track_caller]
pub fn index(length: usize, index: i64) -> Result<usize> {
    let location = std::panic::Location::caller();
    let index = if index < 0 {
        length as i64 + index
    } else {
        index
    };
    if index < 0 || index as usize >= length {
        return Err(
            format!("index out of range: {index} for length {length} at {location}").into(),
        );
    }
    Ok(index as usize)
}
pub fn index_of<T: PartialEq>(values: &[T], value: &T) -> Result<i64> {
    values
        .iter()
        .position(|item| item == value)
        .map(|index| index as i64)
        .ok_or_else(|| "value is not in sequence".into())
}

#[track_caller]
pub fn at<T: Clone>(values: &[T], i: i64) -> Result<T> {
    let location = std::panic::Location::caller();
    let position = index(values.len(), i).map_err(|error| format!("{error}; at {location}"))?;
    Ok(values[position].clone())
}
pub fn char_at_view(value: &str, position: i64) -> Result<&str> {
    let character = if position < 0 {
        let distance =
            usize::try_from(position.unsigned_abs() - 1).map_err(|_| "index out of range")?;
        value.char_indices().rev().nth(distance)
    } else {
        let distance = usize::try_from(position).map_err(|_| "index out of range")?;
        value.char_indices().nth(distance)
    };
    let (start, character) = character.ok_or("index out of range")?;
    Ok(&value[start..start + character.len_utf8()])
}

pub fn char_at(value: &str, position: i64) -> Result<String> {
    Ok(char_at_view(value, position)?.to_owned())
}
pub fn str_find(value: &str, needle: &str) -> i64 {
    value
        .find(needle)
        .map(|p| value[..p].chars().count() as i64)
        .unwrap_or(-1)
}
pub fn str_rfind(value: &str, needle: &str) -> i64 {
    value
        .rfind(needle)
        .map(|p| value[..p].chars().count() as i64)
        .unwrap_or(-1)
}
mod split_views;
pub use split_views::{split_item, str_split_count, str_split_iter, str_split_whitespace_iter};

pub fn str_split(value: &str, separator: &str) -> Result<Vec<String>> {
    if separator.is_empty() {
        return Err("empty separator".into());
    }
    Ok(value.split(separator).map(str::to_string).collect())
}

pub fn str_strip(value: &str) -> String {
    value.trim_matches(py_whitespace).to_string()
}
pub fn str_strip_edges(value: &str, characters: Option<&str>, left: bool, right: bool) -> String {
    // Python treats an explicit string as a set of characters, including the empty set.
    let characters = characters.map(|text| text.chars().collect::<std::collections::BTreeSet<_>>());
    let matches = |c: char| match &characters {
        Some(characters) => characters.contains(&c),
        None => py_whitespace(c),
    };
    let value = if left {
        value.trim_start_matches(matches)
    } else {
        value
    };
    let value = if right {
        value.trim_end_matches(matches)
    } else {
        value
    };
    value.to_string()
}
fn py_whitespace(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}
pub fn str_split_whitespace(value: &str) -> Vec<String> {
    value
        .split(py_whitespace)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .collect()
}

pub fn shlex_split(value: &str) -> Result<Vec<String>> {
    #[derive(Clone, Copy, PartialEq)]
    enum Quote {
        None,
        Single,
        Double,
    }
    let mut words = Vec::new();
    let mut word = String::new();
    let mut quote = Quote::None;
    let mut escaped = false;
    let mut started = false;
    for character in value.chars() {
        if escaped {
            if quote == Quote::Double && !matches!(character, '$' | '`' | '"' | '\\' | '\n') {
                word.push('\\');
            }
            if character != '\n' {
                word.push(character);
            }
            escaped = false;
            continue;
        }
        if character == '\\' && quote != Quote::Single {
            escaped = true;
            started = true;
            continue;
        }
        if quote == Quote::Single {
            if character == '\'' {
                quote = Quote::None;
            } else {
                word.push(character);
            }
            continue;
        }
        if quote == Quote::Double {
            if character == '"' {
                quote = Quote::None;
            } else {
                word.push(character);
            }
            continue;
        }
        match character {
            '\'' | '"' => {
                quote = if character == '\'' {
                    Quote::Single
                } else {
                    Quote::Double
                };
                started = true;
            }
            character if py_whitespace(character) => {
                if started {
                    words.push(std::mem::take(&mut word));
                    started = false;
                }
            }
            _ => {
                word.push(character);
                started = true;
            }
        }
    }
    if escaped {
        return Err("No escaped character".into());
    }
    if quote != Quote::None {
        return Err("No closing quotation".into());
    }
    if started {
        words.push(word);
    }
    Ok(words)
}

pub fn finite(value: f64) -> Result<f64> {
    if !value.is_finite() {
        return Err("non-finite floating point result".into());
    }
    Ok(value)
}

pub fn format_int(value: i64, spec: &str) -> String {
    let digits = spec.strip_suffix('d').unwrap_or(spec);
    let zero = digits.starts_with('0');
    let width = digits.parse::<usize>().unwrap_or(0);
    let text = value.to_string();
    let padding = width.saturating_sub(text.len());
    if zero {
        let sign = if value < 0 { "-" } else { "" };
        let unsigned = text.trim_start_matches('-');
        format!("{sign}{}{}", "0".repeat(padding), unsigned)
    } else {
        format!("{}{}", " ".repeat(padding), text)
    }
}

pub fn format_text(value: &str, spec: &str) -> String {
    let digits = spec.strip_suffix('s').unwrap_or(spec);
    let (width, precision) = digits
        .split_once('.')
        .map(|(width, precision)| {
            (
                width.parse::<usize>().unwrap_or(0),
                precision.parse::<usize>().unwrap_or(usize::MAX),
            )
        })
        .unwrap_or((digits.parse::<usize>().unwrap_or(0), usize::MAX));
    let text: String = value.chars().take(precision).collect();
    let padding = width.saturating_sub(text.chars().count());
    format!("{text}{}", " ".repeat(padding))
}

pub fn format_float(value: f64, spec: &str) -> Result<String> {
    let precision = spec
        .strip_prefix('.')
        .and_then(|text| text.strip_suffix('f'))
        .map(|text| text.parse::<usize>())
        .transpose()?
        .unwrap_or(6);
    Ok(format!("{value:.precision$}"))
}

pub fn repr_text(value: &str) -> String {
    let quote = if value.contains('\'') && !value.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut output = String::from(quote);
    for character in value.chars() {
        match character {
            '\\' => output.push_str("\\\\"),
            '\n' => output.push_str("\\n"),
            '\r' => output.push_str("\\r"),
            '\t' => output.push_str("\\t"),
            character if character == quote => {
                output.push('\\');
                output.push(character);
            }
            character if character.is_control() => {
                output.push_str(&format!("\\x{:02x}", character as u32))
            }
            character => output.push(character),
        }
    }
    output.push(quote);
    output
}

pub fn stream_write(stream: i64, value: &str) -> Result<()> {
    match stream {
        1 => std::io::stdout().write_all(value.as_bytes())?,
        2 => std::io::stderr().write_all(value.as_bytes())?,
        _ => return Err("stream is not writable".into()),
    }
    Ok(())
}

pub fn stream_flush(stream: i64) -> Result<()> {
    match stream {
        1 => std::io::stdout().flush()?,
        2 => std::io::stderr().flush()?,
        _ => return Err("stream is not writable".into()),
    }
    Ok(())
}

pub fn stream_readline(stream: i64) -> Result<String> {
    if stream != 0 {
        return Err("stream is not readable".into());
    }
    let mut value = String::new();
    std::io::stdin().read_line(&mut value)?;
    Ok(value)
}

pub fn unix_time() -> Result<f64> {
    Ok(SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs_f64())
}
pub fn monotonic() -> f64 {
    static START: OnceLock<Instant> = OnceLock::new();
    START.get_or_init(Instant::now).elapsed().as_secs_f64()
}
pub fn sleep(seconds: f64) -> Result<()> {
    if !seconds.is_finite() || !(0.0..=86400.0).contains(&seconds) {
        return Err("sleep must be between 0 and 86400 seconds".into());
    }
    std::thread::sleep(Duration::from_secs_f64(seconds));
    Ok(())
}
pub fn utc_now() -> DateTime {
    Utc::now()
}
pub fn datetime_parse(text: &str) -> Result<DateTime> {
    static PATTERN: OnceLock<regex::Regex> = OnceLock::new();
    let pattern = PATTERN.get_or_init(|| {
        regex::Regex::new(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)$")
            .expect("valid built-in RFC3339 pattern")
    });
    if !text.is_ascii() || !pattern.is_match(text) || &text[17..19] == "60" {
        return Err(
            "expected RFC3339 timestamp with explicit offset and at most 6 fractional digits"
                .into(),
        );
    }
    let value = chrono::DateTime::parse_from_rfc3339(text)?.with_timezone(&Utc);
    if !(1..=9999).contains(&value.year()) {
        return Err("datetime year out of range".into());
    }
    Ok(value)
}
pub fn datetime_iso(value: &DateTime) -> String {
    value.to_rfc3339_opts(SecondsFormat::Micros, false)
}
pub fn datetime_add_seconds(value: &DateTime, seconds: i64) -> Result<DateTime> {
    let delta = TimeDelta::try_seconds(seconds).ok_or("datetime delta out of range")?;
    let result = value.checked_add_signed(delta).ok_or("datetime overflow")?;
    if !(1..=9999).contains(&result.year()) {
        return Err("datetime year out of range".into());
    }
    Ok(result)
}

pub fn datetime_from_unix(seconds: i64) -> Result<DateTime> {
    if !(-62135596800..=253402300799).contains(&seconds) {
        return Err("Unix timestamp must be an integer within years 0001..9999".into());
    }
    DateTime::from_timestamp(seconds, 0).ok_or_else(|| "Unix timestamp out of range".into())
}
pub fn datetime_unix_microseconds(value: &DateTime) -> i64 {
    value.timestamp_micros()
}

pub fn datetime_format(value: &DateTime, pattern: &str) -> Result<String> {
    if pattern.len() > 1024 || !(1..=9999).contains(&value.year()) {
        return Err(
            "expected a datetime in years 0001..9999 and a format of at most 1024 bytes".into(),
        );
    }
    const WEEKDAYS: [&str; 7] = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ];
    const MONTHS: [&str; 12] = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ];
    let weekday = WEEKDAYS[value.weekday().num_days_from_monday() as usize];
    let month = MONTHS[value.month0() as usize];
    let mut result = String::new();
    let mut escaped = false;
    for character in pattern.chars() {
        if escaped {
            let field = match character {
                '%' => "%".to_string(),
                'Y' => format!("{:04}", value.year()),
                'm' => format!("{:02}", value.month()),
                'd' => format!("{:02}", value.day()),
                'H' => format!("{:02}", value.hour()),
                'M' => format!("{:02}", value.minute()),
                'S' => format!("{:02}", value.second()),
                'f' => format!("{:06}", value.timestamp_subsec_micros()),
                'z' => "+0000".to_string(),
                'Z' => "UTC".to_string(),
                'j' => format!("{:03}", value.ordinal()),
                'a' => weekday[..3].to_string(),
                'A' => weekday.to_string(),
                'b' => month[..3].to_string(),
                'B' => month.to_string(),
                'w' => value.weekday().num_days_from_sunday().to_string(),
                'u' => value.weekday().number_from_monday().to_string(),
                _ => return Err("unsupported datetime format directive".into()),
            };
            result.push_str(&field);
            escaped = false;
        } else if character == '%' {
            escaped = true;
        } else {
            result.push(character);
        }
    }
    if escaped {
        return Err("incomplete datetime format directive".into());
    }
    Ok(result)
}

static LOG_LEVEL: AtomicI64 = AtomicI64::new(30);
fn level_name(level: i64) -> Result<&'static str> {
    match level {
        10 => Ok("DEBUG"),
        20 => Ok("INFO"),
        30 => Ok("WARNING"),
        40 => Ok("ERROR"),
        50 => Ok("CRITICAL"),
        _ => Err("invalid logging level".into()),
    }
}
pub fn log_configure(level: i64) -> Result<()> {
    level_name(level)?;
    LOG_LEVEL.store(level, Ordering::Relaxed);
    Ok(())
}
pub fn log(level: i64, message: &str) -> Result<()> {
    let name = level_name(level)?;
    if level >= LOG_LEVEL.load(Ordering::Relaxed) {
        eprintln!("{name}:{message}");
    }
    Ok(())
}

pub fn read_text(path: &str) -> Result<String> {
    Ok(std::fs::read_to_string(path)?)
}

pub fn read_text_encoding(path: &str, encoding: &str) -> Result<String> {
    let bytes = std::fs::read(path)?;
    let text = decode_bytes(
        &bytes,
        if encoding == "utf-8-sig" {
            "utf-8"
        } else {
            encoding
        },
        "strict",
    )?;
    Ok(text.strip_prefix('\u{feff}').unwrap_or(&text).to_owned())
}
pub fn write_text(path: &str, value: &str) -> Result<()> {
    Ok(std::fs::write(path, value.as_bytes())?)
}
pub fn read_bytes(path: &str) -> Result<Vec<u8>> {
    Ok(std::fs::read(path)?)
}
pub fn write_bytes(path: &str, value: &[u8]) -> Result<()> {
    Ok(std::fs::write(path, value)?)
}
pub fn mkdir_all(path: &str) -> Result<()> {
    Ok(std::fs::create_dir_all(path)?)
}
pub fn list_dir(path: &str) -> Result<Vec<String>> {
    let mut entries = Vec::new();
    for entry in std::fs::read_dir(path)? {
        entries.push(
            entry?
                .file_name()
                .into_string()
                .map_err(|_| "non-UTF8 filename")?,
        );
    }
    entries.sort();
    Ok(entries)
}
pub fn path_exists(path: &str) -> bool {
    std::path::Path::new(path).exists()
}

pub fn path_is_dir(path: &str) -> Result<bool> {
    Ok(std::fs::metadata(path)?.is_dir())
}

pub fn path_is_file(path: &str) -> Result<bool> {
    Ok(std::fs::metadata(path)?.is_file())
}

pub fn path_iterdir(path: &str) -> Result<Vec<String>> {
    let mut entries = Vec::new();
    for entry in std::fs::read_dir(path)? {
        entries.push(
            entry?
                .path()
                .into_os_string()
                .into_string()
                .map_err(|_| "non-UTF8 path")?,
        );
    }
    entries.sort();
    Ok(entries)
}
pub fn path_suffix(path: &str) -> String {
    let name = path.rsplit('/').next().unwrap_or(path);
    match name.rfind('.') {
        Some(index) if index > 0 && index + 1 < name.len() => name[index..].to_owned(),
        _ => String::new(),
    }
}

pub fn path_join(parent: &str, child: &str) -> Result<String> {
    Ok(std::path::Path::new(parent)
        .join(child)
        .into_os_string()
        .into_string()
        .map_err(|_| "non-UTF8 path")?)
}
pub fn remove_file(path: &str) -> Result<()> {
    Ok(std::fs::remove_file(path)?)
}
pub fn remove_dir(path: &str) -> Result<()> {
    Ok(std::fs::remove_dir(path)?)
}

mod regular_expressions;
pub use regular_expressions::{
    regex_capture, regex_capture_groups, regex_findall, regex_fullmatch, regex_replace,
    regex_search,
};

mod web;
pub use web::{
    stream_chunk, web_response, web_serve, web_serve_stream, web_stream, StreamChunk, WebRequest,
    WebResponse,
};
pub fn env_get(name: &str, default: &str) -> String {
    std::env::var(name).unwrap_or_else(|_| default.to_string())
}
pub fn random_token() -> Result<String> {
    use std::fmt::Write as _;
    use std::io::Read;
    let mut bytes = [0u8; 32];
    std::fs::File::open("/dev/urandom")?.read_exact(&mut bytes)?;
    let mut output = String::with_capacity(64);
    for byte in bytes {
        write!(output, "{byte:02x}")?;
    }
    Ok(output)
}
pub fn constant_time_equal(left: &[u8], right: &[u8]) -> bool {
    use subtle::ConstantTimeEq;
    bool::from(left.ct_eq(right))
}
pub fn write_text_atomic(path: &str, text: &str) -> Result<()> {
    use std::io::Write;
    let path = std::path::Path::new(path);
    let directory = path
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(std::path::Path::new("."));
    let temporary = directory.join(format!(".{}.tmp", random_token()?));
    let result = (|| -> Result<()> {
        let mut file = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)?;
        file.write_all(text.as_bytes())?;
        file.sync_all()?;
        std::fs::rename(&temporary, path)?;
        std::fs::File::open(directory)?.sync_all()?;
        Ok(())
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(temporary);
    }
    result
}
pub fn json_kind(value: &Json) -> String {
    match value {
        Json::Null => "null",
        Json::Bool(_) => "bool",
        Json::Number(_) => "number",
        Json::String(_) => "string",
        Json::Array(_) => "array",
        Json::Object(_) => "object",
    }
    .into()
}
pub fn json_parse(text: &str, default: &Json) -> Json {
    json_loads(text).unwrap_or_else(|_| default.clone())
}
/// Numeric-only repeated character access; ASCII stays borrowed and allocation-free.
pub enum CodepointIndex<'a> {
    Ascii(&'a [u8]),
    Unicode(Vec<char>),
}

impl<'a> CodepointIndex<'a> {
    pub fn new(value: &'a str) -> Self {
        if value.is_ascii() {
            Self::Ascii(value.as_bytes())
        } else {
            Self::Unicode(value.chars().collect())
        }
    }
    pub fn len(&self) -> usize {
        match self {
            Self::Ascii(value) => value.len(),
            Self::Unicode(value) => value.len(),
        }
    }
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
    #[inline]
    pub fn codepoint(&self, position: i64) -> Result<i64> {
        match self {
            Self::Ascii(value) => Ok(i64::from(value[index(value.len(), position)?])),
            Self::Unicode(value) => Ok(i64::from(value[index(value.len(), position)?] as u32)),
        }
    }
}

/// Character views with direct ASCII access and bounded UTF-8 boundary scans.
pub struct TextIndex<'a> {
    value: &'a str,
    length: usize,
    ascii: bool,
    boundaries: Option<Vec<usize>>,
    stride: usize,
    cursor: std::cell::Cell<(usize, usize)>,
}

impl<'a> TextIndex<'a> {
    pub fn new(value: &'a str) -> Self {
        let ascii = value.is_ascii();
        let stride = if value.len() <= 65_536 { 1 } else { 8 };
        let mut length = value.len();
        let boundaries = if ascii {
            None
        } else {
            let mut entries = Vec::new();
            length = 0;
            for (position, (offset, _)) in value.char_indices().enumerate() {
                if position % stride == 0 {
                    entries.push(offset);
                }
                length = position + 1;
            }
            Some(entries)
        };
        Self {
            value,
            length,
            ascii,
            boundaries,
            stride,
            cursor: std::cell::Cell::new((0, 0)),
        }
    }

    pub fn len(&self) -> usize {
        self.length
    }
    pub fn is_empty(&self) -> bool {
        self.length == 0
    }

    fn boundary(&self, position: usize) -> usize {
        if self.ascii {
            return position;
        }
        if position == self.length {
            return self.value.len();
        }
        let boundaries = self.boundaries.as_ref().expect("Unicode boundary index");
        if self.stride == 1 {
            return boundaries[position];
        }
        let checkpoint = position / self.stride;
        let base = checkpoint * self.stride;
        let (previous, offset) = self.cursor.get();
        let (previous, offset) = if base <= previous && previous <= position {
            (previous, offset)
        } else {
            (base, boundaries[checkpoint])
        };
        let distance = position - previous;
        debug_assert!(distance < self.stride);
        let offset = if distance == 0 {
            offset
        } else {
            offset
                + self.value[offset..]
                    .char_indices()
                    .nth(distance)
                    .expect("validated character boundary")
                    .0
        };
        self.cursor.set((position, offset));
        offset
    }

    /// Decode an indexed character directly, without constructing a string view.
    pub fn codepoint(&self, position: i64) -> Result<i64> {
        let position = index(self.length, position)?;
        let start = self.boundary(position);
        let character = self.value[start..]
            .chars()
            .next()
            .expect("validated character index");
        Ok(i64::from(character as u32))
    }

    pub fn at_view(&self, position: i64) -> Result<&'a str> {
        let position = index(self.length, position)?;
        let start = self.boundary(position);
        let width = self.value[start..]
            .chars()
            .next()
            .expect("validated character index")
            .len_utf8();
        Ok(&self.value[start..start + width])
    }

    pub fn at(&self, position: i64) -> Result<String> {
        Ok(self.at_view(position)?.to_owned())
    }

    pub fn slice(&self, start: i64, end: i64) -> &'a str {
        let length = self.length as i64;
        let bound = |n: i64| if n < 0 { (length + n).max(0) } else { n.min(length) } as usize;
        let (start, end) = (bound(start), bound(end));
        if end <= start {
            return &self.value[..0];
        }
        let start_byte = self.boundary(start);
        let end_byte = self.boundary(end);
        // Overlapping sequential slices can keep using the start cursor.
        self.cursor.set((start, start_byte));
        &self.value[start_byte..end_byte]
    }
}

pub fn str_slice_view(value: &str, start: i64, end: i64) -> &str {
    let length = if start < 0 || end < 0 {
        value.chars().count() as i64
    } else {
        0
    };
    let bound = |n: i64| {
        if n < 0 {
            (length + n).max(0) as usize
        } else {
            n as usize
        }
    };
    let (start, end) = (bound(start), bound(end));
    if end <= start {
        return &value[..0];
    }
    let start_byte = value
        .char_indices()
        .nth(start)
        .map_or(value.len(), |(offset, _)| offset);
    let tail = &value[start_byte..];
    let end_byte = if end == i64::MAX as usize {
        tail.len()
    } else {
        tail.char_indices()
            .nth(end - start)
            .map_or(tail.len(), |(offset, _)| offset)
    };
    &tail[..end_byte]
}

pub fn str_slice(value: &str, start: i64, end: i64) -> String {
    str_slice_view(value, start, end).to_owned()
}

pub fn bytes_slice(value: &[u8], start: i64, end: i64) -> Vec<u8> {
    list_slice(value, start, end)
}
pub fn list_slice<T: Clone>(value: &[T], start: i64, end: i64) -> Vec<T> {
    slice_view(value, start, end).to_vec()
}

pub fn slice_view<T>(value: &[T], start: i64, end: i64) -> &[T] {
    let length = value.len() as i64;
    let bound = |n: i64| if n < 0 { (length + n).max(0) } else { n.min(length) } as usize;
    let (start, end) = (bound(start), bound(end));
    &value[start..end.max(start)]
}
pub fn bytes_find(value: &[u8], needle: &[u8]) -> i64 {
    if needle.is_empty() {
        return 0;
    }
    value
        .windows(needle.len())
        .position(|window| window == needle)
        .map(|position| position as i64)
        .unwrap_or(-1)
}
pub fn url_quote(value: &str) -> String {
    let mut output = String::new();
    for byte in value.bytes() {
        if byte.is_ascii_alphanumeric() || b"-._~".contains(&byte) {
            output.push(byte as char);
        } else {
            output.push_str(&format!("%{byte:02X}"));
        }
    }
    output
}

/// Lazy signed range; an overflowing next value is necessarily past an i64 stop.
pub fn integer_range(start: i64, stop: i64, step: i64) -> Result<impl Iterator<Item = i64>> {
    if step == 0 {
        return Err("range() arg 3 must not be zero".into());
    }
    Ok(
        std::iter::successors(Some(start), move |value| value.checked_add(step)).take_while(
            move |value| {
                if step > 0 {
                    *value < stop
                } else {
                    *value > stop
                }
            },
        ),
    )
}

mod gzip;
pub use gzip::{
    gzip_create, gzip_finish, gzip_open, gzip_read, gzip_reader_close, gzip_write,
    gzip_writer_close, GzipReader, GzipWriter,
};

#[cfg(test)]
mod text_index_tests {
    use super::*;

    #[test]
    fn indexed_views_match_character_bounds() {
        let bounds = [i64::MIN, -9, -3, -1, 0, 1, 3, 9, i64::MAX];
        for value in ["", "abc", "a世界🙂e\u{301}", "🙂🙂"] {
            let indexed = TextIndex::new(value);
            let chars: Vec<char> = value.chars().collect();
            let length = chars.len() as i64;
            let bound = |n: i64| if n < 0 { (length + n).max(0) } else { n.min(length) } as usize;
            for start in bounds {
                for end in bounds {
                    let (left, right) = (bound(start), bound(end));
                    let expected: String = chars[left..right.max(left)].iter().collect();
                    assert_eq!(indexed.slice(start, end), expected);
                    assert_eq!(str_slice_view(value, start, end), expected);
                }
                match index(chars.len(), start) {
                    Ok(position) => {
                        assert_eq!(indexed.at(start).unwrap(), chars[position].to_string())
                    }
                    Err(_) => assert!(indexed.at(start).is_err()),
                }
            }
        }
    }

    #[test]
    fn large_unicode_uses_sparse_checkpoints() {
        let value = "a🙂".repeat(40_000);
        let indexed = TextIndex::new(&value);
        assert_eq!(indexed.stride, 8);
        assert_eq!(indexed.boundaries.as_ref().unwrap().len(), 10_000);
        assert_eq!(indexed.len(), 80_000);
        for position in 0..80_000 {
            let expected = if position % 2 == 0 { "a" } else { "🙂" };
            assert_eq!(indexed.slice(position, position + 1), expected);
            assert_eq!(indexed.at(position).unwrap(), expected);
        }
        assert_eq!(indexed.at(-1).unwrap(), "🙂");
        assert_eq!(indexed.slice(0, 2), "a🙂");
        assert_eq!(indexed.slice(79_998, i64::MAX), "a🙂");
    }
}

#[cfg(test)]
mod sparse_index_tests {
    use super::*;
    #[test]
    fn unicode_orders_and_storage_bounds() {
        for length in [0, 1, 7, 8, 9, 16_384, 32_768, 65_536, 131_072] {
            let value: String = ['a', 'é', '🙂', '\u{301}']
                .into_iter()
                .cycle()
                .take(length)
                .collect();
            let characters: Vec<char> = value.chars().collect();
            let indexed = TextIndex::new(&value);
            assert_eq!(indexed.len(), characters.len());
            if value.len() > 65_536 {
                assert_eq!(indexed.stride, 8);
                let entries = indexed.boundaries.as_ref().unwrap();
                assert_eq!(entries.len(), length.div_ceil(8));
                assert!(entries.capacity() * std::mem::size_of::<usize>() <= 2 * value.len() + 16);
            }
            for position in (0..length).rev() {
                let expected = characters[position].to_string();
                assert_eq!(indexed.at_view(position as i64).unwrap(), expected);
                assert_eq!(
                    indexed.codepoint(position as i64 - length as i64).unwrap(),
                    i64::from(characters[position] as u32)
                );
                assert_eq!(
                    indexed.at(position as i64 - length as i64).unwrap(),
                    expected
                );
                assert_eq!(
                    indexed.slice(position as i64, position as i64 + 1),
                    expected
                );
            }
            for request in 0..length {
                let position = request.wrapping_mul(7919) % length;
                let end = (position + request % 19).min(length);
                let expected: String = characters[position..end].iter().collect();
                assert_eq!(indexed.slice(position as i64, end as i64), expected);
                assert_eq!(
                    indexed.at_view(position as i64).unwrap(),
                    characters[position].to_string()
                );
            }
            assert!(indexed.at_view(i64::MIN).is_err());
            assert!(indexed.codepoint(i64::MIN).is_err());
            assert!(indexed.codepoint(i64::MAX).is_err());
            assert!(indexed.at_view(i64::MAX).is_err());
            assert_eq!(indexed.slice(i64::MIN, i64::MAX), value);
            assert_eq!(indexed.slice(i64::MAX, i64::MIN), "");
        }
    }

    #[test]
    fn ascii_and_view_lifetime() {
        let value = "abcdef".repeat(40_000);
        let indexed = TextIndex::new(&value);
        assert!(indexed.boundaries.is_none());
        assert_eq!(indexed.at_view(-1).unwrap(), "f");
        let text = "a🙂é".to_string();
        let view = {
            let index = TextIndex::new(&text);
            index.at_view(1).unwrap()
        };
        assert_eq!(view, "🙂");
        assert_eq!(view.as_ptr(), text[1..].as_ptr());
    }
}

mod integer_lookup;
pub use integer_lookup::IntLookup;

mod memoization;
pub use memoization::{memoized, MemoCache};
