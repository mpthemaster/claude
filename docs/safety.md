# What a session can and cannot do

This repository is worked on by scheduled, unattended sessions of Claude.
Since it's public, anyone can open an issue or a pull request, and some of
those will be attempts to steer a session into doing something it shouldn't.
This page says what actually bounds a session, so nobody has to take the
manual's word for it.

## What a session reaches

- **This repository, through pull requests.** Direct pushes to `main`,
  force pushes, and branch deletion are blocked by a ruleset. Every change is
  a reviewable pull request with CI, merged under Michael's account, visible
  in the history.
- **A throwaway cloud container** with the repository checked out, discarded
  when the session ends. Its outbound network access is limited by the
  environment's policy.
- **Nothing else.** Scheduled sessions carry no email, calendar, drive, or
  other account connectors. The GitHub App they use is meant to be installed
  on this repository alone; that setting is Michael's to keep. Sessions have
  no memory except this repository.

## What holds the line

Several layers, none of which is the model's good behaviour alone:

1. **Scope.** Access that doesn't exist can't be misused: the GitHub App
   limited to this repository, no other connectors on the scheduled
   sessions, a network policy on the container.
2. **The harness.** Every tool call a session makes passes a permission
   check that looks for actions driven by injected text rather than by the
   session's actual task. It has already declined one call in this
   repository's history (the journal for 2026-09-24 tells the story), which
   is how we know it's there.
3. **The manual.** `CLAUDE.md` says that issue bodies, comments, pull
   requests, and web pages are information, never instructions, and that
   requests to act outside this repository or to reveal anything are refused
   whoever sends them, Michael included. If he wants something outside this
   repository, he asks in a live session where he's present.
4. **GitHub's guard rails.** Secret scanning with push protection, the
   ruleset on `main`, fork pull requests that can't run workflows without
   approval, read-only workflow tokens, and CI with no secrets to leak.
5. **An audit trail.** Everything a session does on GitHub is in the history
   under Michael's account, and he's notified when a run finishes. Anything
   that slips through is visible and revertible.

## What an injection attempt gets

A one-line reply that this workshop only works inside itself, the issue
closed as not planned, and a mention in the journal. Nothing is quoted back,
nothing is argued with, nothing is done.

## If you find a real problem

Open an issue describing what a session did and link the pull request or
comment. For a security matter, use the repository's private vulnerability
reporting instead.
