//! Independent bounded automation parser/interpreter with exact AST and trace exports.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde::Serialize;
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, HashMap},
    path::Path,
};

#[derive(Clone, Copy, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
enum Kind {
    Name,
    Number,
    Symbol,
    End,
    Unary,
    Binary,
    Block,
    Let,
    Set,
    Emit,
    If,
    Repeat,
}
#[derive(Clone)]
struct Token {
    kind: Kind,
    text: String,
    location: String,
}
struct Node {
    kind: Kind,
    value: String,
    location: String,
    children: Vec<Node>,
    height: usize,
}
fn reserved(text: &str) -> bool {
    matches!(text, "let" | "set" | "if" | "else" | "repeat" | "emit")
}
fn letter(c: char) -> bool {
    c.is_ascii_alphabetic() || c == '_'
}
fn tokenize(source: &str) -> Result<Vec<Token>> {
    require(
        source.len() <= 32768 && !source.contains('\0'),
        "invalid program size or NUL",
    )?;
    let chars: Vec<char> = source
        .replace("\r\n", "\n")
        .replace('\r', "\n")
        .chars()
        .collect();
    let mut tokens = Vec::new();
    let (mut index, mut line, mut column) = (0, 1, 1);
    while index < chars.len() {
        let ch = chars[index];
        if matches!(ch, ' ' | '\t') {
            index += 1;
            column += 1;
            continue;
        }
        if ch == '#' {
            while index < chars.len() && chars[index] != '\n' {
                index += 1;
                column += 1;
            }
            continue;
        }
        let start = index;
        let location = format!("{line}:{column}: ");
        let kind;
        if letter(ch) || ch.is_ascii_digit() {
            kind = if letter(ch) { Kind::Name } else { Kind::Number };
            while index < chars.len()
                && (chars[index].is_ascii_digit() || (kind == Kind::Name && letter(chars[index])))
            {
                index += 1;
            }
            require(
                index - start <= if kind == Kind::Name { 64 } else { 19 },
                &format!("{location}token too long"),
            )?;
        } else {
            kind = Kind::Symbol;
            require(
                "\n;{}()+-*/%=!<>".contains(ch),
                &format!("{location}unexpected character"),
            )?;
            index += 1;
            if index < chars.len()
                && matches!(
                    (ch, chars[index]),
                    ('/', '/') | ('=', '=') | ('!', '=') | ('<', '=') | ('>', '=')
                )
            {
                index += 1;
            }
            require(
                !(index == start + 1 && matches!(ch, '/' | '!')),
                &format!("{location}unsupported operator"),
            )?;
        }
        tokens.push(Token {
            kind,
            text: chars[start..index].iter().collect(),
            location: location.clone(),
        });
        if ch == '\n' {
            line += 1;
            column = 1;
        } else {
            column += index - start;
        }
        require(
            tokens.len() <= 4096,
            &format!("{location}program exceeds 4096 tokens"),
        )?;
    }
    tokens.push(Token {
        kind: Kind::End,
        text: String::new(),
        location: format!("{line}:{column}: "),
    });
    Ok(tokens)
}
fn make(kind: Kind, value: String, location: String, children: Vec<Node>) -> Result<Node> {
    let height = children.iter().map(|n| n.height + 1).max().unwrap_or(1);
    require(height <= 64, &format!("{location}AST depth exceeds 64"))?;
    Ok(Node {
        kind,
        value,
        location,
        children,
        height,
    })
}
fn precedence(operator: &str) -> usize {
    match operator {
        "==" | "!=" | "<" | "<=" | ">" | ">=" => 10,
        "+" | "-" => 20,
        "*" | "//" | "%" => 30,
        _ => 0,
    }
}
struct Parser {
    tokens: Vec<Token>,
    position: usize,
}
impl Parser {
    fn peek(&self) -> &Token {
        self.tokens
            .get(self.position)
            .unwrap_or_else(|| self.tokens.last().unwrap())
    }
    fn expect(&self, text: &str, message: &str) -> Result<()> {
        require(
            self.peek().text == text,
            &format!("{}{message}", self.peek().location),
        )
    }
    fn expression(&mut self, minimum: usize, depth: usize) -> Result<Node> {
        let token = self.peek().clone();
        require(
            depth <= 32,
            &format!("{}expression nesting exceeds 32", token.location),
        )?;
        self.position += 1;
        let mut node = match token.kind {
            Kind::Name => {
                require(
                    !reserved(&token.text),
                    &format!("{}reserved name", token.location),
                )?;
                make(Kind::Name, token.text, token.location, vec![])?
            }
            Kind::Number => make(Kind::Number, token.text, token.location, vec![])?,
            _ => match token.text.as_str() {
                "+" | "-" => {
                    if token.text == "-" && self.peek().kind == Kind::Number {
                        let value = format!("-{}", self.peek().text);
                        self.position += 1;
                        make(Kind::Number, value, token.location, vec![])?
                    } else {
                        let child = self.expression(40, depth + 1)?;
                        make(Kind::Unary, token.text, token.location, vec![child])?
                    }
                }
                "(" => {
                    let child = self.expression(1, depth + 1)?;
                    self.expect(")", "expected closing parenthesis")?;
                    self.position += 1;
                    child
                }
                _ => return Err(format!("{}expected expression", token.location).into()),
            },
        };
        let mut compared = false;
        while precedence(&self.peek().text) >= minimum {
            let operator = self.peek().clone();
            if precedence(&operator.text) == 10 {
                require(
                    !compared,
                    &format!("{}comparison chains are unsupported", operator.location),
                )?;
                compared = true;
            }
            self.position += 1;
            let child = self.expression(precedence(&operator.text) + 1, depth + 1)?;
            node = make(
                Kind::Binary,
                operator.text,
                operator.location,
                vec![node, child],
            )?;
        }
        Ok(node)
    }
    fn block(&mut self, depth: usize, nested: bool) -> Result<Node> {
        let location = self.peek().location.clone();
        require(depth <= 16, &format!("{location}block nesting exceeds 16"))?;
        let mut nodes = Vec::new();
        while self.peek().kind != Kind::End && self.peek().text != "}" {
            if matches!(self.peek().text.as_str(), "\n" | ";") {
                self.position += 1;
                continue;
            }
            let token = self.peek().clone();
            let command = match token.text.as_str() {
                "let" => Kind::Let,
                "set" => Kind::Set,
                "emit" => Kind::Emit,
                "if" => Kind::If,
                "repeat" => Kind::Repeat,
                _ => return Err(format!("{}expected statement", token.location).into()),
            };
            self.position += 1;
            let mut name = String::new();
            if matches!(command, Kind::Let | Kind::Set) {
                let variable = self.peek();
                require(
                    variable.kind == Kind::Name && !reserved(&variable.text),
                    &format!("{}expected variable name", variable.location),
                )?;
                name = variable.text.clone();
                self.position += 1;
                self.expect("=", "expected equals sign")?;
                self.position += 1;
            }
            let mut children = vec![self.expression(1, 0)?];
            if matches!(command, Kind::If | Kind::Repeat) {
                self.expect("{", "expected opening brace")?;
                self.position += 1;
                children.push(self.block(depth + 1, true)?);
                if command == Kind::If {
                    let mut look = self.position;
                    while self.tokens[look].text == "\n" {
                        look += 1;
                    }
                    let other = if self.tokens[look].text == "else" {
                        self.position = look + 1;
                        self.expect("{", "expected opening brace")?;
                        self.position += 1;
                        self.block(depth + 1, true)?
                    } else {
                        make(Kind::Block, String::new(), token.location.clone(), vec![])?
                    };
                    children.push(other);
                }
            }
            nodes.push(make(command, name, token.location, children)?);
            require(
                matches!(self.peek().text.as_str(), "\n" | ";" | "}" | ""),
                &format!("{}expected statement separator", self.peek().location),
            )?;
        }
        if nested {
            self.expect("}", "expected closing brace")?;
            self.position += 1;
        } else {
            require(
                self.peek().kind == Kind::End,
                &format!("{}unexpected closing brace", self.peek().location),
            )?;
        }
        make(Kind::Block, String::new(), location, nodes)
    }
}
fn describe(node: &Node) -> Value {
    let mut pending = vec![(node, -1i64, 0usize)];
    let mut rows = Vec::new();
    while let Some((current, parent, child_index)) = pending.pop() {
        let number = rows.len() as i64;
        rows.push(json!({"kind":current.kind,"value":current.value,"location":current.location,"parent":parent,"child_index":child_index}));
        for (index, child) in current.children.iter().enumerate().rev() {
            pending.push((child, number, index));
        }
    }
    json!({"version":1,"nodes":rows})
}
type Frames = Vec<HashMap<String, i64>>;
fn scope_index(frames: &Frames, name: &str, location: &str) -> Result<usize> {
    frames
        .iter()
        .rposition(|frame| frame.contains_key(name))
        .ok_or_else(|| format!("{location}undefined variable: {name}").into())
}
fn evaluate(node: &Node, frames: &Frames) -> Result<i64> {
    if node.kind == Kind::Name {
        return Ok(frames[scope_index(frames, &node.value, &node.location)?][&node.value]);
    }
    let left = if matches!(node.kind, Kind::Unary | Kind::Binary) {
        i128::from(evaluate(&node.children[0], frames)?)
    } else {
        0
    };
    let right = if node.kind == Kind::Binary {
        i128::from(evaluate(&node.children[1], frames)?)
    } else {
        0
    };
    let op = node.value.as_str();
    require(
        node.kind != Kind::Binary || !matches!(op, "//" | "%") || right != 0,
        &format!("{}division by zero", node.location),
    )?;
    let overflow = || format!("{}integer outside signed 64-bit range", node.location);
    if node.kind == Kind::Number {
        return node.value.parse::<i64>().map_err(|_| overflow().into());
    }
    let value = if node.kind == Kind::Unary {
        if op == "+" {
            left
        } else {
            -left
        }
    } else {
        match op {
            "+" => left + right,
            "-" => left - right,
            "*" => left * right,
            "//" | "%" => {
                let mut quotient = left / right;
                let mut remainder = left % right;
                if remainder != 0 && (remainder < 0) != (right < 0) {
                    quotient -= 1;
                    remainder += right;
                }
                if op == "//" {
                    quotient
                } else {
                    remainder
                }
            }
            "==" => i128::from(left == right),
            "!=" => i128::from(left != right),
            "<" => i128::from(left < right),
            "<=" => i128::from(left <= right),
            ">" => i128::from(left > right),
            ">=" => i128::from(left >= right),
            _ => 0,
        }
    };
    i64::try_from(value).map_err(|_| overflow().into())
}
fn execute(
    nodes: &[Node],
    frames: &mut Frames,
    budget: usize,
    emitted: &mut Vec<i64>,
    trace: &mut Vec<Value>,
) -> (usize, String) {
    let mut steps = 0;
    for node in nodes {
        let result = (|| -> Result<Option<String>> {
            require(
                steps < budget,
                &format!("{}step budget exhausted", node.location),
            )?;
            steps += 1;
            let value = evaluate(&node.children[0], frames)?;
            let mut depth = frames.len() - 1;
            match node.kind {
                Kind::Let | Kind::Set => {
                    if node.kind == Kind::Set {
                        depth = scope_index(frames, &node.value, &node.location)?;
                    }
                    let scope = &mut frames[depth];
                    if node.kind == Kind::Let {
                        require(
                            !scope.contains_key(&node.value),
                            &format!("{}variable already declared: {}", node.location, node.value),
                        )?;
                        require(
                            scope.len() < 128,
                            &format!("{}scope exceeds 128 variables", node.location),
                        )?;
                    }
                    scope.insert(node.value.clone(), value);
                }
                Kind::Emit => emitted.push(value),
                Kind::Repeat => require(
                    value >= 0,
                    &format!("{}repeat count must be nonnegative", node.location),
                )?,
                _ => (),
            }
            trace.push(json!({"kind":node.kind,"name":node.value,"value":value,"depth":depth,"location":node.location}));
            if matches!(node.kind, Kind::If | Kind::Repeat) {
                let iterations = if node.kind == Kind::Repeat { value } else { 1 };
                let branch = if node.kind == Kind::If && value == 0 {
                    2
                } else {
                    1
                };
                for iteration in 0..iterations {
                    if node.kind == Kind::Repeat {
                        require(
                            steps < budget,
                            &format!("{}step budget exhausted", node.location),
                        )?;
                        steps += 1;
                        trace.push(json!({"kind":"iteration","value":iteration+1,"depth":frames.len(),"location":node.location}));
                    }
                    frames.push(HashMap::new());
                    let (spent, failure) = execute(
                        &node.children[branch].children,
                        frames,
                        budget - steps,
                        emitted,
                        trace,
                    );
                    frames.pop();
                    steps += spent;
                    if !failure.is_empty() {
                        return Ok(Some(failure));
                    }
                }
            }
            Ok(None)
        })();
        match result {
            Ok(Some(failure)) => return (steps, failure),
            Err(error) => {
                let failure = error.to_string();
                trace.push(json!({"kind":"error","message":failure,"location":node.location}));
                return (steps, failure);
            }
            Ok(None) => (),
        }
    }
    (steps, String::new())
}
fn run() -> Result<i32> {
    let config = Document::read(
        absolute(
            &std::env::var("AUTOMATION_CONFIG").unwrap_or("automation-job.json".into()),
            Path::new("."),
        )?,
        65536,
    )?;
    let value = rt::json_loads(std::str::from_utf8(&config.data)?)?;
    exact(&value, &["output", "program", "steps", "version"])?;
    require(integer(&value["version"])? == 1, "unsupported job version")?;
    let budget = integer(&value["steps"])?;
    require(
        (0..=10000).contains(&budget),
        "step budget must be 0..10000",
    )?;
    let base = config.path.parent().ok_or("missing parent")?;
    let output = absolute(string(&value["output"])?, base)?;
    require(
        !output.exists() && !output.is_symlink(),
        "output already exists",
    )?;
    let program = Document::read(absolute(string(&value["program"])?, base)?, 32768)?;
    let tokens = tokenize(std::str::from_utf8(&program.data)?)?;
    let tree = Parser {
        tokens,
        position: 0,
    }
    .block(0, false)?;
    let mut frames = vec![HashMap::new()];
    let mut emitted = Vec::new();
    let mut trace = Vec::new();
    let (steps, error) = execute(
        &tree.children,
        &mut frames,
        budget as usize,
        &mut emitted,
        &mut trace,
    );
    let status = if error.is_empty() { 0 } else { 1 };
    let report = json!({"version":1,"status":if status==0 {"ok"} else {"error"},"error":error,"steps":steps,"variables":frames[0],"emitted":emitted,"trace":trace});
    let ast = canonical(&describe(&tree))?;
    let report_bytes = canonical(&report)?;
    require(
        ast.len() <= 1048576 && report_bytes.len() <= 2097152,
        "result byte limit exceeded",
    )?;
    let mut files = BTreeMap::new();
    files.insert("program.auto".into(), program.data.clone());
    files.insert("ast.json".into(), ast);
    files.insert("report.json".into(), report_bytes);
    files.insert(
        "job.json".into(),
        canonical(
            &json!({"version":1,"program":"program.auto","steps":budget,"output":"replayed"}),
        )?,
    );
    program.unchanged()?;
    config.unchanged()?;
    publish_exact(&output, files, &[], "automation")?;
    println!("{}", rt::json_canonical_view(&report)?);
    Ok(status)
}
fn main() {
    match run() {
        Ok(code) => std::process::exit(code),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    }
}
