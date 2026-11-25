//! Consumers of temporary splits preserve Python separators and whitespace.
use crate::{index, py_whitespace, Result};

pub fn str_split_iter<'a>(
    value: &'a str,
    separator: &'a str,
) -> Result<impl Iterator<Item = &'a str> + Clone> {
    if separator.is_empty() {
        return Err("empty separator".into());
    }
    Ok(value.split(separator))
}

pub fn str_split_whitespace_iter(value: &str) -> impl Iterator<Item = &str> + Clone {
    value.split(py_whitespace).filter(|part| !part.is_empty())
}

pub fn split_item<'a>(
    mut parts: impl Iterator<Item = &'a str> + Clone,
    position: i64,
) -> Result<String> {
    // A negative index counts the forward split. rsplit would change the result
    // for overlapping multi-character separators, e.g. "aaa".split("aa")[-1].
    let offset = if position < 0 {
        index(parts.clone().count(), position)?
    } else {
        usize::try_from(position)?
    };
    Ok(parts.nth(offset).ok_or("index out of range")?.to_owned())
}

/// Count without allocating, using the character-pattern fast path when equivalent.
pub fn str_split_count(value: &str, separator: &str) -> Result<i64> {
    let mut characters = separator.chars();
    let first = characters.next().ok_or("empty separator")?;
    let count = if characters.next().is_none() {
        value.split(first).count()
    } else {
        value.split(separator).count()
    };
    Ok(i64::try_from(count)?)
}
