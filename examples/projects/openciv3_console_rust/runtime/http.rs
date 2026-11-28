//! Blocking public API with TLS and bounded, sequential connection handling.
use crate::{json_dumps, json_loads, Json, Result};
use http_body_util::{BodyExt, Full, Limited};
use hyper::{body::Bytes, body::Incoming, header, Request, Response};
use hyper_util::rt::TokioIo;
use std::convert::Infallible;
use std::fs::File;
use std::io::{BufReader, Read};
use std::net::TcpListener;
use std::sync::Arc;
use std::sync::Mutex;
use std::time::{Duration, Instant};

#[derive(Clone, Debug)]
pub struct HttpResponse {
    pub status: i64,
    pub body: String,
}

pub struct HttpServer {
    listener: TcpListener,
    tls: Option<Arc<rustls::ServerConfig>>,
}

struct ReaderState {
    reader: Option<Box<dyn Read + Send + Sync>>,
    received: u64,
    limit: u64,
    deadline: Instant,
}
#[derive(Clone)]
pub struct HttpReader {
    pub status: u16,
    pub headers: indexmap::IndexMap<String, String>,
    inner: Arc<Mutex<ReaderState>>,
}
impl crate::resources::Resource for HttpReader {
    fn check_open(&self) -> Result<()> {
        self.inner
            .lock()
            .map_err(|_| "HTTP reader lock poisoned")?
            .reader
            .as_ref()
            .ok_or("HTTP reader is closed")?;
        Ok(())
    }
    fn close(&self) -> Result<()> {
        self.inner
            .lock()
            .map_err(|_| "HTTP reader lock poisoned")?
            .reader
            .take();
        Ok(())
    }
}
pub fn web_open(
    url: &str,
    headers: &indexmap::IndexMap<String, String>,
    timeout_ms: i64,
    max_body: i64,
) -> Result<HttpReader> {
    open_request("GET", url, &[], headers, timeout_ms, max_body, None)
}
pub fn web_open_ca(
    url: &str,
    headers: &indexmap::IndexMap<String, String>,
    timeout_ms: i64,
    max_body: i64,
    ca_file: &str,
) -> Result<HttpReader> {
    open_request(
        "GET",
        url,
        &[],
        headers,
        timeout_ms,
        max_body,
        Some(ca_file),
    )
}
pub fn web_read(handle: &HttpReader, count: i64) -> Result<Vec<u8>> {
    if !(1..=33554432).contains(&count) {
        return Err("HTTP read size must be 1..32 MiB".into());
    }
    let mut state = handle
        .inner
        .lock()
        .map_err(|_| "HTTP reader lock poisoned")?;
    let remaining = state.limit - state.received;
    if Instant::now() >= state.deadline {
        state.reader.take();
        return Err("HTTP response deadline exceeded".into());
    }
    let reader = state.reader.as_mut().ok_or("HTTP reader is closed")?;
    let mut bytes = Vec::new();
    let read = reader
        .take((count as u64).min(remaining + 1))
        .read_to_end(&mut bytes);
    if let Err(error) = read {
        state.reader.take();
        return Err(error.into());
    }
    if Instant::now() >= state.deadline {
        state.reader.take();
        return Err("HTTP response deadline exceeded".into());
    }
    if bytes.len() as u64 > remaining {
        state.reader.take();
        return Err("HTTP body limit exceeded".into());
    }
    state.received += bytes.len() as u64;
    Ok(bytes)
}
pub fn web_close(handle: &HttpReader) -> Result<()> {
    crate::resources::Resource::close(handle)
}

fn certificates(path: &str) -> Result<Vec<rustls::pki_types::CertificateDer<'static>>> {
    let certificates = rustls_pemfile::certs(&mut BufReader::new(File::open(path)?))
        .collect::<std::io::Result<Vec<_>>>()?;
    if certificates.is_empty() {
        return Err("PEM file contains no certificates".into());
    }
    Ok(certificates)
}

