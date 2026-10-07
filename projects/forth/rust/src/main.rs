//! A tiny Forth, ported from ../forth.py: the same words, the same prelude,
//! the same op list and inner loop, with i64 cells that wrap when asked to.
//!
//!     cargo run --release               # a prompt
//!     cargo run --release file.fs ...   # run files, then exit

// The word tables wrap a statement in Ok(...) to keep each word to a line.
#![allow(clippy::unit_arg)]

use std::collections::HashMap;
use std::io::{self, BufRead, Write};
use std::process::ExitCode;

#[derive(Clone, Copy, PartialEq)]
enum Op {
    Lit,
    Call,
    Branch,
    ZBranch,
    Exit,
    Do,
    Loop,
    Leave,
    Does,
    Str,
    // what `resolve` leaves of a call, a do or a string: in forth.py it
    // overwrites their argument with a number, which fails when they run
    IntCall,
    IntDo,
    IntStr,
}

/// One instruction. `n` is the literal, the jump target, the word called,
/// the string printed (an index into `Forth::strings`) or where a loop ends;
/// `q` says a DO is ?do, and `resolved` that `resolve` has set `n`.
#[derive(Clone, Copy)]
struct Instr {
    op: Op,
    n: i64,
    q: bool,
    resolved: bool,
}

fn instr(op: Op, n: i64) -> Instr {
    Instr { op, n, q: false, resolved: false }
}

/// A Forth error prints as it is; a Python one (here, the message Python's
/// would have had) is prefixed with the word being interpreted, as
/// `except Exception` does in forth.py.
enum Error {
    Forth(String),
    Python(String),
}

type R<T = ()> = Result<T, Error>;
type Prim = fn(&mut Forth) -> R;

fn fail<T>(message: impl Into<String>) -> R<T> {
    Err(Error::Forth(message.into()))
}

fn python<T>(message: &str) -> R<T> {
    Err(Error::Python(message.to_string()))
}

/// An execution token is a word's index in `Forth::all`, offset so that a
/// small number on the stack is not mistaken for one.
const XT_BASE: i64 = 1 << 40;

struct Word {
    name: String,
    prim: Option<Prim>,
    immediate: bool,
    code: usize, // an index into Forth::codes; 0 is empty
    start: usize,
    body: Option<i64>, // a data address to push
    depth: usize,      // the stack depth at :, which ; checks
}

struct Forth {
    stack: Vec<i64>,
    rstack: Vec<i64>,
    mem: Vec<i64>,
    out: String,
    words: HashMap<String, usize>,
    all: Vec<Word>,
    codes: Vec<Vec<Instr>>,
    strings: Vec<String>,
    text: Vec<char>,
    pos: usize,
    compiling: bool,
    current: Option<usize>,
    latest: usize,
    execute_word: usize,
    nesting: usize,    // how deep execute calls itself, through execute
    printed_int: bool, // an IntStr ran, so forth.py's "".join(self.out) will fail
    crashed: bool,     // ... and it did, which ends forth.py with a traceback
}

impl Forth {
    fn new() -> Forth {
        let mut f = Forth {
            stack: Vec::new(),
            rstack: Vec::new(),
            mem: Vec::new(),
            out: String::new(),
            words: HashMap::new(),
            all: Vec::new(),
            codes: vec![Vec::new()],
            strings: Vec::new(),
            text: Vec::new(),
            pos: 0,
            compiling: false,
            current: None,
            latest: 0,
            execute_word: 0,
            nesting: 0,
            printed_int: false,
            crashed: false,
        };
        for (table, immediate) in [(PRIMITIVES, false), (IMMEDIATES, true)] {
            for &(name, prim) in table {
                let w = f.new_word(name.to_string(), Some(prim), immediate);
                f.words.insert(name.to_string(), w);
            }
        }
        f.execute_word = f.words["execute"];
        if f.interpret(PRELUDE).is_err() {
            panic!("the prelude failed");
        }
        f
    }

