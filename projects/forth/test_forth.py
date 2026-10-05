from pathlib import Path

import forth
import pytest
from forth import Forth, ForthError

HERE = Path(__file__).parent

# A small test harness written in the Forth itself, in the style of the
# T{ ... -> ... }T tests that Forth implementations are checked with: run the
# code before ->, then check that it left exactly the values after it.
TESTER = r"""
variable start  variable count  create results 64 allot
: t{ depth start ! ;
: -> depth start @ - dup count !  0 ?do  results i + !  loop ;
: }t
  depth start @ - count @ <> if ." wrong depth " depth start @ - 0 ?do drop loop exit then
  count @ 0 ?do  results i + @ <> if ." wrong result " then  loop ;
"""

CORE = r"""
t{ 1 2 3 rot -> 2 3 1 }t      t{ 1 2 3 -rot -> 3 1 2 }t
t{ 1 2 swap -> 2 1 }t         t{ 1 2 over -> 1 2 1 }t
t{ 1 2 nip -> 2 }t            t{ 1 2 tuck -> 2 1 2 }t
t{ 1 2 2dup -> 1 2 1 2 }t     t{ 1 2 3 4 2swap -> 3 4 1 2 }t
t{ 1 2 3 4 2over -> 1 2 3 4 1 2 }t
t{ 0 ?dup -> 0 }t             t{ 5 ?dup -> 5 5 }t
t{ 1 2 3 2 pick -> 1 2 3 1 }t t{ 1 2 depth -> 1 2 2 }t
t{ 7 3 /mod -> 1 2 }t         t{ -7 3 /mod -> 2 -3 }t
t{ 7 -3 / -> -3 }t            t{ 7 -3 mod -> -2 }t
t{ -5 abs -> 5 }t             t{ 5 negate -> -5 }t
t{ 3 9 min -> 3 }t            t{ 3 9 max -> 9 }t
t{ 1 2 < -> true }t           t{ 2 1 < -> false }t
t{ 1 2 > -> false }t          t{ 0 0= -> -1 }t
t{ -1 0< -> -1 }t             t{ 1 1 <> -> 0 }t
t{ -1 1 u< -> false }t        t{ 1 -1 u< -> true }t
t{ 0 invert -> -1 }t          t{ 6 3 and -> 2 }t
t{ 6 3 or -> 7 }t             t{ 6 3 xor -> 5 }t
t{ 1 4 lshift -> 16 }t        t{ -8 2/ -> -4 }t
t{ 1 63 lshift -> -9223372036854775808 }t
t{ -1 1 rshift -> 9223372036854775807 }t
t{ 9223372036854775807 1+ -> -9223372036854775808 }t
t{ 0x7f -> 127 }t
t{ : ab if 1 else 2 then ; -> }t
t{ true ab false ab -> 1 2 }t
t{ : count-down begin dup 0> while dup 1- repeat ; -> }t
t{ 3 count-down -> 3 2 1 0 }t
t{ : to-zero begin 1- dup 0= until ; 5 to-zero -> 0 }t
t{ : sum 0 swap 0 do i + loop ; 10 sum -> 45 }t
t{ : evens 0 10 0 do i + 2 +loop ; evens -> 20 }t
t{ : down 0 0 10 do i + -1 +loop ; down -> 55 }t
t{ : pairs 3 0 do 2 0 do j 10 * i + loop loop ; pairs -> 0 1 10 11 20 21 }t
t{ : skip 0 0 ?do 99 loop ; skip -> }t
t{ : first-big 100 0 do i dup 7 > if leave then drop loop ; first-big -> 8 }t
t{ : early 10 0 do i 3 = if i unloop exit then loop 0 ; early -> 3 }t
t{ : rs 1 >r 2 r@ r> ; rs -> 2 1 1 }t
t{ variable v 5 v ! 3 v +! v @ -> 8 }t
t{ 42 constant answer answer -> 42 }t
t{ create table 1 , 2 , 3 , table 2 cells + @ -> 3 }t
t{ here 2 allot here swap - -> 2 }t
t{ : pair create , , does> dup @ swap cell+ @ ; 1 2 pair p p -> 2 1 }t
t{ : fact dup 1 > if dup 1- recurse * then ; 10 fact -> 3628800 }t
t{ : sq dup * ; ' sq 7 swap execute -> 49 }t
t{ : sq3 3 ['] sq execute ; sq3 -> 9 }t
t{ : five [ 2 3 + ] literal ; five -> 5 }t
t{ char A -> 65 }t
t{ : chr [char] B ; chr -> 66 }t
t{ ( a comment ) 1 \ and the rest of the line
   -> 1 }t
"""


def run(source):
    f = Forth()
    return f.interpret(source)


def test_the_core_words_pass_the_forth_written_tests():
    f = Forth()
    f.interpret(TESTER)
    for line in CORE.strip().split("\n"):
        assert f.interpret(line) == "", line
    assert f.stack == []


