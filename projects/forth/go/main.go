// A tiny Forth, ported from ../forth.py: the same words, the same prelude,
// the same op list and inner loop, with int64 cells that wrap by themselves.
//
//	go run .               # a prompt
//	go run . file.fs ...   # run files, then exit
package main

import (
	"bufio"
	"bytes"
	"errors"
	"fmt"
	"io"
	"math/big"
	"os"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"
)

const (
	LIT = iota
	CALL
	BRANCH
	ZBRANCH
	EXIT
	DO
	LOOP
	LEAVE
	DOES
	STR
)

// An execution token is a word's index in Forth.all, offset so that a small
// number on the stack is not mistaken for one.
const xtBase = 1 << 40

type forthError string

func (e forthError) Error() string { return string(e) }

func fail(format string, args ...any) { panic(forthError(fmt.Sprintf(format, args...))) }

// One instruction. A DO keeps where its loop ends in n and whether it is ?do in q.
type instr struct {
	op int
	n  int64
	w  *Word
	s  string
	q  bool
}

type Word struct {
	name      string
	prim      func(*Forth)
	immediate bool
	code      []instr
	start     int
	body      int64 // a data address to push, or -1
	xt        int64
	depth     int // the stack depth at :, which ; checks
}

type Forth struct {
	stack, rstack, mem []int64
	out                strings.Builder
	words              map[string]*Word
	all                []*Word
	text               []rune
	pos                int
	compiling          bool
	current, latest    *Word
	executeWord        *Word
	nesting            int // how deep execute calls itself, through execute
}

func New() *Forth {
	f := &Forth{words: map[string]*Word{}}
	for name, fn := range primitives {
		f.words[name] = f.newWord(name, fn, false)
	}
	for name, fn := range immediates {
		f.words[name] = f.newWord(name, fn, true)
	}
	f.executeWord = f.words["execute"]
	if _, err := f.Interpret(prelude); err != nil {
		panic(err)
	}
	return f
}

func (f *Forth) newWord(name string, prim func(*Forth), immediate bool) *Word {
	w := &Word{name: name, prim: prim, immediate: immediate, body: -1, xt: xtBase + int64(len(f.all))}
	f.all = append(f.all, w)
	return w
}

// -- stacks and input ------------------------------------------------------

func (f *Forth) push(values ...int64) { f.stack = append(f.stack, values...) }

func (f *Forth) pop() int64 {
	if len(f.stack) == 0 {
		fail("stack underflow")
	}
	v := f.stack[len(f.stack)-1]
	f.stack = f.stack[:len(f.stack)-1]
	return v
}

// pops returns the top n cells, which stay valid only until the next push.
// Copying them instead allocated on every arithmetic word, and that was most
// of the run time.
func (f *Forth) pops(n int) []int64 {
	if len(f.stack) < n {
		fail("stack underflow")
	}
	values := f.stack[len(f.stack)-n:]
	f.stack = f.stack[:len(f.stack)-n]
	return values
}

func (f *Forth) rpop() int64 {
	if len(f.rstack) == 0 {
		panic(errors.New("pop from empty list"))
	}
	v := f.rstack[len(f.rstack)-1]
	f.rstack = f.rstack[:len(f.rstack)-1]
	return v
}

// lower is Python's str.lower. strings.ToLower differs from it on two
// characters: İ, which Python lowers to i and a combining dot, and Σ, which
// Python lowers to final ς at the end of a word. (Go's Unicode tables are
// also a version newer, which matters only for characters new in that one.)
func lower(s string) string {
	s = strings.ReplaceAll(s, "İ", "i\u0307")
	if !strings.ContainsRune(s, 'Σ') {
		return strings.ToLower(s)
	}
	runes := []rune(s)
	lowered := []rune(strings.ToLower(s)) // rune for rune, once İ is gone
	for i, r := range runes {
		if r == 'Σ' && casedNext(runes, i, -1) && !casedNext(runes, i, 1) {
			lowered[i] = 'ς'
		}
	}
	return string(lowered)
}