pub fn http_request(
    method: &str,
    url: &str,
    body: &str,
    timeout_ms: i64,
    max_body: i64,
) -> Result<HttpResponse> {
    request(method, url, body, timeout_ms, max_body, None)
}

/// Trust only the explicitly supplied CA bundle; hostname verification stays on.
pub fn https_request_ca(
    method: &str,
    url: &str,
    body: &str,
    timeout_ms: i64,
    max_body: i64,
    ca_file: &str,
) -> Result<HttpResponse> {
    request(method, url, body, timeout_ms, max_body, Some(ca_file))
}

fn request(
    method: &str,
    url: &str,
    body: &str,
    timeout_ms: i64,
    max_body: i64,
    ca_file: Option<&str>,
) -> Result<HttpResponse> {
    if !(1..=1048576).contains(&max_body) {
        return Err("invalid HTTP body limit".into());
    }
    let headers = [("content-type".to_string(), "application/json".to_string())].into();
    let response = request_bytes(
        method,
        url,
        body.as_bytes(),
        &headers,
        timeout_ms,
        max_body,
        ca_file,
    )?;
    Ok(HttpResponse {
        status: response.status as i64,
        body: String::from_utf8(response.body)?,
    })
}

pub fn web_request(
    method: &str,
    url: &str,
    body: &[u8],
    headers: &indexmap::IndexMap<String, String>,
    timeout_ms: i64,
    max_body: i64,
) -> Result<crate::WebResponse> {
    request_bytes(method, url, body, headers, timeout_ms, max_body, None)
}

pub fn web_request_ca(
    method: &str,
    url: &str,
    body: &[u8],
    headers: &indexmap::IndexMap<String, String>,
    timeout_ms: i64,
    max_body: i64,
    ca_file: &str,
) -> Result<crate::WebResponse> {
    request_bytes(
        method,
        url,
        body,
        headers,
        timeout_ms,
        max_body,
        Some(ca_file),
    )
}

fn request_bytes(
    method: &str,
    url: &str,
    body: &[u8],
    headers: &indexmap::IndexMap<String, String>,
    timeout_ms: i64,
    max_body: i64,
    ca_file: Option<&str>,
) -> Result<crate::WebResponse> {
    let response = open_request(method, url, body, headers, timeout_ms, max_body, ca_file)?;
    let mut buffer = Vec::new();
    loop {
        let chunk = web_read(&response, 65536)?;
        if chunk.is_empty() {
            break;
        }
        buffer.extend_from_slice(&chunk);
    }
    Ok(crate::WebResponse {
        status: response.status,
        headers: response.headers.clone(),
        body: buffer,
        stream: None,
    })
}
fn open_request(
    method: &str,
    url: &str,
    body: &[u8],
    headers: &indexmap::IndexMap<String, String>,
    timeout_ms: i64,
    max_body: i64,
    ca_file: Option<&str>,
) -> Result<HttpReader> {
    if !["GET", "POST", "PUT", "DELETE"].contains(&method) {
        return Err("unsupported HTTP method".into());
    }
    let parsed = url::Url::parse(url)?;
    if !["http", "https"].contains(&parsed.scheme())
        || parsed.host_str().is_none()
        || !parsed.username().is_empty()
        || parsed.password().is_some()
        || parsed.fragment().is_some()
    {
        return Err("expected an http/https URL without credentials or fragment".into());
    }
    if ca_file.is_some() && parsed.scheme() != "https" {
        return Err("https_request_ca requires an https URL".into());
    }
    if !(1..=86400000).contains(&timeout_ms)
        || !(1..=33554432).contains(&max_body)
        || body.len() > 33554432
    {
        return Err("invalid HTTP timeout or body limit".into());
    }
    let mut normalized = indexmap::IndexMap::new();
    for (name, value) in headers {
        hyper::header::HeaderName::from_bytes(name.as_bytes())?;
        if !value
            .bytes()
            .all(|byte| byte == b'\t' || (32..=126).contains(&byte))
        {
            return Err("HTTP header values must be printable ASCII or tab".into());
        }
        let name = name.to_ascii_lowercase();
        if ["host", "content-length", "transfer-encoding", "connection"].contains(&name.as_str()) {
            return Err("transport header is managed by the client".into());
        }
        if normalized.insert(name, value).is_some() {
            return Err("duplicate HTTP header".into());
        }
    }
    let mut builder = ureq::AgentBuilder::new()
        .try_proxy_from_env(false)
        .redirects(0)
        .timeout(Duration::from_millis(timeout_ms as u64));
    if let Some(ca_file) = ca_file {
        let mut roots = rustls::RootCertStore::empty();
        for certificate in certificates(ca_file)? {
            roots.add(certificate)?;
        }
        let config = rustls::ClientConfig::builder()
            .with_root_certificates(roots)
            .with_no_client_auth();
        builder = builder.tls_config(Arc::new(config));
    }
    let agent = builder.build();
    let mut request = agent.request(method, url).set("connection", "close");
    if !normalized.contains_key("content-type") {
        request = request.set("content-type", "application/octet-stream");
    }
    for (name, value) in normalized {
        request = request.set(&name, value);
    }
    let deadline = Instant::now() + Duration::from_millis(timeout_ms as u64);
    let response = match request.send_bytes(body) {
        Ok(r) | Err(ureq::Error::Status(_, r)) => r,
        Err(e) => return Err(e.into()),
    };
    let status = response.status();
    let mut response_headers = indexmap::IndexMap::new();
    for name in response.headers_names() {
        let value = response
            .header(&name)
            .ok_or("response header is not valid UTF-8")?;
        if !value
            .bytes()
            .all(|byte| byte == b'\t' || (32..=126).contains(&byte))
        {
            return Err("response header is not printable ASCII".into());
        }
        response_headers
            .entry(name.to_ascii_lowercase())
            .or_insert_with(|| value.to_string());
    }
    Ok(HttpReader {
        status,
        headers: response_headers,
        inner: Arc::new(Mutex::new(ReaderState {
            reader: Some(response.into_reader()),
            received: 0,
            limit: max_body as u64,
            deadline,
        })),
    })
}

