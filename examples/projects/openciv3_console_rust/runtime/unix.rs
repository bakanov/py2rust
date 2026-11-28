//! Filesystem Unix sockets with owned-path cleanup and the shared stream contract.
use crate::{resources::Resource, Result};
use std::io::{ErrorKind, Read, Write};
use std::net::Shutdown;
use std::os::unix::fs::{FileTypeExt, MetadataExt};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

fn socket_path(path: &str) -> Result<PathBuf> {
    if path.is_empty() || path.as_bytes().contains(&0) || path.ends_with('/') {
        return Err("Unix socket requires a nonempty filesystem path".into());
    }
    let path = Path::new(path);
    let name = path.file_name().ok_or("Unix socket requires a basename")?;
    let parent = path
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let absolute = parent.canonicalize()?.join(name);
    if absolute.to_str().ok_or("Unix path must be UTF-8")?.len() > 107 {
        return Err("Unix socket path exceeds 107 UTF-8 bytes".into());
    }
    Ok(absolute)
}
fn identity(path: &Path) -> std::io::Result<(u64, u64)> {
    let meta = path.symlink_metadata()?;
    if !meta.file_type().is_socket() {
        return Err(std::io::Error::new(
            ErrorKind::AlreadyExists,
            "Unix socket path is not a socket",
        ));
    }
    Ok((meta.dev(), meta.ino()))
}
fn remove_owned(path: &Path, expected: (u64, u64)) -> Result<()> {
    match identity(path) {
        Ok(actual) if actual == expected => std::fs::remove_file(path)?,
        Ok(_) => {}
        Err(error) if matches!(error.kind(), ErrorKind::NotFound | ErrorKind::AlreadyExists) => {}
        Err(error) => return Err(error.into()),
    }
    Ok(())
}
struct Bound {
    socket: std::os::unix::net::UnixListener,
    path: PathBuf,
    identity: (u64, u64),
}
impl Drop for Bound {
    fn drop(&mut self) {
        let _ = remove_owned(&self.path, self.identity);
    }
}
fn duration(timeout_ms: i64) -> Result<Duration> {
    if !(1..=86400000).contains(&timeout_ms) {
        return Err("Unix timeout must be 1..86400000 milliseconds".into());
    }
    Ok(Duration::from_millis(timeout_ms as u64))
}
fn remaining(deadline: Instant) -> Result<Duration> {
    deadline
        .checked_duration_since(Instant::now())
        .filter(|value| !value.is_zero())
        .ok_or_else(|| "Unix deadline exceeded".into())
}

