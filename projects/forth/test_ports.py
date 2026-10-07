"""The Go and Rust ports are checked against the Python Forth: the same
programs, run through each, must print the same output, the same errors and
the same exit code. The Python interpreter is the specification;
test_forth.py tests it.
"""

import io
import os
import random
import shutil
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import bench
import forth
import pytest
from test_forth import CORE, TESTER

HERE = Path(__file__).parent
EXAMPLES = sorted((HERE / "examples").glob("*.fs"))
TOOLCHAINS = {"go": "go", "rust": "cargo"}


@pytest.fixture(scope="module", params=sorted(TOOLCHAINS))
def port(request, tmp_path_factory):
    # In CI a missing toolchain is a failure, not a skip.
    if shutil.which(TOOLCHAINS[request.param]) is None and not os.environ.get("CI"):
        pytest.skip(f"{TOOLCHAINS[request.param]} is not installed")
    return bench.build(request.param, tmp_path_factory.mktemp(request.param))


def python_forth(args, stdin):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out), redirect_stderr(err):
        code = forth.main(args)
    return out.getvalue(), err.getvalue(), code


def both(port, args=(), stdin=""):
    # bytes, since text=True would read the port's "\r\n" as "\n"
    done = subprocess.run([port, *args], input=stdin.encode(), capture_output=True, timeout=30)
    ported = done.stdout.decode(), done.stderr.decode(), done.returncode
    return python_forth(list(args), stdin), ported


# Each runs at the prompt, one line at a time, so output and errors interleave.
PROGRAMS = [
    TESTER + CORE,
    '1 . -2 . cr\n." hello" 32 emit .( world)\n: greet ." hi, " ." you" ; greet\n',
    "42 5 .r 7 0 .r 3 spaces\n1 2 3 .s\n",
    ": Sq dup * ; 3 SQ .\n: a 1 ; : b a ; : a 2 ; b . a .\n: c 10 ; : c c 1+ ; c .\n",
    ": counter create 0 , does> 1 over +! @ ; counter tick tick . tick . tick .\n",
    ": fib dup 2 < if exit then dup 1- recurse swap 2 - recurse + ; 20 fib .\n",
    ": deep dup 0> if 1- recurse then ; 5000 deep .\n",
    "variable xt : deep dup 0> if 1- xt @ execute then ; ' deep xt ! 5000 deep .\n",
    "variable action  ' . action !  : run action @ execute ;  7 run\n",
    ": sq dup * ; create ops ' sq , ' 1+ ,  5 ops cell+ @ execute ops @ execute .\n",
    "1 1000000000000 lshift . 1 64 lshift . 1 63 lshift 0< .\n",
    ": w 0 -9223372036854775808 9223372036854775807 do 1+ dup 3 = if leave then loop ; w .\n",
    "1 \\\n2 .\n3 . .\n",
    "-7 2 /mod . . 7 -2 /mod . . -9223372036854775808 -1 / .\n",
    "123456789012345678901234567890 . -0x8000000000000001 . 0xFFFFFFFFFFFFFFFF .\n",
    "words\n",
    ": sq\ndup * ;\n4 sq .\n",
    # errors, each followed by a line showing the interpreter recovered
    "frobnicate\n1 .\ndrop\n1 2 0 / .\n99 @\n: x if ;\nif\n:\n2 .\n",
    ": forever recurse ; forever\n1 2 3 .s\n",
    "1 2 3\n: broken 1 2 nosuchword ;\n.s broken\n",
    "1 .\n: half 2 /",
    # where Python's own behaviour leaks through, and the port copies it
    "0x-5 .\n0x+5 .\n1_000 .\n0x_ff .\n1__0 .\n1" + "0" * 5000 + " .\n2 .\n",
    "1 2 3 -1 pick . -3 pick .\n1 2 3 -4 pick\n9 pick\n2 .\n",
    "65 emit -1 emit\n1114112 emit\n5 -3 .r 1 .\n1 -1 lshift\n1 -1 rshift\nchar\n2 .\n",
    "1\x1c2 . .\n",
    "1 . 13 emit 10 emit 2 .\n",
    # names are case-insensitive the way Python's str.lower is
    "i\nr@\nr>\nj\nunloop 2 .\n",
    ": ΟΣ 7 ; ος . οσ\n: İ 1 ; i\u0307 . i\n: AΣ.B 2 ; aσ.b . aς.b\n: ẞ 3 ; ß .\n",
    # found by feeding all three random programs: a string or comment left
    # open at the end of a line, the compiler words with no definition open,
    # and a loop or jump resolved against something that isn't one
    'cr ." no closing quote\n.( nor here\n( nor here\n1 .\n',
    ";\n] 5\n] mark\nrecurse\n] recurse\n5 execute\n2 .\n",
    "true : x leave loop\n: y [ 0 ] 1 loop ;\n: z exit [ 0 ] +loop ;\n-9 : w loop\n2 .\n",
    ": w 5 [ -1 ] then ; w .\n-5 : v then\n2 .\n",
]


