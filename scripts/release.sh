#!/usr/bin/env bash
# release.sh — tag and release, but only from a green tree.
#
# The reason this exists: 0.1.9 was tagged and published while its own test
# suite was red. The tests had run — through `| tail -2`, which reports the exit
# status of `tail`. The pipeline looked green because the last command in it was.
#
# So: no pipes around the suite, `set -e`, and the version is read from the
# changelog heading rather than typed twice.
#
# Usage: scripts/release.sh [--dry-run]
set -euo pipefail

cd "$(dirname "$0")/.."

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

suite=$(mktemp)
if ! python3 tests/run.py >"$suite" 2>&1; then
    tail -20 "$suite" >&2
    echo "release: the suite is red, nothing tagged" >&2
    exit 1
fi
tail -3 "$suite"

if [ -n "$(git status --porcelain)" ]; then
    echo "release: the tree is dirty, commit first:" >&2
    git status --short >&2
    exit 1
fi

version=$(grep -m1 -oE '^## \[[0-9]+\.[0-9]+\.[0-9]+\]' CHANGELOG.md | tr -d '#[] ')
[ -n "$version" ] || { echo "release: no version heading in CHANGELOG.md" >&2; exit 1; }

if git rev-parse -q --verify "refs/tags/v$version" >/dev/null; then
    echo "release: v$version is already tagged; bump CHANGELOG.md first" >&2
    exit 1
fi

notes=$(mktemp)
sed -n "/^## \[$version\]/,/^## \[/p" CHANGELOG.md | sed '$d' >"$notes"

echo "releasing v$version"
if [ "$dry_run" -eq 1 ]; then
    echo "--- notes ---"
    cat "$notes"
    exit 0
fi

git tag -a "v$version" -m "v$version" 
git push -q origin main --tags
gh release create "v$version" --title "v$version" --notes-file "$notes"