// casedNext says whether the first character from i in direction step that
// isn't case-ignorable is cased, Unicode's test for a final sigma.
func casedNext(runes []rune, i, step int) bool {
	for i += step; 0 <= i && i < len(runes); i += step {
		r := runes[i]
		if !caseIgnorable(r) {
			return unicode.In(r, unicode.Lu, unicode.Ll, unicode.Lt,
				unicode.Other_Lowercase, unicode.Other_Uppercase)
		}
	}
	return false
}

func caseIgnorable(r rune) bool {
	switch r {
	case '\'', '.', ':', '^', '`', 0xB7, 0x387, 0x55F, 0x5F4, 0x2018, 0x2019,
		0x2024, 0x2027, 0xFE13, 0xFE52, 0xFE55, 0xFF07, 0xFF0E, 0xFF1A:
		return true
	}
	return unicode.In(r, unicode.Mn, unicode.Me, unicode.Cf, unicode.Lm, unicode.Sk)
}

// isSpace is Python's str.isspace, which also counts U+001C to U+001F.
func isSpace(r rune) bool { return unicode.IsSpace(r) || 0x1c <= r && r <= 0x1f }

// parse returns the next word of input, or with a delimiter the text up to
// it, which is consumed.
func (f *Forth) parse(delimiter rune) string {
	t := f.text
	f.pos = min(f.pos, len(t)) // a delimiter not found leaves pos one past the end
	if delimiter == 0 {
		for f.pos < len(t) && isSpace(t[f.pos]) {
			f.pos++
		}
		start := f.pos
		for f.pos < len(t) && !isSpace(t[f.pos]) {
			f.pos++
		}
		return string(t[start:f.pos])
	}
	// past the one space after the parsing word, unless it ends the text at once
	start := f.pos
	if start >= len(t) || t[start] != delimiter {
		start++
	}
	start = min(start, len(t))
	end := start
	for end < len(t) && t[end] != delimiter {
		end++
	}
	f.pos = end + 1
	return string(t[start:end])
}

func (f *Forth) name() string {
	name := lower(f.parse(0))
	if name == "" {
		fail("a name was expected")
	}
	return name
}

func (f *Forth) find(name string) *Word {
	w, ok := f.words[lower(name)]
	if !ok {
		fail("%s ?", name)
	}
	return w
}

func (f *Forth) token(xt int64) *Word {
	if xt < xtBase || xt-xtBase >= int64(len(f.all)) {
		panic(errors.New("'int' object has no attribute 'prim'")) // as Python's says it
	}
	return f.all[xt-xtBase]
}

// The literals Python's int() takes: single underscores between digits, and
// at most 4300 decimal digits. Python also takes non-ASCII digits; this doesn't.
var (
	decimal = regexp.MustCompile(`^[+-]?[0-9]+(_[0-9]+)*$`)
	hex     = regexp.MustCompile(`^0[xX](_?[0-9a-fA-F]+)+$`)
)

// number reads a token as a decimal or 0x number, wrapped to a cell.
func number(token string) (int64, bool) {
	digits, base := strings.ReplaceAll(token, "_", ""), 10
	if hex.MatchString(token) {
		digits, base = digits[2:], 16
	} else if !decimal.MatchString(token) || len(strings.TrimLeft(digits, "+-")) > 4300 {
		return 0, false
	}
	n, ok := new(big.Int).SetString(digits, base)
	if !ok {
		return 0, false
	}
	return int64(new(big.Int).And(n, new(big.Int).SetUint64(^uint64(0))).Uint64()), true
}

// -- the outer interpreter -------------------------------------------------

