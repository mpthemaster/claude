# A tiny Forth

A Forth interpreter in 299 lines of Python, with colon definitions,
`if`/`else`/`then`, `begin` loops, counted `do` loops with `leave`,
recursion, variables and constants, `create ... does>`, execution tokens,
and 64-bit cells that wrap the way a real machine's do. It's enough to run
ordinary Forth programs. The picture below was drawn by one,
[`examples/sierpinski.fs`](examples/sierpinski.fs), which prints the SVG
one `."` at a time.

<p align="center">
  <img src="out/sierpinski.svg" width="360" alt="Sierpinski's triangle as a right triangle of blue squares, 64 squares on a side, with the corner at top left: square (x, y) is filled when x and y have no binary 1 in common.">
</p>

## Run

```sh
python projects/forth/forth.py                              # a prompt: type Forth, get " ok"
python projects/forth/forth.py projects/forth/examples/sieve.fs   # primes below 100
python projects/forth/forth.py projects/forth/examples/sierpinski.fs > projects/forth/out/sierpinski.svg
pytest projects/forth
```

```
$ printf ': sq dup * ;\n7 sq .\n: squares 0 swap 1 do i sq + loop ;\n11 squares .\n' | python projects/forth/forth.py
 ok
49  ok
 ok
385  ok
```

From Python, `Forth().interpret(text)` runs the text and returns what it
printed. An error raises `ForthError` and clears both stacks, as `abort`
would.

## How it works

Forth has almost no syntax. The outer interpreter reads one
space-delimited word at a time. If the word is in the dictionary, it runs
it. If not, it reads it as a number and pushes it. `:` switches it into
compiling mode. From then on, words are appended to the new definition
instead of being run, except for *immediate* words, which run anyway.
Every control structure is an immediate word that writes jumps into the
definition being built.

A compiled definition here is a Python list of `(op, argument)` pairs,
with ten ops: push a literal, call a word, jump, jump if zero, exit, the
three loop ops, `does>`, and print a string. One `while` loop in
`Forth.execute` runs them. Calls between Forth words push a frame on a
Python list rather than recursing in Python, so a Forth word can recurse
ten thousand deep without hitting Python's recursion limit.

Of the 105 words in the dictionary, 64 are Python and 41 are Forth, in a
prelude that the interpreter compiles when it starts. The prelude
includes `if`, `else`, `then`, `begin`, `while`, `repeat`, `until` and
`again`. These are written in Forth on top of four compiler words from
Python: `mark` (where am I), `branch,` and `0branch,` (compile a jump and
leave its address on the stack), and `resolve` (point an earlier jump
here):

```forth
: if     0 0branch, ; immediate        \ a forward jump, target unknown yet
: then   resolve ; immediate           \ ... which lands here
: else   0 branch, swap resolve ; immediate
: begin  mark ; immediate
: until  0branch, drop ; immediate     \ jump back to begin while false
: while  0 0branch, swap ; immediate
: repeat branch, drop resolve ; immediate
```

Real Forths are built this way too. The compiler keeps its bookkeeping
(the addresses waiting to be filled in) on the same data stack the
program uses. That's why `;` can catch `: x if ;` with one comparison: if
the stack is deeper than it was at `:`, some jump was never resolved.

Memory is a Python list of cells. An address is an index into it, so
`cells` does nothing and `cell+` adds one. Division is floored (`-7 3 /`
is `-3`), which Forth-2012 allows and Python does already.

## Tests

The core words are tested by a harness written in this Forth, in the
`T{ ... -> ... }T` style that Forth implementations are conventionally
checked with: run what's before `->`, then check the stack holds exactly
what's after it. The harness is six lines. It needs `variable`,
`create ... allot`, `depth`, `?do`, `exit` and comparisons, so before it
can test anything it has already exercised most of the interpreter. The
pytest side checks output, errors, redefinition, both examples, and
the 300-line budget.

## What I found

- **The budget shaped the design for the better.** The first working
  version was 423 lines, with every word a Python function. The way down
  was to move words into Forth, which is how Forth is meant to be built:
  a small core in the machine's language and the rest in itself.
  `if`/`then` as five Forth words is the nicest code in the file, and
  writing them taught me more about how Forth compiles than writing them
  in Python had.
- **`do` loops are a trap.** In standard Forth, `+loop` stops when the
  index crosses the boundary between `limit - 1` and `limit`, not when
  it passes the limit. That makes `0 10 do ... -1 +loop` count down
  from 10 through 0 inclusive. But it also means a loop that starts past its
  limit runs until the index wraps all the way around. With 64-bit cells
  that's 2⁶⁴ iterations. My first sieve did this, and `strike` now checks
  `p*p < n` before looping. `?do` covers only the equal case.
- **It's slow, about a hundred times slower than Python.** Naive
  `25 fib`, 242,785 calls, takes a second; the same function in Python
  takes a hundredth of one. A million-iteration `do` loop takes a second
  and a half. Each Forth word costs a tuple unpack, an if-chain and a
  Python call, and a word like `1+` is a call into another compiled
  definition.

