//! Compiler syntax exchange. Binding and type decisions belong to the portable frontend.
use crate::{Json, Result};
use ruff_python_ast::{self as ast, Expr, Stmt};
use ruff_python_parser::{Token, TokenKind};
use ruff_text_size::Ranged;
use serde_json::json;

pub(super) struct Syntax<'a> {
    source: &'a str,
    tokens: &'a [Token],
}
impl<'a> Syntax<'a> {
    pub(super) fn new(source: &'a str, tokens: &'a [Token]) -> Self {
        Self { source, tokens }
    }
    fn node(&self, node: &impl Ranged, mut fields: Json) -> Json {
        let offset = node.range().start().to_usize();
        let prefix = &self.source[..offset];
        fields["line"] = json!(prefix.bytes().filter(|b| *b == b'\n').count() + 1);
        fields["column"] = json!(prefix.rfind('\n').map_or(offset, |i| offset - i - 1));
        fields
    }
    fn optional(&self, value: Option<&Expr>) -> Result<Json> {
        value
            .map(|v| self.expr(v))
            .transpose()
            .map(|v| v.unwrap_or(Json::Null))
    }
    fn expressions(&self, values: &[Expr]) -> Result<Vec<Json>> {
        values.iter().map(|v| self.expr(v)).collect()
    }
    fn unsupported(&self, node: &impl Ranged) -> Box<dyn std::error::Error + Send + Sync> {
        let position = self.node(node, json!({}));
        format!(
            "unsupported compiler syntax at {}:{}",
            position["line"], position["column"]
        )
        .into()
    }
    fn keywords(&self, values: &[ast::Keyword]) -> Result<Vec<Json>> {
        values
            .iter()
            .map(|v| {
                Ok(json!({"arg":v.arg.as_ref().map(|a| a.as_str()),"value":self.expr(&v.value)?}))
            })
            .collect()
    }
    fn expr(&self, value: &Expr) -> Result<Json> {
        let fields = match value {
            Expr::Name(n) => json!({"kind":"Name","id":n.id.as_str()}),
            Expr::StringLiteral(n) => {
                json!({"kind":"Constant","tag":"str","text":n.value.to_str()})
            }
            Expr::BytesLiteral(n) => {
                json!({"kind":"Constant","tag":"bytes","text":n.value.bytes().map(|b|format!("{b:02x}")).collect::<String>()})
            }
            Expr::NumberLiteral(_) => {
                json!({"kind":"Constant","tag":"number","text":&self.source[value.range()]})
            }
            Expr::BooleanLiteral(n) => {
                json!({"kind":"Constant","tag":"bool","text":if n.value {"True"} else {"False"}})
            }
            Expr::NoneLiteral(_) => json!({"kind":"Constant","tag":"none","text":""}),
            Expr::BinOp(n) => {
                json!({"kind":"BinOp","op":format!("{:?}",n.op),"left":self.expr(&n.left)?,"right":self.expr(&n.right)?})
            }
            Expr::UnaryOp(n) => {
                json!({"kind":"UnaryOp","op":format!("{:?}",n.op),"operand":self.expr(&n.operand)?})
            }
            Expr::BoolOp(n) => {
                json!({"kind":"BoolOp","op":format!("{:?}",n.op),"values":self.expressions(&n.values)?})
            }
            Expr::Compare(n) => {
                json!({"kind":"Compare","left":self.expr(&n.left)?,"ops":n.ops.iter().map(|op|format!("{op:?}")).collect::<Vec<_>>(),"comparators":self.expressions(&n.comparators)?})
            }
            Expr::If(n) => {
                json!({"kind":"IfExp","test":self.expr(&n.test)?,"body":self.expr(&n.body)?,"orelse":self.expr(&n.orelse)?})
            }
            Expr::Call(n) => {
                json!({"kind":"Call","func":self.expr(&n.func)?,"args":self.expressions(&n.arguments.args)?,"keywords":self.keywords(&n.arguments.keywords)?})
            }
            Expr::FString(n) => {
                let mut values = Vec::new();
                for element in n.value.elements() {
                    match element {
                        ast::FStringElement::Literal(literal) => values.push(self.node(
                            element,
                            json!({"kind":"Constant","tag":"str","text":literal.value}),
                        )),
                        ast::FStringElement::Expression(expression) => {
                            if expression.format_spec.is_some() {
                                return Err(self.unsupported(value));
                            }
                            values.push(self.node(
                                element,
                                json!({
                                    "kind":"FormattedValue",
                                    "value":self.expr(&expression.expression)?,
                                    "format_spec":Json::Null,
                                    "conversion":expression.conversion as i32,
                                }),
                            ));
                        }
                    }
                }
                json!({"kind":"JoinedStr","values":values})
            }
            Expr::Attribute(n) => {
                json!({"kind":"Attribute","value":self.expr(&n.value)?,"attr":n.attr.as_str()})
            }
            Expr::Subscript(n) => {
                json!({"kind":"Subscript","value":self.expr(&n.value)?,"slice":self.expr(&n.slice)?})
            }
            Expr::Slice(n) => {
                json!({"kind":"Slice","lower":self.optional(n.lower.as_deref())?,"upper":self.optional(n.upper.as_deref())?,"step":self.optional(n.step.as_deref())?})
            }
            Expr::List(n) => json!({"kind":"List","elts":self.expressions(&n.elts)?}),
            Expr::Tuple(n) => json!({"kind":"Tuple","elts":self.expressions(&n.elts)?}),
            Expr::Set(n) => json!({"kind":"Set","elts":self.expressions(&n.elts)?}),
            Expr::Dict(n) => {
                json!({"kind":"Dict","keys":n.items.iter().map(|v|self.optional(v.key.as_ref())).collect::<Result<Vec<_>>>()?,"values":n.items.iter().map(|v|self.expr(&v.value)).collect::<Result<Vec<_>>>()?})
            }
            _ => return Err(self.unsupported(value)),
        };
        Ok(self.node(value, fields))
    }
    pub(super) fn suite(&self, values: &[Stmt]) -> Result<Vec<Json>> {
        values.iter().map(|v| self.statement(v)).collect()
    }
    fn statement(&self, value: &Stmt) -> Result<Json> {
        let fields = match value {
            Stmt::FunctionDef(n) if !n.is_async && n.type_params.is_none() => {
                let p = &n.parameters;
                if !p.posonlyargs.is_empty()
                    || !p.kwonlyargs.is_empty()
                    || p.vararg.is_some()
                    || p.kwarg.is_some()
                {
                    return Err(self.unsupported(value));
                }
                let parameters = p.args.iter().map(|v|Ok(json!({"name":v.parameter.name.as_str(),"annotation":self.optional(v.parameter.annotation.as_deref())?,"default":self.optional(v.default.as_deref())?}))).collect::<Result<Vec<_>>>()?;
                json!({"kind":"FunctionDef","name":n.name.as_str(),"parameters":parameters,"returns":self.optional(n.returns.as_deref())?,"decorators":n.decorator_list.iter().map(|v|self.expr(&v.expression)).collect::<Result<Vec<_>>>()?,"body":self.suite(&n.body)?})
            }
            Stmt::ClassDef(n) if n.type_params.is_none() => {
                json!({"kind":"ClassDef","name":n.name.as_str(),"bases":self.expressions(n.bases())?,"keywords":self.keywords(n.keywords())?,"decorators":n.decorator_list.iter().map(|v|self.expr(&v.expression)).collect::<Result<Vec<_>>>()?,"body":self.suite(&n.body)?})
            }
            Stmt::Assign(n) => {
                json!({"kind":"Assign","targets":self.expressions(&n.targets)?,"value":self.expr(&n.value)?})
            }
            Stmt::AnnAssign(n) => {
                json!({"kind":"AnnAssign","target":self.expr(&n.target)?,"annotation":self.expr(&n.annotation)?,"value":self.optional(n.value.as_deref())?})
            }
            Stmt::AugAssign(n) => {
                json!({"kind":"AugAssign","target":self.expr(&n.target)?,"op":format!("{:?}",n.op),"value":self.expr(&n.value)?})
            }
            Stmt::Return(n) => json!({"kind":"Return","value":self.optional(n.value.as_deref())?}),
            Stmt::Expr(n) => json!({"kind":"Expr","value":self.expr(&n.value)?}),
            Stmt::Assert(n) => {
                json!({"kind":"Assert","test":self.expr(&n.test)?,"msg":self.optional(n.msg.as_deref())?})
            }
            Stmt::Delete(n) => json!({"kind":"Delete","targets":self.expressions(&n.targets)?}),
            Stmt::For(n) if !n.is_async => {
                json!({"kind":"For","target":self.expr(&n.target)?,"iter":self.expr(&n.iter)?,"body":self.suite(&n.body)?,"orelse":self.suite(&n.orelse)?})
            }
            Stmt::While(n) => {
                json!({"kind":"While","test":self.expr(&n.test)?,"body":self.suite(&n.body)?,"orelse":self.suite(&n.orelse)?})
            }
            Stmt::If(n) => {
                let mut other = Vec::new();
                for clause in n.elif_else_clauses.iter().rev() {
                    if let Some(test) = &clause.test {
                        other = vec![self.node(clause, json!({"kind":"If","test":self.expr(test)?,"body":self.suite(&clause.body)?,"orelse":other}))];
                    } else {
                        other = self.suite(&clause.body)?;
                    }
                }
                json!({"kind":"If","test":self.expr(&n.test)?,"body":self.suite(&n.body)?,"orelse":other})
            }
            Stmt::Import(n) => json!({"kind":"Import","names":aliases(&n.names)}),
            Stmt::ImportFrom(n) => {
                json!({"kind":"ImportFrom","module":n.module.as_ref().map(|v|v.as_str()).unwrap_or(""),"level":n.level,"names":aliases(&n.names)})
            }
            Stmt::Pass(_) => json!({"kind":"Pass"}),
            Stmt::Break(_) => json!({"kind":"Break"}),
            Stmt::Continue(_) => json!({"kind":"Continue"}),
            _ => return Err(self.unsupported(value)),
        };
        let mut result = self.node(value, fields);
        let definition = match value {
            Stmt::FunctionDef(n) => Some((n.name.range.start(), TokenKind::Def)),
            Stmt::ClassDef(n) => Some((n.name.range.start(), TokenKind::Class)),
            _ => None,
        };
        if let Some((end, keyword)) = definition {
            let offset = self
                .tokens
                .iter()
                .rev()
                .find(|token| token.range().end() <= end && token.kind() == keyword)
                .ok_or("definition position unavailable")?
                .range()
                .start()
                .to_usize();
            let prefix = &self.source[..offset];
            result["line"] = json!(prefix.bytes().filter(|b| *b == b'\n').count() + 1);
            result["column"] = json!(prefix.rfind('\n').map_or(offset, |i| offset - i - 1));
        }
        Ok(result)
    }
}
fn aliases(values: &[ast::Alias]) -> Vec<Json> {
    values.iter().map(|v|json!({"name":v.name.as_str(),"asname":v.asname.as_ref().map(|a|a.as_str()).unwrap_or("")})).collect()
}
