//! Independent scoped metrics, import classification and source-browser publication.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::{
    collections::{BTreeMap, HashMap, HashSet},
    fmt::Write as _,
    fs,
    io::Write as _,
    path::{Path, PathBuf},
};

#[derive(Deserialize)]
struct Alias {
    name: String,
    asname: String,
}
#[derive(Deserialize)]
struct Decorator {
    line: usize,
}
#[derive(Deserialize)]
struct Node {
    parent: i64,
    kind: String,
    name: String,
    line: usize,
    column: usize,
    end_line: usize,
    end_column: usize,
    decorators: Vec<Decorator>,
    names: Vec<Alias>,
    module: String,
    level: usize,
}
#[derive(Deserialize)]
struct Tree {
    nodes: Vec<Node>,
}
#[derive(Default, Serialize)]
struct Counter {
    statements: usize,
    control_statements: usize,
    max_depth: usize,
    kinds: BTreeMap<String, usize>,
}
#[derive(Serialize)]
struct Definition {
    id: usize,
    kind: String,
    name: String,
    qualified: String,
    line: usize,
    column: usize,
    end_line: usize,
    end_column: usize,
    start_line: usize,
    lines: usize,
    metrics: Counter,
    flags: Vec<&'static str>,
}
#[derive(Serialize)]
struct Import {
    kind: String,
    line: usize,
    column: usize,
    scope: String,
    module: String,
    level: usize,
    name: String,
    alias: String,
    status: &'static str,
    target: String,
    href: String,
}
#[derive(Serialize)]
struct Module {
    path: String,
    name: String,
    package: bool,
    page: String,
    bytes: usize,
    sha256: String,
    lines: usize,
    statements: usize,
    kinds: BTreeMap<String, usize>,
    top_level: Counter,
    definitions: Vec<Definition>,
    functions: usize,
    classes: usize,
    flagged_functions: usize,
    imports: Vec<Import>,
}
#[derive(Serialize, Deserialize)]
struct Thresholds {
    lines: usize,
    statements: usize,
    depth: usize,
}
struct Source {
    document: Document,
    text: String,
}
struct Project {
    config: Document,
    root: PathBuf,
    output: PathBuf,
    excluded: HashSet<String>,
    prefix: String,
    thresholds: Thresholds,
    paths: Vec<String>,
    sources: Vec<Source>,
    modules: Vec<Module>,
}
fn discover(root: &Path, excluded: &HashSet<String>) -> Result<Vec<String>> {
    let mut pending = vec![(String::new(), 0)];
    let mut sources = Vec::new();
    let mut entries = 0;
    while let Some((relative, depth)) = pending.pop() {
        require(depth <= 8, "source directory depth limit")?;
        let directory = root.join(&relative);
        require(
            fs::symlink_metadata(&directory)?.is_dir(),
            "source directory required",
        )?;
        for entry in fs::read_dir(directory)? {
            let entry = entry?;
            entries += 1;
            require(entries <= 4096, "source inventory entry limit")?;
            let name = entry
                .file_name()
                .into_string()
                .map_err(|_| "non-UTF8 source path")?;
            if name.starts_with('.') || excluded.contains(&name) {
                continue;
            }
            let child = if relative.is_empty() {
                name.clone()
            } else {
                format!("{relative}/{name}")
            };
            let kind = entry.file_type()?;
            require(
                kind.is_file() || kind.is_dir(),
                "unsupported source-tree entry",
            )?;
            if kind.is_dir() {
                pending.push((child, depth + 1));
            } else if name.ends_with(".py") {
                sources.push(child);
                require(sources.len() <= 64, "at most 64 Python modules")?;
            }
        }
    }
    sources.sort();
    Ok(sources)
}
fn analyze(
    path: String,
    name: String,
    package: bool,
    page: String,
    source: &Source,
    tree: Tree,
    thresholds: &Thresholds,
) -> Module {
    let nodes = tree.nodes;
    let mut owners: Vec<usize> = Vec::with_capacity(nodes.len());
    let mut depths: Vec<usize> = Vec::with_capacity(nodes.len());
    let mut scopes: Vec<String> = Vec::with_capacity(nodes.len());
    let mut counts: Vec<Counter> = (0..=nodes.len()).map(|_| Counter::default()).collect();
    let mut definitions = Vec::new();
    let mut imports = Vec::new();
    let mut kinds = BTreeMap::new();
    for (index, node) in nodes.iter().enumerate() {
        let mut owner = if node.parent < 0 {
            0
        } else {
            owners[node.parent as usize]
        };
        let depth = if node.parent + 1 == owner as i64 {
            0
        } else {
            depths[node.parent as usize] + 1
        };
        let mut scope = if node.parent < 0 {
            name.clone()
        } else {
            scopes[node.parent as usize].clone()
        };
        *kinds.entry(node.kind.clone()).or_insert(0) += 1;
        let counter = &mut counts[owner];
        counter.statements += 1;
        counter.max_depth = counter.max_depth.max(depth);
        *counter.kinds.entry(node.kind.clone()).or_insert(0) += 1;
        if matches!(
            node.kind.as_str(),
            "If" | "For"
                | "AsyncFor"
                | "While"
                | "Try"
                | "TryStar"
                | "With"
                | "AsyncWith"
                | "Match"
        ) {
            counter.control_statements += 1;
        }
        if matches!(
            node.kind.as_str(),
            "ClassDef" | "FunctionDef" | "AsyncFunctionDef"
        ) {
            let qualified = format!("{scope}.{}", node.name);
            let start = node
                .decorators
                .iter()
                .map(|d| d.line)
                .fold(node.line, usize::min);
            definitions.push(Definition {
                id: index,
                kind: node.kind.clone(),
                name: node.name.clone(),
                qualified: qualified.clone(),
                line: node.line,
                column: node.column,
                end_line: node.end_line,
                end_column: node.end_column,
                start_line: start,
                lines: node.end_line - start + 1,
                metrics: Counter::default(),
                flags: Vec::new(),
            });
            owner = index + 1;
            scope = qualified;
            if node.kind != "ClassDef" {
                scope.push_str(".<locals>");
            }
        }
        if matches!(node.kind.as_str(), "Import" | "ImportFrom") {
            for alias in &node.names {
                imports.push(Import {
                    kind: node.kind.clone(),
                    line: node.line,
                    column: node.column,
                    scope: scope.clone(),
                    module: node.module.clone(),
                    level: node.level,
                    name: alias.name.clone(),
                    alias: alias.asname.clone(),
                    status: "",
                    target: String::new(),
                    href: String::new(),
                });
            }
        }
        owners.push(owner);
        depths.push(depth);
        scopes.push(scope);
    }
    let (mut functions, mut flagged) = (0, 0);
    for d in &mut definitions {
        d.metrics = std::mem::take(&mut counts[d.id + 1]);
        if d.kind != "ClassDef" {
            functions += 1;
            if d.lines > thresholds.lines {
                d.flags.push("lines");
            }
            if d.metrics.statements > thresholds.statements {
                d.flags.push("statements");
            }
            if d.metrics.max_depth > thresholds.depth {
                d.flags.push("depth");
            }
        }
        if !d.flags.is_empty() {
            flagged += 1;
        }
    }
    Module {
        path,
        name,
        package,
        page,
        bytes: source.document.data.len(),
        sha256: digest(&source.document.data),
        lines: source.text.lines().count(),
        statements: nodes.len(),
        kinds,
        top_level: std::mem::take(&mut counts[0]),
        classes: definitions.len() - functions,
        functions,
        flagged_functions: flagged,
        definitions,
        imports,
    }
}
fn connect(modules: &mut [Module]) {
    let mut pages: HashMap<String, Vec<String>> = HashMap::new();
    let mut namespaces = HashSet::new();
    for m in modules.iter() {
        pages
            .entry(m.name.clone())
            .or_default()
            .push(m.page.clone());
        let parts: Vec<_> = m.name.split('.').collect();
        for i in 1..parts.len() {
            namespaces.insert(parts[..i].join("."));
        }
    }
    for m in modules {
        for item in &mut m.imports {
            let mut base = item.module.clone();
            let mut outside = false;
            if item.level > 0 {
                let mut parts: Vec<_> = m.name.split('.').collect();
                if !m.package {
                    parts.pop();
                }
                outside = item.level > parts.len();
                if !outside {
                    let prefix = parts[..parts.len() - item.level + 1].join(".");
                    base = if base.is_empty() {
                        prefix
                    } else {
                        format!("{prefix}.{base}")
                    };
                }
            }
            let imported = item.kind == "ImportFrom";
            let candidate = if imported {
                format!("{base}.{}", item.name)
            } else {
                item.name.clone()
            };
            item.status = "external";
            item.target = candidate;
            if outside {
                item.status = "outside_root";
                item.target.clear();
                continue;
            }
            let member =
                imported && !pages.contains_key(&item.target) && !namespaces.contains(&item.target);
            if member && (pages.contains_key(&base) || namespaces.contains(&base)) {
                item.target = base;
                item.status = if item.name == "*" {
                    "local_wildcard"
                } else {
                    "local_member"
                };
            }
            if let Some(matches) = pages.get(&item.target) {
                if matches.len() > 1 {
                    item.status = "ambiguous";
                } else {
                    item.href = matches[0].clone();
                    if !member {
                        item.status = "local_module";
                    }
                }
            } else if namespaces.contains(&item.target) {
                if !member {
                    item.status = "namespace";
                }
                item.href = "index.html".into();
            } else {
                let first = item.target.split('.').next().unwrap();
                if item.level > 0 || pages.contains_key(first) || namespaces.contains(first) {
                    item.status = "missing_local";
                }
            }
        }
    }
}
fn load(config: Document) -> Result<Project> {
    let value = config.json()?;
    exact(
        &value,
        &[
            "version",
            "root",
            "output",
            "package",
            "exclude",
            "thresholds",
        ],
    )?;
    require(integer(&value["version"])? == 1, "unsupported version")?;
    let base = config.path.parent().ok_or("missing parent")?;
    let root = absolute(string(&value["root"])?, base)?;
    let output = absolute(string(&value["output"])?, base)?;
    require(
        !output.exists() && !output.is_symlink(),
        "output already exists",
    )?;
    require(
        root != Path::new("/") && !output.starts_with(&root),
        "output must be outside source root",
    )?;
    let prefix = string(&value["package"])?;
    let pattern = r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*";
    require(
        prefix.chars().count() <= 128
            && (prefix.is_empty() || rt::regex_fullmatch(pattern, prefix)?),
        "package name",
    )?;
    if !prefix.is_empty() {
        rt::python_statement_tree(&format!("import {prefix}"))?;
    }
    let excluded_values = value["exclude"].as_array().ok_or("expected exclusions")?;
    require(excluded_values.len() <= 16, "too many exclusions")?;
    let mut excluded = HashSet::new();
    for entry in excluded_values {
        let name = string(entry)?;
        require(
            rt::regex_fullmatch("[A-Za-z_][A-Za-z0-9_-]{0,63}", name)?
                && excluded.insert(name.to_owned()),
            "invalid exclusion",
        )?;
    }
    exact(&value["thresholds"], &["lines", "statements", "depth"])?;
    for key in ["lines", "statements", "depth"] {
        require(
            (0..=if key == "depth" { 64 } else { 4096 })
                .contains(&integer(&value["thresholds"][key])?),
            "invalid threshold",
        )?;
    }
    let thresholds: Thresholds = serde_json::from_value(value["thresholds"].clone())?;
    let paths = discover(&root, &excluded)?;
    let (mut sources, mut modules) = (Vec::new(), Vec::new());
    let (mut total, mut statements) = (0, 0);
    for (index, relative) in paths.iter().enumerate() {
        let mut name = relative[..relative.len() - 3].replace('/', ".");
        let package = name == "__init__" || name.ends_with(".__init__");
        if package {
            if name == "__init__" {
                name.clear();
            } else {
                name.truncate(name.len() - 9);
            }
        }
        require(
            !name.is_empty() || !prefix.is_empty(),
            "root __init__.py requires a package name",
        )?;
        if !prefix.is_empty() {
            name = if name.is_empty() {
                prefix.to_owned()
            } else {
                format!("{prefix}.{name}")
            };
        }
        require(
            name.chars().count() <= 256 && rt::regex_fullmatch(pattern, &name)?,
            "invalid module path",
        )?;
        rt::python_statement_tree(&format!("import {name}"))?;
        let document = Document::read(absolute(relative, &root)?, 131072)?;
        total += document.data.len();
        require(total <= 1048576, "source project exceeds 1 MiB")?;
        let raw = std::str::from_utf8(&document.data)?;
        let text = raw
            .strip_prefix('\u{feff}')
            .unwrap_or(raw)
            .replace("\r\n", "\n")
            .replace('\r', "\n");
        require(
            text.lines().count() <= 4096,
            "source module exceeds 4096 lines",
        )?;
        let tree: Tree = serde_json::from_value(
            rt::python_statement_tree(&text).map_err(|error| format!("{relative}: {error}"))?,
        )?;
        statements += tree.nodes.len();
        require(
            statements <= 32768,
            "source project exceeds 32768 statements",
        )?;
        let source = Source { document, text };
        modules.push(analyze(
            relative.clone(),
            name,
            package,
            format!("module-{index}.html"),
            &source,
            tree,
            &thresholds,
        ));
        sources.push(source);
    }
    connect(&mut modules);
    Ok(Project {
        config,
        root,
        output,
        excluded,
        prefix: prefix.into(),
        thresholds,
        paths,
        sources,
        modules,
    })
}
fn escape(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(c),
        }
    }
    out
}
fn link(href: &str, label: &str) -> String {
    format!("<a href=\"{}\">{}</a>", escape(href), escape(label))
}
fn shell(title: &str, body: &str, modules: &[Module]) -> Vec<u8> {
    let mut nav = link("index.html", "Project overview");
    for m in modules {
        nav.push_str(&link(&m.page, &m.path));
    }
    format!("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>{} · Code metrics</title><style>{STYLE}</style></head><body><header><small>PYTHON PROJECT / STRUCTURAL METRICS</small><h1>{}</h1><div>Static source analysis · Use browser Find to search</div></header><div class=\"layout\"><nav>{nav}</nav><main>{body}</main></div></body></html>",escape(title),escape(title)).into_bytes()
}
fn definitions(module: &Module) -> String {
    let mut body=String::from("<table><thead><tr><th>Definition</th><th>Lines</th><th>Statements</th><th>Control</th><th>Depth</th><th>Flags</th></tr></thead><tbody>");
    for d in &module.definitions {
        let css = if d.flags.is_empty() {
            ""
        } else {
            " class=\"flag\""
        };
        write!(
            body,
            "<tr{css}><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>",
            link(&format!("{}#L{}", module.page, d.line), &d.qualified),
            d.lines,
            d.metrics.statements,
            d.metrics.control_statements,
            d.metrics.max_depth,
            escape(&d.flags.join(", "))
        )
        .unwrap();
    }
    body.push_str("</tbody></table>");
    body
}
fn render(source: &Source, module: &Module, modules: &[Module]) -> Vec<u8> {
    let mut body = format!(
        "<article><h2>Definitions</h2>{}</article><article><h2>Imports</h2><ul>",
        definitions(module)
    );
    for item in &module.imports {
        let label = format!("{} · {}", item.module, item.name);
        write!(
            body,
            "<li>{} — {} <small>{}</small></li>",
            link(&format!("#L{}", item.line), &format!("line {}", item.line)),
            if item.href.is_empty() {
                escape(&label)
            } else {
                link(&item.href, &label)
            },
            escape(item.status)
        )
        .unwrap();
    }
    body.push_str("</ul></article><h2>Source</h2><pre class=\"source\"><code>");
    for (i, line) in source.text.lines().enumerate() {
        let n = i + 1;
        write!(
            body,
            "<span class=\"line\" id=\"L{n}\"><a class=\"number\" href=\"#L{n}\">{n}</a>{}</span>",
            escape(line)
        )
        .unwrap();
    }
    body.push_str("</code></pre>");
    shell(&module.name, &body, modules)
}
#[derive(Serialize)]
struct Summary {
    modules: usize,
    functions: usize,
    classes: usize,
    statements: usize,
    flagged_functions: usize,
}
fn overview(modules: &[Module], summary: &Summary) -> Vec<u8> {
    let mut body = String::from("<article><h2>Project overview</h2><p>");
    for (name, value) in [
        ("modules", summary.modules),
        ("functions", summary.functions),
        ("classes", summary.classes),
        ("statements", summary.statements),
        ("flagged functions", summary.flagged_functions),
    ] {
        write!(body, "{value} {name} · ").unwrap();
    }
    body.push_str("</p><p class=\"muted\">Function spans include decorators. Owned statements exclude nested definition bodies. Control counts describe statements, not cyclomatic complexity.</p></article>");
    for m in modules {
        write!(
            body,
            "<article><h2>{}</h2><p class=\"muted\">{} · {} source lines</p>{}</article>",
            link(&m.page, &m.path),
            escape(&m.name),
            m.lines,
            definitions(m)
        )
        .unwrap();
    }
    shell("Code metrics browser", &body, modules)
}
// Inventory and source snapshots are checked after staging, before the no-replace rename.
fn publish_project(project: &Project, files: &BTreeMap<String, Vec<u8>>) -> Result<()> {
    let parent = project.output.parent().ok_or("missing output parent")?;
    let staging = parent.join(format!(".metrics-{}", rt::random_token()?));
    fs::create_dir(&staging)?;
    let result = (|| -> Result<()> {
        for (name, data) in files {
            let mut file = fs::OpenOptions::new()
                .read(true)
                .write(true)
                .create_new(true)
                .open(staging.join(name))?;
            file.write_all(data)?;
            file.sync_all()?;
        }
        fs::File::open(&staging)?.sync_all()?;
        require(
            discover(&project.root, &project.excluded)? == project.paths,
            "source inventory changed",
        )?;
        project.config.unchanged()?;
        for source in &project.sources {
            source.document.unchanged()?;
        }
        rt::rename_no_replace(
            staging.to_str().ok_or("invalid path")?,
            project.output.to_str().ok_or("invalid path")?,
        )?;
        fs::File::open(parent)?.sync_all()?;
        Ok(())
    })();
    if staging.exists() {
        fs::remove_dir_all(&staging)?;
    }
    result
}
fn run() -> Result<()> {
    let config = Document::read(
        absolute(
            &std::env::var("METRICS_CONFIG").unwrap_or_else(|_| "metrics-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let project = load(config)?;
    let modules = &project.modules;
    let summary = Summary {
        modules: modules.len(),
        functions: modules.iter().map(|m| m.functions).sum(),
        classes: modules.iter().map(|m| m.classes).sum(),
        statements: modules.iter().map(|m| m.statements).sum(),
        flagged_functions: modules.iter().map(|m| m.flagged_functions).sum(),
    };
    let mut files = BTreeMap::new();
    let mut archive = Vec::new();
    for (source, module) in project.sources.iter().zip(modules) {
        files.insert(module.page.clone(), render(source, module, modules));
        archive.push(json!({"path":module.path,"data":rt::base64_encode(&source.document.data)?}));
    }
    files.insert("index.html".into(), overview(modules, &summary));
    files.insert("report.json".into(),canonical(&json!({"version":1,"package":project.prefix,"thresholds":project.thresholds,"summary":summary,"modules":modules}))?);
    // Preserve exclusion order from the request in the reusable source archive.
    let excluded = project.config.json()?["exclude"].clone();
    files.insert("sources.json".into(),canonical(&json!({"version":1,"package":project.prefix,"exclude":excluded,"thresholds":project.thresholds,"files":archive}))?);
    require(
        files.values().map(Vec::len).sum::<usize>() <= 16777216,
        "report bundle exceeds 16 MiB",
    )?;
    let manifest: BTreeMap<_, _> = files
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
        canonical(&serde_json::to_value(manifest)?)?,
    );
    publish_project(&project, &files)?;
    print!(
        "{}",
        std::str::from_utf8(&canonical(&serde_json::to_value(summary)?)?)?
    );
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}

// Shared static stylesheet.
const STYLE: &str = r##"
*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#1b2b42;font:15px system-ui}
header{padding:24px 32px;background:#172d46;color:white}header small{color:#a5c9e8}h1{margin:8px 0}
a{color:#126aa4;text-decoration:none}a:hover{text-decoration:underline}.layout{display:flex;min-height:85vh}
nav{width:250px;flex-shrink:0;padding:24px;background:white;border-right:1px solid #dce5ee}
nav a{display:block;padding:7px;overflow-wrap:anywhere}main{padding:28px;min-width:0;flex:1}
article{background:white;border:1px solid #dce5ee;border-radius:10px;padding:20px;margin-bottom:20px}
table{border-collapse:collapse;width:100%;font-size:14px}
td,th{text-align:left;padding:10px;border-bottom:1px solid #e8eef4}
th{color:#536780}.flag{color:#a33828;background:#fff1ec}.muted{color:#64758a}code,pre{font:13px ui-monospace,monospace}
.source{overflow:auto;white-space:pre;padding:16px;background:#152538;color:#dce9f5;border-radius:8px}
.line{display:block;min-height:1.5em}.line:target{background:#38516a}
.number{display:inline-block;width:4em;color:#8bbce0}
@media(max-width:760px){.layout{display:block}nav{width:auto}main{padding:12px}table{display:block;overflow:auto}}
"##;
