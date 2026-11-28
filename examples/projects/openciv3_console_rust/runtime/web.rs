//! General HTTP adapter. Application routing and persistence stay in Python.
use crate::{Json, Result};
use http_body_util::{BodyExt, Limited};
use hyper::{
    body::{Body, Bytes, Frame, Incoming, SizeHint},
    Request, Response,
};
use hyper_util::rt::TokioIo;
use indexmap::IndexMap;
use std::{
    convert::Infallible,
    future::Future,
    pin::Pin,
    sync::{
        atomic::{AtomicUsize, Ordering},
        Arc,
    },
    task::{Context, Poll},
    time::Duration,
};

const BODY_LIMIT: usize = 32 * 1024 * 1024;
#[derive(Clone, Debug)]
pub struct WebRequest {
    pub method: String,
    pub path: String,
    pub target: String,
    pub headers: IndexMap<String, String>,
    pub query: IndexMap<String, String>,
    pub body: Vec<u8>,
}
#[derive(Clone, Debug)]
pub struct WebResponse {
    pub status: u16,
    pub body: Vec<u8>,
    pub headers: IndexMap<String, String>,
    pub(crate) stream: Option<StreamOptions>,
}
#[derive(Clone, Debug)]
pub(crate) struct StreamOptions {
    state: Json,
    interval: Duration,
}
#[derive(Clone, Debug)]
pub struct StreamChunk {
    body: Vec<u8>,
    state: Json,
    done: bool,
}
const STREAM_LIMIT: usize = 65536;
fn check_state(state: &Json) -> Result<()> {
    if crate::json_dumps(state)?.len() > STREAM_LIMIT {
        return Err("stream state exceeds 64 KiB".into());
    }
    Ok(())
}
/// One bounded piece of a response and the state for the next poll.
pub fn stream_chunk(body: &[u8], state: &Json, done: bool) -> Result<StreamChunk> {
    if body.len() > STREAM_LIMIT {
        return Err("stream chunk exceeds 64 KiB".into());
    }
    check_state(state)?;
    Ok(StreamChunk {
        body: body.to_vec(),
        state: state.clone(),
        done,
    })
}
/// The adapter owns HTTP framing; the application owns the bytes and cursor.
pub fn web_stream(
    headers: &IndexMap<String, String>,
    state: &Json,
    interval_ms: i64,
) -> Result<WebResponse> {
    if !(1..=60000).contains(&interval_ms) {
        return Err("stream interval must be 1..60000 milliseconds".into());
    }
    if headers.keys().any(|key| {
        matches!(
            key.to_ascii_lowercase().as_str(),
            "content-length" | "transfer-encoding" | "connection" | "trailer"
        )
    }) {
        return Err("stream framing headers are managed by the server".into());
    }
    check_state(state)?;
    let mut response = web_response(200, &[], headers)?;
    response.stream = Some(StreamOptions {
        state: state.clone(),
        interval: Duration::from_millis(interval_ms as u64),
    });
    Ok(response)
}
pub fn web_response(
    status: i64,
    body: &[u8],
    headers: &IndexMap<String, String>,
) -> Result<WebResponse> {
    let status = u16::try_from(status)?;
    if !(200..=599).contains(&status) {
        return Err("invalid response status".into());
    }
    for (key, value) in headers {
        hyper::header::HeaderName::from_bytes(key.as_bytes())?;
        hyper::header::HeaderValue::from_str(value)?;
    }
    Ok(WebResponse {
        status,
        body: body.to_vec(),
        headers: headers.clone(),
        stream: None,
    })
}
type Handler = fn(WebRequest) -> Result<WebResponse>;
type StreamPoll = fn(Json) -> Result<StreamChunk>;

