
#!/bin/bash
# Usage:
#   ./git_update.sh -m "Commit message" [-v v0.05] [-b main]
#
# Notes:
# - Default branch: main
# - Tags are optional; if provided, they are created and pushed.

set -euo pipefail

usage() {
    echo "Usage: $0 -m <commit_message> [-v <version_tag>] [-b <branch>]"
    exit 1
}

commit_message=""
version_tag=""
branch="main"

while getopts ":m:v:b:" opt; do
    case $opt in
        m) commit_message="$OPTARG" ;;
        v) version_tag="$OPTARG" ;;
        b) branch="$OPTARG" ;;
        *) usage ;;
    esac
done

if [ -z "$commit_message" ]; then
    usage
fi

REPO_DIR="/home/sybednar/Seedling_Imager/seedling_imager_controller"

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "Error: $REPO_DIR is not a Git repository."
    exit 1
fi

cd "$REPO_DIR"

echo "== Git status =="
git status

# Show untracked files (helpful sanity check)
echo "== Untracked files =="
git ls-files --others --exclude-standard

# Stage all changes (new/modified/deleted)
git add -A

# Commit (if there are staged changes)
if git diff --cached --quiet; then
    echo "Nothing staged; no commit created."
else
    git commit -m "$commit_message"
fi

# Confirm branch exists
if ! git rev-parse --verify "$branch" >/dev/null 2>&1; then
    echo "Branch '$branch' not found. Creating it from current HEAD..."
    git branch "$branch"
fi

echo "Pushing to origin/$branch ..."
git push origin "$branch"

# Optional tag handling
if [ -n "$version_tag" ]; then
    if git rev-parse "$version_tag" >/dev/null 2>&1; then
        echo "Tag '$version_tag' already exists. Skipping tag creation."
    else
        echo "Creating tag '$version_tag' ..."
        git tag "$version_tag" -m "$commit_message"
        echo "Pushing tag '$version_tag' ..."
        git push origin "$version_tag"
    fi
fi

echo "Update complete."
