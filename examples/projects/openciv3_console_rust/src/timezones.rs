//! TZif conversion primitives. Selection policies and appointment reports stay in Python.
use crate::{DateTime, Json, Result};
use chrono::{Datelike, NaiveDateTime, Timelike};
use std::collections::BTreeMap;
use std::sync::OnceLock;
use tz::{datetime::FoundDateTimeKind, TimeZone};

fn zone(data: &[u8]) -> Result<TimeZone> {
    if !(44..=1048576).contains(&data.len()) {
        return Err("TZif data must be 44 bytes..1 MiB".into());
    }
    let version = data[4];
    if ![0, b'2', b'3'].contains(&version) {
        return Err("expected TZif version 1, 2 or 3".into());
    }
    let (mut position, mut width) = (0usize, 4usize);
    for _ in 0..if version == 0 { 1 } else { 2 } {
        let header = data
            .get(position..position + 44)
            .ok_or("truncated TZif header")?;
        if &header[..4] != b"TZif" || header[4] != version {
            return Err("inconsistent TZif header".into());
        }
        let count = |index: usize| -> usize {
            u32::from_be_bytes(header[index..index + 4].try_into().expect("header width")) as usize
        };
        let (utc, standard, leaps, times, types, characters) = (
            count(20),
            count(24),
            count(28),
            count(32),
            count(36),
            count(40),
        );
        if !(1..=256).contains(&types)
            || !(1..=4096).contains(&characters)
            || times > 20000
            || leaps != 0
            || ![0, types].contains(&utc)
            || ![0, types].contains(&standard)
        {
            return Err("unsupported TZif counts or leap-second table".into());
        }
        let size = times * (width + 1) + types * 6 + characters + utc + standard;
        let start = position + 44;
        let block = data
            .get(start..start + size)
            .ok_or("truncated TZif block")?;
        let transitions: Vec<i64> = block[..times * width]
            .chunks_exact(width)
            .map(|bytes| {
                if width == 4 {
                    i64::from(i32::from_be_bytes(bytes.try_into().expect("width")))
                } else {
                    i64::from_be_bytes(bytes.try_into().expect("width"))
                }
            })
            .collect();
        if transitions.windows(2).any(|pair| pair[0] >= pair[1]) {
            return Err("TZif transitions must increase strictly".into());
        }
        if block[times * width..times * (width + 1)]
            .iter()
            .any(|&index| index as usize >= types)
        {
            return Err("invalid TZif transition type".into());
        }
        let table = times * (width + 1);
        let names = &block[table + types * 6..table + types * 6 + characters];
        for index in 0..types {
            let entry = &block[table + index * 6..table + (index + 1) * 6];
            let offset = i32::from_be_bytes(entry[..4].try_into().expect("entry width"));
            let abbreviation = entry[5] as usize;
            if !(-86400..86400).contains(&offset)
                || offset == -86400
                || entry[4] > 1
                || abbreviation >= names.len()
                || !names[abbreviation..].contains(&0)
                || !names.is_ascii()
            {
                return Err("invalid TZif local time type".into());
            }
            let designation = names[abbreviation..]
                .split(|&byte| byte == 0)
                .next()
                .unwrap_or_default();
            if !(3..=7).contains(&designation.len())
                || !designation
                    .iter()
                    .all(|byte| byte.is_ascii_alphanumeric() || [b'+', b'-'].contains(byte))
            {
                return Err("expected a 3..7-character TZif designation".into());
            }
        }
        let flags = &block[table + types * 6 + characters..];
        if flags.iter().any(|&flag| flag > 1) {
            return Err("invalid TZif indicator".into());
        }
        if utc != 0
            && (0..types)
                .any(|index| flags[standard + index] != 0 && (standard == 0 || flags[index] == 0))
        {
            return Err("UTC TZif indicators require standard indicators".into());
        }
        position = start + size;
        width = 8;
    }
    if version == 0 && position != data.len() {
        return Err("unexpected TZif trailing data".into());
    }
    if version != 0 && !(data.get(position) == Some(&b'\n') && data.last() == Some(&b'\n')) {
        return Err("invalid TZif footer".into());
    }
    let original = TimeZone::from_tz_data(data)?;
    let source = original.as_ref();
    let mut types = source.local_time_types().to_vec();
    let mut transitions = source.transitions().to_vec();
    let mut rule = *source.extra_rule();
    // ZoneInfo uses the first standard type before recorded transitions, and
    // continues the final type indefinitely when a POSIX footer is absent.
    if rule.is_none() {
        let last = transitions
            .last()
            .map_or(types.len() - 1, |entry| entry.local_time_type_index());
        rule = Some(tz::timezone::TransitionRule::Fixed(types[last]));
    }
    let before = types.iter().position(|kind| !kind.is_dst()).unwrap_or(0);
    types.swap(0, before);
    for entry in &mut transitions {
        let index = entry.local_time_type_index();
        let remapped = if index == 0 {
            before
        } else if index == before {
            0
        } else {
            index
        };
        *entry = tz::timezone::Transition::new(entry.unix_leap_time(), remapped);
    }
    Ok(TimeZone::new(transitions, types, Vec::new(), rule)?)
}