// Interpret runs text and returns what it printed. An error clears both stacks.
func (f *Forth) Interpret(text string) (output string, err error) {
	f.text, f.pos = []rune(text), 0
	f.out.Reset()
	token := ""
	defer func() {
		if r := recover(); r != nil {
			f.stack, f.rstack = f.stack[:0], f.rstack[:0]
			f.compiling, f.current, f.nesting = false, nil, 0
			if e, ok := r.(forthError); ok {
				err = e
			} else { // a Go error inside a word is a Forth error too
				if e, ok := r.(runtime.Error); ok && strings.Contains(e.Error(), "index out of range") {
					r = "list index out of range" // as Python says it, for i or r@ outside a loop
				} else if ok && strings.Contains(e.Error(), "nil pointer") {
					r = "'NoneType' object has no attribute 'code'" // f.current, after ]
				}
				err = forthError(fmt.Sprintf("%s: %v", token, r))
			}
		}
	}()
	for token = f.parse(0); token != ""; token = f.parse(0) {
		word, ok := f.words[lower(token)]
		switch {
		case !ok:
			n, isNumber := number(token)
			if !isNumber {
				fail("%s ?", token)
			}
			if f.compiling {
				f.comma(instr{op: LIT, n: n})
			} else {
				f.push(n)
			}
		case f.compiling && !word.immediate:
			f.comma(instr{op: CALL, w: word})
		default:
			f.execute(word)
		}
	}
	return f.out.String(), nil
}

// comma appends an instruction to the definition being compiled and returns its index.
func (f *Forth) comma(in instr) int64 {
	if !f.compiling {
		fail("compile-only word")
	}
	f.current.code = append(f.current.code, in)
	return int64(len(f.current.code) - 1)
}

// -- the inner interpreter -------------------------------------------------

type frame struct {
	code []instr
	ip   int
}

func (f *Forth) execute(word *Word) {
	// Only `' execute execute` and the like nest here, but Go can't recover
	// from running out of stack, so stop where Python would.
	if f.nesting++; f.nesting > 900 {
		panic(errors.New("maximum recursion depth exceeded"))
	}
	defer func() { f.nesting-- }()
	if word.prim != nil {
		word.prim(f)
		return
	}
	var frames []frame
	code, ip := []instr{{op: CALL, w: word}}, 0
	for {
		if ip >= len(code) {
			if len(frames) == 0 {
				return
			}
			top := frames[len(frames)-1]
			frames = frames[:len(frames)-1]
			code, ip = top.code, top.ip
			continue
		}
		in := &code[ip]
		ip++
		switch in.op {
		case CALL:
			w := in.w
			if w == f.executeWord { // call the token here, not by recursing
				w = f.token(f.pop())
			}
			if w.prim != nil {
				w.prim(f)
				continue
			}
			if w.body >= 0 {
				f.push(w.body)
			}
			if len(frames) > 10_000 {
				fail("return stack overflow")
			}
			frames = append(frames, frame{code, ip})
			code, ip = w.code, w.start
		case LIT:
			f.push(in.n)
		case BRANCH:
			ip = int(in.n)
		case ZBRANCH:
			if f.pop() == 0 {
				ip = int(in.n)
			}
		case EXIT:
			ip = len(code)
		case DO:
			index, limit := f.pop(), f.pop()
			if in.q && index == limit {
				ip = int(in.n)
			} else {
				f.rstack = append(f.rstack, in.n, limit, index)
			}
		case LOOP: // +loop: stop on crossing from limit-1 to limit
			rs := f.rstack
			before := uint64(rs[len(rs)-1] - rs[len(rs)-2]) // index - limit, unsigned
			step := f.pop()
			rs[len(rs)-1] += step
			var crossed bool
			if step >= 0 {
				crossed = before+uint64(step) < before
			} else {
				crossed = before < uint64(-step)
			}
			if crossed {
				f.rstack = rs[:len(rs)-3]
			} else {
				ip = int(in.n)
			}
		case LEAVE:
			ip = int(f.rstack[len(f.rstack)-3])
			f.rstack = f.rstack[:len(f.rstack)-3]
		case DOES: // the word create just made runs the code after does>
			f.latest.code, f.latest.start = code, int(in.n)
			ip = len(code)
		case STR:
			f.out.WriteString(in.s)
		}
	}
}

