//! Small TOML reader for Cargo manifests (std only): tables, dotted and quoted keys, arrays of
//! tables, strings (basic, literal, multi-line), integers, floats, booleans, arrays and inline
//! tables. Every entry keeps its line number for findings. Not an entry point; `mod toml;`.
#![allow(dead_code)]

#[derive(Debug, Clone)]
pub enum Val {
    Str(String),
    Int(i64),
    Float(f64),
    Bool(bool),
    Arr(Vec<Val>),
    Tbl(Table),
}

#[derive(Debug, Clone, Default)]
pub struct Table {
    pub entries: Vec<(String, Val, usize)>,
    pub line: usize,
}

impl Val {
    pub fn as_str(&self) -> Option<&str> {
        if let Val::Str(s) = self { Some(s) } else { None }
    }
    pub fn as_bool(&self) -> Option<bool> {
        if let Val::Bool(b) = self { Some(*b) } else { None }
    }
    pub fn as_table(&self) -> Option<&Table> {
        if let Val::Tbl(t) = self { Some(t) } else { None }
    }
    pub fn as_array(&self) -> Option<&[Val]> {
        if let Val::Arr(a) = self { Some(a) } else { None }
    }
}

impl Table {
    pub fn get(&self, key: &str) -> Option<&Val> {
        self.entries.iter().find(|(k, _, _)| k == key).map(|(_, v, _)| v)
    }
    pub fn line_of(&self, key: &str) -> usize {
        self.entries.iter().find(|(k, _, _)| k == key).map_or(self.line, |(_, _, l)| *l)
    }
    pub fn table(&self, key: &str) -> Option<&Table> {
        self.get(key).and_then(Val::as_table)
    }
    /// Follow a dotted path of tables: `path(&["workspace", "package"])`.
    pub fn path(&self, keys: &[&str]) -> Option<&Val> {
        let (last, init) = keys.split_last()?;
        let mut t = self;
        for k in init {
            t = t.table(k)?;
        }
        t.get(last)
    }
    pub fn str_at(&self, keys: &[&str]) -> Option<&str> {
        self.path(keys).and_then(Val::as_str)
    }
    fn get_mut(&mut self, key: &str) -> Option<&mut Val> {
        self.entries.iter_mut().find(|(k, _, _)| k == key).map(|(_, v, _)| v)
    }
    /// Get or create the sub-table `key` (for headers and dotted keys).
    fn child(&mut self, key: &str, line: usize) -> Result<&mut Table, String> {
        if self.get(key).is_none() {
            self.entries.push((key.to_string(), Val::Tbl(Table { entries: vec![], line }), line));
        }
        match self.get_mut(key) {
            Some(Val::Tbl(t)) => Ok(t),
            Some(Val::Arr(a)) => match a.last_mut() {
                Some(Val::Tbl(t)) => Ok(t),
                _ => Err(format!("line {line}: `{key}` is not a table")),
            },
            _ => Err(format!("line {line}: `{key}` is not a table")),
        }
    }
}

/// Parse a whole document.
pub fn parse(text: &str) -> Result<Table, String> {
    let mut p = P { s: text.as_bytes(), i: 0, line: 1 };
    let mut root = Table { entries: vec![], line: 1 };
    let mut current: Vec<String> = Vec::new();
    loop {
        p.skip_ws_nl();
        let Some(c) = p.peek() else { break };
        if c == b'[' {
            let array = p.s.get(p.i + 1) == Some(&b'[');
            p.i += if array { 2 } else { 1 };
            let keys = p.key_path(b']')?;
            p.expect(b']')?;
            if array {
                p.expect(b']')?;
            }
            let line = p.line;
            let (last, init) = keys.split_last().ok_or(format!("line {line}: empty table header"))?;
            let mut t = &mut root;
            for k in init {
                t = t.child(k, line)?;
            }
            if array {
                match t.get_mut(last) {
                    Some(Val::Arr(a)) => a.push(Val::Tbl(Table { entries: vec![], line })),
                    None => t.entries.push((last.clone(), Val::Arr(vec![Val::Tbl(Table { entries: vec![], line })]), line)),
                    _ => return Err(format!("line {line}: `{last}` is not an array of tables")),
                }
            } else {
                t.child(last, line)?;
            }
            current = keys;
            p.end_of_line()?;
        } else {
            let line = p.line;
            let keys = p.key_path(b'=')?;
            p.skip_ws();
            p.expect(b'=')?;
            let val = p.value()?;
            let mut t = &mut root;
            for k in &current {
                t = t.child(k, line)?;
            }
            let (last, init) = keys.split_last().ok_or(format!("line {line}: empty key"))?;
            for k in init {
                t = t.child(k, line)?;
            }
            t.entries.push((last.clone(), val, line));
            p.end_of_line()?;
        }
    }
    Ok(root)
}