    fn new_word(&mut self, name: String, prim: Option<Prim>, immediate: bool) -> usize {
        let word = Word { name, prim, immediate, code: 0, start: 0, body: None, depth: 0 };
        self.all.push(word);
        self.all.len() - 1
    }

    // -- stacks and input ---------------------------------------------------

    fn push(&mut self, value: i64) {
        self.stack.push(value);
    }

    fn pop(&mut self) -> R<i64> {
        match self.stack.pop() {
            Some(v) => Ok(v),
            None => fail("stack underflow"),
        }
    }

    /// The top two cells, second and top. Checked before popping either,
    /// as forth.py's `pops(2)` is.
    fn pop2(&mut self) -> R<(i64, i64)> {
        if self.stack.len() < 2 {
            return fail("stack underflow");
        }
        let b = self.stack.pop().unwrap();
        Ok((self.stack.pop().unwrap(), b))
    }

    fn rget(&self, back: usize) -> R<i64> {
        match self.rstack.len().checked_sub(back) {
            Some(i) => Ok(self.rstack[i]),
            None => python("list index out of range"),
        }
    }

    fn rdrop3(&mut self) {
        self.rstack.truncate(self.rstack.len().saturating_sub(3));
    }

    /// The next word of input, or with a delimiter the text up to it, which
    /// is consumed.
    fn parse(&mut self, delimiter: Option<char>) -> String {
        let t = &self.text;
        // a delimiter not found leaves pos one past the end, where Python's re starts at the end
        self.pos = self.pos.min(t.len());
        let Some(d) = delimiter else {
            while self.pos < t.len() && is_space(t[self.pos]) {
                self.pos += 1;
            }
            let start = self.pos;
            while self.pos < t.len() && !is_space(t[self.pos]) {
                self.pos += 1;
            }
            return t[start..self.pos].iter().collect();
        };
        // past the one space after the parsing word, unless it ends the text at once
        let mut start = self.pos;
        if t.get(start) != Some(&d) {
            start += 1;
        }
        let start = start.min(t.len());
        let end = t[start..].iter().position(|&c| c == d).map_or(t.len(), |i| start + i);
        self.pos = end + 1;
        t[start..end].iter().collect()
    }

    fn name(&mut self) -> R<String> {
        let name = self.parse(None).to_lowercase();
        if name.is_empty() {
            return fail("a name was expected");
        }
        Ok(name)
    }

    fn find(&self, name: &str) -> R<usize> {
        match self.words.get(&name.to_lowercase()) {
            Some(&w) => Ok(w),
            None => fail(format!("{name} ?")),
        }
    }

    fn token(&self, xt: i64) -> R<usize> {
        if xt < XT_BASE || xt - XT_BASE >= self.all.len() as i64 {
            return python("'int' object has no attribute 'prim'");
        }
        Ok((xt - XT_BASE) as usize)
    }

    fn xt(w: usize) -> i64 {
        XT_BASE + w as i64
    }

    /// The definition being compiled, which only `]` can leave missing.
    fn current(&self) -> R<usize> {
        match self.current {
            Some(w) => Ok(w),
            None => python("'NoneType' object has no attribute 'code'"),
        }
    }

    fn code_len(&self) -> R<i64> {
        Ok(self.codes[self.all[self.current()?].code].len() as i64)
    }

    // -- the outer interpreter ----------------------------------------------

