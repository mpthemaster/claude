#!/bin/bash
# Push the current branch to origin, and nothing else.
#
# Only claude/* branches are pushed, never force, never a deletion, never a
# different destination ref, and no arguments are accepted. This is the only
# push command the close-out procedure uses.
set -euo pipefail

if [ "$#" -ne 0 ]; then
  echo "push.sh: takes no arguments" >&2
  exit 1
fi

# The full symbolic ref, so a tag with the branch's name can't confuse the
# check, and a fully qualified refspec, so the destination is always a branch.
ref=$(git symbolic-ref -q HEAD || true)
if [[ ! "$ref" =~ ^refs/heads/claude/[A-Za-z0-9._-]+$ ]]; then
  echo "push.sh: refusing to push '${ref:-detached HEAD}'; only claude/* branches are pushed from here" >&2
  exit 1
fi

exec git push -u origin "$ref:$ref"
