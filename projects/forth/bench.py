"""Time the Python Forth against the Go and Rust ports on the same programs.

    python projects/forth/bench.py           # builds both ports, prints a table

Each time is the best of three whole runs, so it includes starting the
process and compiling the prelude; the start-up row measures that alone.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).parent


def programs(scale: int = 1) -> dict[str, str]:
    """The benchmark programs; `scale` 0 makes them small enough for a test."""
    fib, loop, sieve = (27, 2_000_000, 200_000) if scale else (10, 1000, 1000)
    return {
        "start-up": "",
        f"{fib} fib": f": fib dup 2 < if exit then dup 1- recurse swap 2 - recurse + ; {fib} fib .",
        f"{loop:,} loop": f": count 0 {loop} 0 do i + loop ; count .",
        f"sieve to {sieve:,}": f"""{sieve} constant n  create sieve n allot
            : strike dup dup * n < if n over dup * do 1 sieve i + ! dup +loop then drop ;
            : primes 0 n 2 do sieve i + @ 0= if 1+ i strike then loop ; primes .""",
    }


def build(port: str, out_dir: Path) -> Path:
    """Build the "go" or "rust" port into `out_dir` and return the binary."""
    out_dir = out_dir.resolve()  # each builds from its own directory
    if port == "go":
        binary = out_dir / "forth-go"
        subprocess.run(["go", "build", "-o", str(binary), "."], cwd=HERE / "go", check=True)
        return binary
    command = ["cargo", "build", "--quiet", "--release", "--target-dir", str(out_dir)]
    subprocess.run(command, cwd=HERE / "rust", check=True)
    return out_dir / "release" / "forth"


def run(command: list[str], source: str) -> tuple[str, float]:
    """What the program printed, and the best wall time of three runs."""
    with tempfile.NamedTemporaryFile("w", suffix=".fs") as file:
        file.write(source)
        file.flush()
        best, out = float("inf"), ""
        for _ in range(3):
            start = time.perf_counter()
            done = subprocess.run([*command, file.name], capture_output=True, text=True, check=True)
            best, out = min(best, time.perf_counter() - start), done.stdout
    return out, best


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        commands = {
            "Python": [sys.executable, str(HERE / "forth.py")],
            "Go": [str(build("go", Path(tmp)))],
            "Rust": [str(build("rust", Path(tmp)))],
        }
        header = "".join(f"{name:>10}" for name in commands)
        print(f"{'program':<22}{header}  Py/Go  Py/Rust")
        for name, source in programs().items():
            results = [run(command, source) for command in commands.values()]
            if len({out for out, _ in results}) != 1:
                raise SystemExit(f"{name}: the interpreters disagree: {results}")
            times = [t for _, t in results]
            row = "".join(f"{t:>9.3f}s" for t in times)
            ratios = f"{times[0] / times[1]:>6.0f}x{times[0] / times[2]:>8.0f}x"
            print(f"{name:<22}{row}{ratios}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
