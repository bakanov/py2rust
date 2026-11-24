//! Deliberately invalid native return values exercise generated boundary validation.
fn scalar(mode: &str) -> f64 {
    match mode {
        "nan" => f64::NAN,
        "inf" => f64::INFINITY,
        "negative_inf" => f64::NEG_INFINITY,
        _ => 1.25,
    }
}
pub fn special(mode: &str) -> f64 {
    scalar(mode)
}
pub fn nested(mode: &str) -> (Vec<f64>, (f64, String)) {
    let first = if mode == "nan" { f64::NAN } else { 1.25 };
    let last = if mode == "inf" || mode == "negative_inf" {
        scalar(mode)
    } else {
        2.5
    };
    (vec![first, -0.0], (last, "ok".to_owned()))
}
pub fn document(mode: &str) -> serde_json::Value {
    if mode == "wide" {
        serde_json::json!({"value": u64::MAX})
    } else {
        serde_json::json!({"items": [1, true, null, {"text": "世界"}]})
    }
}
pub fn roundtrip(value: serde_json::Value) -> serde_json::Value {
    value
}
