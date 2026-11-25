//! Handwritten benchmark I/O: bounded snapshots and durable, no-replace publication.
use py2rust_service_runtime as rt;
use serde_json::Value;
use std::{
    collections::BTreeMap,
    fs,
    io::{Read, Write},
    path::{Path, PathBuf},
};
pub type Result<T> = rt::Result<T>;

pub fn require(condition: bool, message: &str) -> Result<()> {
    if condition {
        Ok(())
    } else {
        Err(message.into())
    }
}
pub fn exact(value: &Value, fields: &[&str]) -> Result<()> {
    let object = value.as_object().ok_or("expected object")?;
    require(
        object.len() == fields.len() && fields.iter().all(|key| object.contains_key(*key)),
        "unexpected fields",
    )
}
pub fn string(value: &Value) -> Result<&str> {
    value.as_str().ok_or_else(|| "expected string".into())
}
pub fn integer(value: &Value) -> Result<i64> {
    value.as_i64().ok_or_else(|| "expected integer".into())
}
pub fn canonical(value: &Value) -> Result<Vec<u8>> {
    Ok((rt::json_canonical_view(value)? + "\n").into_bytes())
}
pub fn digest(data: &[u8]) -> String {
    rt::sha256_digest(&rt::sha256_update(&rt::sha256_new(), data))
}
pub fn absolute(path: &str, base: &Path) -> Result<PathBuf> {
    require(!path.is_empty() && !path.contains('\0'), "invalid path")?;
    let path = base.join(path);
    Ok(path
        .parent()
        .ok_or("missing parent")?
        .canonicalize()?
        .join(path.file_name().ok_or("missing filename")?))
}
fn stamp(path: &Path) -> Result<Value> {
    let mut stamp = rt::path_stat(path.to_str().ok_or("invalid UTF-8 path")?, false)?;
    require(
        stamp["kind"] == "file" && stamp["links"] == 1,
        "expected unaliased regular input",
    )?;
    stamp.as_object_mut().unwrap().remove("atime_ns");
    Ok(stamp)
}
pub struct Document {
    pub path: PathBuf,
    pub data: Vec<u8>,
    stamp: Value,
}
impl Document {
    pub fn read(path: PathBuf, limit: usize) -> Result<Self> {
        let before = stamp(&path)?;
        let size = integer(&before["size"])? as usize;
        require(size <= limit, "input byte limit exceeded")?;
        let mut data = Vec::with_capacity(size);
        fs::File::open(&path)?
            .take(size as u64)
            .read_to_end(&mut data)?;
        require(
            data.len() == size && before == stamp(&path)?,
            "input changed while reading",
        )?;
        Ok(Self {
            path,
            data,
            stamp: before,
        })
    }
    pub fn metadata(&self) -> &Value {
        &self.stamp
    }
    pub fn unchanged(&self) -> Result<()> {
        require(
            self.stamp == stamp(&self.path)?,
            "input changed before publication",
        )
    }
    pub fn json(&self) -> Result<Value> {
        rt::json_loads_unique(std::str::from_utf8(&self.data)?)
    }
}
pub fn publish(
    output: &Path,
    mut files: BTreeMap<String, Vec<u8>>,
    inputs: &[Document],
    prefix: &str,
) -> Result<()> {
    let manifest: BTreeMap<_, _> = files
        .iter()
        .map(|(name, data)| {
            (
                name,
                serde_json::json!({"bytes":data.len(),"sha256":digest(data)}),
            )
        })
        .collect();
    files.insert(
        "manifest.json".into(),
        canonical(&serde_json::to_value(manifest)?)?,
    );
    publish_exact(output, files, inputs, prefix)
}
pub fn publish_exact(
    output: &Path,
    files: BTreeMap<String, Vec<u8>>,
    inputs: &[Document],
    prefix: &str,
) -> Result<()> {
    let parent = output.parent().ok_or("missing output parent")?;
    let staging = parent.join(format!(".{prefix}-{}", rt::random_token()?));
    fs::create_dir(&staging)?;
    let result = (|| -> Result<()> {
        for (name, data) in &files {
            let mut file = fs::OpenOptions::new()
                .read(true)
                .write(true)
                .create_new(true)
                .open(staging.join(name))?;
            file.write_all(data)?;
            file.sync_all()?;
        }
        fs::File::open(&staging)?.sync_all()?;
        for input in inputs {
            require(
                input.stamp == stamp(&input.path)?,
                "input changed before publication",
            )?;
        }
        rt::rename_no_replace(
            staging.to_str().ok_or("invalid path")?,
            output.to_str().ok_or("invalid path")?,
        )?;
        fs::File::open(parent)?.sync_all()?;
        Ok(())
    })();
    if staging.exists() {
        fs::remove_dir_all(staging)?;
    }
    result
}
