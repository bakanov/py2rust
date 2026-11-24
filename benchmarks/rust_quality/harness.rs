// Handwritten baselines retain checked integer arithmetic and Unicode character counts.
use std::hint::black_box;
use std::time::Instant;
#[cfg(feature = "alloc-metrics")]
mod allocations {
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicU64, Ordering};
    pub static CALLS: AtomicU64 = AtomicU64::new(0);
    pub static BYTES: AtomicU64 = AtomicU64::new(0);
    pub struct Counter;
    unsafe impl GlobalAlloc for Counter {
        unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
            CALLS.fetch_add(1, Ordering::Relaxed);
            BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
            System.alloc(layout)
        }
        unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) { System.dealloc(ptr, layout); }
        unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, size: usize) -> *mut u8 {
            CALLS.fetch_add(1, Ordering::Relaxed);
            BYTES.fetch_add(size as u64, Ordering::Relaxed);
            System.realloc(ptr, layout, size)
        }
    }
}
#[cfg(feature = "alloc-metrics")]
#[global_allocator]
static ALLOCATOR: allocations::Counter = allocations::Counter;

fn main() -> rt::Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let case = &args[1]; let native = args[2] == "native";
    let size: usize = args[3].parse()?; let rounds: i64 = args[4].parse()?;
    let repeats: usize = args[5].parse()?;
    let data = vec![42u8; if case == "bytes" {size} else {0}];
    let values: Vec<i64> = (0..if case == "list" {size} else {0}).map(|i| (i % 101) as i64).collect();
    let mut doc = serde_json::Map::new();
    doc.insert("route".into(), serde_json::json!("/messages/世界"));
    for i in 0..if case == "json" {size} else {0} { doc.insert(format!("key{i}"), serde_json::json!("x".repeat(64))); }
    let document = serde_json::Value::Object(doc);
    #[cfg(feature = "alloc-metrics")]
    { allocations::CALLS.store(0, std::sync::atomic::Ordering::Relaxed); allocations::BYTES.store(0, std::sync::atomic::Ordering::Relaxed); }
    let start = Instant::now(); let mut answer = 0i64;
    for _ in 0..repeats {
        answer = if native {
            match case.as_str() {
                "bytes" => { let mut t=0i64; for _ in 0..black_box(rounds) { t=t.checked_add(black_box(&data).len() as i64).ok_or("overflow")?; } t },
                "list" => { let mut t=0i64; for _ in 0..black_box(rounds) { for v in black_box(&values) { t=t.checked_add(*v).ok_or("overflow")?; } } t },
                "json" => { let mut t=0i64; for _ in 0..black_box(rounds) { let s=black_box(&document).get("route").and_then(|v|v.as_str()).ok_or("expected string")?; t=t.checked_add(s.chars().count() as i64).ok_or("overflow")?; } t },
                "text" => { let mut s=String::new(); for _ in 0..black_box(size) { s.push_str("message "); } black_box(s).len() as i64 },
                "arithmetic" => { let mut t=0i64; for i in 0..black_box(size as i64) { t=t.checked_add(i).ok_or("overflow")?; } t },
                _ => return Err("unknown case".into()),
            }
        } else {
            match case.as_str() {
                "bytes" => read_payload(black_box(data.as_slice()), black_box(rounds))?,
                "list" => sum_values(black_box(values.as_slice()), black_box(rounds))?,
                "json" => route(black_box(&document), black_box(rounds))?,
                "text" => black_box(build_text(black_box(size as i64))?).len() as i64,
                "arithmetic" => arithmetic(black_box(size as i64))?,
                _ => return Err("unknown case".into()),
            }
        };
        black_box(answer);
    }
    let elapsed = start.elapsed().as_nanos();
    let (mut calls, mut bytes) = (0u64,0u64);
    #[cfg(feature = "alloc-metrics")]
    { calls=allocations::CALLS.load(std::sync::atomic::Ordering::Relaxed); bytes=allocations::BYTES.load(std::sync::atomic::Ordering::Relaxed); }
    println!("{{\"answer\":{answer},\"ns\":{elapsed},\"allocations\":{calls},\"allocated_bytes\":{bytes}}}");
    Ok(())
}