    /// Run `text` and return what it printed. An error clears both stacks.
    fn interpret(&mut self, text: &str) -> Result<String, String> {
        self.text = text.chars().collect();
        self.pos = 0;
        self.out.clear();
        self.printed_int = false;
        let mut token = String::new();
        let result = (|| -> R {
            loop {
                token = self.parse(None);
                if token.is_empty() {
                    return Ok(());
                }
                match self.words.get(&token.to_lowercase()).copied() {
                    None => {
                        let Some(n) = number(&token) else {
                            return fail(format!("{token} ?"));
                        };
                        if self.compiling {
                            self.comma(instr(Op::Lit, n))?;
                        } else {
                            self.push(n);
                        }
                    }
                    Some(w) if self.compiling && !self.all[w].immediate => {
                        self.comma(instr(Op::Call, w as i64))?;
                    }
                    Some(w) => self.execute(w)?,
                }
            }
        })();
        match result {
            Ok(()) if self.printed_int => {
                self.crashed = true;
                Err("TypeError: sequence item: expected str instance, int found".to_string())
            }
            Ok(()) => Ok(std::mem::take(&mut self.out)),
            Err(error) => {
                self.stack.clear();
                self.rstack.clear();
                self.compiling = false;
                self.current = None;
                self.nesting = 0;
                Err(match error {
                    Error::Forth(message) => message,
                    Error::Python(message) => format!("{token}: {message}"),
                })
            }
        }
    }

    /// Append an instruction to the definition being compiled; return its index.
    fn comma(&mut self, ins: Instr) -> R<i64> {
        if !self.compiling {
            return fail("compile-only word");
        }
        let block = self.all[self.current()?].code;
        let code = &mut self.codes[block];
        code.push(ins);
        Ok(code.len() as i64 - 1)
    }

    /// Point the jump at `at` (a Python index, so -1 is the last) to `target`.
    fn resolve(&mut self, at: i64, target: i64) -> R {
        let block = self.all[self.current()?].code;
        let code = &mut self.codes[block];
        let Some(i) = py_index(code.len(), at) else {
            return python("list index out of range");
        };
        let ins = &mut code[i];
        (ins.n, ins.resolved) = (target, true);
        ins.op = match ins.op {
            Op::Call => Op::IntCall,
            Op::Do => Op::IntDo,
            Op::Str => Op::IntStr,
            op => op,
        };
        Ok(())
    }

    // -- the inner interpreter ----------------------------------------------

    fn execute(&mut self, word: usize) -> R {
        // Only `' execute execute` and the like nest here, but Rust can't
        // recover from running out of stack, so stop where Python would.
        if self.nesting >= 900 {
            return python("maximum recursion depth exceeded");
        }
        self.nesting += 1;
        let result = self.run(word);
        self.nesting -= 1;
        result
    }

