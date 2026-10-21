//! Error-module generator used by scaffold_errors.rs: validates a JSON spec and renders a
//! thiserror 2 enum with code(), is_retryable(), http_status(), a Result alias, an optional
//! axum IntoResponse impl and tests. Not an entry point; pulled in with `mod errgen;`.
#![allow(dead_code)]

use crate::json::Json;

pub struct Variant {
    pub name: String,
    pub fields: Vec<(String, String)>,
    pub message: String,
    pub from: Option<String>,
    pub source: Option<String>,
    pub transparent: Option<String>,
    pub retryable: bool,
    pub http: Option<u16>,
    pub code: Option<String>,
    pub doc: Option<String>,
}

pub struct Spec {
    pub lib: bool,
    pub name: String,
    pub http: bool,
    pub variants: Vec<Variant>,
}

const KEYS: &[&str] = &["name", "fields", "message", "from", "source", "transparent", "retryable", "http", "code", "doc"];
const KEYWORDS: &[&str] = &["type", "match", "fn", "struct", "enum", "impl", "mod", "ref", "loop", "move", "use", "where", "async", "await", "dyn", "box", "in", "for", "if", "else", "let", "mut", "pub", "return", "static", "trait", "unsafe", "while", "const", "crate", "extern", "true", "false"];

fn camel(s: &str) -> bool {
    s.chars().next().is_some_and(|c| c.is_ascii_uppercase()) && s.chars().all(|c| c.is_ascii_alphanumeric())
}

fn screaming(s: &str) -> String {
    let mut out = String::new();
    for (i, c) in s.chars().enumerate() {
        if c.is_ascii_uppercase() && i > 0 {
            out.push('_');
        }
        out.push(c.to_ascii_uppercase());
    }
    out
}

fn ident(name: &str) -> String {
    if KEYWORDS.contains(&name) { format!("r#{name}") } else { name.to_string() }
}

/// Named placeholders in a thiserror message (`{id}`, `{key:?}`), skipping `{{` escapes.
fn placeholders(msg: &str) -> Result<Vec<String>, String> {
    let b = msg.as_bytes();
    let (mut i, mut out) = (0, Vec::new());
    while i < b.len() {
        match b[i] {
            b'{' if b.get(i + 1) == Some(&b'{') => i += 2,
            b'{' => {
                let end = msg[i..].find('}').map(|n| i + n).ok_or("unclosed '{' in message")?;
                let name = msg[i + 1..end].split(':').next().unwrap_or("").trim().to_string();
                out.push(name);
                i = end + 1;
            }
            _ => i += 1,
        }
    }
    Ok(out)
}

fn status_for(name: &str) -> u16 {
    let has = |w: &str| name.contains(w);
    if has("NotFound") { 404 } else if has("Conflict") { 409 }
    else if has("Invalid") || has("Validation") || has("BadRequest") { 400 }
    else if has("Unauthorized") || has("Unauthenticated") { 401 }
    else if has("Forbidden") || has("PermissionDenied") { 403 }
    else if has("RateLimited") || has("TooMany") { 429 }
    else if has("Busy") || has("Unavailable") || has("Timeout") { 503 }
    else { 500 }
}

