// Ordinary Rust functions: the project compiler reads these signatures.
pub fn route(path: &str) -> String {
    path.split('?').next().unwrap_or("/").to_owned()
}

pub fn payload_size(data: &[u8]) -> usize {
    data.len()
}