    fn run(&mut self, word: usize) -> R {
        if let Some(prim) = self.all[word].prim {
            return prim(self);
        }
        let entry = [instr(Op::Call, word as i64)];
        let mut frames: Vec<(usize, i64)> = Vec::new();
        // `code` is None for the one-instruction entry, else a code block.
        // ip is signed: a jump can go to a negative index, which Python
        // counts from the end.
        let (mut code, mut ip): (Option<usize>, i64) = (None, 0);
        loop {
            let block: &[Instr] = match code {
                None => &entry,
                Some(c) => &self.codes[c],
            };
            if ip >= block.len() as i64 {
                match frames.pop() {
                    None => return Ok(()),
                    Some((c, i)) => (code, ip) = (Some(c), i),
                }
                continue;
            }
            let ins = if ip >= 0 {
                block[ip as usize]
            } else {
                match py_index(block.len(), ip) {
                    Some(i) => block[i],
                    None => return python("list index out of range"),
                }
            };
            ip += 1;
            match ins.op {
                Op::Call => {
                    let mut w = ins.n as usize;
                    if w == self.execute_word {
                        // call the token here, not by recursing
                        let xt = self.pop()?;
                        w = self.token(xt)?;
                    }
                    let word = &self.all[w];
                    if let Some(prim) = word.prim {
                        prim(self)?;
                        continue;
                    }
                    let (body, next, start) = (word.body, word.code, word.start);
                    if let Some(body) = body {
                        self.push(body);
                    }
                    if frames.len() > 10_000 {
                        return fail("return stack overflow");
                    }
                    frames.push((code.unwrap_or(0), ip));
                    (code, ip) = (Some(next), start as i64);
                }
                Op::Lit => self.push(ins.n),
                Op::Branch => ip = ins.n,
                Op::ZBranch => {
                    if self.pop()? == 0 {
                        ip = ins.n;
                    }
                }
                Op::Exit => ip = i64::MAX,
                Op::Do => {
                    let index = self.pop()?;
                    let limit = self.pop()?;
                    if ins.q && index == limit {
                        ip = ins.n;
                    } else {
                        self.rstack.extend([ins.n, limit, index]);
                    }
                }
                Op::Loop => {
                    // +loop: stop on crossing from limit-1 to limit
                    let index = self.rget(1)?;
                    let before = index.wrapping_sub(self.rget(2)?) as u64; // unsigned
                    let step = self.pop()?;
                    *self.rstack.last_mut().unwrap() = index.wrapping_add(step);
                    let crossed = if step >= 0 {
                        before.checked_add(step as u64).is_none()
                    } else {
                        before < step.unsigned_abs()
                    };
                    if crossed {
                        self.rdrop3();
                    } else {
                        ip = ins.n;
                    }
                }
                Op::Leave => {
                    ip = self.rget(3)?;
                    self.rdrop3();
                }
                Op::Does => {
                    // the word create just made runs the code after does>
                    let latest = &mut self.all[self.latest];
                    (latest.code, latest.start) = (code.unwrap_or(0), ins.n as usize);
                    ip = i64::MAX;
                }
                Op::Str => {
                    let s = &self.strings[ins.n as usize];
                    self.out.push_str(s);
                }
                Op::IntCall => return python("'int' object has no attribute 'prim'"),
                Op::IntDo => {
                    self.pop()?;
                    self.pop()?;
                    return python("'int' object is not subscriptable");
                }
                Op::IntStr => self.printed_int = true,
            }
        }
    }
}

/// Python's index into a list of `len`, where -1 is the last.
fn py_index(len: usize, i: i64) -> Option<usize> {
    let i = if i < 0 { i.checked_add(len as i64)? } else { i };
    (0 <= i && i < len as i64).then_some(i as usize)
}

/// Python's str.isspace, which also counts U+001C to U+001F.
fn is_space(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}

/// The literals Python's `int()` takes, wrapped to a cell: a sign, single
/// underscores between digits, and at most 4300 decimal digits; or 0x and
/// hex digits, with an underscore allowed after the x. Python also takes
/// non-ASCII digits; this doesn't.
fn number(token: &str) -> Option<i64> {
    let (base, digits) = match token.get(..2) {
        Some("0x" | "0X") => (16, &token[2..]),
        _ => (10, token.strip_prefix(['+', '-']).unwrap_or(token)),
    };
    let groups: Vec<&str> = digits.split('_').collect();
    let leading = base == 16 && groups.len() > 1 && groups[0].is_empty();
    let groups = if leading { &groups[1..] } else { &groups[..] };
    if groups.iter().any(|g| g.is_empty() || !g.chars().all(|c| c.is_digit(base))) {
        return None;
    }
    if base == 10 && groups.iter().map(|g| g.len()).sum::<usize>() > 4300 {
        return None;
    }
    let mut n: u64 = 0;
    for c in groups.concat().chars() {
        n = n.wrapping_mul(base as u64).wrapping_add(c.to_digit(base)? as u64);
    }
    Some(if token.starts_with('-') { (n as i64).wrapping_neg() } else { n as i64 })
}

// -- primitives that need more than a line ----------------------------------

fn flag(b: bool) -> i64 {
    -(b as i64)
}

fn binary(f: &mut Forth, op: fn(i64, i64) -> R<i64>) -> R {
    let (a, b) = f.pop2()?;
    let r = op(a, b)?;
    f.push(r);
    Ok(())
}

