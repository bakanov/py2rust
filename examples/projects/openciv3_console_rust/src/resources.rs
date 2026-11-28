//! Scoped regular files and incremental digests; protocol policy stays in applications.
use crate::Result;
use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, Read, Seek, SeekFrom, Write};
use std::path::Path;
use std::sync::{Arc, Mutex, MutexGuard};

pub trait Resource: Clone {
    fn check_open(&self) -> Result<()>;
    fn close(&self) -> Result<()>;
}
/// Drop also runs on Result propagation, returns, break and continue.
pub struct ResourceGuard<T: Resource>(T);
impl<T: Resource> ResourceGuard<T> {
    pub fn new(handle: T) -> Result<Self> {
        handle.check_open()?;
        Ok(Self(handle))
    }
    pub fn handle(&self) -> T {
        self.0.clone()
    }
}
impl<T: Resource> Drop for ResourceGuard<T> {
    fn drop(&mut self) {
        let _ = self.0.close();
    }
}

#[derive(Clone, Debug)]
pub struct FileHandle(Arc<Mutex<Option<File>>>);
impl FileHandle {
    fn lock(&self) -> Result<MutexGuard<'_, Option<File>>> {
        Ok(self.0.lock().map_err(|_| "file lock poisoned")?)
    }
}
impl Resource for FileHandle {
    fn check_open(&self) -> Result<()> {
        self.lock()?.as_ref().ok_or("file is closed")?;
        Ok(())
    }
    fn close(&self) -> Result<()> {
        self.lock()?.take();
        Ok(())
    }
}

/// A shared, buffered, read-only byte cursor. Chunks never exceed the caller's
/// limit; a single oversized logical line can therefore be streamed or skipped.
#[derive(Clone, Debug)]
pub struct LineReader(Arc<Mutex<Option<BufReader<File>>>>);
impl LineReader {
    fn lock(&self) -> Result<MutexGuard<'_, Option<BufReader<File>>>> {
        Ok(self.0.lock().map_err(|_| "line reader lock poisoned")?)
    }
}
impl Resource for LineReader {
    fn check_open(&self) -> Result<()> {
        self.lock()?.as_ref().ok_or("line reader is closed")?;
        Ok(())
    }
    fn close(&self) -> Result<()> {
        self.lock()?.take();
        Ok(())
    }
}
pub fn line_open(path: &str, offset: i64) -> Result<LineReader> {
    let offset = u64::try_from(offset)
        .map_err(|_| "line offset must fit a nonnegative signed 64-bit integer")?;
    if let Ok(metadata) = std::fs::metadata(path) {
        if !metadata.is_file() {
            return Err("expected a regular file".into());
        }
    }
    let file = File::open(path)?;
    if !file.metadata()?.is_file() {
        return Err("expected a regular file".into());
    }
    if offset > file.metadata()?.len() {
        return Err("line offset exceeds file size".into());
    }
    let mut reader = BufReader::with_capacity(65536, file);
    reader.seek(SeekFrom::Start(offset))?;
    Ok(LineReader(Arc::new(Mutex::new(Some(reader)))))
}
pub fn line_read(handle: &LineReader, limit: i64) -> Result<(Vec<u8>, bool)> {
    if !(1..=1048576).contains(&limit) {
        return Err("line read limit must be 1..1 MiB".into());
    }
    let mut guard = handle.lock()?;
    let reader = guard.as_mut().ok_or("line reader is closed")?;
    let mut data = Vec::new();
    while data.len() < limit as usize {
        let buffer = reader.fill_buf()?;
        let count = buffer.len().min(limit as usize - data.len());
        if count == 0 {
            break;
        }
        let part = &buffer[..count];
        let take = part
            .iter()
            .position(|byte| *byte == b'\n')
            .map_or(count, |index| index + 1);
        data.extend_from_slice(&part[..take]);
        reader.consume(take);
        if data.ends_with(b"\n") {
            break;
        }
    }
    let complete = data.ends_with(b"\n") || reader.fill_buf()?.is_empty();
    Ok((data, complete))
}
pub fn line_position(handle: &LineReader) -> Result<i64> {
    Ok(i64::try_from(
        handle
            .lock()?
            .as_mut()
            .ok_or("line reader is closed")?
            .stream_position()?,
    )?)
}
pub fn line_close(handle: &LineReader) -> Result<()> {
    handle.close()
}

/// Nonblocking, exclusive advisory lock. Closing the shared handle releases it;
/// the persistent lock file must not be removed while processes may use it.
#[cfg(unix)]
pub fn file_lock(path: &str) -> Result<FileHandle> {
    use std::os::fd::AsRawFd;
    use std::os::unix::fs::OpenOptionsExt;
    if path.is_empty() || path.as_bytes().contains(&0) {
        return Err("lock path must be nonempty and NUL-free".into());
    }
    let path: std::path::PathBuf = Path::new(path).components().collect();
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)?;
    if !file.metadata()?.is_file() {
        return Err("lock requires a regular file".into());
    }
    // SAFETY: the descriptor is owned by the live File and flock retains no pointer.
    if unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    Ok(FileHandle(Arc::new(Mutex::new(Some(file)))))
}
#[cfg(not(unix))]
pub fn file_lock(_path: &str) -> Result<FileHandle> {
    Err("file_lock currently requires Unix".into())
}

