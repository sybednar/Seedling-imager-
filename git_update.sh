
#!/bin/bash
# Usage: ./git_update.sh -m "Commit message" -v v0.1.0

usage() {
    echo "Usage: $0 -m <commit_message> [-v <version_tag>]"
    exit 1
}

commit_message=""
version_tag=""

while getopts ":m:v:" opt; do
    case $opt in
        m) commit_message="$OPTARG" ;;
        v) version_tag="$OPTARG" ;;
        *) usage ;;
    esac
done

if [ -z "$commit_message" ]; then
    usage
fi

cd /home/sybednar/Seedling_Imager/seedling_imager_controller || { echo "Directory not found"; exit 1; }

git add -A
git commit -m "$commit_message" || echo "Nothing to commit."
git push origin main

if [ -n "$version_tag" ]; then
    if git rev-parse "$version_tag" >/dev/null 2>&1; then
        echo "Tag $version_tag already exists."
    else
        git tag "$version_tag" -m "$commit_message"
        git push origin "$version_tag"
    fi
fi

echo "Update complete."