fn divmod(f: &mut Forth) -> R {
    let (a, b) = f.pop2()?;
    if b == 0 {
        return fail("division by zero");
    }
    let (mut q, mut r) = (a.wrapping_div(b), a.wrapping_rem(b));
    if r != 0 && (r < 0) != (b < 0) {
        // floored, like Forth-2012's FM/MOD
        (q, r) = (q - 1, r + b);
    }
    f.push(r);
    f.push(q);
    Ok(())
}

fn shift(b: i64) -> R<Option<u32>> {
    match b {
        ..=-1 => python("negative shift count"),
        0..=63 => Ok(Some(b as u32)),
        _ => Ok(None), // every bit shifted out
    }
}

fn address(f: &mut Forth) -> R<usize> {
    let a = f.pop()?;
    if a < 0 || a >= f.mem.len() as i64 {
        return fail(format!("invalid address {a}"));
    }
    Ok(a as usize)
}

fn pick(f: &mut Forth) -> R {
    // stack[-1 - n], with Python's negative indexing
    let n = f.pop()?;
    match n.checked_neg().and_then(|m| m.checked_sub(1)) {
        Some(i) => match py_index(f.stack.len(), i) {
            Some(i) => Ok(f.push(f.stack[i])),
            None => python("list index out of range"),
        },
        None => python("list index out of range"),
    }
}

fn allot(f: &mut Forth) -> R {
    let n = f.pop()?;
    // a Rust program can't recover from running out of memory
    if n > (1 << 28) - f.mem.len() as i64 {
        return python("out of memory");
    }
    if n > 0 {
        f.mem.resize(f.mem.len() + n as usize, 0);
    }
    Ok(())
}

fn emit(f: &mut Forth) -> R {
    let n = f.pop()?;
    if !(0..=0x10FFFF).contains(&n) {
        return python("chr() arg not in range(0x110000)");
    }
    match char::from_u32(n as u32) {
        Some(c) => Ok(f.out.push(c)),
        None => python("surrogates not allowed"), // Python can't print these either
    }
}

fn dot_r(f: &mut Forth) -> R {
    // Python's "{0:>{1}}" reads the sign of the width as a flag
    let (v, width) = f.pop2()?;
    let width = width.unsigned_abs();
    if width > 1 << 28 {
        return python("out of memory"); // as with allot
    }
    let s = format!("{v:>width$}", width = width as usize);
    f.out.push_str(&s);
    Ok(())
}

fn dot_s(f: &mut Forth) -> R {
    f.out.push_str(&format!("<{}> ", f.stack.len()));
    for v in &f.stack {
        f.out.push_str(&format!("{v} "));
    }
    Ok(())
}

fn first_char(f: &mut Forth) -> R<i64> {
    match f.parse(None).chars().next() {
        Some(c) => Ok(c as i64),
        None => python("string index out of range"),
    }
}

fn words(f: &mut Forth) -> R {
    let mut names: Vec<&str> = f.words.keys().map(String::as_str).collect();
    names.sort();
    let line = names.join(" ") + "\n";
    f.out.push_str(&line);
    Ok(())
}

fn execute(f: &mut Forth) -> R {
    let xt = f.pop()?;
    let w = f.token(xt)?;
    f.execute(w)
}

fn create(f: &mut Forth) -> R {
    let name = f.name()?;
    let w = f.new_word(name.clone(), None, false);
    f.all[w].body = Some(f.mem.len() as i64);
    f.latest = w;
    f.words.insert(name, w);
    Ok(())
}

fn colon(f: &mut Forth) -> R {
    let name = f.name()?;
    let w = f.new_word(name, None, false);
    f.codes.push(Vec::new());
    f.all[w].code = f.codes.len() - 1;
    f.all[w].depth = f.stack.len(); // the control words use the stack meanwhile
    f.current = Some(w);
    f.compiling = true;
    Ok(())
}

