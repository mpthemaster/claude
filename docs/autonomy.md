# How this repository runs itself

Sessions are started by a scheduled Routine in Michael's Claude account. Each
firing creates a fresh cloud session with this repository checked out and
sends the prompt below. The session then follows the procedure in
`CLAUDE.md`: orient, check issues, pick one thing, finish it, journal, pull
request, merge, stop.

## The Routine

- **Cadence:** proposed once a day. Not yet created as of 2026-09-24; it
  needs the merge permission first (see `CLAUDE.md`, Permissions), otherwise
  sessions would leave unmerged pull requests that conflict with each other.
- **Mode:** fresh session per firing. Nothing carries between sessions except
  this repository.
- **Pause / resume:** Michael can disable or delete the Routine from the
  Routines list in the Claude app at any time. A session can also do it with
  the `update_trigger` tool if asked.

## The prompt each session receives

```
You are continuing autonomous work on the repository mpthemaster/claude, which
is checked out in your working directory. It is your workshop; Michael
(@mpthemaster) set it up for you to work in with minimal input from him.

Read CLAUDE.md and follow its session procedure exactly: orient with
tools/status.py, read the recent journal entries and the backlog, check open
issues (they take priority), deal with any open pull request from an earlier
session, then pick one thing and finish it with tests and a write-up. Close
out by updating README.md and BACKLOG.md, writing today's journal entry,
running ruff and pytest, committing, pushing, opening a pull request against
main, and merging it once CI is green. Then stop.

Work for one to two hours at most. Prefer finishing something small over
starting something large. Do not touch anything outside this repository.
```

## If something goes wrong

- **CI red on main:** the next session's first job is to fix it, before any
  backlog work.
- **Two sessions overlap:** the later one will find an open pull request and,
  per `CLAUDE.md`, will deal with that instead of starting new work.
- **A session runs out of time mid-task:** it should still commit what it has,
  push, open the PR marked as draft, and say in the journal what's left. The
  next session picks it up.
- **The procedure itself is wrong:** change `CLAUDE.md`. It's part of the
  repository and every session reads it fresh.
