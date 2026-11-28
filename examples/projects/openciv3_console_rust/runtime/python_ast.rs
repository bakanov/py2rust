//! A bounded, flat projection of Python statements; no code is executed.
use crate::{Json, Result};
use ruff_python_ast::visitor::source_order::{self, SourceOrderVisitor};
use ruff_python_ast::{self as ast, Stmt, StringFlags};
use ruff_python_parser::{lexer, Mode, ParseOptions, Token, TokenKind as K};
use ruff_text_size::{Ranged, TextRange};
use serde_json::json;

struct Projection<'a> {
    source: &'a str,
    tokens: &'a [Token],
    lines: Vec<usize>,
    rows: Vec<Json>,
}
impl<'a> Projection<'a> {
    fn new(source: &'a str, tokens: &'a [Token]) -> Self {
        let mut lines = vec![0];
        lines.extend(
            source
                .bytes()
                .enumerate()
                .filter_map(|(i, b)| (b == b'\n').then_some(i + 1)),
        );
        Self {
            source,
            tokens,
            lines,
            rows: Vec::new(),
        }
    }
    fn position(&self, offset: usize) -> (usize, usize) {
        let index = self
            .lines
            .partition_point(|start| *start <= offset)
            .saturating_sub(1);
        (index + 1, offset - self.lines[index])
    }
    fn location(&self, range: TextRange) -> Json {
        let (line, column) = self.position(range.start().to_usize());
        let (end_line, end_column) = self.position(range.end().to_usize());
        json!({"line":line,"column":column,"end_line":end_line,"end_column":end_column})
    }
    fn syntax(&self, offset: usize) -> String {
        let (line, column) = self.position(offset);
        format!("python syntax error at {line}:{column}")
    }
    fn push(
        &mut self,
        kind: &str,
        range: TextRange,
        parent: i64,
        block: &str,
        depth: usize,
    ) -> Result<usize> {
        if depth > 64 || self.rows.len() >= 4096 {
            return Err("python statement limit exceeded".into());
        }
        let mut row = self.location(range);
        let fields = row.as_object_mut().unwrap();
        fields.extend(json!({"kind":kind,"parent":parent,"block":block,"name":"","decorators":[],"names":[],"module":"","level":0,"string":null}).as_object().unwrap().clone());
        let index = self.rows.len();
        self.rows.push(row);
        Ok(index)
    }
    fn definition_start(&self, name: TextRange, kind: K) -> Result<ruff_text_size::TextSize> {
        self.tokens
            .iter()
            .rev()
            .find(|token| token.range().end() <= name.start() && token.kind() == kind)
            .map(|token| token.range().start())
            .ok_or_else(|| "python definition location unavailable".into())
    }
    fn decorators(&self, values: &[ast::Decorator]) -> Json {
        Json::Array(
            values
                .iter()
                .map(|value| {
                    let mut result = self.location(value.expression.range());
                    result["text"] = json!(&self.source[value.expression.range()]);
                    result
                })
                .collect(),
        )
    }
    fn aliases(values: &[ast::Alias]) -> Json {
        Json::Array(values.iter().map(|value| json!({"name":value.name.as_str(),"asname":value.asname.as_ref().map(|name|name.as_str()).unwrap_or("")})).collect())
    }
    fn suite(&mut self, statements: &[Stmt], parent: i64, block: &str, depth: usize) -> Result<()> {
        for statement in statements {
            self.statement(statement, parent, block, depth)?;
        }
        Ok(())
    }
    fn alternatives(
        &mut self,
        clauses: &[ast::ElifElseClause],
        end: ruff_text_size::TextSize,
        parent: i64,
        depth: usize,
    ) -> Result<()> {
        if let Some((clause, rest)) = clauses.split_first() {
            if clause.test.is_some() {
                let index = self.push(
                    "If",
                    TextRange::new(clause.range.start(), end),
                    parent,
                    "orelse",
                    depth,
                )?;
                self.suite(&clause.body, index as i64, "body", depth + 1)?;
                self.alternatives(rest, end, index as i64, depth + 1)?;
            } else {
                self.suite(&clause.body, parent, "orelse", depth)?;
            }
        }
        Ok(())
    }
    fn statement(
        &mut self,
        statement: &Stmt,
        parent: i64,
        block: &str,
        depth: usize,
    ) -> Result<()> {
        let kind = match statement {
            Stmt::FunctionDef(n) => {
                if n.is_async {
                    "AsyncFunctionDef"
                } else {
                    "FunctionDef"
                }
            }
            Stmt::ClassDef(_) => "ClassDef",
            Stmt::Return(_) => "Return",
            Stmt::Delete(_) => "Delete",
            Stmt::TypeAlias(_) => "TypeAlias",
            Stmt::Assign(_) => "Assign",
            Stmt::AugAssign(_) => "AugAssign",
            Stmt::AnnAssign(_) => "AnnAssign",
            Stmt::For(n) => {
                if n.is_async {
                    "AsyncFor"
                } else {
                    "For"
                }
            }
            Stmt::While(_) => "While",
            Stmt::If(_) => "If",
            Stmt::With(n) => {
                if n.is_async {
                    "AsyncWith"
                } else {
                    "With"
                }
            }
            Stmt::Match(_) => "Match",
            Stmt::Raise(_) => "Raise",
            Stmt::Try(n) => {
                if n.is_star {
                    "TryStar"
                } else {
                    "Try"
                }
            }
            Stmt::Assert(_) => "Assert",
            Stmt::Import(_) => "Import",
            Stmt::ImportFrom(_) => "ImportFrom",
            Stmt::Global(_) => "Global",
            Stmt::Nonlocal(_) => "Nonlocal",
            Stmt::Expr(_) => "Expr",
            Stmt::Pass(_) => "Pass",
            Stmt::Break(_) => "Break",
            Stmt::Continue(_) => "Continue",
            Stmt::IpyEscapeCommand(_) => return Err("IPython syntax is unsupported".into()),
        };
        let mut range = statement.range();
        match statement {
            Stmt::FunctionDef(n) => {
                range = TextRange::new(
                    self.definition_start(
                        n.name.range,
                        if n.is_async { K::Async } else { K::Def },
                    )?,
                    range.end(),
                )
            }
            Stmt::ClassDef(n) => {
                range = TextRange::new(self.definition_start(n.name.range, K::Class)?, range.end())
            }
            _ => {}
        }
        let index = self.push(kind, range, parent, block, depth)?;
        let parent = index as i64;
        match statement {
            Stmt::FunctionDef(n) => {
                self.rows[index]["name"] = json!(n.name.as_str());
                self.rows[index]["decorators"] = self.decorators(&n.decorator_list);
                self.suite(&n.body, parent, "body", depth + 1)?;
            }
            Stmt::ClassDef(n) => {
                self.rows[index]["name"] = json!(n.name.as_str());
                self.rows[index]["decorators"] = self.decorators(&n.decorator_list);
                self.suite(&n.body, parent, "body", depth + 1)?;
            }
            Stmt::For(n) => {
                self.suite(&n.body, parent, "body", depth + 1)?;
                self.suite(&n.orelse, parent, "orelse", depth + 1)?;
            }
            Stmt::While(n) => {
                self.suite(&n.body, parent, "body", depth + 1)?;
                self.suite(&n.orelse, parent, "orelse", depth + 1)?;
            }
            Stmt::If(n) => {
                self.suite(&n.body, parent, "body", depth + 1)?;
                self.alternatives(&n.elif_else_clauses, n.range.end(), parent, depth + 1)?;
            }
            Stmt::With(n) => self.suite(&n.body, parent, "body", depth + 1)?,
            Stmt::Match(n) => {
                for (i, case) in n.cases.iter().enumerate() {
                    self.suite(&case.body, parent, &format!("cases.{i}"), depth + 1)?;
                }
            }
            Stmt::Try(n) => {
                self.suite(&n.body, parent, "body", depth + 1)?;
                for (i, handler) in n.handlers.iter().enumerate() {
                    let ast::ExceptHandler::ExceptHandler(handler) = handler;
                    self.suite(&handler.body, parent, &format!("handlers.{i}"), depth + 1)?;
                }
                self.suite(&n.orelse, parent, "orelse", depth + 1)?;
                self.suite(&n.finalbody, parent, "finalbody", depth + 1)?;
            }
            Stmt::Import(n) => self.rows[index]["names"] = Self::aliases(&n.names),
            Stmt::ImportFrom(n) => {
                self.rows[index]["names"] = Self::aliases(&n.names);
                self.rows[index]["module"] =
                    json!(n.module.as_ref().map(|value| value.as_str()).unwrap_or(""));
                self.rows[index]["level"] = json!(n.level);
            }
            Stmt::Global(n) => {
                self.rows[index]["names"] = json!(n
                    .names
                    .iter()
                    .map(|name| json!({"name":name.as_str(),"asname":""}))
                    .collect::<Vec<_>>())
            }
            Stmt::Nonlocal(n) => {
                self.rows[index]["names"] = json!(n
                    .names
                    .iter()
                    .map(|name| json!({"name":name.as_str(),"asname":""}))
                    .collect::<Vec<_>>())
            }
            Stmt::TypeAlias(n) => {
                if let ast::Expr::Name(name) = n.name.as_ref() {
                    self.rows[index]["name"] = json!(name.id.as_str());
                }
            }
            Stmt::Expr(n) => {
                if let ast::Expr::StringLiteral(value) = n.value.as_ref() {
                    self.rows[index]["string"] = json!(value.value.to_str());
                }
            }
            _ => {}
        }
        Ok(())
    }
}

