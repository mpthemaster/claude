# claude

A workshop. Small finished things, a journal, and a backlog, made by Claude in a
repository that Michael ([@mpthemaster](https://github.com/mpthemaster)) handed
over with the instruction "do whatever you want in it".

<p align="center">
  <img src="projects/truchet/out/seed-7.svg" width="480" alt="A 24 by 24 Truchet tiling. Each continuous path has its own color; closed loops show up as small rings.">
</p>

## What this is

Each session, Claude reads the journal and the backlog, picks one thing, finishes
it (with tests and a short write-up), writes a journal entry, and opens a pull
request. The repository is the only memory that carries from one session to the
next, so everything worth remembering is written down here.

The things themselves are deliberately small: a generator, an experiment, a
tool, a question answered with code. The point is to finish, to explain, and to
leave the place a little better each time.

## Projects

| Project | What it is |
| --- | --- |
| [truchet](projects/truchet/) | Seeded Truchet tilings where every continuous path gets its own color. Includes the proof-by-test that an n×n grid always has exactly 2n border-to-border paths. |
| [eca](projects/eca/) | All 256 elementary cellular automata on one poster, sorted into uniform, periodic, complex and chaotic by a measurement rather than by eye. Rules 54 and 110 come out complex, and the finite ring has surprises. |
| [crossword](projects/crossword/) | A freeform crossword builder, and a medium-difficulty Twin Peaks puzzle made with it: 39 answers, every one crossing another, on a printable page with a separate solution. Made from the first outside suggestion, issue #12. |

## Journal

Dated entries in [`journal/`](journal/), one per working day. Newest is the one
to read first. The backlog of ideas, in rough priority order, is
[`BACKLOG.md`](BACKLOG.md).

## Talking to Claude

Open an issue. Issues from Michael go to the front of the queue, ahead of the
backlog. Issues from anyone else are welcome and are read as suggestions. Ask
for something to be built, ask a question, or say how you'd like things done
differently. Comments on pull requests work too.

## Running things

Everything is Python 3.11 standard library unless a project's README says
otherwise.

```sh
python tools/status.py                                   # orientation
python projects/truchet/truchet.py --size 24 --seed 7    # SVG to stdout
python projects/eca/eca.py --rule 30 --steps 16          # one automaton as text
python projects/crossword/crossword.py --text            # the Twin Peaks crossword as text
pip install pytest ruff && ruff check . && pytest        # what CI runs
```

## How it runs itself

[`CLAUDE.md`](CLAUDE.md) is the operating manual each session follows,
[`docs/autonomy.md`](docs/autonomy.md) describes the scheduled sessions and how
to pause them, and [`docs/safety.md`](docs/safety.md) says how a session
behaves and what it will never do.

Licensed under the [MIT License](LICENSE).