@pytest.mark.parametrize("stdin", PROGRAMS, ids=range(len(PROGRAMS)))
def test_the_port_matches_at_the_prompt(port, stdin):
    python, ported = both(port, stdin=stdin)
    assert ported == python


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_the_port_runs_the_examples(port, path):
    python, ported = both(port, args=[str(path)])
    assert ported == python
    assert ported[2] == 0


@pytest.mark.parametrize(
    "stdin",
    [
        "r>\n",
        "5 execute\n",
        "variable v : r v @ ['] execute execute ; ' r v ! r\n",
        "1 40 lshift allot\n",
        "5 1000000000000 .r\n",
    ],
)
def test_the_port_reports_errors_from_inside_a_word(port, stdin):
    # The messages differ (each wraps its own language's error, or runs out of
    # something different), but both name the word and recover.
    (_, py_err, py_code), (_, port_err, port_code) = both(port, stdin=stdin)
    word = stdin.split()[-1]
    assert word in py_err and word in port_err
    assert py_code == port_code == 1
    # and both carry on afterwards
    python, ported = both(port, stdin=stdin + "2 .\n")
    assert python[0].endswith("2  ok\n") and ported[0].endswith("2  ok\n")


def test_the_port_reads_files_with_universal_newlines(port, tmp_path):
    source = tmp_path / "crlf.fs"
    source.write_bytes(b"1 .\r\n2 . \\ a comment\r\n.( x\r\ny)\r.( z)")
    python, ported = both(port, args=[str(source)])
    assert ported == python
    assert python[0] == "1 2 x\ny" + "z"


def random_programs(count, seed=0):
    """Lines of random words, a few numbers and names among them. Words that
    print a lot or loop forever are left out, and so are ' and ['], since a
    Python execution token is an object and the ports' tokens are numbers."""
    rng = random.Random(seed)
    leave_out = {"words", "allot", ".r", "spaces", "begin", "again", "'", "[']"}
    vocab = sorted(set(forth.Forth().words) - leave_out)
    vocab += ["0", "1", "2", "-1", "64", "-9223372036854775808", "x", ": x", "char a"]
    for _ in range(count):
        words = [rng.choices(vocab, k=rng.randint(1, 8)) for _ in range(rng.randint(1, 4))]
        lines = map(" ".join, words)
        yield "\n".join(lines) + "\n"


def test_random_programs_agree(port):
    # The Go port's first version passed every program written for it here;
    # random ones found more bugs in both ports.
    for stdin in random_programs(300):
        try:
            python, ported = both(port, stdin=stdin)
        except AttributeError:  # Python stops with a traceback after a stray ]
            done = subprocess.run([port], input=stdin.encode(), capture_output=True, timeout=30)
            assert done.returncode == 1 and done.stderr, stdin
            continue
        assert ported == python, stdin


@pytest.mark.parametrize("name, source", bench.programs(scale=0).items())
def test_the_benchmark_programs_agree_at_a_small_size(port, name, source):
    python, ported = both(port, stdin=source + "\n")
    assert ported == python
    assert ported[2] == 0


@pytest.mark.parametrize(
    "case", ["a surrogate", "invalid UTF-8", "a full disk", "unreadable input", "a stray ]"]
)
def test_both_fail_where_input_or_output_does(port, tmp_path, case):
    # Python stops with a traceback in each case. The port has to fail too,
    # rather than print a replacement character, exit 0, or spin.
    source = tmp_path / "source.fs"
    source.write_bytes(b".( caf\xe9)" if case == "invalid UTF-8" else b"1 2 + .")
    with open(os.devnull, "rb") as devnull, open("/dev/full", "wb") as full:
        run = {"args": [str(source)], "stdin": devnull, "stdout": subprocess.PIPE}
        if case == "a surrogate":
            run = {"args": [], "input": b"55296 emit\n", "stdout": subprocess.PIPE}
        elif case == "a stray ]":  # compiling at the end, with no definition to name
            run = {"args": [], "input": b"]\n", "stdout": subprocess.PIPE}
        elif case == "a full disk":
            run["stdout"] = full
        elif case == "unreadable input":
            run = {"args": [], "stdin": os.open(tmp_path, os.O_RDONLY), "stdout": subprocess.PIPE}
        args = run.pop("args")
        for command in ([sys.executable, str(HERE / "forth.py")], [str(port)]):
            done = subprocess.run([*command, *args], stderr=subprocess.PIPE, timeout=30, **run)
            assert done.returncode != 0, (command, case)
            assert done.stderr, (command, case)