pub fn file_open(path: &str, mode: &str) -> Result<FileHandle> {
    let mut options = OpenOptions::new();
    match mode {
        "rb" => {
            options.read(true);
        }
        "r+b" => {
            options.read(true).write(true);
        }
        "x+b" => {
            options.read(true).write(true).create_new(true);
        }
        "w+b" => {
            options.read(true).write(true).create(true).truncate(true);
        }
        _ => return Err("file mode must be rb, r+b, x+b or w+b".into()),
    }
    if let Ok(metadata) = std::fs::metadata(path) {
        if !metadata.is_file() {
            return Err("expected a regular file".into());
        }
    }
    let file = options.open(path)?;
    if !file.metadata()?.is_file() {
        return Err("expected a regular file".into());
    }
    Ok(FileHandle(Arc::new(Mutex::new(Some(file)))))
}
pub fn file_read(handle: &FileHandle, count: i64) -> Result<Vec<u8>> {
    if !(1..=33554432).contains(&count) {
        return Err("file read size must be 1..32 MiB".into());
    }
    let mut guard = handle.lock()?;
    let file = guard.as_mut().ok_or("file is closed")?;
    let mut data = Vec::new();
    file.take(count as u64).read_to_end(&mut data)?;
    Ok(data)
}
pub fn file_write(handle: &FileHandle, data: &[u8]) -> Result<()> {
    if data.len() > 33554432 {
        return Err("file write exceeds 32 MiB".into());
    }
    handle
        .lock()?
        .as_mut()
        .ok_or("file is closed")?
        .write_all(data)?;
    Ok(())
}
pub fn file_seek(handle: &FileHandle, offset: i64, whence: i64) -> Result<i64> {
    let seek = match whence {
        0 => SeekFrom::Start(u64::try_from(offset)?),
        1 => SeekFrom::Current(offset),
        2 => SeekFrom::End(offset),
        _ => return Err("seek whence must be 0, 1 or 2".into()),
    };
    Ok(i64::try_from(
        handle
            .lock()?
            .as_mut()
            .ok_or("file is closed")?
            .seek(seek)?,
    )?)
}
pub fn file_size(handle: &FileHandle) -> Result<i64> {
    let size = handle
        .lock()?
        .as_ref()
        .ok_or("file is closed")?
        .metadata()?
        .len();
    Ok(i64::try_from(size)?)
}
pub fn file_truncate(handle: &FileHandle, length: i64) -> Result<()> {
    handle
        .lock()?
        .as_mut()
        .ok_or("file is closed")?
        .set_len(u64::try_from(length)?)?;
    Ok(())
}
pub fn file_sync(handle: &FileHandle) -> Result<()> {
    handle
        .lock()?
        .as_ref()
        .ok_or("file is closed")?
        .sync_all()?;
    Ok(())
}
pub fn file_close(handle: &FileHandle) -> Result<()> {
    handle.close()
}
pub fn link_file(source: &str, destination: &str) -> Result<()> {
    if !std::fs::metadata(source)?.is_file() {
        return Err("expected a regular source file".into());
    }
    std::fs::hard_link(source, destination)?;
    Ok(())
}
pub fn sync_directory(path: &str) -> Result<()> {
    let file = File::open(path)?;
    if !file.metadata()?.is_dir() {
        return Err("expected a directory".into());
    }
    file.sync_all()?;
    Ok(())
}
pub fn path_parent(path: &str) -> Result<String> {
    let path = Path::new(path);
    let parent = path.parent().unwrap_or_else(|| {
        if path.has_root() {
            path
        } else {
            Path::new(".")
        }
    });
    Ok(if parent.as_os_str().is_empty() {
        "."
    } else {
        parent.to_str().ok_or("path is not UTF-8")?
    }
    .to_string())
}
pub fn path_name(path: &str) -> Result<String> {
    Ok(Path::new(path)
        .file_name()
        .ok_or("path needs a file name")?
        .to_str()
        .ok_or("path is not UTF-8")?
        .to_string())
}
pub fn path_is_symlink(path: &str) -> Result<bool> {
    match std::fs::symlink_metadata(path) {
        Ok(metadata) => Ok(metadata.file_type().is_symlink()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(error) => Err(error.into()),
    }
}
pub fn path_same(left: &str, right: &str) -> Result<bool> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        let a = std::fs::metadata(left)?;
        let b = std::fs::metadata(right)?;
        Ok(a.dev() == b.dev() && a.ino() == b.ino())
    }
    #[cfg(not(unix))]
    {
        let _ = (left, right);
        Err("file identity checks currently require Unix".into())
    }
}

#[derive(Clone)]
pub struct Sha256(ring::digest::Context);
pub fn sha256_new() -> Sha256 {
    Sha256(ring::digest::Context::new(&ring::digest::SHA256))
}
pub fn sha256_update(state: &Sha256, bytes: &[u8]) -> Sha256 {
    let mut updated = state.clone();
    updated.0.update(bytes);
    updated
}
pub fn sha256_digest(state: &Sha256) -> String {
    crate::bytes_hex(state.0.clone().finish().as_ref())
}
