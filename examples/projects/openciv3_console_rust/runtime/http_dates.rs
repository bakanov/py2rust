//! Bounded Retry-After parsing with RFC 9110's rolling obsolete-year window.
use crate::Result;
use chrono::{Datelike, NaiveDate, Timelike, Utc};
use regex::Regex;
use std::sync::OnceLock;

pub fn http_retry_after(value: &str, now: f64) -> Result<f64> {
    const LAST_SECOND: f64 = 253402300799.0;
    if !now.is_finite() || !(0.0..=LAST_SECOND).contains(&now) || value.len() > 64 {
        return Err("invalid Retry-After input or reference time".into());
    }
    let text = value.trim_matches([' ', '\t']);
    if !text.is_empty() && text.bytes().all(|byte| byte.is_ascii_digit()) {
        // Accumulate with a bound rather than rejecting valid leading zeroes.
        let mut seconds = 0_u64;
        for byte in text.bytes() {
            seconds = seconds * 10 + u64::from(byte - b'0');
            if seconds > LAST_SECOND as u64 {
                return Err("Retry-After exceeds year 9999".into());
            }
        }
        let deadline = now + seconds as f64;
        if deadline > LAST_SECOND {
            return Err("Retry-After exceeds year 9999".into());
        }
        return Ok(deadline);
    }
    static PATTERNS: OnceLock<[Regex; 3]> = OnceLock::new();
    let patterns = PATTERNS.get_or_init(|| [
        Regex::new(r"\A([A-Z][a-z]{2}), ([0-9]{2}) ([A-Z][a-z]{2}) ([0-9]{4}) ([0-9]{2}):([0-9]{2}):([0-9]{2}) GMT\z").unwrap(),
        Regex::new(r"\A([A-Z][a-z]+), ([0-9]{2})-([A-Z][a-z]{2})-([0-9]{2}) ([0-9]{2}):([0-9]{2}):([0-9]{2}) GMT\z").unwrap(),
        Regex::new(r"\A([A-Z][a-z]{2}) ([A-Z][a-z]{2}) ([ 0-9][0-9]) ([0-9]{2}):([0-9]{2}):([0-9]{2}) ([0-9]{4})\z").unwrap(),
    ]);
    for (index, pattern) in patterns.iter().enumerate() {
        let Some(parts) = pattern.captures(text) else {
            continue;
        };
        let (day, month, year, hour, minute, second) = if index == 2 {
            (
                &parts[3], &parts[2], &parts[7], &parts[4], &parts[5], &parts[6],
            )
        } else {
            (
                &parts[2], &parts[3], &parts[4], &parts[5], &parts[6], &parts[7],
            )
        };
        let mut year: i32 = year.parse()?;
        let month = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        .iter()
        .position(|name| *name == month)
        .ok_or("invalid HTTP date month")? as u32
            + 1;
        let day: u32 = day.trim_start().parse()?;
        let hour: u32 = hour.parse()?;
        let minute: u32 = minute.parse()?;
        let second: u32 = second.parse()?;
        if index == 1 {
            let reference = chrono::DateTime::<Utc>::from_timestamp(now.floor() as i64, 0)
                .ok_or("invalid HTTP date reference time")?;
            year += (reference.year() + 50) / 100 * 100;
            let candidate = (year, month, day, hour, minute, second);
            let boundary = (
                reference.year() + 50,
                reference.month(),
                reference.day(),
                reference.hour(),
                reference.minute(),
                reference.second(),
            );
            if candidate > boundary {
                year -= 100;
            }
        }
        if !(1..=9999).contains(&year) || second > 60 {
            return Err("HTTP date outside supported range".into());
        }
        let date = NaiveDate::from_ymd_opt(year, month, day).ok_or("invalid HTTP date")?;
        let names = if index == 1 {
            [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
        } else {
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        };
        if names[date.weekday().num_days_from_monday() as usize] != &parts[1] {
            return Err("HTTP date weekday does not match date".into());
        }
        let time = date
            .and_hms_opt(hour, minute, second.min(59))
            .ok_or("invalid HTTP date time")?;
        let deadline = time.and_utc().timestamp() as f64 + if second == 60 { 1.0 } else { 0.0 };
        if deadline > LAST_SECOND {
            return Err("Retry-After exceeds year 9999".into());
        }
        return Ok(now.max(deadline));
    }
    Err("expected delay-seconds or HTTP-date".into())
}