struct P<'a> {
    s: &'a [u8],
    i: usize,
    line: usize,
}

impl P<'_> {
    fn peek(&self) -> Option<u8> {
        self.s.get(self.i).copied()
    }
    fn err<T>(&self, what: &str) -> Result<T, String> {
        Err(format!("line {}: {what}", self.line))
    }
    fn expect(&mut self, c: u8) -> Result<(), String> {
        self.skip_ws();
        if self.peek() == Some(c) {
            self.i += 1;
            Ok(())
        } else {
            self.err(&format!("expected '{}'", c as char))
        }
    }
    fn skip_ws(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t')) {
            self.i += 1;
        }
    }
    /// Whitespace, newlines and comments.
    fn skip_ws_nl(&mut self) {
        loop {
            match self.peek() {
                Some(b' ' | b'\t' | b'\r') => self.i += 1,
                Some(b'\n') => { self.i += 1; self.line += 1; }
                Some(b'#') => while !matches!(self.peek(), None | Some(b'\n')) { self.i += 1 },
                _ => return,
            }
        }
    }
    fn end_of_line(&mut self) -> Result<(), String> {
        self.skip_ws();
        if self.peek() == Some(b'#') {
            while !matches!(self.peek(), None | Some(b'\n')) {
                self.i += 1;
            }
        }
        match self.peek() {
            None | Some(b'\n') | Some(b'\r') => Ok(()),
            _ => self.err("unexpected text after value"),
        }
    }
    /// `a.b."c d".'e'` up to (not including) `stop`.
    fn key_path(&mut self, stop: u8) -> Result<Vec<String>, String> {
        let mut keys = Vec::new();
        loop {
            self.skip_ws();
            let key = match self.peek() {
                Some(b'"') => self.basic_string()?,
                Some(b'\'') => self.literal_string()?,
                _ => {
                    let start = self.i;
                    while matches!(self.peek(), Some(c) if c.is_ascii_alphanumeric() || c == b'_' || c == b'-') {
                        self.i += 1;
                    }
                    if start == self.i {
                        return self.err("expected a key");
                    }
                    String::from_utf8_lossy(&self.s[start..self.i]).into_owned()
                }
            };
            keys.push(key);
            self.skip_ws();
            match self.peek() {
                Some(b'.') => self.i += 1,
                Some(c) if c == stop => return Ok(keys),
                _ => return self.err(&format!("expected '.' or '{}' after key", stop as char)),
            }
        }
    }
    fn value(&mut self) -> Result<Val, String> {
        self.skip_ws();
        match self.peek() {
            Some(b'"') => self.basic_string().map(Val::Str),
            Some(b'\'') => self.literal_string().map(Val::Str),
            Some(b'[') => {
                self.i += 1;
                let mut items = Vec::new();
                loop {
                    self.skip_ws_nl();
                    if self.peek() == Some(b']') {
                        self.i += 1;
                        return Ok(Val::Arr(items));
                    }
                    items.push(self.value()?);
                    self.skip_ws_nl();
                    match self.peek() {
                        Some(b',') => self.i += 1,
                        Some(b']') => {}
                        _ => return self.err("expected ',' or ']' in array"),
                    }
                }
            }
            Some(b'{') => {
                self.i += 1;
                let mut t = Table { entries: vec![], line: self.line };
                loop {
                    self.skip_ws();
                    if self.peek() == Some(b'}') {
                        self.i += 1;
                        return Ok(Val::Tbl(t));
                    }
                    let line = self.line;
                    let keys = self.key_path(b'=')?;
                    self.expect(b'=')?;
                    let val = self.value()?;
                    let (last, init) = keys.split_last().ok_or("empty key")?;
                    let mut sub = &mut t;
                    for k in init {
                        sub = sub.child(k, line)?;
                    }
                    sub.entries.push((last.clone(), val, line));
                    self.skip_ws();
                    match self.peek() {
                        Some(b',') => self.i += 1,
                        Some(b'}') => {}
                        _ => return self.err("expected ',' or '}' in inline table"),
                    }
                }
            }
            Some(b't') if self.s[self.i..].starts_with(b"true") => { self.i += 4; Ok(Val::Bool(true)) }
            Some(b'f') if self.s[self.i..].starts_with(b"false") => { self.i += 5; Ok(Val::Bool(false)) }
            Some(c) if c == b'-' || c == b'+' || c.is_ascii_digit() => {
                let start = self.i;
                while matches!(self.peek(), Some(c) if c.is_ascii_alphanumeric() || matches!(c, b'.' | b'-' | b'+' | b'_' | b':')) {
                    self.i += 1;
                }
                let text: String = String::from_utf8_lossy(&self.s[start..self.i]).replace('_', "");
                if let Ok(n) = text.parse::<i64>() {
                    Ok(Val::Int(n))
                } else if let Ok(f) = text.parse::<f64>() {
                    Ok(Val::Float(f))
                } else {
                    Ok(Val::Str(text)) // dates and other scalars: keep the text
                }
            }
            _ => self.err("expected a value"),
        }
    }
    fn basic_string(&mut self) -> Result<String, String> {
        let multi = self.s[self.i..].starts_with(b"\"\"\"");
        self.i += if multi { 3 } else { 1 };
        if multi && self.peek() == Some(b'\n') {
            self.i += 1;
            self.line += 1;
        }
        let mut out = String::new();
        loop {
            let Some(c) = self.peek() else { return self.err("unterminated string") };
            if multi && self.s[self.i..].starts_with(b"\"\"\"") {
                self.i += 3;
                return Ok(out);
            }
            self.i += 1;
            match c {
                b'"' if !multi => return Ok(out),
                b'\n' if !multi => return self.err("newline in string"),
                b'\n' => { self.line += 1; out.push('\n'); }
                b'\\' => {
                    let Some(e) = self.peek() else { return self.err("bad escape") };
                    self.i += 1;
                    match e {
                        b'n' => out.push('\n'),
                        b't' => out.push('\t'),
                        b'r' => out.push('\r'),
                        b'"' => out.push('"'),
                        b'\\' => out.push('\\'),
                        b'u' | b'U' => {
                            let n = if e == b'u' { 4 } else { 8 };
                            let hex = String::from_utf8_lossy(self.s.get(self.i..self.i + n).unwrap_or_default()).into_owned();
                            self.i += n;
                            out.push(u32::from_str_radix(&hex, 16).ok().and_then(char::from_u32).unwrap_or('\u{fffd}'));
                        }
                        b'\n' if multi => { self.line += 1; self.skip_ws_nl(); }
                        _ => return self.err("bad escape"),
                    }
                }
                _ => {
                    let start = self.i - 1;
                    let len = match c { 0..=0x7f => 1, 0xc0..=0xdf => 2, 0xe0..=0xef => 3, _ => 4 };
                    out.push_str(&String::from_utf8_lossy(&self.s[start..(start + len).min(self.s.len())]));
                    self.i = start + len;
                }
            }
        }
    }
    fn literal_string(&mut self) -> Result<String, String> {
        let multi = self.s[self.i..].starts_with(b"'''");
        self.i += if multi { 3 } else { 1 };
        let close: &[u8] = if multi { b"'''" } else { b"'" };
        let start = self.i;
        while self.i < self.s.len() && !self.s[self.i..].starts_with(close) {
            if self.s[self.i] == b'\n' {
                if !multi {
                    return self.err("newline in string");
                }
                self.line += 1;
            }
            self.i += 1;
        }
        if self.i >= self.s.len() {
            return self.err("unterminated string");
        }
        let text = String::from_utf8_lossy(&self.s[start..self.i]).into_owned();
        self.i += close.len();
        Ok(text)
    }
}