fn preflight(source: &str) -> Result<()> {
    let mut lexer = lexer::lex(source, Mode::Module);
    let (mut count, mut brackets, mut indent) = (0, 0i32, 0i32);
    loop {
        let kind = lexer.next_token();
        if kind == K::EndOfFile {
            break;
        }
        if !matches!(kind, K::Comment | K::NonLogicalNewline) {
            count += 1;
        }
        match kind {
            K::Lpar | K::Lsqb | K::Lbrace => brackets += 1,
            K::Rpar | K::Rsqb | K::Rbrace => brackets -= 1,
            K::Indent => indent += 1,
            K::Dedent => indent -= 1,
            _ => {}
        }
        if count > 16384 || brackets > 128 || indent > 64 {
            return Err("python token/nesting limit exceeded".into());
        }
    }
    if let Some(error) = lexer.finish().first() {
        return Err(Projection::new(source, &[])
            .syntax(error.location().start().to_usize())
            .into());
    }
    Ok(())
}

fn scalar_escapes(source: &str, tokens: &[Token]) -> Result<()> {
    for token in tokens {
        if !matches!(token.kind(), K::String | K::FStringMiddle) {
            continue;
        }
        let prefix = token.unwrap_string_flags().prefix();
        if prefix.is_raw() || prefix.is_bytes() {
            continue;
        }
        let data = source[token.range()].as_bytes();
        let mut i = 0;
        while i < data.len() {
            if data[i] == b'\\' && i + 1 < data.len() {
                let length = match data[i + 1] {
                    b'u' => 4,
                    b'U' => 8,
                    _ => 0,
                };
                if length > 0 && i + 2 + length <= data.len() {
                    let digits = &source[token.range()][i + 2..i + 2 + length];
                    if let Ok(code) = u32::from_str_radix(digits, 16) {
                        if (0xD800..=0xDFFF).contains(&code) {
                            return Err("python strings require Unicode scalar values".into());
                        }
                    }
                }
                i += 2;
            } else {
                i += 1;
            }
        }
    }
    Ok(())
}

