//! Small cache for compiler-proven deterministic parsers. Never retain failures.
use crate::Result;
use std::collections::VecDeque;
use std::sync::Mutex;

const MAX_ENTRIES: usize = 64;
const MAX_KEY_BYTES: usize = 256;

pub struct MemoCache<T> {
    entries: Mutex<VecDeque<(String, T)>>,
}
impl<T> MemoCache<T> {
    pub const fn new() -> Self {
        Self {
            entries: Mutex::new(VecDeque::new()),
        }
    }
}
impl<T> Default for MemoCache<T> {
    fn default() -> Self {
        Self::new()
    }
}

/// `calculate` must be deterministic for this key; the compiler audits its body.
/// No lock is held during calculation, and long keys bypass the cache entirely.
pub fn memoized<T: Copy>(
    cache: &MemoCache<T>,
    key: &str,
    calculate: impl FnOnce() -> Result<T>,
) -> Result<T> {
    if key.len() > MAX_KEY_BYTES {
        return calculate();
    }
    {
        let entries = cache
            .entries
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        if let Some((_, value)) = entries.iter().find(|(stored, _)| stored == key) {
            return Ok(*value);
        }
    }
    let result = calculate()?;
    let mut entries = cache
        .entries
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    // Concurrent callers may have computed the same deterministic result.
    if !entries.iter().any(|(stored, _)| stored == key) {
        if entries.len() == MAX_ENTRIES {
            entries.pop_front();
        }
        entries.push_back((key.to_owned(), result));
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::Cell;

    #[test]
    fn caches_success_but_not_failures_or_long_keys() {
        let cache = MemoCache::new();
        let calls = Cell::new(0);
        for _ in 0..3 {
            assert_eq!(
                memoized(&cache, "12", || {
                    calls.set(calls.get() + 1);
                    Ok(12)
                })
                .unwrap(),
                12
            );
        }
        assert_eq!(calls.get(), 1);
        for _ in 0..3 {
            assert!(memoized(&cache, "bad", || {
                calls.set(calls.get() + 1);
                Err("invalid".into())
            })
            .is_err());
        }
        assert_eq!(calls.get(), 4);
        for _ in 0..2 {
            memoized(&cache, &"x".repeat(257), || {
                calls.set(calls.get() + 1);
                Ok(0)
            })
            .unwrap();
        }
        assert_eq!(calls.get(), 6);
        assert_eq!(cache.entries.lock().unwrap().len(), 1);
    }

    #[test]
    fn bounded_fifo_and_calculation_without_lock() {
        let cache = MemoCache::new();
        for value in 0..100 {
            assert_eq!(
                memoized(&cache, &value.to_string(), || Ok(value)).unwrap(),
                value
            );
        }
        assert_eq!(cache.entries.lock().unwrap().len(), MAX_ENTRIES);
        assert_eq!(cache.entries.lock().unwrap().front().unwrap().0, "36");
        memoized(&cache, "outer", || memoized(&cache, "inner", || Ok(100))).unwrap();
        assert_eq!(cache.entries.lock().unwrap().len(), MAX_ENTRIES);
    }
    #[test]
    fn concurrent_identical_keys_keep_one_entry() {
        let cache = MemoCache::new();
        let ready = std::sync::Barrier::new(8);
        std::thread::scope(|scope| {
            for _ in 0..8 {
                scope.spawn(|| {
                    ready.wait();
                    for _ in 0..100 {
                        assert_eq!(
                            memoized(&cache, "same", || Ok((1, 2, 3))).unwrap(),
                            (1, 2, 3)
                        );
                    }
                });
            }
        });
        assert_eq!(cache.entries.lock().unwrap().len(), 1);
    }
}