pub fn http_listen(host: &str, port: i64) -> Result<HttpServer> {
    let address: std::net::Ipv4Addr = host.parse()?;
    let port = u16::try_from(port)?;
    let listener = TcpListener::bind((address, port))?;
    listener.set_nonblocking(true)?;
    Ok(HttpServer {
        listener,
        tls: None,
    })
}

pub fn https_listen(host: &str, port: i64, cert_file: &str, key_file: &str) -> Result<HttpServer> {
    let chain = certificates(cert_file)?;
    let key = rustls_pemfile::private_key(&mut BufReader::new(File::open(key_file)?))?
        .ok_or("PEM file contains no private key")?;
    let config = rustls::ServerConfig::builder()
        .with_no_client_auth()
        .with_single_cert(chain, key)?;
    let mut server = http_listen(host, port)?;
    server.tls = Some(Arc::new(config));
    Ok(server)
}

pub fn http_port(server: &HttpServer) -> Result<i64> {
    Ok(server.listener.local_addr()?.port() as i64)
}

type Handler = fn(String, String, Json) -> Result<Json>;

pub fn http_serve_json(
    server: &HttpServer,
    handler: Handler,
    count: i64,
    max_body: i64,
) -> Result<()> {
    http_serve_json_timeout(server, handler, count, max_body, 30_000, 10_000)
}

