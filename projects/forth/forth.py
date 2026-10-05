"""A tiny Forth: 64-bit integer cells, a dictionary, colon definitions and
the control words, compiled to lists of (op, argument) pairs and run by a
small loop. Most words are Python; the rest are Forth, in PRELUDE.

    python projects/forth/forth.py               # a prompt
    python projects/forth/forth.py file.fs ...   # run files, then exit
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LIT, CALL, BRANCH, ZBRANCH, EXIT, DO, LOOP, LEAVE, DOES, STR = range(10)
MASK = (1 << 64) - 1
TOKEN = re.compile(r"\s*(\S*)")


def cell(n):
    """Wrap an integer to a signed 64-bit cell."""
    n &= MASK
    return n - (1 << 64) if n >> 63 else n


class ForthError(Exception):
    pass


class Word:
    def __init__(self, name, prim=None, immediate=False):
        self.name, self.prim, self.immediate = name, prim, immediate
        self.code, self.start, self.body = [], 0, None  # body: a data address to push


class Forth:
    def __init__(self):
        self.stack, self.rstack, self.mem, self.out = [], [], [], []
        self.words: dict[str, Word] = {}
        self.text, self.pos = "", 0
        self.compiling, self.current, self.latest = False, None, None
        for table, immediate in ((PRIMITIVES, False), (IMMEDIATES, True)):
            self.words.update({name: Word(name, fn, immediate) for name, fn in table.items()})
        self.interpret(PRELUDE)

    # -- stacks and input ----------------------------------------------------
    def push(self, *values):
        self.stack.extend(values)

    def pop(self):
        return self.pops(1)[0]

    def pops(self, n):
        if len(self.stack) < n:
            raise ForthError("stack underflow")
        values = self.stack[-n:]
        del self.stack[-n:]
        return values

    def parse(self, delimiter=None):
        """The next word of input, or the text up to `delimiter`, which is consumed."""
        if delimiter is None:
            match = TOKEN.match(self.text, self.pos)
            self.pos = match.end()
            return match.group(1)
        start = self.pos + 1  # past the one space after the word that is parsing
        end = self.text.find(delimiter, start)
        end = len(self.text) if end < 0 else end
        self.pos = end + 1
        return self.text[start:end]

    def name(self):
        if not (name := self.parse().lower()):
            raise ForthError("a name was expected")
        return name

    def find(self, name):
        if (word := self.words.get(name.lower())) is None:
            raise ForthError(f"{name} ?")
        return word

    # -- the outer interpreter -----------------------------------------------
    def interpret(self, text):
        """Run `text` and return what it printed. An error clears both stacks."""
        self.text, self.pos, self.out = text, 0, []
        token = ""
        try:
            while token := self.parse():
                word = self.words.get(token.lower())
                if word is None:
                    try:
                        number = cell(int(token, 16 if token[:2].lower() == "0x" else 10))
                    except ValueError:
                        raise ForthError(f"{token} ?") from None
                    self.comma(LIT, number) if self.compiling else self.push(number)
                elif self.compiling and not word.immediate:
                    self.comma(CALL, word)
                else:
                    self.execute(word)
        except (ForthError, AttributeError, IndexError, TypeError, ValueError) as error:
            del self.stack[:], self.rstack[:]
            self.compiling, self.current = False, None
            forth_error = isinstance(error, ForthError)
            raise (error if forth_error else ForthError(f"{token}: {error}")) from None
        return "".join(self.out)

    def comma(self, op, arg=None):
        """Append an instruction to the definition being compiled; return its index."""
        if not self.compiling:
            raise ForthError("compile-only word")
        self.current.code.append((op, arg))
        return len(self.current.code) - 1

    def here(self):
        return len(self.current.code)

    def resolve(self, at, target=None):
        """Fill in the jump target of the instruction at `at` (default: here)."""
        op, _ = self.current.code[at]
        self.current.code[at] = (op, self.here() if target is None else target)

    # -- the inner interpreter -----------------------------------------------
    def execute(self, word):
        if word.prim is not None:
            return word.prim(self)
        rs, push, pop = self.rstack, self.stack.append, self.pop
        frames, code, ip = [], [(CALL, word)], 0
        while True:
            if ip >= len(code):
                if not frames:
                    return
                code, ip = frames.pop()
                continue
            op, arg = code[ip]
            ip += 1
            if op == CALL:
                if arg.prim is not None:
                    arg.prim(self)
                    continue
                if arg.body is not None:
                    push(arg.body)
                if len(frames) > 10_000:
                    raise ForthError("return stack overflow")
                frames.append((code, ip))
                code, ip = arg.code, arg.start
            elif op == LIT:
                push(arg)
            elif op == BRANCH or (op == ZBRANCH and pop() == 0):
                ip = arg
            elif op == EXIT:
                ip = len(code)
            elif op == DO:  # arg: (where the loop ends, whether this is ?do)
                index, limit = pop(), pop()
                if arg[1] and index == limit:
                    ip = arg[0]
                else:
                    rs.extend((arg[0], limit, index))
            elif op == LOOP:  # +loop: stop on crossing from limit-1 to limit
                before = rs[-1] - rs[-2]
                rs[-1] = cell(rs[-1] + (step := pop()))
                if (before < 0) == (before + step < 0):
                    ip = arg
                else:
                    del rs[-3:]
            elif op == LEAVE:
                ip = rs[-3]
                del rs[-3:]
            elif op == DOES:  # the word create just made runs the code after does>
                self.latest.code, self.latest.start = code, arg
                ip = len(code)
            elif op == STR:
                self.out.append(arg)

    # -- primitives that need more than a line -------------------------------
    def divmod(self):
        a, b = self.pops(2)
        if b == 0:
            raise ForthError("division by zero")
        q, r = divmod(a, b)  # floored, like Forth-2012's FM/MOD
        self.push(cell(r), cell(q))

    def address(self):
        if not 0 <= (a := self.pop()) < len(self.mem):
            raise ForthError(f"invalid address {a}")
        return a

    def create(self):
        self.latest = self.words[name] = Word(name := self.name())
        self.latest.body = len(self.mem)

    def colon(self):
        self.current, self.compiling = Word(self.name()), True
        self.current.depth = len(self.stack)  # the control words use the stack meanwhile

    def semicolon(self):
        if len(self.stack) != self.current.depth:
            raise ForthError(f"unbalanced control structure in {self.current.name}")
        self.comma(EXIT)
        self.words[self.current.name] = self.latest = self.current
        self.compiling, self.current = False, None

    def dot_quote(self):
        text = self.parse('"')
        self.comma(STR, text) if self.compiling else self.out.append(text)

    def plus_loop(self):
        self.comma(LOOP, (do := self.pop()) + 1)
        self.resolve(do, (self.here(), self.current.code[do][1][1]))


def binary(fn):
    """A word taking two cells. A comparison's True or False becomes -1 or 0."""
    return lambda f: f.push(cell(-r if isinstance(r := fn(*f.pops(2)), bool) else r))