fn semicolon(f: &mut Forth) -> R {
    let Some(w) = f.current else {
        return python("'NoneType' object has no attribute 'depth'");
    };
    if f.stack.len() != f.all[w].depth {
        return fail(format!("unbalanced control structure in {}", f.all[w].name));
    }
    f.comma(instr(Op::Exit, 0))?;
    f.words.insert(f.all[w].name.clone(), w);
    f.latest = w;
    f.compiling = false;
    f.current = None;
    Ok(())
}

fn dot_quote(f: &mut Forth) -> R {
    let text = f.parse(Some('"'));
    if f.compiling {
        f.strings.push(text);
        f.comma(instr(Op::Str, f.strings.len() as i64 - 1))?;
    } else {
        f.out.push_str(&text);
    }
    Ok(())
}

fn do_loop(f: &mut Forth, q: bool) -> R {
    let at = f.comma(Instr { op: Op::Do, n: 0, q, resolved: false })?;
    f.push(at);
    Ok(())
}

fn plus_loop(f: &mut Forth) -> R {
    let at = f.pop()?;
    f.comma(instr(Op::Loop, at.wrapping_add(1)))?;
    let code = &f.codes[f.all[f.current()?].code];
    let Some(i) = py_index(code.len(), at) else {
        return python("list index out of range");
    };
    // forth.py reads `code[at][1][1]`: the ?do flag of a DO's argument, or
    // the second character of a string, and anything else is an error
    let ins = code[i];
    match ins.op {
        _ if ins.resolved => return python("'int' object is not subscriptable"),
        Op::Do => {}
        Op::Str if f.strings[ins.n as usize].chars().count() < 2 => {
            return python("string index out of range");
        }
        Op::Str => {} // compiles, and then can't print: the resolve below spoils it
        Op::Exit | Op::Leave => return python("'NoneType' object is not subscriptable"),
        Op::Call => return python("'Word' object is not subscriptable"),
        _ => return python("'int' object is not subscriptable"),
    }
    let end = code.len() as i64;
    if ins.op == Op::Do {
        let block = f.all[f.current()?].code;
        f.codes[block][i].n = end; // where the loop ends, not a jump
        return Ok(());
    }
    f.resolve(at, end)
}

fn branch_comma(f: &mut Forth, op: Op) -> R {
    let target = f.pop()?;
    let at = f.comma(instr(op, target))?;
    f.push(at);
    Ok(())
}

macro_rules! words {
    ($($name:expr => $body:expr),* $(,)?) => { &[$(($name, $body)),*] };
}