pub fn from_json(j: &Json) -> Result<Spec, String> {
    let name = j.get("name").and_then(Json::as_str).ok_or("spec needs \"name\" (e.g. \"StoreError\")")?.to_string();
    if !camel(&name) {
        return Err(format!("name '{name}' must be a CamelCase identifier"));
    }
    let lib = match j.get("crate_kind").and_then(Json::as_str).unwrap_or("lib") {
        "lib" => true,
        "app" => false,
        k => return Err(format!("crate_kind must be \"lib\" or \"app\", got '{k}'")),
    };
    let http = j.get("http").and_then(Json::as_bool).unwrap_or(false);
    let list = j.get("variants").and_then(Json::as_array).ok_or("spec needs a \"variants\" array")?;
    if list.is_empty() {
        return Err("\"variants\" is empty".into());
    }
    let mut variants: Vec<Variant> = Vec::new();
    for v in list {
        let obj = v.as_object().ok_or("each variant must be an object")?;
        if let Some((k, _)) = obj.iter().find(|(k, _)| !KEYS.contains(&k.as_str())) {
            return Err(format!("unknown variant key '{k}' (allowed: {})", KEYS.join(", ")));
        }
        let s = |k: &str| v.get(k).and_then(Json::as_str).map(str::to_string);
        let vname = s("name").ok_or("every variant needs a \"name\"")?;
        if !camel(&vname) || variants.iter().any(|x| x.name == vname) {
            return Err(format!("variant name '{vname}' must be CamelCase and unique"));
        }
        let fields: Vec<(String, String)> = v.get("fields").and_then(Json::as_object).unwrap_or(&[])
            .iter()
            .map(|(k, t)| (k.clone(), t.as_str().unwrap_or("String").to_string()))
            .collect();
        let var = Variant {
            message: s("message").unwrap_or_default(),
            from: s("from"), source: s("source"), transparent: s("transparent"),
            retryable: v.get("retryable").and_then(Json::as_bool).unwrap_or(false),
            http: v.get("http").and_then(Json::as_f64).map(|n| n as u16),
            code: s("code"), doc: s("doc"), name: vname.clone(), fields,
        };
        let err = |m: &str| Err(format!("variant {vname}: {m}"));
        if var.from.is_some() && (!var.fields.is_empty() || var.source.is_some()) {
            return err("#[from] must be the only field: drop \"fields\"/\"source\" or use \"source\" instead of \"from\"");
        }
        if var.transparent.is_some() && (!var.fields.is_empty() || var.source.is_some() || var.from.is_some()) {
            return err("\"transparent\" wraps exactly one error and takes no other fields");
        }
        if var.transparent.is_none() && var.message.is_empty() {
            return err("needs a \"message\"");
        }
        if var.http.is_some_and(|c| !(100..=599).contains(&c)) {
            return err("\"http\" must be a status code between 100 and 599");
        }
        for p in placeholders(&var.message)? {
            if p.starts_with("r#") {
                return err(&format!("write {{{}}} instead of {{{p}}} (thiserror 2 uses the unraw name)", &p[2..]));
            }
            if p == "source" || (var.from.is_some() && p == "0") {
                return err("the message must not print the source error: the report prints the chain via source()");
            }
            if p.is_empty() || p.chars().all(|c| c.is_ascii_digit()) {
                return err("use named placeholders like {id}, not {} or {0}");
            }
            if !var.fields.iter().any(|(f, _)| *f == p) {
                return err(&format!("placeholder {{{p}}} is not a field"));
            }
        }
        let wrapped = var.from.as_ref().or(var.transparent.as_ref());
        if let Some(t) = wrapped {
            if variants.iter().any(|x| x.from.as_ref().or(x.transparent.as_ref()) == Some(t)) {
                return err(&format!("a second #[from] {t}: two From impls for the same type conflict"));
            }
        }
        variants.push(var);
    }
    Ok(Spec { lib, name, http, variants })
}

fn pattern(v: &Variant) -> String {
    match () {
        _ if v.from.is_some() || v.transparent.is_some() => format!("Self::{}(..)", v.name),
        _ if v.fields.is_empty() && v.source.is_none() => format!("Self::{}", v.name),
        _ => format!("Self::{} {{ .. }}", v.name),
    }
}

