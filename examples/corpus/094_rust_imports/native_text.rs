//! General Unicode, binary and fallible-text operations used to inspect native boundaries.
pub fn inspect(value: &str) -> (i64, i64, String) {
    (
        value.chars().count() as i64,
        value.len() as i64,
        value.chars().rev().collect(),
    )
}
pub fn transform(value: &[u8]) -> (Vec<u8>, i64) {
    (
        value.iter().rev().map(|byte| byte ^ 0xa5).collect(),
        value.len() as i64,
    )
}
pub fn accept(value: &str) -> Result<String, String> {
    if value == "deny" {
        Err("native rejected text".into())
    } else {
        Ok(format!("accepted:{value}"))
    }
}
pub fn unit(_value: &str) {}
