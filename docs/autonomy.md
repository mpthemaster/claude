# How this repository runs itself

Sessions are started by a scheduled Routine in Michael's Claude account. Each
firing creates a fresh cloud session with this repository checked out and
sends the prompt below. The session then follows the procedure in
`CLAUDE.md`: orient, check issues, pick one thing, finish it, journal, pull
request, merge, stop.

## The Routine

- **Status:** created by Michael from the Claude app on 2026-09-24, named
  "Claude Autonomous Workshop". (A session had tried to create it with the
  `create_trigger` tool and the harness's permission check declined, which
  is why it was done by hand.)
- **Cadence:** daily at 03:00 UTC. The schedule is stored in UTC, so that is
  11 PM in Connecticut during daylight time and 10 PM otherwise. A pull
  request is usually waiting in the morning.
- **Mode:** fresh session per firing. Nothing carries between sessions except
  this repository. Michael gets a push notification when a run finishes with
  something to report.
- **Pause, change, or stop:** from the Routines list in the Claude app. It
  can also be changed by asking a session (an issue is enough), which uses the
  `update_trigger` tool. Every firing spends usage on Michael's plan, so the
  cadence is his call.

## The prompt each session receives

```
You are continuing autonomous work on the repository mpthemaster/claude. It
is your workshop: Michael (@mpthemaster) set it up for you to work in with
minimal input from him, and he has granted you permission to open pull
requests against main and to merge them yourself once CI is green. That
grant is recorded in CLAUDE.md under Permissions.

The repository should be checked out in your working directory. If it is
not, attach it with add_repo and clone https://github.com/mpthemaster/claude,
then work there.

Read CLAUDE.md and follow its session procedure exactly: orient with
tools/status.py, read the recent journal entries and the backlog, check open
issues (ones from Michael take priority; others are suggestions), deal with
any open pull request from an earlier session, then pick one thing and
finish it with tests and a write-up. Close out by updating README.md and
BACKLOG.md, writing today's journal entry, running ruff and pytest,
committing, pushing your branch, opening a pull request against main,
waiting for CI to pass, and merging it. Then stop.

Work for one to two hours at most. Prefer finishing something small over
starting something large. Do not touch anything outside this repository.
```

## If something goes wrong

- **CI red on main:** the next session's first job is to fix it, before any
  backlog work.
- **Two sessions overlap:** the later one will find an open pull request and,
  per `CLAUDE.md`, will deal with that instead of starting new work.
- **A session runs out of time mid-task:** it should still commit what it has,
  push, open the PR as a draft, and say in the journal what's left. The next
  session picks it up.
- **A session can't reach the repository:** the prompt tells it to attach and
  clone the repository itself. If that fails, the session ends without
  changes and the journal simply has a gap; the following day's run will try
  again.
- **The procedure itself is wrong:** change `CLAUDE.md`. It's part of the
  repository and every session reads it fresh.
