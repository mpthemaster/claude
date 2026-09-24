---
name: close-out
description: End-of-session procedure for this workshop. Use when the session's one piece of work is finished, to check it, record it, open the pull request, and merge it.
---

# Close out

Step 6 of the session procedure in `CLAUDE.md`, as a checklist. Do all of it,
in this order; the merge comes near the end, not first.

1. **Record.** The projects table in `README.md` has a row for any new
   project. `BACKLOG.md` has the item moved to Done with today's date and a
   link, plus any new ideas that came up. `journal/YYYY-MM-DD.md` (append if
   it exists) says what was done, why, what was learned, and what didn't
   work, in plain language and in the first person.
2. **Check.** `ruff check . && ruff format --check . && pytest`. Fix
   anything red; never skip or weaken a test.
3. **Commit.** One commit, or a few with clear messages. The commit message
   ends with the attribution trailer lines the harness asks for and nothing
   else about the model. Commit before the review so the reviewer sees
   everything; a diff between commits doesn't include uncommitted work.
4. **Review.** Ask the `reviewer` agent (`.claude/agents/reviewer.md`) to
   read the committed diff against `origin/main`. Fix what it finds that's
   real, re-run the checks, and commit again; note in the journal what you
   disagreed with and why.
5. **Push.** `bash tools/push.sh`. It pushes the current `claude/*` branch
   and refuses anything else.
6. **Pull request.** Open it against `main` with the GitHub tools, or with
   `gh pr create` if that's what the session has. If a draft pull request
   already exists for this branch, mark it ready instead. Title: what changed, in
   one line. Body: what and why, what was checked, and the generated-with
   lines the harness asks for. If the session has no way to open a pull
   request, write that in the journal entry, commit it, push, and stop; the
   next session will find the branch and finish it.
7. **Wait for green, and for reviews.** Read the pull request's check runs
   until every one has completed; red means fix it and push again, and a
   check that died before running anything can be re-run once. Then give
   any review bot Michael has enabled up to ten minutes to post, and read
   every review comment on the pull request. A bot's finding is a bug
   report: verify it, fix what's real, commit, push, and wait for green
   again; reply in one line to anything that isn't real. A comment from
   Michael is addressed the same way, with a reply. Resolve each thread you
   handled.
8. **Merge.** Squash merge with the head commit's full 40-character SHA as
   the expected head. If the merge is refused because the branch is behind
   `main`: `git fetch origin main && git merge origin/main`, resolve, run
   the checks, push, wait for green, merge again. If it's refused for an
   unresolved thread, go back to step 7.
9. **Issue.** If the work came from an issue, comment there with what was
   done and a link to the pull request, then close it as completed.
10. **Stop.** The merged branch is deleted automatically; don't push it
    again. A stop hook may report unpushed commits on the merged branch;
    that's expected, the work is on `main`.
