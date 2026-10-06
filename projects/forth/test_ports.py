"""The Go port is checked against the Python Forth: the same programs, run
through both, must print the same output, the same errors and the same exit
code. The Python interpreter is the specification; test_forth.py tests it.
"""

import io
import os
import shutil
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import bench
import forth
import pytest
from test_forth import CORE, TESTER

HERE = Path(__file__).parent
EXAMPLES = sorted((HERE / "examples").glob("*.fs"))

# In CI a missing toolchain is a failure, not a skip.
if shutil.which("go") is None and not os.environ.get("CI"):
    pytest.skip("go is not installed", allow_module_level=True)


@pytest.fixture(scope="module")
def go_forth(tmp_path_factory):
    binary = tmp_path_factory.mktemp("go") / "forth"
    subprocess.run(["go", "build", "-o", str(binary), "."], cwd=HERE / "go", check=True)
    return binary


def python_forth(args, stdin):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out), redirect_stderr(err):
        code = forth.main(args)
    return out.getvalue(), err.getvalue(), code


def both(go_forth, args=(), stdin=""):
    go = subprocess.run([go_forth, *args], input=stdin, capture_output=True, text=True, timeout=30)
    return python_forth(list(args), stdin), (go.stdout, go.stderr, go.returncode)


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
]


@pytest.mark.parametrize("stdin", PROGRAMS, ids=range(len(PROGRAMS)))
def test_the_go_port_matches_at_the_prompt(go_forth, stdin):
    python, go = both(go_forth, stdin=stdin)
    assert go == python


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_the_go_port_runs_the_examples(go_forth, path):
    python, go = both(go_forth, args=[str(path)])
    assert go == python
    assert go[2] == 0


@pytest.mark.parametrize("stdin", ["r>\n", "5 execute\n"])
def test_the_go_port_reports_errors_from_inside_a_word(go_forth, stdin):
    # The messages differ (each wraps its own language's error), but both name the word.
    (_, py_err, py_code), (_, go_err, go_code) = both(go_forth, stdin=stdin)
    word = stdin.split()[-1]
    assert word in py_err and word in go_err
    assert py_code == go_code == 1


@pytest.mark.parametrize("name, source", bench.programs(scale=0).items())
def test_the_benchmark_programs_agree_at_a_small_size(go_forth, name, source):
    python, go = both(go_forth, stdin=source + "\n")
    assert go == python
    assert go[2] == 0