def test_the_tester_catches_a_wrong_result_and_a_wrong_depth():
    f = Forth()
    f.interpret(TESTER)
    assert f.interpret("t{ 1 2 + -> 4 }t") == "wrong result "
    assert f.interpret("t{ 1 2 -> 1 }t") == "wrong depth "


def test_output_words():
    assert run("1 . -2 . cr") == "1 -2 \n"
    assert run('." hello" 32 emit .( world)') == "hello world"
    assert run(': greet ." hi, " ." you" ; greet') == "hi, you"
    assert run("42 5 .r 7 0 .r 3 spaces") == "   427   "
    assert run("1 2 3 .s") == "<3> 1 2 3 "


def test_names_are_case_insensitive_and_can_be_redefined():
    assert run(": Sq dup * ; 3 SQ .") == "9 "
    # A word compiled before a redefinition keeps calling the old one.
    assert run(": a 1 ; : b a ; : a 2 ; b . a .") == "1 2 "
    # During its own definition a word can't see itself, so this calls the old one.
    assert run(": c 10 ; : c c 1+ ; c .") == "11 "


def test_does_makes_a_defining_word():
    source = ": counter create 0 , does> 1 over +! @ ; counter tick tick . tick . tick ."
    assert run(source) == "1 2 3 "


def test_recursion_runs_deep_without_python_recursion():
    assert run(": fib dup 2 < if exit then dup 1- recurse swap 2 - recurse + ; 20 fib .") == "6765 "
    assert run(": deep dup 0> if 1- recurse then ; 5000 deep .") == "0 "


@pytest.mark.parametrize(
    "source, message",
    [
        ("frobnicate", "frobnicate ?"),
        ("drop", "stack underflow"),
        ("1 0 /", "division by zero"),
        ("99 @", "invalid address 99"),
        (": x if ;", "unbalanced control structure in x"),
        ("if", "compile-only word"),
        (":", "a name was expected"),
        (": forever recurse ; forever", "return stack overflow"),
    ],
)
def test_errors(source, message):
    with pytest.raises(ForthError, match=message):
        run(source)


def test_an_error_resets_the_interpreter():
    f = Forth()
    f.interpret("1 2 3")
    with pytest.raises(ForthError):
        f.interpret(": broken 1 2 nosuchword ;")
    assert f.stack == [] and not f.compiling
    assert f.interpret("5 .") == "5 "
    assert "broken" not in f.words


def test_python_errors_come_out_as_forth_errors():
    with pytest.raises(ForthError, match="r>"):
        run("r>")
    with pytest.raises(ForthError, match="execute"):
        run("5 execute")


def test_the_sieve_example():
    out = run((HERE / "examples" / "sieve.fs").read_text())
    assert out.split() == [str(p) for p in range(2, 100) if all(p % d for d in range(2, p))]


def test_the_sierpinski_example_matches_the_committed_picture():
    out = run((HERE / "examples" / "sierpinski.fs").read_text())
    assert out == (HERE / "out" / "sierpinski.svg").read_text()
    # 3^6 filled squares: each halving of the 64 square keeps three of its four parts.
    assert out.count("z") == 3**6


def test_main_runs_files_and_reports_errors(tmp_path, capsys):
    good, bad = tmp_path / "good.fs", tmp_path / "bad.fs"
    good.write_text("2 3 + .")
    bad.write_text("drop")
    assert forth.main([str(good)]) == 0
    assert capsys.readouterr().out == "5 "
    assert forth.main([str(bad)]) == 1
    assert "stack underflow" in capsys.readouterr().err


def test_the_interpreter_stays_under_300_lines():
    assert len((HERE / "forth.py").read_text().splitlines()) < 300


def test_a_backslash_at_the_end_of_a_line_ends_only_that_line():
    assert run("1 \\\n2 .\n3 . .") == "2 3 1 "
    assert run("\\") == ""


def test_execution_tokens_can_be_stored_and_fetched():
    source = "variable action  ' . action !  : run action @ execute ;  7 run"
    assert run(source) == "7 "
    assert (
        run(": sq dup * ; create ops ' sq , ' 1+ ,  5 ops cell+ @ execute ops @ execute .") == "36 "
    )


def test_runaway_recursion_through_execute_is_a_forth_error():
    f = Forth()
    with pytest.raises(ForthError):
        f.interpret("variable v : r v @ execute ; ' r v ! 1 2 3 r")
    assert f.stack == [] and f.rstack == []


def test_plus_loop_wraps_like_a_64_bit_cell():
    # From the largest index to the smallest limit crosses limit-1 to limit, so one
    # pass; the leave after three only stops a wrong loop from running for ever.
    source = ": w 0 -9223372036854775808 9223372036854775807 do 1+ dup 3 = if leave then loop ; w"
    assert run(source + " .") == "1 "
