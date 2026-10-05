# A tiny Forth

A Forth interpreter in 297 lines of Python, with colon definitions,
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

## Not here

Strings in memory (`s"`, `type`), `postpone`, number bases other than
decimal and `0x`, `key`, floating point, and a byte-addressed memory.
None of them would be hard. The 300-line budget is what keeps them out.