#[derive(Default)]
struct Complexity {
    depth: usize,
    exceeded: bool,
}
impl<'a> SourceOrderVisitor<'a> for Complexity {
    fn visit_expr(&mut self, expr: &'a ast::Expr) {
        self.depth += 1;
        if self.depth > 128 {
            self.exceeded = true;
        } else {
            source_order::walk_expr(self, expr);
        }
        self.depth -= 1;
    }
}

fn parse(source: String, compiler_syntax: bool) -> Result<Json> {
    preflight(&source)?;
    let parsed = ruff_python_parser::parse_unchecked(
        &source,
        ParseOptions::from(Mode::Module).with_target_version(ast::PythonVersion::PY312),
    );
    let positions = Projection::new(&source, &[]);
    if let Some(error) = parsed.errors().first() {
        return Err(positions.syntax(error.location.start().to_usize()).into());
    }
    if let Some(error) = parsed.unsupported_syntax_errors().first() {
        return Err(positions.syntax(error.range.start().to_usize()).into());
    }
    for token in parsed
        .tokens()
        .iter()
        .filter(|token| token.kind() == K::Name)
    {
        if !crate::python_identifiers::valid(&source[token.range()]) {
            return Err(positions.syntax(token.range().start().to_usize()).into());
        }
    }
    scalar_escapes(&source, parsed.tokens())?;
    let mut complexity = Complexity::default();
    complexity.visit_mod(parsed.syntax());
    if complexity.exceeded {
        return Err("python expression complexity limit exceeded".into());
    }
    let module = parsed
        .syntax()
        .as_module()
        .ok_or("expected a Python module")?;
    if compiler_syntax {
        return Ok(
            json!({"version":1,"body":crate::python_syntax::Syntax::new(&source, parsed.tokens()).suite(&module.body)?}),
        );
    }
    let mut projection = Projection::new(&source, parsed.tokens());
    projection.suite(&module.body, -1, "body", 1)?;
    Ok(json!({"version":1,"nodes":projection.rows}))
}

pub fn python_statement_tree(source: &str) -> Result<Json> {
    parse_worker(source, false)
}

pub fn python_syntax_tree(source: &str) -> Result<Json> {
    parse_worker(source, true)
}

fn parse_worker(source: &str, compiler_syntax: bool) -> Result<Json> {
    if source.len() > 131072 || source.contains('\0') {
        return Err("invalid Python source bytes".into());
    }
    let source = source
        .strip_prefix('\u{feff}')
        .unwrap_or(source)
        .replace("\r\n", "\n")
        .replace('\r', "\n");
    // Parsing and recursive AST destruction have a separate bounded stack; never execute source.
    std::thread::Builder::new()
        .name("python-parser".into())
        .stack_size(64 * 1024 * 1024)
        .spawn(move || parse(source, compiler_syntax))
        .map_err(|_| "cannot start Python parser worker")?
        .join()
        .map_err(|_| "Python parser worker failed")?
}
