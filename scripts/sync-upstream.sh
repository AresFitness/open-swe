#!/usr/bin/env bash
# sync-upstream.sh — Merge latest changes from upstream langchain-ai/open-swe into our fork.
#
# This fetches upstream/main and merges it into our main branch.
# If there are conflicts, it aborts and reports them.
#
# Usage:
#   ./scripts/sync-upstream.sh          # merge upstream into current branch
#   ./scripts/sync-upstream.sh --dry    # just check what's new, don't merge

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_DIR}"

DRY_RUN=false
if [ "${1:-}" = "--dry" ]; then
    DRY_RUN=true
fi

# Ensure upstream remote exists
if ! git remote get-url upstream &>/dev/null; then
    echo "Adding upstream remote..."
    git remote add upstream https://github.com/langchain-ai/open-swe.git
fi

echo "Fetching upstream..."
git fetch upstream 2>&1

# Check how many commits behind
BEHIND=$(git rev-list --count HEAD..upstream/main 2>/dev/null || echo "0")
AHEAD=$(git rev-list --count upstream/main..HEAD 2>/dev/null || echo "0")

echo ""
echo "Status: ${BEHIND} commits behind upstream, ${AHEAD} commits ahead (our customizations)"

if [ "${BEHIND}" = "0" ]; then
    echo "✅ Already up to date with upstream."
    exit 0
fi

echo ""
echo "New upstream commits:"
git log --oneline HEAD..upstream/main | head -20

if [ "${DRY_RUN}" = true ]; then
    echo ""
    echo "(dry run — no changes made)"
    exit 0
fi

echo ""
echo "Merging upstream/main..."
if git merge upstream/main --no-edit 2>&1; then
    echo ""
    echo "✅ Merged ${BEHIND} commits from upstream."
    echo ""
    echo "Run tests: .venv/bin/python -m pytest tests/ -q"
    echo "Push:      git push origin main"
else
    echo ""
    echo "❌ Merge conflicts detected. Resolve manually:"
    git diff --name-only --diff-filter=U
    echo ""
    echo "After resolving: git add . && git commit && git push origin main"
    exit 1
fi
