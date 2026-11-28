//! Streaming single-member gzip. Explicit finish is the only writer success receipt.
use crate::resources::Resource;
use crate::Result;
use flate2::{bufread::GzDecoder, write::GzEncoder, Compression, GzBuilder};
use std::fs::{File, OpenOptions};
use std::io::{self, BufRead, BufReader, Read, Write};
use std::sync::{Arc, Mutex};

fn limit(value: i64) -> Result<u64> {
    Ok(u64::try_from(value).map_err(|_| "gzip limit must be nonnegative")?)
}

fn open(path: &str, writing: bool) -> Result<File> {
    if path.is_empty() || path.as_bytes().contains(&0) {
        return Err("gzip path must be nonempty and NUL-free".into());
    }
    let mut options = OpenOptions::new();
    if writing {
        options.write(true).create_new(true);
    } else {
        options.read(true);
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK);
    }
    let file = options.open(path)?;
    if !file.metadata()?.is_file() {
        return Err("gzip requires a regular file".into());
    }
    Ok(file)
}

#[derive(Debug)]
struct LimitedFile {
    file: File,
    maximum: u64,
    count: u64,
    failed: bool,
}
impl Read for LimitedFile {
    fn read(&mut self, data: &mut [u8]) -> io::Result<usize> {
        if data.is_empty() {
            return Ok(0);
        }
        let available = (self.maximum - self.count).min(data.len() as u64) as usize;
        if available == 0 {
            let mut probe = [0u8; 1];
            return match self.file.read(&mut probe)? {
                0 => Ok(0),
                _ => Err(io::Error::other("gzip compressed input exceeds limit")),
            };
        }
        let count = self.file.read(&mut data[..available])?;
        self.count += count as u64;
        Ok(count)
    }
}
impl Write for LimitedFile {
    fn write(&mut self, data: &[u8]) -> io::Result<usize> {
        if self.failed || data.len() as u64 > self.maximum - self.count {
            self.failed = true;
            return Err(io::Error::other(
                "gzip compressed output exceeds limit or writer aborted",
            ));
        }
        let count = self.file.write(data)?;
        self.count += count as u64;
        Ok(count)
    }
    fn flush(&mut self) -> io::Result<()> {
        self.file.flush()
    }
}

#[derive(Debug)]
struct WriterState {
    encoder: GzEncoder<LimitedFile>,
    expanded: u64,
    maximum: u64,
}
impl Drop for WriterState {
    fn drop(&mut self) {
        // GzEncoder's drop tries to finish. An abandoned resource must not gain
        // a success trailer, and a failed encoder must not retry partial writes.
        self.encoder.get_mut().failed = true;
    }
}
#[derive(Clone, Debug)]
pub struct GzipWriter(Arc<Mutex<Option<WriterState>>>);
impl Resource for GzipWriter {
    fn check_open(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "gzip writer lock poisoned")?
            .as_ref()
            .ok_or("gzip writer is closed")?;
        Ok(())
    }
    fn close(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "gzip writer lock poisoned")?
            .take();
        Ok(())
    }
}
pub fn gzip_create(
    path: &str,
    level: i64,
    compressed_limit: i64,
    expanded_limit: i64,
) -> Result<GzipWriter> {
    let compressed = limit(compressed_limit)?;
    let expanded = limit(expanded_limit)?;
    if !(0..=9).contains(&level) {
        return Err("gzip compression level must be 0..9".into());
    }
    if compressed < 10 {
        return Err("gzip output limit is smaller than its header".into());
    }
    let file = LimitedFile {
        file: open(path, true)?,
        maximum: compressed,
        count: 0,
        failed: false,
    };
    let mut encoder = GzBuilder::new()
        .mtime(0)
        .operating_system(255)
        .write(file, Compression::new(level as u32));
    // Emit the header now in both engines; write_all(empty) would skip Write::write.
    if let Err(error) = encoder.write(&[]) {
        encoder.get_mut().failed = true;
        return Err(error.into());
    }
    Ok(GzipWriter(Arc::new(Mutex::new(Some(WriterState {
        encoder,
        expanded: 0,
        maximum: expanded,
    })))))
}
pub fn gzip_write(handle: &GzipWriter, data: &[u8]) -> Result<()> {
    if data.len() > 1048576 {
        return Err("gzip write requires at most 1 MiB of bytes".into());
    }
    let mut guard = handle.0.lock().map_err(|_| "gzip writer lock poisoned")?;
    let result = (|| -> Result<()> {
        let state = guard.as_mut().ok_or("gzip writer is closed")?;
        if data.len() as u64 > state.maximum - state.expanded {
            return Err("gzip expanded output exceeds limit".into());
        }
        state.encoder.write_all(data)?;
        state.expanded += data.len() as u64;
        Ok(())
    })();
    if result.is_err() {
        guard.take();
    }
    result
}
pub fn gzip_finish(handle: &GzipWriter) -> Result<(i64, i64)> {
    let mut state = handle
        .0
        .lock()
        .map_err(|_| "gzip writer lock poisoned")?
        .take()
        .ok_or("gzip writer is closed")?;
    state.encoder.try_finish()?;
    state.encoder.get_ref().file.sync_all()?;
    Ok((state.encoder.get_ref().count as i64, state.expanded as i64))
}
pub fn gzip_writer_close(handle: &GzipWriter) -> Result<()> {
    handle.close()
}