struct StreamBody {
    options: StreamOptions,
    callback: StreamPoll,
    timer: Pin<Box<tokio::time::Sleep>>,
    done: bool,
    active: Arc<AtomicUsize>,
}
impl Drop for StreamBody {
    fn drop(&mut self) {
        self.active.fetch_sub(1, Ordering::Relaxed);
    }
}
enum ResponseBody {
    Complete(Option<Bytes>),
    Streaming(StreamBody),
}
impl Body for ResponseBody {
    type Data = Bytes;
    type Error = Box<dyn std::error::Error + Send + Sync>;
    fn poll_frame(
        self: Pin<&mut Self>,
        cx: &mut Context<'_>,
    ) -> Poll<Option<Result<Frame<Bytes>>>> {
        match self.get_mut() {
            Self::Complete(bytes) => Poll::Ready(bytes.take().map(|value| Ok(Frame::data(value)))),
            Self::Streaming(stream) => {
                if stream.done {
                    return Poll::Ready(None);
                }
                if stream.timer.as_mut().poll(cx).is_pending() {
                    return Poll::Pending;
                }
                // Hyper only asks for another frame when its bounded writer can
                // accept one. There is no producer task or unbounded event queue.
                match (stream.callback)(stream.options.state.clone()) {
                    Ok(chunk) => {
                        stream.options.state = chunk.state;
                        stream.done = chunk.done;
                        stream
                            .timer
                            .as_mut()
                            .reset(tokio::time::Instant::now() + stream.options.interval);
                        if !chunk.body.is_empty() {
                            return Poll::Ready(Some(Ok(Frame::data(Bytes::from(chunk.body)))));
                        }
                        if stream.done {
                            return Poll::Ready(None);
                        }
                        let _ = stream.timer.as_mut().poll(cx);
                        Poll::Pending
                    }
                    Err(error) => {
                        stream.done = true;
                        Poll::Ready(Some(Err(error)))
                    }
                }
            }
        }
    }
    fn is_end_stream(&self) -> bool {
        match self {
            Self::Complete(bytes) => bytes.is_none(),
            Self::Streaming(stream) => stream.done,
        }
    }
    fn size_hint(&self) -> SizeHint {
        match self {
            Self::Complete(bytes) => {
                SizeHint::with_exact(bytes.as_ref().map_or(0, |value| value.len() as u64))
            }
            Self::Streaming(_) => SizeHint::default(),
        }
    }
}
fn response(
    status: u16,
    body: Vec<u8>,
    headers: IndexMap<String, String>,
) -> Response<ResponseBody> {
    make_response(
        status,
        ResponseBody::Complete(Some(Bytes::from(body))),
        headers,
    )
}
fn make_response(
    status: u16,
    body: ResponseBody,
    headers: IndexMap<String, String>,
) -> Response<ResponseBody> {
    let mut out = Response::builder().status(status);
    let has_cache_control = headers
        .keys()
        .any(|name| name.eq_ignore_ascii_case("cache-control"));
    for (key, value) in headers {
        out = out.header(key, value);
    }
    if !has_cache_control {
        out = out.header("cache-control", "no-store");
    }
    out.header("x-content-type-options", "nosniff")
        .body(body)
        .expect("validated response")
}
fn error(status: u16, message: &str) -> Response<ResponseBody> {
    response(
        status,
        serde_json::json!({"error": message})
            .to_string()
            .into_bytes(),
        [("content-type".into(), "application/json".into())].into(),
    )
}
async fn dispatch(
    request: Request<Incoming>,
    handler: Handler,
    poll: Option<StreamPoll>,
    active: Arc<AtomicUsize>,
) -> std::result::Result<Response<ResponseBody>, Infallible> {
    let method = request.method().to_string();
    let path = request.uri().path().to_string();
    let target = request.uri().to_string();
    let query = url::form_urlencoded::parse(request.uri().query().unwrap_or("").as_bytes())
        .into_owned()
        .collect();
    let headers: IndexMap<String, String> = request
        .headers()
        .iter()
        .filter_map(|(k, v)| v.to_str().ok().map(|v| (k.to_string(), v.to_string())))
        .collect();
    // Cookie-bearing mutations must originate from the same web origin.
    if method != "GET" && method != "HEAD" {
        if let Some(origin) = headers.get("origin") {
            let parsed = url::Url::parse(origin);
            let authority = parsed
                .as_ref()
                .ok()
                .map(|u| u[url::Position::BeforeHost..url::Position::AfterPort].to_string());
            if authority.as_ref() != headers.get("host") {
                return Ok(error(403, "Origin is not allowed"));
            }
        }
    }
    let body = match Limited::new(request.into_body(), BODY_LIMIT)
        .collect()
        .await
    {
        Ok(value) => value.to_bytes().to_vec(),
        Err(_) => return Ok(error(413, "Upload is too large (32 MiB maximum)")),
    };
    match handler(WebRequest {
        method,
        path,
        target,
        query,
        headers,
        body,
    }) {
        Ok(out) => {
            if let Some(options) = out.stream {
                let Some(callback) = poll else {
                    return Ok(error(500, "No stream poll callback configured"));
                };
                // Reserve at least half the connection slots for ordinary requests.
                if active.fetch_add(1, Ordering::Relaxed) >= 32 {
                    active.fetch_sub(1, Ordering::Relaxed);
                    return Ok(error(503, "Stream capacity reached"));
                }
                Ok(make_response(
                    out.status,
                    ResponseBody::Streaming(StreamBody {
                        options,
                        callback,
                        timer: Box::pin(tokio::time::sleep(Duration::ZERO)),
                        done: false,
                        active,
                    }),
                    out.headers,
                ))
            } else {
                Ok(response(out.status, out.body, out.headers))
            }
        }
        Err(e) => {
            eprintln!("request failed: {e}");
            Ok(error(500, "The request could not be completed"))
        }
    }
}
/// Concurrent network reads, serialized synchronous application callbacks.
pub fn web_serve(host: &str, port: i64, handler: Handler) -> Result<()> {
    serve(host, port, handler, None)
}
pub fn web_serve_stream(host: &str, port: i64, handler: Handler, poll: StreamPoll) -> Result<()> {
    serve(host, port, handler, Some(poll))
}
fn serve(host: &str, port: i64, handler: Handler, poll: Option<StreamPoll>) -> Result<()> {
    let listener = std::net::TcpListener::bind((host, u16::try_from(port)?))?;
    listener.set_nonblocking(true)?;
    println!("LISTENING http://{}", listener.local_addr()?);
    use std::io::Write;
    std::io::stdout().flush()?;
    tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()?
        .block_on(async {
            let listener = tokio::net::TcpListener::from_std(listener)?;
            let mut tasks = tokio::task::JoinSet::new();
            let active = Arc::new(AtomicUsize::new(0));
            loop {
                // Cap active connections and release completed tasks.
                while tasks.try_join_next().is_some() {}
                if tasks.len() >= 64 {
                    tasks.join_next().await;
                    continue;
                }
                let (stream, _) = listener.accept().await?;
                let active = active.clone();
                tasks.spawn(async move {
                    let connection = hyper::server::conn::http1::Builder::new()
                        .keep_alive(false)
                        .max_buf_size(32768)
                        .serve_connection(
                            TokioIo::new(stream),
                            hyper::service::service_fn(move |r| {
                                dispatch(r, handler, poll, active.clone())
                            }),
                        );
                    let _ = tokio::time::timeout(Duration::from_secs(60), connection).await;
                });
            }
        })
}