// -- primitives that need more than a line ---------------------------------

func divmod(f *Forth) {
	ab := f.pops(2)
	a, b := ab[0], ab[1]
	if b == 0 {
		fail("division by zero")
	}
	q, r := a/b, a%b
	if r != 0 && (r < 0) != (b < 0) { // floored, like Forth-2012's FM/MOD
		q, r = q-1, r+b
	}
	f.push(r, q)
}

func (f *Forth) address() int64 {
	a := f.pop()
	if a < 0 || a >= int64(len(f.mem)) {
		fail("invalid address %d", a)
	}
	return a
}

func create(f *Forth) {
	name := f.name()
	f.latest = f.newWord(name, nil, false)
	f.latest.body = int64(len(f.mem))
	f.words[name] = f.latest
}

func colon(f *Forth) {
	f.current, f.compiling = f.newWord(f.name(), nil, false), true
	f.current.depth = len(f.stack) // the control words use the stack meanwhile
}

func semicolon(f *Forth) {
	if f.current == nil {
		panic(errors.New("'NoneType' object has no attribute 'depth'"))
	}
	if len(f.stack) != f.current.depth {
		fail("unbalanced control structure in %s", f.current.name)
	}
	f.comma(instr{op: EXIT})
	f.words[f.current.name], f.latest = f.current, f.current
	f.compiling, f.current = false, nil
}

func dotQuote(f *Forth) {
	text := f.parse('"')
	if f.compiling {
		f.comma(instr{op: STR, s: text})
	} else {
		f.out.WriteString(text)
	}
}

// pyIndex is Python's index i into a list of n, where -1 is the last.
func pyIndex(n int, i int64) int64 {
	if i < 0 {
		i += int64(n)
	}
	if i < 0 || i >= int64(n) {
		panic(errors.New("list index out of range"))
	}
	return i
}

func plusLoop(f *Forth) {
	do := f.pop()
	f.comma(instr{op: LOOP, n: do + 1})
	code := f.current.code
	do = pyIndex(len(code), do)
	switch code[do].op { // forth.py reads code[do][1][1], which only a DO's argument has
	case DO:
	case EXIT, LEAVE:
		panic(errors.New("'NoneType' object is not subscriptable"))
	case CALL:
		panic(errors.New("'Word' object is not subscriptable"))
	case STR:
		panic(errors.New("a string where a loop was expected"))
	default:
		panic(errors.New("'int' object is not subscriptable"))
	}
	code[do].n = int64(len(code))
}

func doLoop(q bool) func(*Forth) {
	return func(f *Forth) { f.push(f.comma(instr{op: DO, q: q})) }
}

func flag(b bool) int64 {
	if b {
		return -1
	}
	return 0
}

// binary makes a word taking two cells.
func binary(fn func(a, b int64) int64) func(*Forth) {
	return func(f *Forth) { ab := f.pops(2); f.push(fn(ab[0], ab[1])) }
}

func shuffle(n int, picks ...int) func(*Forth) {
	return func(f *Forth) {
		var v [3]int64 // a copy, since pushing overwrites what pops returned
		copy(v[:], f.pops(n))
		for _, p := range picks {
			f.push(v[p])
		}
	}
}

func shift(b int64) uint {
	if b < 0 {
		panic(errors.New("negative shift count"))
	}
	return uint(min(b, 64))
}

func firstChar(s string) int64 {
	for _, r := range s {
		return int64(r)
	}
	panic(errors.New("string index out of range"))
}

var primitives map[string]func(*Forth)
var immediates map[string]func(*Forth)