#[rustfmt::skip]
static PRIMITIVES: &[(&str, Prim)] = words! {
    "+" => |f| binary(f, |a, b| Ok(a.wrapping_add(b))),
    "-" => |f| binary(f, |a, b| Ok(a.wrapping_sub(b))),
    "*" => |f| binary(f, |a, b| Ok(a.wrapping_mul(b))), "/mod" => divmod,
    "and" => |f| binary(f, |a, b| Ok(a & b)), "or" => |f| binary(f, |a, b| Ok(a | b)),
    "xor" => |f| binary(f, |a, b| Ok(a ^ b)), "invert" => |f| { let a = f.pop()?; Ok(f.push(!a)) },
    "lshift" => |f| binary(f, |a, b| Ok(shift(b)?.map_or(0, |b| a << b))),
    "rshift" => |f| binary(f, |a, b| Ok(shift(b)?.map_or(0, |b| (a as u64 >> b) as i64))),
    "u<" => |f| binary(f, |a, b| Ok(flag((a as u64) < b as u64))),
    "=" => |f| binary(f, |a, b| Ok(flag(a == b))), "<" => |f| binary(f, |a, b| Ok(flag(a < b))),
    "dup" => |f| { let a = f.pop()?; f.stack.extend([a, a]); Ok(()) },
    "drop" => |f| f.pop().map(drop),
    "swap" => |f| { let (a, b) = f.pop2()?; f.stack.extend([b, a]); Ok(()) },
    "over" => |f| { let (a, b) = f.pop2()?; f.stack.extend([a, b, a]); Ok(()) },
    "rot" => |f| {
        if f.stack.len() < 3 { return fail("stack underflow"); }
        let n = f.stack.len();
        f.stack[n - 3..].rotate_left(1);
        Ok(())
    },
    "pick" => pick, "depth" => |f| Ok(f.push(f.stack.len() as i64)),
    ">r" => |f| { let a = f.pop()?; Ok(f.rstack.push(a)) },
    "r>" => |f| match f.rstack.pop() { Some(a) => Ok(f.push(a)), None => python("pop from empty list") },
    "r@" => |f| { let a = f.rget(1)?; Ok(f.push(a)) }, "i" => |f| { let a = f.rget(1)?; Ok(f.push(a)) },
    "j" => |f| { let a = f.rget(4)?; Ok(f.push(a)) },
    "unloop" => |f| Ok(f.rdrop3()),
    "@" => |f| { let a = address(f)?; Ok(f.push(f.mem[a])) },
    "!" => |f| { let a = address(f)?; f.mem[a] = f.pop()?; Ok(()) },
    "," => |f| { let a = f.pop()?; Ok(f.mem.push(a)) }, "here" => |f| Ok(f.push(f.mem.len() as i64)),
    "allot" => allot, "create" => create,
    "emit" => emit, "." => |f| { let a = f.pop()?; Ok(f.out.push_str(&format!("{a} "))) },
    ".r" => dot_r, ".s" => dot_s,
    "char" => |f| { let c = first_char(f)?; Ok(f.push(c)) },
    "words" => words,
    "execute" => execute, "'" => |f| { let name = f.parse(None); let w = f.find(&name)?; Ok(f.push(Forth::xt(w))) },
    ":" => colon, "]" => |f| Ok(f.compiling = true),
    "immediate" => |f| Ok(f.all[f.latest].immediate = true),
    // the compiler words that if, else, then, begin, while and the rest are made of
    "mark" => |f| { let n = f.code_len()?; Ok(f.push(n)) },
    "resolve" => |f| { let at = f.pop()?; let here = f.code_len()?; f.resolve(at, here) },
    "branch," => |f| branch_comma(f, Op::Branch), "0branch," => |f| branch_comma(f, Op::ZBranch),
};

#[rustfmt::skip]
static IMMEDIATES: &[(&str, Prim)] = words! { // these run even while a definition is being compiled
    ";" => semicolon, ".\"" => dot_quote,
    ".(" => |f| { let s = f.parse(Some(')')); Ok(f.out.push_str(&s)) },
    "(" => |f| Ok(drop(f.parse(Some(')')))), "\\" => |f| Ok(drop(f.parse(Some('\n')))),
    "[" => |f| Ok(f.compiling = false),
    "literal" => |f| { let n = f.pop()?; f.comma(instr(Op::Lit, n)).map(drop) },
    "[']" => |f| { let name = f.parse(None); let w = f.find(&name)?; f.comma(instr(Op::Lit, Forth::xt(w))).map(drop) },
    "[char]" => |f| { let c = first_char(f)?; f.comma(instr(Op::Lit, c)).map(drop) },
    "recurse" => |f| { let w = f.current.unwrap_or(0); f.comma(instr(Op::Call, w as i64)).map(drop) },
    "exit" => |f| f.comma(instr(Op::Exit, 0)).map(drop),
    "does>" => |f| { let n = f.code_len()? + 1; f.comma(instr(Op::Does, n)).map(drop) },
    "do" => |f| do_loop(f, false), "?do" => |f| do_loop(f, true),
    "+loop" => plus_loop, "loop" => |f| { f.comma(instr(Op::Lit, 1))?; plus_loop(f) },
    "leave" => |f| f.comma(instr(Op::Leave, 0)).map(drop),
};

