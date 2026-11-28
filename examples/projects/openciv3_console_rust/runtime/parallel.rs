//! Scoped callback workers. Result order is stable even when completion order is not.
use crate::{json_check, Json, Result};
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Mutex,
};

pub fn parallel_map(
    callback: fn(Json) -> Result<Json>,
    items: &[Json],
    workers: i64,
) -> Result<Vec<Json>> {
    if !(1..=64).contains(&workers) || items.len() > 10000 {
        return Err("parallel_map requires 1..64 workers and at most 10000 JSON items".into());
    }
    for item in items {
        json_check(item, 0)?;
    }
    let next = AtomicUsize::new(0);
    let outcomes: Mutex<Vec<Option<Result<Json>>>> =
        Mutex::new((0..items.len()).map(|_| None).collect());
    std::thread::scope(|scope| -> Result<()> {
        for worker in 0..(workers as usize).min(items.len()) {
            std::thread::Builder::new()
                .name(format!("py2rust-worker-{worker}"))
                .spawn_scoped(scope, || {
                    loop {
                        let index = next.fetch_add(1, Ordering::Relaxed);
                        let Some(item) = items.get(index) else {
                            break;
                        };
                        // Callbacks never run while the result mutex is held.
                        let result = callback(item.clone()).and_then(|value| {
                            json_check(&value, 0)?;
                            Ok(value)
                        });
                        outcomes.lock().unwrap()[index] = Some(result);
                    }
                })?;
        }
        Ok(())
    })?;
    // The scope has joined every worker. Return the first error in input order.
    outcomes
        .into_inner()
        .map_err(|_| "parallel result mutex poisoned")?
        .into_iter()
        .map(|value| {
            value
                .ok_or_else(|| "parallel callback result missing".into())
                .and_then(|value| value)
        })
        .collect()
}