fn view(zone: &TimeZone, value: &DateTime) -> Result<Json> {
    if !(1..=9999).contains(&value.year()) || value.timestamp_subsec_nanos() % 1000 != 0 {
        return Err("expected years 0001..9999 and microsecond precision".into());
    }
    let kind = zone.find_local_time_type(value.timestamp())?;
    let local = value
        .naive_utc()
        .checked_add_signed(chrono::TimeDelta::seconds(i64::from(kind.ut_offset())))
        .ok_or("local datetime overflow")?;
    if !(1..=9999).contains(&local.year()) {
        return Err("local datetime year outside 0001..9999".into());
    }
    Ok(serde_json::json!({
        "utc": crate::datetime_iso(value),
        "local": local.format("%Y-%m-%dT%H:%M:%S%.6f").to_string(),
        "offset_seconds": kind.ut_offset(), "abbreviation": kind.time_zone_designation(), "is_dst": kind.is_dst(),
    }))
}

pub fn timezone_project(data: &[u8], value: &DateTime) -> Result<Json> {
    view(&zone(data)?, value)
}

pub fn timezone_local(data: &[u8], text: &str) -> Result<Json> {
    static PATTERN: OnceLock<regex::Regex> = OnceLock::new();
    let pattern = PATTERN.get_or_init(|| {
        regex::Regex::new(
            r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?\z",
        )
        .expect("local datetime pattern")
    });
    if !pattern.is_match(text) || &text[17..19] == "60" {
        return Err("expected local YYYY-MM-DDTHH:MM:SS with at most 6 fractional digits".into());
    }
    let local = NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M:%S%.f")?;
    if !(1..=9999).contains(&local.year()) {
        return Err("local datetime year outside 0001..9999".into());
    }
    let zone = zone(data)?;
    let found = tz::DateTime::find(
        local.year(),
        local.month() as u8,
        local.day() as u8,
        local.hour() as u8,
        local.minute() as u8,
        local.second() as u8,
        local.nanosecond(),
        zone.as_ref(),
    )?;
    let mut candidates = BTreeMap::new();
    let mut projections = BTreeMap::new();
    for entry in found.into_inner() {
        match entry {
            FoundDateTimeKind::Normal(value) => {
                let utc = DateTime::from_timestamp(value.unix_time(), value.nanoseconds())
                    .ok_or("UTC overflow")?;
                candidates.insert(utc, view(&zone, &utc)?);
            }
            FoundDateTimeKind::Skipped {
                before_transition,
                after_transition,
            } => {
                for value in [before_transition, after_transition] {
                    let seconds = local.and_utc().timestamp()
                        - i64::from(value.local_time_type().ut_offset());
                    let utc = DateTime::from_timestamp(seconds, local.nanosecond())
                        .ok_or("UTC overflow")?;
                    projections.insert(utc, view(&zone, &utc)?);
                }
            }
        }
    }
    let kind = match candidates.len() {
        0 => "gap",
        1 => "unique",
        2 => "fold",
        _ => return Err("more than two local-time candidates".into()),
    };
    if kind == "gap" && projections.len() != 2 {
        return Err("local time has no pair of gap projections".into());
    }
    Ok(serde_json::json!({
        "kind": kind, "local": local.format("%Y-%m-%dT%H:%M:%S%.6f").to_string(),
        "candidates": candidates.into_values().collect::<Vec<_>>(),
        "projections": if kind == "gap" { projections.into_values().collect::<Vec<_>>() } else { Vec::new() },
    }))
}
