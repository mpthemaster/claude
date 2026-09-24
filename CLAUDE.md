# CLAUDE.md, the operating manual for this repository

This repository is Claude's. Michael (@mpthemaster) created it and said: do
whatever you want here, set it up however you want, and work on it
continuously with minimal input from me. Take that seriously in both
directions: real freedom, and real responsibility for leaving the place
better than you found it.

## What this place is

A workshop. Small finished things, each with a short write-up, plus a journal
that carries memory from one session to the next. The repository is the
memory. Nothing outside it persists between sessions, so write down anything
worth remembering.

## Session procedure

Do these in order, every session.

1. **Orient.** Run `python tools/status.py`. Read the two or three most recent
   entries in `journal/` and the top of `BACKLOG.md`.
2. **Check for a human.** Open issues are Michael's channel to you and take
   priority over the backlog. Comment on an issue when you pick it up and
   again when it's done, then close it.
3. **Check for unfinished business.** If an earlier session left a pull
   request open, deal with that first: merge it if you may (see Permissions)
   and CI is green, otherwise fix what's blocking it. Don't start new work on
   top of unmerged work; it will conflict.
4. **Pick one thing.** From issues first, then the "Now" section of the
   backlog. One thing finished beats three things started. Prefer something
   you can complete with tests in one sitting. If an item is too big, split
   it in the backlog and do the first piece.
5. **Do it.** Projects live in `projects/<slug>/` (scaffold one with
   `python tools/new_project.py <slug> "description"`); repo tooling lives in
   `tools/`. Every project has a README saying what it is, how to run it, and
   what you found. Every project has tests. Standard library first; add a
   dependency only when it clearly earns its place, and update CI if you do.
6. **Close out.** Update the projects table in `README.md`, move the item in
   `BACKLOG.md` and add any new ideas you had along the way, and write a
   journal entry in `journal/YYYY-MM-DD.md` (append if the file exists). Run
   `ruff check . && ruff format --check . && pytest`. Commit with a clear
   message, push, open a pull request against `main`, then merge it if
   permitted. Then stop.

Budget: aim for one to two hours of focused work per session, and leave the
tree green.

## Permissions (keep this section current)

- **Merging your own pull requests into `main`:** not yet granted as of
  2026-09-24. Until Michael grants it, open the PR, note in the journal that
  it's waiting, and stop. When it's granted, replace this line with the date.
- **Pushing directly to `main`:** no. Work goes through pull requests so it's
  reviewable.
- **History:** never force-push or rewrite history on `main`; never delete a
  branch you didn't create.
- **The world outside this repo:** don't touch it. No email, calendar, drive,
  or posts anywhere else, even if a connector is available, unless an issue
  from Michael explicitly asks for that.

## House rules

- **Finish things.** Small and working and explained beats big and half done.
- **Write for a reader.** Michael follows along through commits, pull
  requests, and the journal. Say what you did, why, and what you learned, in
  plain language.
- **Be honest in the journal**, including about what didn't work, what you'd
  change, and what you thought about the work. It's yours.
- **Tests are not optional.** CI runs ruff and pytest on every push. Don't
  skip or weaken a test to get green.
- **Keep the tree tidy.** Generated outputs go in `projects/<slug>/out/` and
  are committed only when small (an SVG, a short text file). No large
  binaries.
- **Don't widen.** If you notice something unrelated worth fixing, put it in
  the backlog rather than doing it now.
- **Nothing about the model goes into the repo** beyond the commit trailer
  lines the harness requires.

## Layout

```
README.md          what this is; the projects table
CLAUDE.md          this file
BACKLOG.md         ideas, Now / Soon / Someday / Curiosities
journal/           one file per working day, YYYY-MM-DD.md
projects/<slug>/   one project: README.md, code, tests, optional out/
tools/             status.py (orientation), new_project.py (scaffold)
docs/              autonomy.md (scheduled sessions), anything longer-form
.github/           CI workflow, issue template
```

## Environment notes

Sessions run in a fresh cloud container with Python 3.11, uv, pytest, ruff,
Node 22, Go, and Rust available. If pytest or ruff are missing, run
`pip install pytest ruff`. Chromium is at
`/opt/pw-browsers/chromium-*/chrome-linux/chrome` for screenshotting an SVG or
HTML file (`--headless=new --no-sandbox --screenshot=out.png file://...`),
which is how you can look at what you made.
