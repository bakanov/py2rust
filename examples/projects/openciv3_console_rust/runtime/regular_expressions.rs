//! Common regex syntax with Python 3.13 ASCII boundaries and final-LF anchors.
use crate::{Json, Result};
use std::collections::VecDeque;
use std::sync::{Arc, Mutex, OnceLock};

const WORD_BOUNDARY: &str =
    r"(?:(?<=[A-Za-z0-9_])(?![A-Za-z0-9_])|(?<![A-Za-z0-9_])(?=[A-Za-z0-9_]))";
const NON_BOUNDARY: &str = r"(?:(?<=[A-Za-z0-9_])(?=[A-Za-z0-9_])|(?<![A-Za-z0-9_])(?![A-Za-z0-9_]))(?:(?=[\s\S])|(?<=[\s\S]))";

#[derive(Clone)]
enum Compiled {
    Linear(regex::Regex),
    Assertions(Arc<fancy_regex::Regex>),
}

type Span = (usize, usize);
type Groups = Vec<Option<Span>>;

impl Compiled {
    fn first(&self, text: &str, start: usize) -> Result<Option<Span>> {
        Ok(match self {
            Self::Linear(regex) => regex
                .find_at(text, start)
                .map(|value| (value.start(), value.end())),
            Self::Assertions(regex) => regex
                .find_from_pos(text, start)?
                .map(|value| (value.start(), value.end())),
        })
    }

    fn groups(&self, text: &str) -> Result<Option<Groups>> {
        Ok(match self {
            Self::Linear(regex) => regex.captures(text).map(|groups| {
                groups
                    .iter()
                    .map(|value| value.map(|value| (value.start(), value.end())))
                    .collect()
            }),
            Self::Assertions(regex) => regex.captures(text)?.map(|groups| {
                groups
                    .iter()
                    .map(|value| value.map(|value| (value.start(), value.end())))
                    .collect()
            }),
        })
    }

    fn group_count(&self) -> usize {
        match self {
            Self::Linear(regex) => regex.captures_len(),
            Self::Assertions(regex) => regex.captures_len(),
        }
    }
}

fn translate(pattern: &str) -> Result<(String, bool)> {
    if pattern.contains("(?") || regex::Regex::new(r"\\[1-9]")?.is_match(pattern) {
        return Err("regex extensions and backreferences are unsupported".into());
    }
    let (mut linear, mut assertions) = (String::new(), String::new());
    let (mut in_class, mut first_in_class, mut needs_assertions) = (false, false, false);
    let mut class_can_negate = false;
    let mut chars = pattern.chars();
    while let Some(ch) = chars.next() {
        if ch == '\\' {
            let escaped = chars.next().ok_or("trailing regex escape")?;
            let replacement = match escaped {
                'w' => Some("[A-Za-z0-9_]"),
                'W' => Some("[^A-Za-z0-9_]"),
                'd' => Some("[0-9]"),
                'D' => Some("[^0-9]"),
                's' => Some(r"[\t\n\r\x0c\x0b ]"),
                'S' => Some(r"[^\t\n\r\x0c\x0b ]"),
                'b' if in_class => Some(r"\x08"),
                'Z' if !in_class => Some(r"\z"),
                _ => None,
            };
            if let Some(value) = replacement {
                linear.push_str(value);
                assertions.push_str(value);
            } else if !in_class && (escaped == 'b' || escaped == 'B') {
                if escaped == 'B' {
                    needs_assertions = true;
                }
                linear.push_str(if escaped == 'b' {
                    r"(?-u:\b)"
                } else {
                    r"(?-u:\B)"
                });
                assertions.push_str(if escaped == 'b' {
                    WORD_BOUNDARY
                } else {
                    NON_BOUNDARY
                });
            } else {
                linear.push('\\');
                linear.push(escaped);
                assertions.push('\\');
                assertions.push(escaped);
            }
            first_in_class = false;
            class_can_negate = false;
        } else if ch == '$' && !in_class {
            linear.push('$');
            assertions.push_str(r"(?=\n?\z)");
            needs_assertions = true;
        } else {
            if !in_class && ch == '[' {
                in_class = true;
                first_in_class = true;
                class_can_negate = true;
            } else if in_class {
                if ch == ']' && !first_in_class {
                    in_class = false;
                }
                if ch != '^' || !class_can_negate {
                    first_in_class = false;
                }
                class_can_negate = false;
            }
            linear.push(ch);
            assertions.push(ch);
        }
    }
    Ok((
        if needs_assertions { assertions } else { linear },
        needs_assertions,
    ))
}

