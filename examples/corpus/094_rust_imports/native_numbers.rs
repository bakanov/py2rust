//! Small ABI probes. Case policy and expected-value computation stay in Python.
pub fn narrow(value: u8) -> i64 {
    i64::from(value)
}
pub fn unsigned_result(value: i64) -> u64 {
    if value < 0 {
        u64::MAX
    } else {
        value as u64
    }
}
pub fn double_width(value: i64) -> i128 {
    i128::from(value) * 2
}
pub fn checked_add(left: i64, right: i64) -> Result<i64, String> {
    left.checked_add(right)
        .ok_or_else(|| "native integer overflow".to_owned())
}
pub fn invert(value: bool) -> bool {
    !value
}