/// Deadlines cover waiting for a connection, then its handshake and network I/O.
/// Synchronous application code must finish by itself; it cannot be preempted.
pub fn http_serve_json_timeout(
    server: &HttpServer,
    handler: Handler,
    count: i64,
    max_body: i64,
    accept_timeout_ms: i64,
    connection_timeout_ms: i64,
) -> Result<()> {
    if !(1..=100000).contains(&count) || !(1..=1048576).contains(&max_body) {
        return Err("invalid HTTP request count or body limit".into());
    }
    if !(1..=86_400_000).contains(&accept_timeout_ms)
        || !(1..=86_400_000).contains(&connection_timeout_ms)
    {
        return Err("server timeouts must be between 1 and 86400000 milliseconds".into());
    }
    tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()?
        .block_on(async {
            let listener = tokio::net::TcpListener::from_std(server.listener.try_clone()?)?;
            for _ in 0..count {
                let (stream, _) = tokio::time::timeout(
                    Duration::from_millis(accept_timeout_ms as u64),
                    listener.accept(),
                )
                .await
                .map_err(|_| "HTTP accept deadline exceeded")??;
                // There is one active connection and no detached worker task. Dropping
                // this future closes the socket on timeout, including stalled TLS.
                let work = async {
                    if let Some(config) = &server.tls {
                        let stream = tokio_rustls::TlsAcceptor::from(config.clone())
                            .accept(stream)
                            .await?;
                        serve_connection(stream, handler, max_body).await
                    } else {
                        serve_connection(stream, handler, max_body).await
                    }
                };
                // A bad/timed-out peer consumes one connection slot, then we continue.
                // Listener/accept errors above still propagate to the application.
                let _ =
                    tokio::time::timeout(Duration::from_millis(connection_timeout_ms as u64), work)
                        .await;
            }
            Ok(())
        })
}

async fn serve_connection<I>(stream: I, handler: Handler, max_body: i64) -> Result<()>
where
    I: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin + Send + 'static,
{
    hyper::server::conn::http1::Builder::new()
        .keep_alive(false)
        .max_buf_size(32768)
        .serve_connection(
            TokioIo::new(stream),
            hyper::service::service_fn(move |request| dispatch(request, handler, max_body)),
        )
        .await?;
    Ok(())
}

fn json_response(status: u16, body: String) -> Response<Full<Bytes>> {
    let mut response = Response::new(Full::new(Bytes::from(body)));
    *response.status_mut() = hyper::StatusCode::from_u16(status).expect("fixed HTTP status");
    response.headers_mut().insert(
        header::CONTENT_TYPE,
        header::HeaderValue::from_static("application/json; charset=utf-8"),
    );
    response.headers_mut().insert(
        header::CONNECTION,
        header::HeaderValue::from_static("close"),
    );
    response
}

async fn dispatch(
    request: Request<Incoming>,
    handler: Handler,
    max_body: i64,
) -> std::result::Result<Response<Full<Bytes>>, Infallible> {
    let invalid = |status| json_response(status, "{\"error\":\"invalid request\"}".to_string());
    if request.headers().contains_key(header::TRANSFER_ENCODING) {
        return Ok(invalid(400));
    }
    if request
        .headers()
        .get(header::CONTENT_LENGTH)
        .and_then(|s| s.to_str().ok())
        .and_then(|s| s.parse::<u64>().ok())
        .is_some_and(|length| length > max_body as u64)
    {
        return Ok(invalid(413));
    }
    let method = request.method().as_str().to_string();
    let path = request
        .uri()
        .path_and_query()
        .map(|p| p.as_str())
        .unwrap_or("/")
        .to_string();
    if !["GET", "POST", "PUT", "DELETE"].contains(&method.as_str()) {
        return Ok(invalid(405));
    }
    let body = match Limited::new(request.into_body(), max_body as usize)
        .collect()
        .await
    {
        Ok(body) => body.to_bytes(),
        Err(error) => {
            return Ok(invalid(if error.is::<http_body_util::LengthLimitError>() {
                413
            } else {
                400
            }))
        }
    };
    let input = if body.is_empty() {
        Ok(Json::Null)
    } else {
        std::str::from_utf8(&body)
            .map_err(Into::into)
            .and_then(json_loads)
    };
    let output = match input {
        Err(_) => return Ok(invalid(400)),
        Ok(input) => handler(method, path, input).and_then(|value| json_dumps(&value)),
    };
    Ok(match output {
        Ok(body) => json_response(200, body),
        Err(_) => json_response(500, "{\"error\":\"handler failed\"}".to_string()),
    })
}
