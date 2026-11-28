//! Stable sorting with one fallible key evaluation per source item.
use crate::Result;

pub fn sorted_by_key<T: Clone, K: Ord>(
    values: Vec<T>,
    mut key: impl FnMut(T) -> Result<K>,
    reverse: bool,
) -> Result<Vec<T>> {
    let mut decorated = Vec::with_capacity(values.len());
    for value in values {
        // Source function arguments have owned-value semantics. Keep the
        // original item even if the callback changes its independent copy.
        decorated.push((key(value.clone())?, value));
    }
    decorated.sort_by(|left, right| {
        if reverse {
            right.0.cmp(&left.0)
        } else {
            left.0.cmp(&right.0)
        }
    });
    Ok(decorated.into_iter().map(|(_, value)| value).collect())
}

pub fn sorted_by_comparable_key<T: Clone, K>(
    values: Vec<T>,
    mut key: impl FnMut(T) -> Result<K>,
    reverse: bool,
    compare: impl Fn(&K, &K) -> std::cmp::Ordering,
) -> Result<Vec<T>> {
    let mut decorated = Vec::with_capacity(values.len());
    for value in values {
        decorated.push((key(value.clone())?, value));
    }
    decorated.sort_by(|left, right| {
        if reverse {
            compare(&right.0, &left.0)
        } else {
            compare(&left.0, &right.0)
        }
    });
    Ok(decorated.into_iter().map(|(_, value)| value).collect())
}

pub fn sorted_by_float_key<T: Clone>(
    values: Vec<T>,
    mut key: impl FnMut(T) -> Result<f64>,
    reverse: bool,
) -> Result<Vec<T>> {
    let mut decorated = Vec::with_capacity(values.len());
    for value in values {
        decorated.push((key(value.clone())?, value));
    }
    decorated.sort_by(|left, right| {
        if reverse {
            right.0.total_cmp(&left.0)
        } else {
            left.0.total_cmp(&right.0)
        }
    });
    Ok(decorated.into_iter().map(|(_, value)| value).collect())
}