const PRELUDE: &str = r#"
: if 0 0branch, ; immediate  : then resolve ; immediate  : else 0 branch, swap resolve ; immediate
: begin mark ; immediate  : until 0branch, drop ; immediate  : again branch, drop ; immediate
: while 0 0branch, swap ; immediate  : repeat branch, drop resolve ; immediate
: nip swap drop ;  : tuck swap over ;  : -rot rot rot ;  : ?dup dup if dup then ;
: 2dup over over ;  : 2drop drop drop ;  : 2swap rot >r rot r> ;  : 2over 3 pick 3 pick ;
: 0= 0 = ;  : 0< 0 < ;  : > swap < ;  : 0> 0 > ;  : <> = 0= ;  : true -1 ;  : false 0 ;
: 1+ 1 + ;  : 1- 1 - ;  : 2* 2 * ;  : / /mod nip ;  : mod /mod drop ;  : 2/ 2 / ;
: negate 0 swap - ;  : abs dup 0< if negate then ;
: min 2dup > if swap then drop ;  : max 2dup < if swap then drop ;
: cells ;  : cell+ 1+ ;  : +! dup @ rot + swap ! ;
: variable create 0 , ;  : constant create , does> @ ;
: cr 10 emit ;  : space 32 emit ;  : spaces begin dup 0> while space 1- repeat drop ;
"#;

fn main() -> ExitCode {
    let mut f = Forth::new();
    let paths: Vec<String> = std::env::args().skip(1).collect();
    let mut out = io::BufWriter::new(io::stdout().lock());
    let (mut failed, mut bad_input) = (false, false);
    // Like forth.py, stop on what Python would stop on with a traceback: a
    // file that can't be read or isn't UTF-8, output that can't be written,
    // and a string that resolve spoiled.
    let stop = |error: &dyn std::fmt::Display| -> ExitCode {
        eprintln!("{error}");
        ExitCode::FAILURE
    };
    let mut run =
        |f: &mut Forth, source: &str, after: &str, out: &mut dyn Write| -> io::Result<()> {
            match f.interpret(source) {
                Ok(text) => out.write_all((text + after).as_bytes()),
                Err(error) if f.crashed => Err(io::Error::other(error)),
                Err(error) => {
                    out.flush()?;
                    eprintln!("{error}");
                    failed = true;
                    Ok(())
                }
            }
        };
    if !paths.is_empty() {
        let mut sources = Vec::new(); // forth.py reads every file before running any
        for path in &paths {
            match std::fs::read(path).map(String::from_utf8) {
                Ok(Ok(source)) => sources.push(source.replace("\r\n", "\n").replace('\r', "\n")),
                Ok(Err(error)) => return stop(&format!("{path}: {error}")),
                Err(error) => return stop(&format!("{path}: {error}")),
            }
        }
        for source in sources {
            if let Err(error) = run(&mut f, &source, "", &mut out) {
                return stop(&error);
            }
        }
    } else {
        let mut stdin = io::stdin().lock();
        let mut line = Vec::new();
        loop {
            line.clear();
            match stdin.read_until(b'\n', &mut line) {
                Ok(0) => break,
                Ok(_) => {}
                Err(error) => return stop(&error),
            }
            let Ok(text) = std::str::from_utf8(&line) else {
                // Python's stdin would read the bytes with surrogateescape; this
                // reports the line, as the Go does, and carries on
                let _ = out.flush();
                eprintln!("the input is not valid UTF-8");
                bad_input = true;
                continue;
            };
            if let Err(error) = run(&mut f, text, " ok\n", &mut out).and_then(|_| out.flush()) {
                return stop(&error);
            }
        }
    }
    if let Err(error) = out.flush() {
        return stop(&error);
    }
    match (f.compiling, f.current) {
        (true, Some(w)) => eprintln!("{}: unfinished definition", f.all[w].name),
        (true, None) => return stop(&"'NoneType' object has no attribute 'name'"), // after ]
        _ => {}
    }
    if failed || bad_input || f.compiling {
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}
