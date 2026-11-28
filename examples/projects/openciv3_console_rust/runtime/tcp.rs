//! Scoped TCP handles and absolute I/O deadlines; framing belongs in Python source.
use crate::{resources::Resource, Result};
use std::io::{ErrorKind, Read, Write};
use std::net::{Shutdown, SocketAddr};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

fn address(host: &str, port: i64) -> Result<SocketAddr> {
    Ok(SocketAddr::new(
        host.parse()
            .map_err(|_| "host must be a numeric IP address")?,
        u16::try_from(port).map_err(|_| "port must be between 0 and 65535")?,
    ))
}
fn duration(timeout_ms: i64) -> Result<Duration> {
    if !(1..=86400000).contains(&timeout_ms) {
        return Err("TCP timeout must be 1..86400000 milliseconds".into());
    }
    Ok(Duration::from_millis(timeout_ms as u64))
}
fn remaining(deadline: Instant) -> Result<Duration> {
    deadline
        .checked_duration_since(Instant::now())
        .filter(|value| !value.is_zero())
        .ok_or_else(|| "TCP deadline exceeded".into())
}

#[derive(Clone)]
pub struct TcpListener(Arc<Mutex<Option<std::net::TcpListener>>>);
impl Resource for TcpListener {
    fn check_open(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "TCP listener lock poisoned")?
            .as_ref()
            .ok_or("TCP listener is closed")?;
        Ok(())
    }
    fn close(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "TCP listener lock poisoned")?
            .take();
        Ok(())
    }
}
struct StreamState {
    socket: std::net::TcpStream,
    deadline: Instant,
}
#[derive(Clone)]
pub struct TcpStream(Arc<Mutex<Option<StreamState>>>);
impl Resource for TcpStream {
    fn check_open(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "TCP stream lock poisoned")?
            .as_ref()
            .ok_or("TCP stream is closed")?;
        Ok(())
    }
    fn close(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "TCP stream lock poisoned")?
            .take();
        Ok(())
    }
}
fn stream(socket: std::net::TcpStream, timeout: Duration) -> Result<TcpStream> {
    socket.set_nonblocking(false)?;
    Ok(TcpStream(Arc::new(Mutex::new(Some(StreamState {
        socket,
        deadline: Instant::now() + timeout,
    })))))
}
pub fn tcp_listen(host: &str, port: i64) -> Result<TcpListener> {
    let listener = std::net::TcpListener::bind(address(host, port)?)?;
    listener.set_nonblocking(true)?;
    Ok(TcpListener(Arc::new(Mutex::new(Some(listener)))))
}
pub fn tcp_port(handle: &TcpListener) -> Result<i64> {
    Ok(i64::from(
        handle
            .0
            .lock()
            .map_err(|_| "TCP listener lock poisoned")?
            .as_ref()
            .ok_or("TCP listener is closed")?
            .local_addr()?
            .port(),
    ))
}
pub fn tcp_connect(host: &str, port: i64, timeout_ms: i64) -> Result<TcpStream> {
    let timeout = duration(timeout_ms)?;
    stream(
        std::net::TcpStream::connect_timeout(&address(host, port)?, timeout)?,
        timeout,
    )
}
pub fn tcp_accept_timeout(handle: &TcpListener, accept_ms: i64, io_ms: i64) -> Result<TcpStream> {
    let deadline = Instant::now() + duration(accept_ms)?;
    let io_timeout = duration(io_ms)?;
    loop {
        let left = remaining(deadline)?;
        let accepted = handle
            .0
            .lock()
            .map_err(|_| "TCP listener lock poisoned")?
            .as_ref()
            .ok_or("TCP listener is closed")?
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
pub fn tcp_set_deadline(handle: &TcpStream, timeout_ms: i64) -> Result<()> {
    let deadline = Instant::now() + duration(timeout_ms)?;
    handle
        .0
        .lock()
        .map_err(|_| "TCP stream lock poisoned")?
        .as_mut()
        .ok_or("TCP stream is closed")?
        .deadline = deadline;
    Ok(())
}
pub fn tcp_recv(handle: &TcpStream, count: i64) -> Result<Vec<u8>> {
    if !(1..=1048576).contains(&count) {
        return Err("TCP read size must be 1..1048576 bytes".into());
    }
    let mut guard = handle.0.lock().map_err(|_| "TCP stream lock poisoned")?;
    let state = guard.as_mut().ok_or("TCP stream is closed")?;
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
pub fn tcp_sendall(handle: &TcpStream, data: &[u8]) -> Result<()> {
    if data.len() > 1048576 {
        return Err("TCP write exceeds 1048576 bytes".into());
    }
    let mut guard = handle.0.lock().map_err(|_| "TCP stream lock poisoned")?;
    let state = guard.as_mut().ok_or("TCP stream is closed")?;
    state.socket.set_nonblocking(false)?;
    let mut sent = 0;
    remaining(state.deadline)?;
    while sent < data.len() {
        state
            .socket
            .set_write_timeout(Some(remaining(state.deadline)?))?;
        match state.socket.write(&data[sent..]) {
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            Ok(0) => return Err("TCP write returned zero bytes".into()),
            result => sent += result?,
        }
    }
    remaining(state.deadline)?;
    Ok(())
}
pub fn tcp_shutdown_write(handle: &TcpStream) -> Result<()> {
    handle
        .0
        .lock()
        .map_err(|_| "TCP stream lock poisoned")?
        .as_ref()
        .ok_or("TCP stream is closed")?
        .socket
        .shutdown(Shutdown::Write)?;
    Ok(())
}
pub fn tcp_close(handle: &TcpStream) -> Result<()> {
    handle.close()
}
pub fn tcp_close_listener(handle: &TcpListener) -> Result<()> {
    handle.close()
}

pub fn tcp_accept_ready(handle: &TcpListener, limit: i64, io_ms: i64) -> Result<Vec<TcpStream>> {
    if !(1..=64).contains(&limit) {
        return Err("ready accept limit must be 1..64".into());
    }
    let timeout = duration(io_ms)?;
    let guard = handle.0.lock().map_err(|_| "TCP listener lock poisoned")?;
    let listener = guard.as_ref().ok_or("TCP listener is closed")?;
    let mut accepted = Vec::new();
    while accepted.len() < limit as usize {
        match listener.accept() {
            Ok((socket, _)) => accepted.push(stream(socket, timeout)?),
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            Err(error) if error.kind() == ErrorKind::WouldBlock => break,
            Err(error) => return Err(error.into()),
        }
    }
    Ok(accepted)
}
pub fn tcp_recv_ready(handle: &TcpStream, count: i64) -> Result<(Vec<u8>, bool)> {
    if !(1..=1048576).contains(&count) {
        return Err("TCP read size must be 1..1048576 bytes".into());
    }
    let mut guard = handle.0.lock().map_err(|_| "TCP stream lock poisoned")?;
    let state = guard.as_mut().ok_or("TCP stream is closed")?;
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
pub fn tcp_send_ready(handle: &TcpStream, data: &[u8]) -> Result<i64> {
    if data.len() > 1048576 {
        return Err("TCP write exceeds 1048576 bytes".into());
    }
    let mut guard = handle.0.lock().map_err(|_| "TCP stream lock poisoned")?;
    let state = guard.as_mut().ok_or("TCP stream is closed")?;
    state.socket.set_nonblocking(true)?;
    loop {
        match state.socket.write(data) {
            Ok(0) if !data.is_empty() => return Err("TCP write returned zero bytes".into()),
            Ok(size) => return Ok(size as i64),
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            Err(error) if error.kind() == ErrorKind::WouldBlock => return Ok(0),
            Err(error) => return Err(error.into()),
        }
    }
}
pub fn tcp_send_buffer(handle: &TcpStream, size: i64) -> Result<()> {
    if !(1024..=1048576).contains(&size) {
        return Err("TCP send buffer must be 1024..1048576 bytes".into());
    }
    let guard = handle.0.lock().map_err(|_| "TCP stream lock poisoned")?;
    let state = guard.as_ref().ok_or("TCP stream is closed")?;
    socket2::SockRef::from(&state.socket).set_send_buffer_size(size as usize)?;
    Ok(())
}

/// A fresh registration snapshot provides level-style readiness on Unix.
#[cfg(unix)]
pub fn tcp_select(
    listener: &TcpListener,
    readers: &[TcpStream],
    writers: &[TcpStream],
    timeout_ms: i64,
) -> Result<crate::Json> {
    use mio::{unix::SourceFd, Events, Interest, Poll, Token};
    use std::collections::BTreeSet;
    use std::os::fd::AsRawFd;
    if !(0..=60000).contains(&timeout_ms) || readers.len() > 1024 || writers.len() > 1024 {
        return Err("TCP select requires 0..60000 ms and at most 1024 entries per list".into());
    }
    // Own duplicate descriptors throughout the wait; caller handles remain independently scoped.
    let bound = listener
        .0
        .lock()
        .map_err(|_| "TCP listener lock poisoned")?
        .as_ref()
        .ok_or("TCP listener is closed")?
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
            .map_err(|_| "TCP stream lock poisoned")?
            .as_ref()
            .ok_or("TCP stream is closed")?
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
#[cfg(not(unix))]
pub fn tcp_select(
    _listener: &TcpListener,
    _readers: &[TcpStream],
    _writers: &[TcpStream],
    _timeout_ms: i64,
) -> Result<crate::Json> {
    Err("TCP select currently requires Unix".into())
}

pub fn int_from_bytes(data: &[u8], byteorder: &str) -> Result<i64> {
    if data.len() > 8 || !matches!(byteorder, "big" | "little") {
        return Err("integer byte conversion requires 0..8 bytes and big/little byte order".into());
    }
    let mut buffer = [0u8; 8];
    let value = if byteorder == "big" {
        buffer[8 - data.len()..].copy_from_slice(data);
        u64::from_be_bytes(buffer)
    } else {
        buffer[..data.len()].copy_from_slice(data);
        u64::from_le_bytes(buffer)
    };
    Ok(i64::try_from(value).map_err(|_| "decoded integer exceeds signed 64-bit range")?)
}
pub fn int_from_bytes_signed(data: &[u8], byteorder: &str, signed: bool) -> Result<i64> {
    if data.len() > 8 || !matches!(byteorder, "big" | "little") {
        return Err("integer byte conversion requires 0..8 bytes and big/little byte order".into());
    }
    if !signed {
        return int_from_bytes(data, byteorder);
    }
    let mut buffer = [0u8; 8];
    if byteorder == "big" {
        buffer[8 - data.len()..].copy_from_slice(data);
    } else {
        buffer[..data.len()].copy_from_slice(data);
    }
    let mut value = if byteorder == "big" {
        u64::from_be_bytes(buffer)
    } else {
        u64::from_le_bytes(buffer)
    };
    let bits = data.len() * 8;
    let negative = match byteorder {
        "big" => data.first().is_some_and(|byte| byte & 0x80 != 0),
        _ => data.last().is_some_and(|byte| byte & 0x80 != 0),
    };
    if negative && bits < 64 {
        value |= u64::MAX << bits;
    }
    Ok(value as i64)
}

pub fn int_to_bytes(value: i64, length: i64, byteorder: &str) -> Result<Vec<u8>> {
    if !(0..=8).contains(&length) || !matches!(byteorder, "big" | "little") || value < 0 {
        return Err("integer byte conversion requires nonnegative value, 0..8 bytes and big/little byte order".into());
    }
    let length = length as usize;
    if length < 8 && (value as u64) >= (1u64 << (length * 8)) {
        return Err("integer does not fit byte length".into());
    }
    Ok(if byteorder == "big" {
        value.to_be_bytes()[8 - length..].to_vec()
    } else {
        value.to_le_bytes()[..length].to_vec()
    })
}