func init() { // in init, because some primitives refer to the tables
	primitives = map[string]func(*Forth){
		"+": binary(func(a, b int64) int64 { return a + b }),
		"-": binary(func(a, b int64) int64 { return a - b }),
		"*": binary(func(a, b int64) int64 { return a * b }), "/mod": divmod,
		"and":    binary(func(a, b int64) int64 { return a & b }),
		"or":     binary(func(a, b int64) int64 { return a | b }),
		"xor":    binary(func(a, b int64) int64 { return a ^ b }),
		"invert": func(f *Forth) { f.push(^f.pop()) },
		"lshift": binary(func(a, b int64) int64 { return a << shift(b) }),
		"rshift": binary(func(a, b int64) int64 { return int64(uint64(a) >> shift(b)) }),
		"u<":     binary(func(a, b int64) int64 { return flag(uint64(a) < uint64(b)) }),
		"=":      binary(func(a, b int64) int64 { return flag(a == b) }),
		"<":      binary(func(a, b int64) int64 { return flag(a < b) }),
		"dup":    shuffle(1, 0, 0), "drop": shuffle(1), "swap": shuffle(2, 1, 0),
		"over": shuffle(2, 0, 1, 0), "rot": shuffle(3, 1, 2, 0),
		"pick": func(f *Forth) { // stack[-1 - n], with Python's negative indexing
			i := -1 - f.pop()
			if i < 0 {
				i += int64(len(f.stack))
			}
			if i < 0 || i >= int64(len(f.stack)) {
				panic(errors.New("list index out of range"))
			}
			f.push(f.stack[i])
		},
		"depth":  func(f *Forth) { f.push(int64(len(f.stack))) },
		">r":     func(f *Forth) { f.rstack = append(f.rstack, f.pop()) },
		"r>":     func(f *Forth) { f.push(f.rpop()) },
		"r@":     func(f *Forth) { f.push(f.rstack[len(f.rstack)-1]) },
		"i":      func(f *Forth) { f.push(f.rstack[len(f.rstack)-1]) },
		"j":      func(f *Forth) { f.push(f.rstack[len(f.rstack)-4]) },
		"unloop": func(f *Forth) { f.rstack = f.rstack[:max(len(f.rstack)-3, 0)] },
		"@":      func(f *Forth) { f.push(f.mem[f.address()]) },
		"!":      func(f *Forth) { a := f.address(); f.mem[a] = f.pop() },
		",":      func(f *Forth) { f.mem = append(f.mem, f.pop()) },
		"here":   func(f *Forth) { f.push(int64(len(f.mem))) },
		"allot": func(f *Forth) {
			n := f.pop()
			if n > 1<<28-int64(len(f.mem)) { // a Go program can't recover from running out of memory
				panic(errors.New("out of memory"))
			}
			if n > 0 {
				f.mem = append(f.mem, make([]int64, n)...)
			}
		},
		"create": create,
		"emit": func(f *Forth) {
			if n := f.pop(); n < 0 || n > unicode.MaxRune {
				panic(errors.New("chr() arg not in range(0x110000)"))
			} else if 0xD800 <= n && n <= 0xDFFF { // Python can't print these either
				panic(errors.New("surrogates not allowed"))
			} else {
				f.out.WriteRune(rune(n))
			}
		},
		".": func(f *Forth) { fmt.Fprintf(&f.out, "%d ", f.pop()) },
		".r": func(f *Forth) { // Python's "{0:>{1}}" reads the sign of the width as a flag
			v := f.pops(2)
			s := strconv.FormatInt(v[0], 10)
			width := max(v[1], -v[1])
			pad := width - int64(len(s))
			if pad > 1<<28 { // as with allot, Go can't recover from running out of memory
				panic(errors.New("out of memory"))
			}
			if pad > 0 {
				f.out.WriteString(strings.Repeat(" ", int(pad)))
			}
			f.out.WriteString(s)
		},
		".s": func(f *Forth) {
			fmt.Fprintf(&f.out, "<%d> ", len(f.stack))
			for _, v := range f.stack {
				fmt.Fprintf(&f.out, "%d ", v)
			}
		},
		"char": func(f *Forth) { f.push(firstChar(f.parse(0))) },
		"words": func(f *Forth) {
			names := make([]string, 0, len(f.words))
			for name := range f.words {
				names = append(names, name)
			}
			sort.Strings(names)
			f.out.WriteString(strings.Join(names, " ") + "\n")
		},
		"execute":   func(f *Forth) { f.execute(f.token(f.pop())) },
		"'":         func(f *Forth) { f.push(f.find(f.parse(0)).xt) },
		":":         colon,
		"]":         func(f *Forth) { f.compiling = true },
		"immediate": func(f *Forth) { f.latest.immediate = true },
		// the compiler words that if, else, then, begin, while and the rest are made of
		"mark": func(f *Forth) { f.push(int64(len(f.current.code))) },
		"resolve": func(f *Forth) {
			at := f.pop()
			f.current.code[pyIndex(len(f.current.code), at)].n = int64(len(f.current.code))
		},
		"branch,":  func(f *Forth) { f.push(f.comma(instr{op: BRANCH, n: f.pop()})) },
		"0branch,": func(f *Forth) { f.push(f.comma(instr{op: ZBRANCH, n: f.pop()})) },
	}
	immediates = map[string]func(*Forth){ // these run even while a definition is being compiled
		";": semicolon, `."`: dotQuote,
		".(":      func(f *Forth) { f.out.WriteString(f.parse(')')) },
		"(":       func(f *Forth) { f.parse(')') },
		`\`:       func(f *Forth) { f.parse('\n') },
		"[":       func(f *Forth) { f.compiling = false },
		"literal": func(f *Forth) { f.comma(instr{op: LIT, n: f.pop()}) },
		"[']":     func(f *Forth) { f.comma(instr{op: LIT, n: f.find(f.parse(0)).xt}) },
		"[char]":  func(f *Forth) { f.comma(instr{op: LIT, n: firstChar(f.parse(0))}) },
		"recurse": func(f *Forth) { f.comma(instr{op: CALL, w: f.current}) },
		"exit":    func(f *Forth) { f.comma(instr{op: EXIT}) },
		"does>":   func(f *Forth) { f.comma(instr{op: DOES, n: int64(len(f.current.code) + 1)}) },
		"do":      doLoop(false), "?do": doLoop(true), "+loop": plusLoop,
		"loop":  func(f *Forth) { f.comma(instr{op: LIT, n: 1}); plusLoop(f) },
		"leave": func(f *Forth) { f.comma(instr{op: LEAVE}) },
	}
}

const prelude = `
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
`

func main() {
	f, paths, failed := New(), os.Args[1:], false
	out := bufio.NewWriter(os.Stdout)
	report := func(err error) {
		fmt.Fprintln(os.Stderr, err)
		failed = true
	}
	flush := func() {
		if err := out.Flush(); err != nil { // the output is lost, so stop
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	run := func(source []byte, after string) {
		if !utf8.Valid(source) {
			report(errors.New("the input is not valid UTF-8"))
			return
		}
		text, err := f.Interpret(string(source))
		if err != nil {
			flush()
			report(err)
			return
		}
		out.WriteString(text + after)
	}
	if len(paths) > 0 {
		for _, path := range paths {
			if source, err := os.ReadFile(path); err != nil {
				report(err)
			} else { // Python reads a file with universal newlines
				source = bytes.ReplaceAll(source, []byte("\r\n"), []byte("\n"))
				run(bytes.ReplaceAll(source, []byte("\r"), []byte("\n")), "")
			}
		}
	} else {
		in := bufio.NewReader(os.Stdin)
		for {
			line, err := in.ReadBytes('\n')
			if len(line) > 0 {
				run(line, " ok\n")
				flush()
			}
			if err != nil {
				if err != io.EOF {
					report(err)
				}
				break
			}
		}
	}
	flush()
	if f.compiling && f.current == nil { // after ], where Python stops with a traceback
		fmt.Fprintln(os.Stderr, "'NoneType' object has no attribute 'name'")
		os.Exit(1)
	}
	if f.compiling {
		fmt.Fprintf(os.Stderr, "%s: unfinished definition\n", f.current.name)
	}
	if failed || f.compiling {
		os.Exit(1)
	}
}