## The same Forth in Go

[`go/main.go`](go/main.go) is a port. It has the same words, the same
prelude (copied verbatim), the same ten ops and the same inner loop, so
the two can be compared directly. Only one design choice had to change.
A Python cell can hold a `Word` object, but a Go cell is an `int64`, so an
execution token is the word's index in a list of every word ever made.
The index is offset by 2⁴⁰ so that `5 execute` is still an error, not a
call to the sixth primitive.

```sh
cd projects/forth/go && go run . ../examples/sieve.fs
python projects/forth/bench.py      # builds the Go port and times both
```

The Python interpreter is the specification.
[`test_ports.py`](test_ports.py) feeds the same programs to the Python
and to each port, line by line as at the prompt: the whole `T{ }T` suite,
the examples, the benchmark programs at a small size, and a run of errors
that each need the interpreter to recover. It then checks that stdout,
stderr and the exit code match exactly. The test builds the Go port with
`go build`. It skips on a machine without Go, but fails in CI.

Measured on the day of the port:

| program | Python Forth | Go Forth, first port | Go Forth | ratio |
|---|---:|---:|---:|---:|
| start-up (prelude only) | 0.027 s | 0.002 s | 0.002 s | 12× |
| `27 fib` (635,621 calls) | 2.57 s | 0.161 s | 0.065 s | 39× |
| 2,000,000-iteration `do` loop | 3.04 s | 0.163 s | 0.054 s | 56× |
| sieve to 200,000 | 2.19 s | 0.128 s | 0.046 s | 48× |

Each time is the best of three whole runs, including process start.

- **The first faithful port was only 16 to 19 times faster.** A profile
  put two thirds of its time in the allocator. `pops`, a line-for-line
  translation of the Python, copied the popped cells into a new slice, so
  every `+` and every `<` allocated. Returning a view of the stack
  instead, valid until the next push, took `25 fib` from 1.3 million
  allocations to 629 and made it two and a half times faster. In Python
  the same copy cost nothing extra, because everything there allocates
  anyway. A port that keeps the source's idioms keeps their costs too,
  and those costs differ between languages.
- **The interpreter costs about the same factor in both languages.**
  Plain Go computes fib(27) in 1 ms and plain Python in 26 ms. The Go
  Forth is about 65 times slower than plain Go, and the Python Forth is
  about 100 times slower than plain Python. So the Go Forth still runs
  `fib` two and a half times slower than plain Python. Most of that gap
  is the language's, and the design costs about the same in either.
- **The port is about twice as long: 687 lines against 299.** Some of
  that is gofmt, which puts the word tables one entry per line. The rest
  is what Python did implicitly: a 64-bit wrap Go gets for free, but
  also floored division (Go truncates), arbitrary-size literals that
  have to wrap (`math/big`), and turning a runtime panic into a Forth
  error with `recover`, which is Go's nearest thing to Python's
  `except Exception`.
- **Python's quirks are part of the specification.** The first version
  passed every differential test, and then a review found eight more
  disagreements. Python's `int()` takes `1_000`, so the Forth reads it
  as a number. `-1 pick` reads the bottom of the stack because Python
  lists take negative indexes. `.r` treats a negative width as a
  positive one because Python's format spec reads the minus as a flag.
  The port now copies each of these, with a test for each. Two of the
  findings were worse than disagreements. Runaway nesting through
  `' execute execute` and a huge `allot` each killed the Go process
  outright, because Go can't recover from running out of stack or
  memory and Python can. The port now stops both itself, at limits
  close to where Python gives up. A second review, by the Codex bot on
  the pull request, found five more. One was in Unicode: names are
  case-insensitive through Python's `str.lower`, which lowers `ΟΣ` to
  `ος` with a final sigma, while Go's `strings.ToLower` gives `οσ`.
  Checking every code point showed that this context rule and `İ` are
  the only differences, so the port handles just those two. The other
  four are input and output failures: invalid UTF-8, an unprintable
  surrogate, a full disk and unreadable stdin. Python stops with a
  traceback in each case. The port had carried on, so it now fails too.

  Two differences remain. Python reads non-ASCII digits such as `٣` as
  numbers, and the port doesn't. And Go's Unicode tables are one version
  newer than Python 3.11's, which matters only for characters added in
  that version.

## The same Forth in Rust

[`rust/src/main.rs`](rust/src/main.rs) is the third version, and the
second port. It's written against the Python, like the Go, and checked
by the same tests: `test_ports.py` runs every program through both ports,
building this one with `cargo build --release`. It uses only the standard
library.

```sh
cd projects/forth/rust && cargo run --release ../examples/sieve.fs
python projects/forth/bench.py      # builds both ports and times all three
```

| program | Python Forth | Go Forth | Rust Forth | Python/Go | Python/Rust |
|---|---:|---:|---:|---:|---:|
| start-up (prelude only) | 0.019 s | 0.001 s | 0.001 s | 14× | 16× |
| `27 fib` (635,621 calls) | 1.76 s | 0.044 s | 0.021 s | 40× | 85× |
| 2,000,000-iteration `do` loop | 2.11 s | 0.036 s | 0.021 s | 58× | 101× |
| sieve to 200,000 | 1.54 s | 0.029 s | 0.018 s | 53× | 87× |

