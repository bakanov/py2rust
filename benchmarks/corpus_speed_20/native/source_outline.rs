//! Handwritten project analysis and HTML export over the shared native Python parser.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, HashMap, HashSet},
    fmt::Write,
    path::PathBuf,
};

#[derive(Deserialize)]
struct Alias {
    name: String,
    asname: String,
}
#[derive(Deserialize)]
struct Node {
    parent: i64,
    block: String,
    kind: String,
    name: String,
    line: usize,
    end_line: usize,
    decorators: Vec<Value>,
    string: Option<String>,
    names: Vec<Alias>,
    module: String,
    level: usize,
}
#[derive(Deserialize)]
struct Tree {
    nodes: Vec<Node>,
}
struct Source {
    document: Document,
    text: String,
}
#[derive(Serialize)]
struct Definition {
    node: usize,
    kind: String,
    name: String,
    qualified: String,
    line: usize,
    end_line: usize,
    decorators: Vec<Value>,
    docstring: String,
}
#[derive(Serialize)]
struct Import {
    kind: String,
    scope: String,
    line: usize,
    module: String,
    level: usize,
    name: String,
    alias: String,
    target: String,
    href: String,
}
#[derive(Serialize)]
struct Module {
    name: String,
    package: bool,
    docstring: String,
    definitions: Vec<Definition>,
    imports: Vec<Import>,
    statements: usize,
}
struct Project {
    output: PathBuf,
    sources: Vec<Source>,
    modules: Vec<Module>,
}
// Python's whitespace set additionally contains four ASCII information separators.
fn whitespace(c: char) -> bool {
    c.is_whitespace() || ('\x1c'..='\x1f').contains(&c)
}
fn clean_docstring(text: &str) -> String {
    let mut expanded = String::with_capacity(text.len());
    let mut column = 0;
    for c in text.chars() {
        if c == '\t' {
            let width = 8 - column % 8;
            expanded.extend(std::iter::repeat(' ').take(width));
            column += width;
        } else {
            expanded.push(c);
            column += 1;
            if c == '\n' || c == '\r' {
                column = 0;
            }
        }
    }
    let mut lines: Vec<&str> = expanded.split('\n').collect();
    let margin = lines
        .iter()
        .skip(1)
        .filter_map(|line| {
            let indent = line.chars().take_while(|c| whitespace(*c)).count();
            (line.chars().count() > indent).then_some(indent)
        })
        .min();
    lines[0] = lines[0].trim_start_matches(whitespace);
    if let Some(margin) = margin {
        for line in lines.iter_mut().skip(1) {
            let offset = line
                .char_indices()
                .nth(margin)
                .map_or(line.len(), |(offset, _)| offset);
            *line = &line[offset..];
        }
    }
    let start = lines
        .iter()
        .position(|s| !s.is_empty())
        .unwrap_or(lines.len());
    let end = lines
        .iter()
        .rposition(|s| !s.is_empty())
        .map_or(start, |n| n + 1);
    lines[start..end].join("\n")
}
fn describe(name: String, package: bool, tree: Tree) -> Module {
    let nodes = tree.nodes;
    let mut scopes: Vec<String> = Vec::with_capacity(nodes.len());
    let mut first = HashMap::new();
    let mut definitions = Vec::new();
    let mut imports = Vec::new();
    for (i, node) in nodes.iter().enumerate() {
        if node.block == "body" {
            first.entry(node.parent).or_insert(i);
        }
        let mut scope = if node.parent < 0 {
            name.clone()
        } else {
            scopes[node.parent as usize].clone()
        };
        if matches!(
            node.kind.as_str(),
            "ClassDef" | "FunctionDef" | "AsyncFunctionDef" | "TypeAlias"
        ) {
            let qualified = format!("{scope}.{}", node.name);
            definitions.push(Definition {
                node: i,
                kind: node.kind.clone(),
                name: node.name.clone(),
                qualified: qualified.clone(),
                line: node.line,
                end_line: node.end_line,
                decorators: node.decorators.clone(),
                docstring: String::new(),
            });
            if node.kind != "TypeAlias" {
                scope = qualified;
                if node.kind != "ClassDef" {
                    scope.push_str(".<locals>");
                }
            }
        }
        if matches!(node.kind.as_str(), "Import" | "ImportFrom") {
            for alias in &node.names {
                imports.push(Import {
                    kind: node.kind.clone(),
                    scope: scope.clone(),
                    line: node.line,
                    module: node.module.clone(),
                    level: node.level,
                    name: alias.name.clone(),
                    alias: alias.asname.clone(),
                    target: String::new(),
                    href: String::new(),
                });
            }
        }
        scopes.push(scope);
    }
    let doc = |parent: i64| {
        first
            .get(&parent)
            .and_then(|i| nodes[*i].string.as_deref())
            .map(clean_docstring)
            .unwrap_or_default()
    };
    for definition in &mut definitions {
        definition.docstring = doc(definition.node as i64);
    }
    Module {
        name,
        package,
        docstring: doc(-1),
        definitions,
        imports,
        statements: nodes.len(),
    }
}
fn connect(modules: &mut [Module]) {
    let pages: HashMap<_, _> = modules
        .iter()
        .map(|m| (m.name.clone(), format!("module-{}.html", m.name)))
        .collect();
    let mut symbols: HashMap<String, (usize, String)> = HashMap::new();
    for module in modules.iter() {
        for d in &module.definitions {
            if d.qualified == format!("{}.{}", module.name, d.name) {
                let entry = symbols.entry(d.qualified.clone()).or_default();
                entry.0 += 1;
                entry.1 = format!("module-{}.html#L{}", module.name, d.line);
            }
        }
    }
    for module in modules {
        for item in &mut module.imports {
            let mut base = item.module.clone();
            if item.level > 0 {
                let mut parts: Vec<&str> = module.name.split('.').collect();
                if !module.package {
                    parts.pop();
                }
                if item.level > parts.len() {
                    base = "!outside-project".into();
                } else {
                    parts.truncate(parts.len() - item.level + 1);
                    if !item.module.is_empty() {
                        parts.push(&item.module);
                    }
                    base = parts.join(".");
                }
            }
            let mut target = if item.kind == "ImportFrom" {
                format!("{base}.{}", item.name)
            } else {
                item.name.clone()
            };
            let href = if let Some(page) = pages.get(&target) {
                Some(page)
            } else if item.kind == "ImportFrom" && symbols.get(&target).is_some_and(|s| s.0 == 1) {
                Some(&symbols[&target].1)
            } else if let Some(page) = pages.get(&base) {
                target = base;
                Some(page)
            } else {
                None
            };
            if let Some(href) = href {
                item.target = target;
                item.href = href.clone();
            }
        }
    }
}
fn load(config: &Document) -> Result<Project> {
    let value = rt::json_loads(std::str::from_utf8(&config.data)?)?;
    exact(&value, &["modules", "output", "version"])?;
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
    let entries = value["modules"]
        .as_array()
        .ok_or("expected modules array")?;
    require((1..=32).contains(&entries.len()), "expected 1..32 modules")?;
    let mut names = HashSet::new();
    let mut paths = HashSet::new();
    let (mut sources, mut modules) = (Vec::new(), Vec::new());
    let mut total = 0;
    for entry in entries {
        if entry.get("package").is_some() {
            exact(entry, &["name", "package", "source"])?;
        } else {
            exact(entry, &["name", "source"])?;
        }
        let name = string(&entry["name"])?;
        require(
            name.chars().count() <= 128
                && rt::regex_fullmatch(r"[A-Za-z_][A-Za-z_0-9]*(\.[A-Za-z_][A-Za-z_0-9]*)*", name)?,
            "invalid module name",
        )?;
        require(names.insert(name), "duplicate module name")?;
        let path = absolute(string(&entry["source"])?, parent)?;
        require(
            path.extension().is_some_and(|e| e == "py") && paths.insert(path.clone()),
            "duplicate or non-Python source",
        )?;
        let package = match entry.get("package") {
            Some(v) => v.as_bool().ok_or("expected package boolean")?,
            None => path.file_name().is_some_and(|n| n == "__init__.py"),
        };
        let document = Document::read(path, 131072)?;
        total += document.data.len();
        require(total <= 1048576, "project exceeds 1 MiB")?;
        let text = std::str::from_utf8(&document.data)?;
        let text = text
            .strip_prefix('\u{feff}')
            .unwrap_or(text)
            .replace("\r\n", "\n")
            .replace('\r', "\n");
        require(
            text.split('\n').count() <= 4096,
            "module exceeds 4096 lines",
        )?;
        let tree: Tree = serde_json::from_value(rt::python_statement_tree(&text)?)?;
        modules.push(describe(name.into(), package, tree));
        sources.push(Source { document, text });
    }
    connect(&mut modules);
    Ok(Project {
        output,
        sources,
        modules,
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
fn page(title: &str, body: &str, modules: &[Module]) -> Vec<u8> {
    let mut navigation = link("index.html", "Project");
    for m in modules {
        navigation.push_str(&link(&format!("module-{}.html", m.name), &m.name));
    }
    format!("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>{}</title><style>{STYLE}</style><header><nav>{navigation}</nav><h1>{}</h1></header><main>{body}</main></html>",escape(title),escape(title)).into_bytes()
}
fn render(source: &Source, module: &Module, modules: &[Module]) -> Vec<u8> {
    let mut body = format!(
        "<pre>{}</pre><h2>Definitions</h2>",
        escape(&module.docstring)
    );
    for d in &module.definitions {
        write!(
            body,
            "<article><h3>{}</h3><small>{} · line {}</small>",
            link(&format!("#L{}", d.line), &d.qualified),
            escape(&d.kind),
            d.line
        )
        .unwrap();
        for decorator in &d.decorators {
            write!(
                body,
                "<pre>@{}</pre>",
                escape(decorator["text"].as_str().unwrap())
            )
            .unwrap();
        }
        write!(body, "<pre>{}</pre></article>", escape(&d.docstring)).unwrap();
    }
    body.push_str("<h2>Imports</h2><ul>");
    for item in &module.imports {
        let mut label = format!("{}{} {}", ".".repeat(item.level), item.module, item.name);
        if !item.alias.is_empty() {
            write!(label, " as {}", item.alias).unwrap();
        }
        write!(
            body,
            "<li>{} · ",
            link(&format!("#L{}", item.line), "source")
        )
        .unwrap();
        if item.href.is_empty() {
            write!(
                body,
                "{} <small>(external or unresolved)</small>",
                escape(&label)
            )
            .unwrap();
        } else {
            body.push_str(&link(&item.href, &label));
        }
        body.push_str("</li>");
    }
    body.push_str("</ul><h2>Source</h2><pre class=\"source\"><code>");
    for (index, line) in source.text.split('\n').enumerate() {
        let n = index + 1;
        write!(
            body,
            "<span class=\"line\" id=\"L{n}\"><a class=\"number\" href=\"#L{n}\">{n}</a>{}</span>",
            escape(line)
        )
        .unwrap();
    }
    body.push_str("</code></pre>");
    page(&module.name, &body, modules)
}
fn index_page(modules: &[Module]) -> Vec<u8> {
    let mut body = String::from("<p>Browse modules, definitions, documentation and imports. Use your browser's Find to search a page.</p>");
    for m in modules {
        write!(
            body,
            "<article><h2>{}</h2><pre>{}</pre><ul>",
            link(&format!("module-{}.html", m.name), &m.name),
            escape(&m.docstring)
        )
        .unwrap();
        for d in &m.definitions {
            write!(
                body,
                "<li>{}</li>",
                link(&format!("module-{}.html#L{}", m.name, d.line), &d.qualified)
            )
            .unwrap();
        }
        body.push_str("</ul></article>");
    }
    page("Python project outline", &body, modules)
}
fn run() -> Result<()> {
    let config = Document::read(
        absolute(
            &std::env::var("OUTLINE_CONFIG").unwrap_or_else(|_| "outline-project.json".into()),
            &std::env::current_dir()?,
        )?,
        1048576,
    )?;
    let project = load(&config)?;
    let mut files = BTreeMap::new();
    let mut entries = Vec::new();
    for (source, module) in project.sources.iter().zip(&project.modules) {
        files.insert(
            format!("module-{}.html", module.name),
            render(source, module, &project.modules),
        );
        let filename = format!("source-{}.py", module.name);
        files.insert(filename.clone(), source.document.data.clone());
        entries.push(json!({"name":module.name,"source":filename,"package":module.package}));
    }
    let report = json!({"version":1,"modules":project.modules});
    files.insert("index.html".into(), index_page(&project.modules));
    files.insert("report.json".into(), canonical(&report)?);
    files.insert(
        "project.json".into(),
        canonical(&json!({"version":1,"modules":entries,"output":"rebuilt"}))?,
    );
    require(
        files.values().map(Vec::len).sum::<usize>() <= 16777216,
        "rendered bundle exceeds 16 MiB",
    )?;
    let checksums: BTreeMap<_, _> = files
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
    publish_exact(&project.output, files, &[], "outline")?;
    print!("{}", std::str::from_utf8(&canonical(&report)?)?);
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}

// Shared static stylesheet.
const STYLE: &str = r##"body{margin:0;font:16px system-ui;color:#203040;background:#f4f7fa}header,main{padding:1.5rem;max-width:1100px;margin:auto}header{background:#e2edf5}a{color:#086ba5}nav{display:flex;gap:1rem;flex-wrap:wrap}article{background:white;padding:1rem;margin:1rem 0;border-radius:8px}pre{overflow:auto;white-space:pre-wrap}code{font:14px monospace}.source{white-space:pre;overflow:auto;background:white;padding:1rem}.line{display:block}.line:target{background:#fff1a8}.number{display:inline-block;width:4em;color:#789}small{color:#567}h1{overflow-wrap:anywhere}"##;