fn compile(pattern: &str, full: bool) -> Result<Compiled> {
    let (mut source, assertions) = translate(pattern)?;
    if full {
        source = format!(r"\A(?:{source})\z");
    }
    if assertions {
        Ok(Compiled::Assertions(Arc::new(
            fancy_regex::RegexBuilder::new(&source)
                .backtrack_limit(1_000_000)
                .build()?,
        )))
    } else {
        Ok(Compiled::Linear(regex::Regex::new(&source)?))
    }
}

// Bound retained pattern count and source bytes. Oversized valid patterns still
// work, but are not retained. Compilation and matching never hold the cache lock.
const CACHE_ENTRIES: usize = 16;
const CACHE_PATTERN_BYTES: usize = 4096;
type PatternCache = VecDeque<(String, bool, Arc<Compiled>)>;

fn cached_compile(pattern: &str, full: bool) -> Result<Arc<Compiled>> {
    static CACHE: OnceLock<Mutex<PatternCache>> = OnceLock::new();
    cached_compile_in(
        CACHE.get_or_init(|| Mutex::new(VecDeque::new())),
        pattern,
        full,
    )
}

fn cached_compile_in(
    cache: &Mutex<PatternCache>,
    pattern: &str,
    full: bool,
) -> Result<Arc<Compiled>> {
    if pattern.len() > CACHE_PATTERN_BYTES {
        return Ok(Arc::new(compile(pattern, full)?));
    }
    {
        let mut entries = cache
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        if let Some(index) = entries
            .iter()
            .position(|(key, mode, _)| key == pattern && *mode == full)
        {
            let entry = entries.remove(index).expect("existing regex cache entry");
            let compiled = Arc::clone(&entry.2);
            entries.push_back(entry);
            return Ok(compiled);
        }
    }
    // Fail at the original call site; failed compilations are never cached.
    let compiled = Arc::new(compile(pattern, full)?);
    let mut entries = cache
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    // Another thread may have compiled the same pattern while the lock was free.
    if let Some((_, _, existing)) = entries
        .iter()
        .find(|(key, mode, _)| key == pattern && *mode == full)
    {
        return Ok(Arc::clone(existing));
    }
    if entries.len() == CACHE_ENTRIES {
        entries.pop_front();
    }
    entries.push_back((pattern.to_owned(), full, Arc::clone(&compiled)));
    Ok(compiled)
}

pub fn regex_search(pattern: &str, text: &str) -> Result<bool> {
    Ok(cached_compile(pattern, false)?.first(text, 0)?.is_some())
}

pub fn regex_fullmatch(pattern: &str, text: &str) -> Result<bool> {
    Ok(cached_compile(pattern, true)?.first(text, 0)?.is_some())
}

fn cached_capture(pattern: &str, full: bool) -> Result<Arc<Compiled>> {
    let compiled = cached_compile(pattern, full)?;
    if compiled.group_count() > 65 {
        return Err("regex capture exceeds 64 groups".into());
    }
    Ok(compiled)
}

pub fn regex_capture(pattern: &str, text: &str, full: bool) -> Result<Json> {
    if pattern.len() > 4096 || text.len() > 65536 {
        return Err("regex capture exceeds pattern or input byte limit".into());
    }
    let Some(captures) = cached_capture(pattern, full)?.groups(text)? else {
        return Ok(Json::Null);
    };
    let (mut groups, mut spans) = (
        Vec::with_capacity(captures.len()),
        Vec::with_capacity(captures.len()),
    );
    for value in captures {
        if let Some((start, end)) = value {
            groups.push(serde_json::json!(&text[start..end]));
            spans.push(serde_json::json!([
                text[..start].chars().count(),
                text[..end].chars().count()
            ]));
        } else {
            groups.push(Json::Null);
            spans.push(Json::Null);
        }
    }
    // Move the already constructed JSON values; json! would serialize them again.
    Ok(Json::Object(
        [
            ("groups".to_owned(), Json::Array(groups)),
            ("spans".to_owned(), Json::Array(spans)),
        ]
        .into_iter()
        .collect(),
    ))
}