#[derive(Debug)]
struct ReaderState {
    decoder: GzDecoder<BufReader<LimitedFile>>,
    expanded: u64,
    maximum: u64,
    eof: bool,
}
#[derive(Clone, Debug)]
pub struct GzipReader(Arc<Mutex<Option<ReaderState>>>);
impl Resource for GzipReader {
    fn check_open(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "gzip reader lock poisoned")?
            .as_ref()
            .ok_or("gzip reader is closed")?;
        Ok(())
    }
    fn close(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "gzip reader lock poisoned")?
            .take();
        Ok(())
    }
}
pub fn gzip_open(path: &str, compressed_limit: i64, expanded_limit: i64) -> Result<GzipReader> {
    let compressed = limit(compressed_limit)?;
    let expanded = limit(expanded_limit)?;
    let file = open(path, false)?;
    if file.metadata()?.len() > compressed {
        return Err("gzip compressed input exceeds limit".into());
    }
    let source = LimitedFile {
        file,
        maximum: compressed,
        count: 0,
        failed: false,
    };
    let decoder = GzDecoder::new(BufReader::with_capacity(65536, source));
    if decoder.header().is_none() {
        return Err("invalid or truncated gzip header".into());
    }
    Ok(GzipReader(Arc::new(Mutex::new(Some(ReaderState {
        decoder,
        expanded: 0,
        maximum: expanded,
        eof: false,
    })))))
}
pub fn gzip_read(handle: &GzipReader, count: i64) -> Result<Vec<u8>> {
    if !(1..=1048576).contains(&count) {
        return Err("gzip read size must be 1..1 MiB".into());
    }
    let mut guard = handle.0.lock().map_err(|_| "gzip reader lock poisoned")?;
    let result = (|| -> Result<Vec<u8>> {
        let state = guard.as_mut().ok_or("gzip reader is closed")?;
        let mut output = vec![0u8; count as usize];
        let mut used = 0;
        while used < output.len() && !state.eof {
            let available =
                (state.maximum - state.expanded + 1).min((output.len() - used) as u64) as usize;
            let received = state.decoder.read(&mut output[used..used + available])?;
            if received == 0 {
                if !state.decoder.get_mut().fill_buf()?.is_empty() {
                    return Err("expected exactly one gzip member without trailing data".into());
                }
                state.eof = true;
            } else {
                if received as u64 > state.maximum - state.expanded {
                    return Err("gzip expanded input exceeds limit".into());
                }
                state.expanded += received as u64;
                used += received;
            }
        }
        output.truncate(used);
        Ok(output)
    })();
    if result.is_err() {
        guard.take();
    }
    result
}
pub fn gzip_reader_close(handle: &GzipReader) -> Result<()> {
    handle.close()
}