def shuffle(n, picks):
    return lambda f: f.push(*map(f.pops(n).__getitem__, picks))


# fmt: off
PRIMITIVES = {
    "+": binary(lambda a, b: a + b), "-": binary(lambda a, b: a - b),
    "*": binary(lambda a, b: a * b), "/mod": Forth.divmod,
    "and": binary(lambda a, b: a & b), "or": binary(lambda a, b: a | b),
    "xor": binary(lambda a, b: a ^ b), "invert": lambda f: f.push(~f.pop()),
    "lshift": binary(lambda a, b: a << b), "rshift": binary(lambda a, b: (a & MASK) >> b),
    "=": binary(lambda a, b: a == b), "<": binary(lambda a, b: a < b),
    "u<": binary(lambda a, b: a & MASK < b & MASK),
    "dup": shuffle(1, (0, 0)), "drop": shuffle(1, ()), "swap": shuffle(2, (1, 0)),
    "over": shuffle(2, (0, 1, 0)), "rot": shuffle(3, (1, 2, 0)),
    "pick": lambda f: f.push(f.stack[-1 - f.pop()]), "depth": lambda f: f.push(len(f.stack)),
    ">r": lambda f: f.rstack.append(f.pop()), "r>": lambda f: f.push(f.rstack.pop()),
    "r@": lambda f: f.push(f.rstack[-1]), "i": lambda f: f.push(f.rstack[-1]),
    "j": lambda f: f.push(f.rstack[-4]),
    "unloop": lambda f: f.rstack.__delitem__(slice(-3, None)),
    "@": lambda f: f.push(f.mem[f.address()]),
    "!": lambda f: f.mem.__setitem__(f.address(), cell(f.pop())),
    ",": lambda f: f.mem.append(cell(f.pop())), "here": lambda f: f.push(len(f.mem)),
    "allot": lambda f: f.mem.extend([0] * f.pop()), "create": Forth.create,
    "emit": lambda f: f.out.append(chr(f.pop())), ".": lambda f: f.out.append(f"{f.pop()} "),
    ".r": lambda f: f.out.append("{0:>{1}}".format(*f.pops(2))),
    ".s": lambda f: f.out.append(f"<{len(f.stack)}> " + "".join(f"{v} " for v in f.stack)),
    "char": lambda f: f.push(ord(f.parse()[0])),
    "words": lambda f: f.out.append(" ".join(sorted(f.words)) + "\n"),
    "execute": lambda f: f.execute(f.pop()), "'": lambda f: f.push(f.find(f.parse())),
    ":": Forth.colon, "]": lambda f: setattr(f, "compiling", True),
    "immediate": lambda f: setattr(f.latest, "immediate", True),
    # the compiler words that if, else, then, begin, while and the rest are made of
    "mark": lambda f: f.push(f.here()), "resolve": lambda f: f.resolve(f.pop()),
    "branch,": lambda f: f.push(f.comma(BRANCH, f.pop())),
    "0branch,": lambda f: f.push(f.comma(ZBRANCH, f.pop())),
}
IMMEDIATES = {  # these run even while a definition is being compiled
    ";": Forth.semicolon, '."': Forth.dot_quote, ".(": lambda f: f.out.append(f.parse(")")),
    "(": lambda f: f.parse(")"), "\\": lambda f: f.parse("\n"),
    "[": lambda f: setattr(f, "compiling", False), "literal": lambda f: f.comma(LIT, f.pop()),
    "[']": lambda f: f.comma(LIT, f.find(f.parse())),
    "[char]": lambda f: f.comma(LIT, ord(f.parse()[0])),
    "recurse": lambda f: f.comma(CALL, f.current), "exit": lambda f: f.comma(EXIT),
    "does>": lambda f: f.comma(DOES, f.here() + 1),
    "do": lambda f: f.push(f.comma(DO, (None, False))),
    "?do": lambda f: f.push(f.comma(DO, (None, True))),
    "+loop": Forth.plus_loop, "loop": lambda f: (f.comma(LIT, 1), f.plus_loop()),
    "leave": lambda f: f.comma(LEAVE),
}
# fmt: on

PRELUDE = r"""
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
"""


def main(argv: list[str] | None = None) -> int:
    forth, paths = Forth(), sys.argv[1:] if argv is None else argv
    for source in [Path(path).read_text() for path in paths] if paths else sys.stdin:
        try:
            print(forth.interpret(source), end="" if paths else " ok\n")
        except ForthError as error:
            print(error, file=sys.stderr)
            if paths:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