pub fn render(spec: &Spec) -> String {
    let n = &spec.name;
    let app_http = spec.http && !spec.lib;
    let mut deps = vec!["thiserror = \"2\""];
    if app_http {
        deps.extend(["axum = \"0.8\"", "serde_json = \"1\"", "tracing = \"0.1\""]);
    }
    let mut o = format!("//! Error type generated by scaffold_errors (rust-error-handling-thiserror-anyhow-designer).\n//! Cargo.toml: {}\n\n", deps.join(", "));
    o += &format!("/// Errors returned by this {}.\n#[derive(Debug, thiserror::Error)]\n", if spec.lib { "crate" } else { "application" });
    if spec.lib {
        o += "#[non_exhaustive]\n";
    }
    o += &format!("pub enum {n} {{\n");
    for v in &spec.variants {
        if let Some(d) = &v.doc {
            o += &format!("    /// {d}\n");
        }
        if let Some(t) = &v.transparent {
            o += &format!("    #[error(transparent)]\n    {}(#[from] {t}),\n", v.name);
            continue;
        }
        o += &format!("    #[error(\"{}\")]\n", v.message.replace('\\', "\\\\").replace('"', "\\\""));
        if let Some(t) = &v.from {
            o += &format!("    {}(#[from] {t}),\n", v.name);
        } else if v.fields.is_empty() && v.source.is_none() {
            o += &format!("    {},\n", v.name);
        } else {
            o += &format!("    {} {{\n", v.name);
            for (f, t) in &v.fields {
                o += &format!("        {}: {t},\n", ident(f));
            }
            if let Some(t) = &v.source {
                o += &format!("        #[source]\n        source: {t},\n");
            }
            o += "    },\n";
        }
    }
    o += "}\n\n";
    o += &format!("/// Result alias: `Result<T>` in this crate, `Result<T, OtherError>` when needed.\npub type Result<T, E = {n}> = std::result::Result<T, E>;\n\n");

    let arms = |f: &dyn Fn(&Variant) -> String| -> String {
        spec.variants.iter().map(|v| format!("            {} => {},\n", pattern(v), f(v))).collect()
    };
    o += &format!("impl {n} {{\n");
    o += "    /// Stable machine-readable code for logs, metrics and API responses.\n";
    o += "    pub fn code(&self) -> &'static str {\n        match self {\n";
    o += &arms(&|v| format!("\"{}\"", v.code.clone().unwrap_or_else(|| screaming(&v.name))));
    o += "        }\n    }\n\n";
    o += "    /// True when retrying the same operation may succeed.\n    pub fn is_retryable(&self) -> bool {\n        match self {\n";
    for v in &spec.variants {
        let io = |t: &Option<String>| t.as_deref().is_some_and(|t| t.ends_with("io::Error"));
        let line = if v.retryable {
            format!("            {} => true,\n", pattern(v))
        } else if io(&v.from) {
            format!("            Self::{}(e) => matches!(e.kind(), std::io::ErrorKind::Interrupted | std::io::ErrorKind::TimedOut | std::io::ErrorKind::WouldBlock),\n", v.name)
        } else if io(&v.source) {
            format!("            Self::{} {{ source, .. }} => matches!(source.kind(), std::io::ErrorKind::Interrupted | std::io::ErrorKind::TimedOut | std::io::ErrorKind::WouldBlock),\n", v.name)
        } else {
            format!("            {} => false,\n", pattern(v))
        };
        o += &line;
    }
    o += "        }\n    }\n";
    if spec.http {
        o += "\n    /// HTTP status for this error at an API boundary.\n    pub fn http_status(&self) -> u16 {\n        match self {\n";
        o += &arms(&|v| v.http.unwrap_or_else(|| status_for(&v.name)).to_string());
        o += "        }\n    }\n";
    }
    o += "}\n";

    if app_http {
        o += &format!(r#"
impl axum::response::IntoResponse for {n} {{
    fn into_response(self) -> axum::response::Response {{
        let status = axum::http::StatusCode::from_u16(self.http_status())
            .unwrap_or(axum::http::StatusCode::INTERNAL_SERVER_ERROR);
        // Never leak internals: 5xx bodies are generic, the full error goes to the log once.
        let message = if status.is_server_error() {{
            tracing::error!(error = ?self, code = self.code(), "request failed");
            "internal server error".to_string()
        }} else {{
            self.to_string()
        }};
        let body = axum::Json(serde_json::json!({{ "code": self.code(), "message": message }}));
        (status, body).into_response()
    }}
}}
"#);
    }

    let codes: Vec<String> = spec.variants.iter().map(|v| format!("\"{}\"", v.code.clone().unwrap_or_else(|| screaming(&v.name)))).collect();
    o += &format!("\n#[cfg(test)]\nmod tests {{\n    use super::*;\n\n    #[test]\n    fn codes_are_unique() {{\n        let mut codes = vec![{}];\n        let n = codes.len();\n        codes.sort_unstable();\n        codes.dedup();\n        assert_eq!(codes.len(), n);\n    }}\n", codes.join(", "));
    for v in spec.variants.iter().filter(|v| v.fields.is_empty() && v.source.is_none() && v.from.is_none() && v.transparent.is_none()) {
        o += &format!("\n    #[test]\n    fn {}_message() {{\n        assert_eq!({n}::{}.to_string(), \"{}\");\n    }}\n",
                      screaming(&v.name).to_lowercase(), v.name, v.message.replace('\\', "\\\\").replace('"', "\\\""));
    }
    o += "}\n";
    o
}