#[derive(Clone)]
pub struct UnixListener(Arc<Mutex<Option<Bound>>>);
impl Resource for UnixListener {
    fn check_open(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "Unix listener lock poisoned")?
            .as_ref()
            .ok_or("Unix listener is closed")?;
        Ok(())
    }
    fn close(&self) -> Result<()> {
        let bound = self
            .0
            .lock()
            .map_err(|_| "Unix listener lock poisoned")?
            .take();
        if let Some(bound) = bound {
            remove_owned(&bound.path, bound.identity)?;
        }
        Ok(())
    }
}
struct StreamState {
    socket: std::os::unix::net::UnixStream,
    deadline: Instant,
}
#[derive(Clone)]
pub struct UnixStream(Arc<Mutex<Option<StreamState>>>);
impl Resource for UnixStream {
    fn check_open(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "Unix stream lock poisoned")?
            .as_ref()
            .ok_or("Unix stream is closed")?;
        Ok(())
    }
    fn close(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "Unix stream lock poisoned")?
            .take();
        Ok(())
    }
}
fn stream(socket: std::os::unix::net::UnixStream, timeout: Duration) -> Result<UnixStream> {
    socket.set_nonblocking(false)?;
    Ok(UnixStream(Arc::new(Mutex::new(Some(StreamState {
        socket,
        deadline: Instant::now() + timeout,
    })))))
}
pub fn unix_listen(path: &str, recover_stale: bool) -> Result<UnixListener> {
    let path = socket_path(path)?;
    match path.symlink_metadata() {
        Ok(_) => {
            let expected = identity(&path)?;
            if !recover_stale {
                return Err("Unix socket path already exists".into());
            }
            // A bounded successful probe means a live listener; only ECONNREFUSED
            // establishes a stale filesystem socket. Never unlink on a timeout.
            let probe = socket2::Socket::new(socket2::Domain::UNIX, socket2::Type::STREAM, None)?;
            match probe
                .connect_timeout(&socket2::SockAddr::unix(&path)?, Duration::from_millis(100))
            {
                Err(error) if error.kind() == ErrorKind::ConnectionRefused => {}
                Err(error) => return Err(error.into()),
                Ok(()) => return Err("Unix socket has an active listener".into()),
            }
            if identity(&path)? != expected {
                return Err("Unix socket path changed during recovery".into());
            }
            std::fs::remove_file(&path)?;
        }
        Err(error) if error.kind() == ErrorKind::NotFound => {}
        Err(error) => return Err(error.into()),
    }
    let socket = std::os::unix::net::UnixListener::bind(&path)?;
    let owned = Bound {
        socket,
        identity: identity(&path)?,
        path,
    };
    owned.socket.set_nonblocking(true)?;
    Ok(UnixListener(Arc::new(Mutex::new(Some(owned)))))
}
pub fn unix_connect(path: &str, timeout_ms: i64) -> Result<UnixStream> {
    let timeout = duration(timeout_ms)?;
    let socket = socket2::Socket::new(socket2::Domain::UNIX, socket2::Type::STREAM, None)?;
    socket.connect_timeout(&socket2::SockAddr::unix(socket_path(path)?)?, timeout)?;
    stream(socket.into(), timeout)
}
pub fn unix_accept_timeout(
    handle: &UnixListener,
    accept_ms: i64,
    io_ms: i64,
) -> Result<UnixStream> {
    let deadline = Instant::now() + duration(accept_ms)?;
    let io_timeout = duration(io_ms)?;
    loop {
        let left = remaining(deadline)?;
        let accepted = handle
            .0
            .lock()
            .map_err(|_| "Unix listener lock poisoned")?
            .as_ref()
            .ok_or("Unix listener is closed")?
            .socket
            .accept();
        match accepted {
            Ok((socket, _)) => return stream(socket, io_timeout),
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            Err(error) if error.kind() == ErrorKind::WouldBlock => {
                std::thread::sleep(left.min(Duration::from_millis(2)));
            }
            Err(error) => return Err(error.into()),
        }
    }
}
pub fn unix_set_deadline(handle: &UnixStream, timeout_ms: i64) -> Result<()> {
    let deadline = Instant::now() + duration(timeout_ms)?;
    handle
        .0
        .lock()
        .map_err(|_| "Unix stream lock poisoned")?
        .as_mut()
        .ok_or("Unix stream is closed")?
        .deadline = deadline;
    Ok(())
}
pub fn unix_recv(handle: &UnixStream, count: i64) -> Result<Vec<u8>> {
    if !(1..=1048576).contains(&count) {
        return Err("Unix read size must be 1..1048576 bytes".into());
    }
    let mut guard = handle.0.lock().map_err(|_| "Unix stream lock poisoned")?;
    let state = guard.as_mut().ok_or("Unix stream is closed")?;
    state.socket.set_nonblocking(false)?;
    let mut data = vec![0; count as usize];
    loop {
        state
            .socket
            .set_read_timeout(Some(remaining(state.deadline)?))?;
        match state.socket.read(&mut data) {
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            result => {
                data.truncate(result?);
                remaining(state.deadline)?;
                return Ok(data);
            }
        }
    }
}
pub fn unix_sendall(handle: &UnixStream, data: &[u8]) -> Result<()> {
    if data.len() > 1048576 {
        return Err("Unix write exceeds 1048576 bytes".into());
    }
    let mut guard = handle.0.lock().map_err(|_| "Unix stream lock poisoned")?;
    let state = guard.as_mut().ok_or("Unix stream is closed")?;
    state.socket.set_nonblocking(false)?;
    let mut sent = 0;
    remaining(state.deadline)?;
    while sent < data.len() {
        state
            .socket
            .set_write_timeout(Some(remaining(state.deadline)?))?;
        match state.socket.write(&data[sent..]) {
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            Ok(0) => return Err("Unix write returned zero bytes".into()),
            result => sent += result?,
        }
    }
    remaining(state.deadline)?;
    Ok(())
}
pub fn unix_shutdown_write(handle: &UnixStream) -> Result<()> {
    handle
        .0
        .lock()
        .map_err(|_| "Unix stream lock poisoned")?
        .as_ref()
        .ok_or("Unix stream is closed")?
        .socket
        .shutdown(Shutdown::Write)?;
    Ok(())
}
pub fn unix_close(handle: &UnixStream) -> Result<()> {
    handle.close()
}
pub fn unix_close_listener(handle: &UnixListener) -> Result<()> {
    handle.close()
}

