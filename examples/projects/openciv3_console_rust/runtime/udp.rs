//! Scoped UDP datagrams with explicit source addresses, truncation and bounded waits.
use crate::{resources::Resource, Result};
use std::io::ErrorKind;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

fn address(host: &str, port: i64) -> Result<SocketAddr> {
    Ok(SocketAddr::new(
        host.parse()
            .map_err(|_| "host must be a numeric IP address")?,
        u16::try_from(port).map_err(|_| "port must be between 0 and 65535")?,
    ))
}
fn deadline(timeout_ms: i64) -> Result<Instant> {
    if !(1..=86400000).contains(&timeout_ms) {
        return Err("UDP timeout must be 1..86400000 milliseconds".into());
    }
    Ok(Instant::now() + Duration::from_millis(timeout_ms as u64))
}
fn remaining(end: Instant) -> Result<Duration> {
    end.checked_duration_since(Instant::now())
        .filter(|value| !value.is_zero())
        .ok_or_else(|| "UDP deadline exceeded".into())
}

#[derive(Clone)]
pub struct UdpSocket(Arc<Mutex<Option<std::net::UdpSocket>>>);
impl Resource for UdpSocket {
    fn check_open(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "UDP socket lock poisoned")?
            .as_ref()
            .ok_or("UDP socket is closed")?;
        Ok(())
    }
    fn close(&self) -> Result<()> {
        self.0
            .lock()
            .map_err(|_| "UDP socket lock poisoned")?
            .take();
        Ok(())
    }
}
pub fn udp_bind(host: &str, port: i64) -> Result<UdpSocket> {
    let socket = std::net::UdpSocket::bind(address(host, port)?)?;
    Ok(UdpSocket(Arc::new(Mutex::new(Some(socket)))))
}
pub fn udp_port(handle: &UdpSocket) -> Result<i64> {
    Ok(i64::from(
        handle
            .0
            .lock()
            .map_err(|_| "UDP socket lock poisoned")?
            .as_ref()
            .ok_or("UDP socket is closed")?
            .local_addr()?
            .port(),
    ))
}
pub fn udp_sendto(
    handle: &UdpSocket,
    data: &[u8],
    host: &str,
    port: i64,
    timeout_ms: i64,
) -> Result<()> {
    if data.len() > 65507 || port == 0 {
        return Err("UDP send requires at most 65507 bytes and a nonzero destination port".into());
    }
    let peer = address(host, port)?;
    let end = deadline(timeout_ms)?;
    let guard = handle.0.lock().map_err(|_| "UDP socket lock poisoned")?;
    let socket = guard.as_ref().ok_or("UDP socket is closed")?;
    if socket.local_addr()?.is_ipv4() != peer.is_ipv4() {
        return Err("UDP address family mismatch".into());
    }
    loop {
        socket.set_write_timeout(Some(remaining(end)?))?;
        match socket.send_to(data, peer) {
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            result => {
                if result? != data.len() {
                    return Err("UDP send did not accept the complete datagram".into());
                }
                return Ok(());
            }
        }
    }
}
pub fn udp_recvfrom(
    handle: &UdpSocket,
    limit: i64,
    timeout_ms: i64,
) -> Result<(Vec<u8>, String, i64, bool)> {
    if !(1..=65507).contains(&limit) {
        return Err("UDP receive limit must be 1..65507 bytes".into());
    }
    let end = deadline(timeout_ms)?;
    let guard = handle.0.lock().map_err(|_| "UDP socket lock poisoned")?;
    let socket = guard.as_ref().ok_or("UDP socket is closed")?;
    // One extra byte distinguishes an exact fit from a truncated datagram.
    let mut data = vec![0; limit as usize + 1];
    loop {
        socket.set_read_timeout(Some(remaining(end)?))?;
        match socket.recv_from(&mut data) {
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            result => {
                let (size, source) = result?;
                if let SocketAddr::V6(peer) = source {
                    if peer.scope_id() != 0 {
                        return Err("scoped IPv6 datagrams are unsupported".into());
                    }
                }
                data.truncate(size.min(limit as usize));
                return Ok((
                    data,
                    source.ip().to_string(),
                    i64::from(source.port()),
                    size > limit as usize,
                ));
            }
        }
    }
}
pub fn udp_close(handle: &UdpSocket) -> Result<()> {
    handle.close()
}
