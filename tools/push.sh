#!/bin/bash
# Push the current branch to origin, and nothing else.
#
# Only claude/* branches are pushed, never force, never a deletion, never a
# different destination ref, and no arguments are accepted. This is the one
# push command the session settings approve without asking.
set -euo pipefail

if [ "$#" -ne 0 ]; then
  echo "push.sh: takes no arguments" >&2
  exit 1
fi

branch=$(git rev-parse --abbrev-ref HEAD)
if [[ ! "$branch" =~ ^claude/[A-Za-z0-9._-]+$ ]]; then
  echo "push.sh: refusing to push '$branch'; only claude/* branches are pushed from here" >&2
  exit 1
fi

exec git push -u origin "$branch:$branch"