/// Internal lowering for capture results whose spans cannot be observed.
pub fn regex_capture_groups(pattern: &str, text: &str, full: bool) -> Result<Json> {
    if pattern.len() > 4096 || text.len() > 65536 {
        return Err("regex capture exceeds pattern or input byte limit".into());
    }
    let Some(captures) = cached_capture(pattern, full)?.groups(text)? else {
        return Ok(Json::Null);
    };
    let groups = captures
        .into_iter()
        .map(|span| match span {
            Some((start, end)) => Json::String(text[start..end].to_owned()),
            None => Json::Null,
        })
        .collect();
    Ok(Json::Object(
        [("groups".to_owned(), Json::Array(groups))]
            .into_iter()
            .collect(),
    ))
}

fn spans(pattern: &str, text: &str) -> Result<Vec<Span>> {
    let compiled = cached_compile(pattern, false)?;
    let mut result = Vec::new();
    let mut cursor = 0;
    while let Some((start, end)) = compiled.first(text, cursor)? {
        if start == end {
            return Err("zero-width findall/replace matches are unsupported".into());
        }
        result.push((start, end));
        // Restart at the exact end: an adjacent empty match must be rejected, not skipped.
        cursor = end;
    }
    Ok(result)
}

pub fn regex_findall(pattern: &str, text: &str) -> Result<Vec<String>> {
    Ok(spans(pattern, text)?
        .into_iter()
        .map(|(start, end)| text[start..end].to_string())
        .collect())
}

pub fn regex_replace(pattern: &str, replacement: &str, text: &str) -> Result<String> {
    let matches = spans(pattern, text)?;
    let mut result = String::new();
    let mut previous = 0;
    for (start, end) in matches {
        result.push_str(&text[previous..start]);
        result.push_str(replacement);
        previous = end;
    }
    result.push_str(&text[previous..]);
    Ok(result)
}

#[cfg(test)]
mod cache_tests {
    use super::*;

    #[test]
    fn reuses_patterns_separates_modes_and_evicts() {
        let cache = Mutex::new(VecDeque::new());
        let first = cached_compile_in(&cache, "a", false).unwrap();
        assert!(Arc::ptr_eq(
            &first,
            &cached_compile_in(&cache, "a", false).unwrap()
        ));
        let full = cached_compile_in(&cache, "a", true).unwrap();
        assert!(!Arc::ptr_eq(&first, &full));
        assert!(first.first("ba", 0).unwrap().is_some());
        assert!(full.first("ba", 0).unwrap().is_none());
        for i in 0..CACHE_ENTRIES {
            cached_compile_in(&cache, &format!("pattern{i}"), false).unwrap();
        }
        assert_eq!(cache.lock().unwrap().len(), CACHE_ENTRIES);
        assert!(!Arc::ptr_eq(
            &first,
            &cached_compile_in(&cache, "a", false).unwrap()
        ));
        let count = cache.lock().unwrap().len();
        assert!(cached_compile_in(&cache, "[", false).is_err());
        assert_eq!(cache.lock().unwrap().len(), count);
        let large = "x".repeat(CACHE_PATTERN_BYTES + 1);
        let one = cached_compile_in(&cache, &large, false).unwrap();
        let two = cached_compile_in(&cache, &large, false).unwrap();
        assert!(!Arc::ptr_eq(&one, &two));
        assert_eq!(cache.lock().unwrap().len(), count);
    }

    #[test]
    fn concurrent_reuse_returns_the_same_cached_pattern() {
        let cache = Arc::new(Mutex::new(VecDeque::new()));
        let workers: Vec<_> = (0..8)
            .map(|_| {
                let cache = Arc::clone(&cache);
                std::thread::spawn(move || {
                    let compiled = cached_compile_in(&cache, "[a-z]+", true).unwrap();
                    assert!(compiled.first("hello", 0).unwrap().is_some());
                    compiled
                })
            })
            .collect();
        let results: Vec<_> = workers
            .into_iter()
            .map(|worker| worker.join().unwrap())
            .collect();
        assert!(results
            .iter()
            .all(|compiled| Arc::ptr_eq(&results[0], compiled)));
        assert_eq!(cache.lock().unwrap().len(), 1);
    }
}