pub fn unix_accept_ready(handle: &UnixListener, limit: i64, io_ms: i64) -> Result<Vec<UnixStream>> {
    if !(1..=64).contains(&limit) {
        return Err("ready accept limit must be 1..64".into());
    }
    let timeout = duration(io_ms)?;
    let guard = handle.0.lock().map_err(|_| "Unix listener lock poisoned")?;
    let listener = guard.as_ref().ok_or("Unix listener is closed")?;
    let mut accepted = Vec::new();
    while accepted.len() < limit as usize {
        match listener.socket.accept() {
            Ok((socket, _)) => accepted.push(stream(socket, timeout)?),
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            Err(error) if error.kind() == ErrorKind::WouldBlock => break,
            Err(error) => return Err(error.into()),
        }
    }
    Ok(accepted)
}
pub fn unix_recv_ready(handle: &UnixStream, count: i64) -> Result<(Vec<u8>, bool)> {
    if !(1..=1048576).contains(&count) {
        return Err("Unix read size must be 1..1048576 bytes".into());
    }
    let mut guard = handle.0.lock().map_err(|_| "Unix stream lock poisoned")?;
    let state = guard.as_mut().ok_or("Unix stream is closed")?;
    state.socket.set_nonblocking(true)?;
    let mut data = vec![0; count as usize];
    loop {
        match state.socket.read(&mut data) {
            Ok(size) => {
                data.truncate(size);
                return Ok((data, size == 0));
            }
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            Err(error) if error.kind() == ErrorKind::WouldBlock => return Ok((Vec::new(), false)),
            Err(error) => return Err(error.into()),
        }
    }
}
pub fn unix_send_ready(handle: &UnixStream, data: &[u8]) -> Result<i64> {
    if data.len() > 1048576 {
        return Err("Unix write exceeds 1048576 bytes".into());
    }
    let mut guard = handle.0.lock().map_err(|_| "Unix stream lock poisoned")?;
    let state = guard.as_mut().ok_or("Unix stream is closed")?;
    state.socket.set_nonblocking(true)?;
    loop {
        match state.socket.write(data) {
            Ok(0) if !data.is_empty() => return Err("Unix write returned zero bytes".into()),
            Ok(size) => return Ok(size as i64),
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            Err(error) if error.kind() == ErrorKind::WouldBlock => return Ok(0),
            Err(error) => return Err(error.into()),
        }
    }
}
pub fn unix_send_buffer(handle: &UnixStream, size: i64) -> Result<()> {
    if !(1024..=1048576).contains(&size) {
        return Err("Unix send buffer must be 1024..1048576 bytes".into());
    }
    let guard = handle.0.lock().map_err(|_| "Unix stream lock poisoned")?;
    let state = guard.as_ref().ok_or("Unix stream is closed")?;
    socket2::SockRef::from(&state.socket).set_send_buffer_size(size as usize)?;
    Ok(())
}

/// A fresh registration snapshot provides level-style readiness on Unix.
#[cfg(unix)]
pub fn unix_select(
    listener: &UnixListener,
    readers: &[UnixStream],
    writers: &[UnixStream],
    timeout_ms: i64,
) -> Result<crate::Json> {
    use mio::{unix::SourceFd, Events, Interest, Poll, Token};
    use std::collections::BTreeSet;
    use std::os::fd::AsRawFd;
    if !(0..=60000).contains(&timeout_ms) || readers.len() > 1024 || writers.len() > 1024 {
        return Err("Unix select requires 0..60000 ms and at most 1024 entries per list".into());
    }
    // Own duplicate descriptors throughout the wait; caller handles remain independently scoped.
    let bound = listener
        .0
        .lock()
        .map_err(|_| "Unix listener lock poisoned")?
        .as_ref()
        .ok_or("Unix listener is closed")?
        .socket
        .try_clone()?;
    let mut sockets = Vec::new();
    let mut poll = Poll::new()?;
    poll.registry().register(
        &mut SourceFd(&bound.as_raw_fd()),
        Token(0),
        Interest::READABLE,
    )?;
    for (index, handle) in readers.iter().chain(writers.iter()).enumerate() {
        let socket = handle
            .0
            .lock()
            .map_err(|_| "Unix stream lock poisoned")?
            .as_ref()
            .ok_or("Unix stream is closed")?
            .socket
            .try_clone()?;
        let interest = if index < readers.len() {
            Interest::READABLE
        } else {
            Interest::WRITABLE
        };
        poll.registry().register(
            &mut SourceFd(&socket.as_raw_fd()),
            Token(index + 1),
            interest,
        )?;
        sockets.push(socket);
    }
    let deadline = Instant::now() + Duration::from_millis(timeout_ms as u64);
    let mut events = Events::with_capacity(sockets.len() + 1);
    loop {
        match poll.poll(
            &mut events,
            Some(deadline.saturating_duration_since(Instant::now())),
        ) {
            Err(error) if error.kind() == ErrorKind::Interrupted && Instant::now() < deadline => {
                continue
            }
            Err(error) if error.kind() == ErrorKind::Interrupted => break,
            result => {
                result?;
                break;
            }
        }
    }
    let mut accept = false;
    let mut read = BTreeSet::new();
    let mut write = BTreeSet::new();
    for event in &events {
        let token = event.token().0;
        if token == 0 {
            accept = true;
        } else if token <= readers.len() {
            read.insert(token - 1);
        } else {
            write.insert(token - 1 - readers.len());
        }
    }
    Ok(serde_json::json!({"accept": accept, "read": read, "write": write}))
}
