//! Independent bounded configuration lexer and static HTML exporter.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde::Serialize;
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, HashSet},
    fmt::Write,
    path::PathBuf,
};

#[derive(Clone, Copy, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
enum Kind {
    Space,
    Identifier,
    Keyword,
    Number,
    String,
    Comment,
    Punctuation,
    Error,
}
impl Kind {
    fn name(self) -> &'static str {
        match self {
            Self::Space => "space",
            Self::Identifier => "identifier",
            Self::Keyword => "keyword",
            Self::Number => "number",
            Self::String => "string",
            Self::Comment => "comment",
            Self::Punctuation => "punctuation",
            Self::Error => "error",
        }
    }
}
#[derive(Serialize)]
struct Token {
    kind: Kind,
    text: String,
    start: usize,
    end: usize,
    line: usize,
    column: usize,
    end_line: usize,
    end_column: usize,
}
#[derive(Serialize)]
struct Diagnostic {
    token: usize,
    line: usize,
    column: usize,
    message: &'static str,
}
struct Highlight {
    tokens: Vec<Token>,
    diagnostics: Vec<Diagnostic>,
    lines: usize,
}
fn scan(source: &str) -> Result<Highlight> {
    let text = source.replace("\r\n", "\n").replace('\r', "\n");
    require(!text.contains('\0'), "source contains NUL")?;
    let chars: Vec<char> = text.chars().collect();
    let mut tokens = Vec::new();
    let mut diagnostics = Vec::new();
    let (mut pos, mut line, mut column) = (0, 1, 1);
    while pos < chars.len() {
        let start = pos;
        let c = chars[pos];
        let mut kind = Kind::Punctuation;
        let mut error = "";
        if " \t\n\x0c\x0b".contains(c) {
            kind = Kind::Space;
            while pos < chars.len() && " \t\n\x0c\x0b".contains(chars[pos]) {
                pos += 1;
            }
        } else if c == '#' {
            kind = Kind::Comment;
            while pos < chars.len() && chars[pos] != '\n' {
                pos += 1;
            }
        } else if chars[pos..].starts_with(&['/', '*']) {
            kind = Kind::Comment;
            let mut depth = 1;
            pos += 2;
            while pos < chars.len() && depth > 0 {
                if chars[pos..].starts_with(&['/', '*']) {
                    depth += 1;
                    require(depth <= 8, "comment nesting exceeds 8")?;
                    pos += 2;
                } else if chars[pos..].starts_with(&['*', '/']) {
                    depth -= 1;
                    pos += 2;
                } else {
                    pos += 1;
                }
            }
            if depth != 0 {
                error = "unterminated block comment";
            }
        } else if c == '\'' || c == '"' {
            kind = Kind::String;
            let triple = chars[pos..].starts_with(&[c, c, c]);
            pos += if triple { 3 } else { 1 };
            let mut closed = false;
            while pos < chars.len() {
                if chars[pos] == '\n' && !triple {
                    break;
                }
                if chars[pos] == '\\' {
                    pos += 1;
                    if pos < chars.len() && (triple || chars[pos] != '\n') {
                        pos += 1;
                    }
                } else if chars[pos] == c && (!triple || chars[pos..].starts_with(&[c, c, c])) {
                    pos += if triple { 3 } else { 1 };
                    closed = true;
                    break;
                } else {
                    pos += 1;
                }
            }
            if !closed {
                error = "unterminated string";
            }
        } else if c.is_ascii_alphabetic() || c == '_' {
            kind = Kind::Identifier;
            while pos < chars.len() && (chars[pos].is_ascii_alphanumeric() || chars[pos] == '_') {
                pos += 1;
            }
        } else if c.is_ascii_digit() {
            kind = Kind::Number;
            pos += 1;
            while pos < chars.len()
                && ("0123456789.eE".contains(chars[pos])
                    || ("+-".contains(chars[pos]) && "eE".contains(chars[pos - 1])))
            {
                pos += 1;
            }
        } else {
            pos += 1;
            if !"{}[]():=,;.+-*/".contains(c) {
                error = "unexpected character";
            }
        }
        let value: String = chars[start..pos].iter().collect();
        if kind == Kind::Identifier && matches!(value.as_str(), "true" | "false" | "null") {
            kind = Kind::Keyword;
        }
        if kind == Kind::Number
            && !rt::regex_fullmatch(r"[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?", &value)?
        {
            error = "invalid number";
        }
        if !error.is_empty() {
            kind = Kind::Error;
            diagnostics.push(Diagnostic {
                token: tokens.len(),
                line,
                column,
                message: error,
            });
        }
        let (mut end_line, mut end_column) = (line, column);
        for ch in &chars[start..pos] {
            if *ch == '\n' {
                end_line += 1;
                end_column = 1;
            } else {
                end_column += 1;
            }
        }
        tokens.push(Token {
            kind,
            text: value,
            start,
            end: pos,
            line,
            column,
            end_line,
            end_column,
        });
        require(tokens.len() <= 8192, "source exceeds 8192 tokens")?;
        (line, column) = (end_line, end_column);
    }
    Ok(Highlight {
        tokens,
        diagnostics,
        lines: text.bytes().filter(|c| *c == b'\n').count() + 1,
    })
}
struct Source {
    label: String,
    document: Document,
    highlight: Highlight,
}
struct Project {
    output: PathBuf,
    theme: String,
    sources: Vec<Source>,
}
fn load(config: &Document) -> Result<Project> {
    let value = rt::json_loads(std::str::from_utf8(&config.data)?)?;
    exact(&value, &["files", "output", "theme", "version"])?;
    require(
        integer(&value["version"])? == 1,
        "unsupported project version",
    )?;
    let parent = config.path.parent().ok_or("missing parent")?;
    let output = absolute(string(&value["output"])?, parent)?;
    require(
        !output.exists() && !output.is_symlink(),
        "output already exists",
    )?;
    let theme = string(&value["theme"])?;
    require(
        matches!(theme, "light" | "dark"),
        "theme must be light or dark",
    )?;
    let entries = value["files"].as_array().ok_or("expected source array")?;
    require(
        (1..=16).contains(&entries.len()),
        "expected 1..16 source files",
    )?;
    let mut labels = HashSet::new();
    let mut paths = HashSet::new();
    let mut sources = Vec::new();
    let (mut size, mut count) = (0, 0);
    for entry in entries {
        exact(entry, &["label", "source"])?;
        let label = string(&entry["label"])?;
        require(
            (1..=80).contains(&label.chars().count()) && labels.insert(label),
            "invalid or duplicate label",
        )?;
        require(
            !label.contains(['\0', '\n', '\r']),
            "label must be one line",
        )?;
        let path = absolute(string(&entry["source"])?, parent)?;
        // Document rejects hard links, including path aliases, in this benchmark's input scope.
        require(paths.insert(path.clone()), "duplicate source")?;
        let document = Document::read(path, 65536)?;
        size += document.data.len();
        require(size <= 262144, "project source exceeds 256 KiB")?;
        let highlight = scan(std::str::from_utf8(&document.data)?)?;
        count += highlight.tokens.len();
        require(count <= 32768, "project exceeds 32768 tokens")?;
        sources.push(Source {
            label: label.into(),
            document,
            highlight,
        });
    }
    Ok(Project {
        output,
        theme: theme.into(),
        sources,
    })
}
fn escape(text: &str) -> String {
    let mut result = String::with_capacity(text.len());
    for c in text.chars() {
        match c {
            '&' => result.push_str("&amp;"),
            '<' => result.push_str("&lt;"),
            '>' => result.push_str("&gt;"),
            '"' => result.push_str("&quot;"),
            '\'' => result.push_str("&#39;"),
            _ => result.push(c),
        }
    }
    result
}
fn link(href: &str, label: &str) -> String {
    format!("<a href=\"{}\">{}</a>", escape(href), escape(label))
}
fn page(title: &str, body: &str, project: &Project) -> Vec<u8> {
    let mut navigation = link("index.html", "Project");
    for (i, source) in project.sources.iter().enumerate() {
        navigation.push_str(&link(&format!("file-{i}.html"), &source.label));
    }
    format!("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{}</title><link rel=\"stylesheet\" href=\"style.css\"></head><body class=\"{}\"><header><nav>{navigation}</nav><h1>{}</h1></header><main>{body}<footer>Configuration source viewer · {} theme</footer></main></body></html>", escape(title), project.theme, escape(title), escape(&project.theme)).into_bytes()
}
fn render(source: &Source, index: usize, project: &Project) -> Vec<u8> {
    let h = &source.highlight;
    let mut body = format!("<p><a download href=\"file-{index}.source\">Download original source</a> · {} lines · {} tokens</p>", h.lines, h.tokens.len());
    if !h.diagnostics.is_empty() {
        body.push_str("<section aria-label=\"Diagnostics\"><h2>Diagnostics</h2><ul>");
        for d in &h.diagnostics {
            write!(
                body,
                "<li>{}</li>",
                link(
                    &format!("#t{}", d.token),
                    &format!("{}:{}: {}", d.line, d.column, d.message)
                )
            )
            .unwrap();
        }
        body.push_str("</ul></section>");
    }
    body.push_str("<div class=\"listing\"><pre class=\"gutter\" aria-hidden=\"true\">");
    for n in 1..=h.lines {
        if n > 1 {
            body.push('\n');
        }
        write!(body, "{n}").unwrap();
    }
    body.push_str("</pre><pre><code id=\"source\">");
    for (n, token) in h.tokens.iter().enumerate() {
        write!(
            body,
            "<span class=\"{}\" id=\"t{n}\" data-start=\"{}\" data-end=\"{}\">{}</span>",
            token.kind.name(),
            token.start,
            token.end,
            escape(&token.text)
        )
        .unwrap();
    }
    body.push_str("</code></pre></div>");
    page(&source.label, &body, project)
}
fn index_page(project: &Project) -> Vec<u8> {
    let mut body = String::from(
        "<p>Browse highlighted configuration text. Source is displayed without execution.</p>",
    );
    for (i, source) in project.sources.iter().enumerate() {
        write!(
            body,
            "<article><h2>{}</h2><p>{} tokens · {} diagnostics</p></article>",
            link(&format!("file-{i}.html"), &source.label),
            source.highlight.tokens.len(),
            source.highlight.diagnostics.len()
        )
        .unwrap();
    }
    write!(
        body,
        "<p>{} · {}</p>",
        link("report.json", "Token report"),
        link("highlight-job.json", "Replay project")
    )
    .unwrap();
    page("Configuration source viewer", &body, project)
}
fn run() -> Result<i32> {
    let config = Document::read(
        absolute(
            &std::env::var("HIGHLIGHT_CONFIG").unwrap_or_else(|_| "highlight-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let project = load(&config)?;
    let mut files = BTreeMap::from([
        ("style.css".into(), STYLE.as_bytes().to_vec()),
        ("index.html".into(), index_page(&project)),
    ]);
    let mut reports = Vec::new();
    let mut entries = Vec::new();
    let mut errors = 0;
    for (i, source) in project.sources.iter().enumerate() {
        let h = &source.highlight;
        reports.push(json!({"tokens":h.tokens, "diagnostics":h.diagnostics, "lines":h.lines, "label":source.label, "page":format!("file-{i}.html"), "source":format!("file-{i}.source")}));
        errors += h.diagnostics.len();
        files.insert(format!("file-{i}.html"), render(source, i, &project));
        files.insert(format!("file-{i}.source"), source.document.data.clone());
        entries.push(json!({"label":source.label, "source":format!("file-{i}.source")}));
    }
    let result = json!({"version":1, "theme":project.theme, "diagnostics":errors, "files":reports});
    files.insert("report.json".into(), canonical(&result)?);
    files.insert(
        "highlight-job.json".into(),
        canonical(
            &json!({"version":1, "theme":project.theme, "files":entries, "output":"rebuilt"}),
        )?,
    );
    require(
        files.values().map(Vec::len).sum::<usize>() <= 16777216,
        "rendered bundle exceeds 16 MiB",
    )?;
    let checksums: BTreeMap<_, Value> = files
        .iter()
        .map(|(name, data)| {
            (
                name.clone(),
                json!({"bytes":data.len(),"sha256":digest(data)}),
            )
        })
        .collect();
    files.insert(
        "manifest.json".into(),
        canonical(&json!({"version":1,"files":checksums}))?,
    );
    config.unchanged()?;
    for source in &project.sources {
        source.document.unchanged()?;
    }
    publish_exact(&project.output, files, &[], "highlight")?;
    print!("{}", std::str::from_utf8(&canonical(&result)?)?);
    Ok(if errors > 0 { 1 } else { 0 })
}
fn main() {
    match run() {
        Ok(status) => std::process::exit(status),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    }
}

// Static UI stylesheet shared with the application, not a computed fixture.
const STYLE: &str = r##"*{box-sizing:border-box}body{--bg:#f4f7fb;--panel:#fff;--ink:#223249;--muted:#65758d;--border:#dbe3ed;--link:#1768b2;--string:#156b41;--number:#8b3bb0;--comment:#667d70;--error:#bd2340;margin:0;background:var(--bg);color:var(--ink);font:16px system-ui}.dark{--bg:#141c29;--panel:#1c2839;--ink:#dbe7f6;--muted:#99abc2;--border:#35445b;--link:#80b9ff;--string:#8fd5a6;--number:#d5a5ff;--comment:#9bad9f;--error:#ff9aad}header,main{max-width:1200px;margin:auto;padding:1.5rem}header{border-bottom:1px solid var(--border)}h1{font-size:1.7rem;overflow-wrap:anywhere}a{color:var(--link)}nav{display:flex;gap:1rem;flex-wrap:wrap}article,.listing{background:var(--panel);border:1px solid var(--border);border-radius:.6rem;padding:1rem;margin:1rem 0}.listing{display:flex;padding:0;overflow:auto}pre{margin:0;padding:1rem;white-space:pre;font:14px/1.65 'DejaVu Sans Mono',monospace;tab-size:4}.gutter{color:var(--muted);border-right:1px solid var(--border);text-align:right;user-select:none}code{font:inherit}.keyword{color:var(--link);font-weight:bold}.number{color:var(--number)}.string{color:var(--string)}.comment{color:var(--comment);font-style:italic}.error{color:var(--error);text-decoration:underline wavy}span:target{outline:2px solid var(--link)}small{color:var(--muted)}li{margin:.5rem 0}footer{margin-top:1.5rem;color:var(--muted)}"##;
