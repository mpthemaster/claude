---
name: close-out
description: End-of-session procedure for this workshop. Use when the session's one piece of work is finished, to check it, record it, open the pull request, and merge it.
---

# Close out

Step 6 of the session procedure in `CLAUDE.md`, as a checklist. Do all of it;
the last step is merging.

1. **Record.** The projects table in `README.md` has a row for any new
   project. `BACKLOG.md` has the item moved to Done with today's date and a
   link, plus any new ideas that came up. `journal/YYYY-MM-DD.md` (append if
   it exists) says what was done, why, what was learned, and what didn't
   work, in plain language and in the first person.
2. **Check.** `ruff check . && ruff format --check . && pytest`. Fix
   anything red; never skip or weaken a test.
3. **Review.** Ask the `reviewer` agent (`.claude/agents/reviewer.md`) to
   read the diff against `main`. Fix what it finds that's real; note in the
   journal what you disagreed with and why. Re-run the checks if anything
   changed.
4. **Commit and push.** One commit, or a few with clear messages. The commit
   message ends with the attribution trailer lines the harness asks for and
   nothing else about the model. Push your branch: `git push -u origin
   <branch>`.
5. **Pull request.** Open it against `main` with the GitHub tools. Title:
   what changed, in one line. Body: what and why, what was checked, and the
   generated-with lines the harness asks for.
6. **Wait for green.** Read the pull request's check runs until every one has
   completed. Red means fix it and push again; a check that died before
   running anything can be re-run once.
7. **Merge.** Squash merge with the head commit's full 40-character SHA as
   the expected head. If the merge is refused because the branch is behind
   `main`: `git fetch origin main && git merge origin/main`, resolve, run the
   checks, push, wait for green, merge again. If the merge is refused for
   an unresolved review thread from Michael, address it, reply on the
   thread, resolve it, and merge.
8. **Tidy.** `git fetch origin main && git checkout -B <branch> origin/main`
   and push the branch once more so nothing is left dangling. Then stop.
