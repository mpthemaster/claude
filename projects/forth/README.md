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
- **The port was about twice as long: 687 lines against 299.** Some of
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

| program | Python Forth | Go Forth | Rust Forth, first port | Rust Forth | Python/Go | Python/Rust |
|---|---:|---:|---:|---:|---:|---:|
| start-up (prelude only) | 0.019 s | 0.001 s | 0.001 s | 0.001 s | 14× | 16× |
| `27 fib` (635,621 calls) | 1.78 s | 0.045 s | 0.021 s | 0.023 s | 40× | 79× |
| 2,000,000-iteration `do` loop | 2.09 s | 0.037 s | 0.021 s | 0.025 s | 56× | 84× |
| sieve to 200,000 | 1.51 s | 0.030 s | 0.018 s | 0.021 s | 52× | 74× |

These were measured on a different machine from the Go table above, the
same day as each other, with Python 3.11.

- **Rust didn't need a profile.** The first version that passed the
  tests was 85 to 100 times faster than the Python, and twice as fast as
  the Go after the Go's fix. (A later version gave up some of that to
  copy Python's jumps exactly, and the Rust's second pass won it back.) Go's slow first port
  came from `pops` copying cells into a new slice. The Rust equivalent,
  returning a slice of the stack and then pushing onto the stack, doesn't
  compile, because the slice borrows the stack. So `pop2` returns the two
  cells as a tuple, a copy in registers that costs nothing. Go's
  fix was the same view of the stack, with a comment saying it's valid
  only until the next push. In Rust the compiler enforces that rule, so
  the cheap version was also the obvious one.
- **Why it was faster than the Go.** A CPU profile of the Go port put
  a third of its time in `push`, which took `...int64` and appended with
  a `memmove` on every word. Rust's `Vec::push` writes one cell. The
  next section closes most of that gap. The size
  of an instruction isn't the reason: padding Rust's 16-byte `Instr` out to
  Go's 48 bytes changed nothing measurable.
- **The Rust Forth runs `fib` about as fast as plain Python.** Plain Rust
  computes fib(27) in 0.4 ms, so the Rust Forth is about 55 times slower
  than its host language. The Go Forth was then about 65 times slower than
  plain Go (about 37 after the second pass below), and the Python Forth about 90 to 100 times slower than plain
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
- **It's 846 lines, the longest of the three.** rustfmt leaves the word
  tables alone, so they keep a word to a line, as in the Python. The length is in the error paths.
  Every word returns a `Result`, and 41 lines mention Python, most of
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