These were measured on a different machine from the Go table above, the
same day as each other, with Python 3.11.

- **Rust didn't need a profile.** The first version that passed the
  tests is the one in the table: 85 to 100 times faster than the Python,
  and twice as fast as the Go after the Go's fix. Go's slow first port
  came from `pops` copying cells into a new slice. The Rust equivalent,
  returning a slice of the stack and then pushing onto the stack, doesn't
  compile, because the slice borrows the stack. So `pop2` returns the two
  cells as a tuple, a copy in registers that costs nothing. Go's
  fix was the same view of the stack, with a comment saying it's valid
  only until the next push. In Rust the compiler enforces that rule, so
  the cheap version was also the obvious one.
- **Why it's twice as fast as the Go.** A CPU profile of the Go port puts
  a third of its time in `push`, which takes `...int64` and appends with
  a `memmove` on every word. Rust's `Vec::push` writes one cell. The size
  of an instruction isn't the reason: padding Rust's 16-byte `Instr` out to
  Go's 48 bytes changed nothing measurable.
- **The Rust Forth runs `fib` about as fast as plain Python.** Plain Rust
  computes fib(27) in 0.4 ms, so the Rust Forth is about 50 times slower
  than its host language. The Go Forth is about 65 times slower than
  plain Go, and the Python Forth about 90 to 100 times slower than plain
  Python. The interpreter's design costs a similar factor in each, and
  the faster the host, the smaller that factor.
- **Words and code live in arenas.** In Python and Go, a word that
  `does>` made shares its defining word's code list by reference. Here
  every word is an index into one `Vec<Word>`, and every compiled
  definition an index into one `Vec<Vec<Instr>>`, so an instruction holds
  plain numbers and is `Copy`. The inner loop copies each instruction out
  and then borrows the interpreter mutably, with no reference counting.
  An execution token is the word's index offset by 2⁴⁰, as in Go.
- **The Unicode came free.** Go needed 40 lines to copy Python's
  `str.lower`. Rust's `to_lowercase` already lowers `İ` to `i̇` and
  applies the final-sigma rule. Checking every code point against Python
  3.11 found 307 that differ, either alone or beside a Σ. Of those, 305
  are characters added after Python 3.11's Unicode 14, since Rust 1.97 is
  on Unicode 17. The other two are old characters whose properties
  changed in the meantime: `ʕ` stopped being a cased letter, and an Ahom
  consonant sign became case-ignorable. Whitespace agrees everywhere once
  U+001C to U+001F are added, as in Go.
- **It's 792 lines, the longest of the three.** rustfmt leaves the word
  tables alone, so they keep a word to a line, as in the Python. The length is in the error paths.
  Every word returns a `Result`, and 35 lines mention Python, most of
  them to give the message Python would.

### What a random program found

The Go port's review found eight differences, then the bot found five
more, all in programs nobody had thought to write. So this time I also
fed all three interpreters random lines drawn from the dictionary, with
a few numbers and names mixed in, and compared the results. That took a
throwaway script and a few minutes. Within 400 programs it had found:

- **An unterminated `."`, `.(` or `(` at the end of a line.** Python's
  parser leaves its position one past the end of the text, and Python's
  `re` treats that as the end. The Rust port panicked on the slice, and
  the Go port turned its panic into a bogus error. This one would have
  shown up at a real prompt the first time someone forgot a closing
  quote.
- **`;` with no definition open, and `]` followed by any word.** Python
  says `'NoneType' object has no attribute 'depth'` (or `'code'`). The
  Go port said `invalid memory address or nil pointer dereference`, and
  after a stray `]` it crashed at exit.
- **`loop` with no `do`**, taking whatever was on the stack as the `do`'s
  address. Python fails when it reads the `do`'s argument; Go checked
  nothing and compiled the loop anyway, and treated a negative address
  as out of range where Python counts from the end.

All of these are fixed in both ports, with a case for each in
`test_ports.py`, which now also runs 300 seeded random programs through
each port on every push. Also fixed in Go: Python reads files with universal
newlines, and `5 execute` now gives Python's message. 20,000 more random
programs then found nothing else, apart from one known difference: a
Python execution token is a `Word` object, so `' dup 1+` is a
`TypeError` there and a number in the ports. Writing the fuzzer also
showed that the tests had a blind spot of their own. They captured the
ports' output with `text=True`, which turns `\r\n` into `\n` before
comparing it, so the newline difference in files couldn't fail them.
They compare bytes now.

Differences left: non-ASCII digits, as in Go; Unicode versions; and a
second file that can't be read, where Python reads every file before
running any and Go runs the first one anyway.

## Not here

Strings in memory (`s"`, `type`), `postpone`, number bases other than
decimal and `0x`, `key`, floating point, and a byte-addressed memory.
None of them would be hard. The 300-line budget is what keeps them out.