Then the reviewer agent, working by hand, found what the fuzzer's
vocabulary couldn't reach. `then` will resolve anything, not only a
jump, and in Python that replaces the argument of a call, a `do` or a
string with a number. The call then fails with `'int' object has no
attribute 'prim'`, and the string makes `"".join` fail with a traceback
once the line is done. The Rust port had panicked or called whichever
word had that number. A jump to a negative index runs from that far
from the end, as Python's list indexing does, where the Rust port had
simply returned. The Rust port now copies all of these. That took a
signed instruction pointer, which I measured then as costing about 15%
on the benchmarks (the Rust's second pass below measures it again). I kept it, since the point of the port is to be exact. The Go port
copies them too now; see below.

Differences left:

- non-ASCII digits, in both ports;
- Unicode versions;
- how deep `execute` can nest through itself, since Python's limit
  depends on how deep its own stack already is (about 495 from the
  prompt, fewer under pytest), and the ports stop at 900;
- invalid UTF-8 on stdin. Python reads it with surrogateescape, which
  depends on the locale, and the ports report the line and carry on.

## Go, second pass

The Rust port showed the Go one could be twice as fast, and a profile
said where to look. Then the Go caught up with what the Rust had learned
about odd jumps.

| program | Go Forth before | Go Forth | Rust Forth |
|---|---:|---:|---:|
| `27 fib` (635,621 calls) | 0.049 s | 0.028 s | 0.024 s |
| 2,000,000-iteration `do` loop | 0.037 s | 0.031 s | 0.025 s |
| sieve to 200,000 | 0.030 s | 0.023 s | 0.021 s |

Best of three runs on one machine, the same day, through `bench.py`.

- **Three changes, each found by profiling the last.** `push` now takes
  one cell. A variadic call builds a slice and `append` copies it with a
  `memmove`, and that took `fib` from 49 ms to 36. Next in the profile
  were the stack words. They went through a general `shuffle` that
  copied cells out with `copy` and pushed them back one at a time.
  Writing `dup`, `swap`, `over` and `rot` out, with a two-cell `pop2`
  and `push2`, took it to 30. Last, each arithmetic word was a closure
  calling another closure (`binary(func(a, b) { return a + b })`), so
  every `+` was two indirect calls. Writing them out took the `do` loop
  from 34 ms to 29. The Go is now 10 to 25% slower than the Rust, where
  it was twice as slow. All three changes made the code more like the Rust's,
  not more clever: one cell at a time, no helper in the middle.
- **`pop2` replaced `pops`,** the view of the stack that was only valid
  until the next push. Two `int64`s now come back by value, so the
  comment warning about that rule went too. It's the shape the borrow
  checker had pushed the Rust into.
- **Now the Go Forth costs less over its host than the Rust does.**
  Measured today, plain Go computes fib(27) in 0.72 ms and plain Rust in
  0.37 ms. That puts the Go Forth at about 37 times slower than plain
  Go, and the Rust Forth at about 60 times slower than plain Rust. So the
  gap left between the two Forths is smaller than the gap between the
  two compilers on plain code. The earlier note that "the faster the
  host, the smaller that factor" no longer holds; the factor depends on
  how the interpreter was written, which is the duller and more likely
  explanation.
- **Negative jumps cost 4% on `fib`.** The Rust port paid 15% for a signed
  instruction pointer. In Go, one unsigned comparison,
  `uint(ip) < uint(len(code))`, checks both ends at once, and only the
  slow path asks whether the jump went past the end or below zero. The
  Rust does the same now; see the next section.
- **The rest of the Rust's exactness came over too.** `then` resolved
  onto a call, a `do` or a string now spoils it the way Python does, and a
  file that can't be read stops the run before any file has run, as
  `forth.py` reads them all first. 5,000 random programs found no
  further differences. The Go is 799 lines now, 54 more, mostly the
  stack words written out and the three spoiled ops.

## Rust, second pass

The Go port found a cheaper way to allow negative jumps, so the Rust took
it back. Then the Rust had its first profile.

| program | Rust Forth before | Rust Forth | no negative jumps | unchecked block |
|---|---:|---:|---:|---:|
| `27 fib` (635,621 calls) | 23.8 ms | 22.0 ms | 21.9 ms | 20.4 ms |
| 2,000,000-iteration `do` loop | 23.2 ms | 22.1 ms | 21.4 ms | 20.3 ms |
| sieve to 200,000 | 20.4 ms | 18.8 ms | 18.8 ms | 17.2 ms |

Best of fifteen runs of each binary, interleaved, on one machine the same
day. The last two columns are experiments that weren't kept.

- **One bounds check for both ends.** The loop now fetches each
  instruction with `block.get(ip as usize)`. A negative `ip` becomes a huge
  `usize`, so the one check that slice indexing does anyway also catches
  jumps below zero, and only a miss asks which end it was. That's the Go's
  `uint(ip) < uint(len(code))`, and in Rust it's shorter than the code it
  replaced, which compared twice. It saved 5 to 8%. To see what was left, I
  built a version that drops negative jumps altogether: it's within about 3% of
  the kept one, so being exact about Python's indexing now costs about
  nothing.
- **The 15% wasn't 15% here.** On this machine the signed pointer cost
  5 to 8%, not the 15% I measured when I added it. It was a different
  machine and a noisier method, so the first number was probably too high.
- **The first profile.** There's no `perf` in the container, so I counted
  instructions with valgrind's callgrind on smaller runs. Everything is
  inlined into `run`, about 53 machine instructions per Forth instruction
  on the `do` loop. The largest single cost after the dispatch itself is
  slice indexing, 15%, and most of that is fetching the current block,
  `&self.codes[c]`, again on every instruction.
- **Why that check stays.** The block can't be held across the loop,
  because a primitive gets `&mut self` and may compile into `codes`.
  `create` run from a word adds a block, and that can move the whole
  `Vec`. To measure what this costs, I built a version that read the block
  through an unchecked pointer. It was 7 to 9% faster and wrong, since the
  pointer dangles once `codes` grows. Go doesn't pay this: each word
  owns its own slice, the loop keeps the running one in a local, and the
  garbage collector keeps it valid whatever else gets compiled. In Rust
  the check is the price of reading safely from a list that can move,
  and I kept it.
- **A message fixed.** `+loop` closing onto a literal execution token, as
  in `: x ['] dup [ 0 ] +loop ;`, now says `'Word' object is not
  subscriptable` in both ports, as Python does, since Python's token is
  the `Word` itself. The ports' tokens are numbers from 2⁴⁰ up, so a
  literal in that range reads as a token. That's the same approximation
  `execute` already makes. It covers `[ ' dup ] literal` too.

## Not here

Strings in memory (`s"`, `type`), `postpone`, number bases other than
decimal and `0x`, `key`, floating point, and a byte-addressed memory.
None of them would be hard. The 300-line budget is what keeps them out.
