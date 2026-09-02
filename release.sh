#!/usr/bin/env bash

# Script for automated releases

# Prerequisites:
# - existing git tag with current version
# - pyproject.toml with project `version` and `name` entry
# - CHANGELOG.md with unreleased section containing current changes
# - release branch which can be merged into from development branch

# Will do the following:
# - Retrieve current version from latest git tag
# - Release a new version based on the specified version bump type:
#   - Bump version in pyproject.toml
#   - Update CHANGELOG.md
#   - Commit changes to development branch
#   - Merge development branch into release branch
#   - Create git tag for new version
# - Prepare a GitHub release draft with changelog entries
# - Prepare for next development version:
#   - Bump minor version in pyproject.toml and set to .0.dev
#   - Update CHANGELOG.md
#   - Commit changes to development branch


human_readable_project_name="Metadata API"  # Used in GitHub release title

######################################################
# Define and parse command line options
######################################################

# Default values
version_bump="patch"
development_branch="dev"
release_branch="main"

# Define help message
show_help() {
  echo "Usage: $0 [-h] [-v <major|minor|patch>] [-d <development_branch>] [-r <release_branch>]"
  echo ""
  echo "Options:"
  echo "  -h                Show this help message and exit"
  echo "  -v <type>         Bump version: major, minor, or patch (default: patch)"
  echo "  -d <branch>       Development branch name (default: dev)"
  echo "  -r <branch>       Release branch name (default: main)"
}

# Parse command line options
while getopts "hv:d:r:" opt; do
  case $opt in
    h)
      show_help
      exit 0
      ;;
    v)
      if [[ "$OPTARG" =~ ^(major|minor|patch)$ ]]; then
        version_bump="$OPTARG"
      else
        echo "Invalid version bump type: $OPTARG"
        show_help
        exit 1
      fi
      ;;
    d)
      development_branch="$OPTARG"
      ;;
    r)
      release_branch="$OPTARG"
      ;;
    *)
      show_help
      exit 1
      ;;
  esac
done


######################################################
# Helpers
######################################################

# Define colors used in messages
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m'

print_abort_commit() {
  echo -e "Commit aborted. You can commit later or revert the changes:\n"
  echo -e "${YELLOW}git restore --source=HEAD --staged --worktree pyproject.toml CHANGELOG.md${NC}"
}

print_push_reminder_and_exit() {
echo -e "\nDon't forget to push the changes:\n"
  if [[ "$1" == "all" ]]; then
    echo -e "${YELLOW}git push origin --all && git push origin --tags${NC}"
  else
    echo -e "${YELLOW}git push origin && git push origin --tags${NC}"
  fi
  exit 0
}

error_exit() {
  echo -e "${RED}Error: $1${NC}"
  exit 1
}

######################################################
# Determine current and new version
######################################################

# Get current version from latest git tag
current_version=$(git tag | sort -V | tail -n 1)
# Strip v. from major if present
current_version=${current_version#v}

IFS='.' read -r major minor patch <<< "$current_version"

# Create new version based on bump type
case $version_bump in
  major)
    major=$((major + 1))
    minor=0
    patch=0
    ;;
  minor)
    minor=$((minor + 1))
    patch=0
    ;;
  patch)
    patch=$((patch + 1))
    ;;
esac
new_version="$major.$minor.$patch"

# Get project name from pyproject.toml
project_name=$(grep "^name = " pyproject.toml | cut -d '"' -f 2)

# Prompt for confirmation
echo -e "Bumping ${YELLOW}$project_name${NC} ${YELLOW}$current_version${NC} --> ${GREEN}$new_version${NC} ($version_bump update)"
read -p "Proceed with release? (y/n): " confirm
if [[ "$confirm" != "y" ]]; then
  echo "Release aborted. No changes made."
  exit 0
fi

#####################################################
# Determine GitHub repository URL
#####################################################

# Get repository URL and format it into https://github.com/{organization}/{repository}
repository_url=$(git config --get remote.origin.url)
# Remove .git suffix if present
repository_url=${repository_url%.git}
# Extract organization/repository from SSH or HTTPS remote URL
if [[ "$repository_url" =~ ^git@github\.com:(.*)/(.*)$ ]]; then
  org="${BASH_REMATCH[1]}"
  repo="${BASH_REMATCH[2]}"
  github_url="https://github.com/${org}/${repo}"
elif [[ "$repository_url" =~ ^https://github\.com/(.*)/(.*)$ ]]; then
  org="${BASH_REMATCH[1]}"
  repo="${BASH_REMATCH[2]}"
  github_url="https://github.com/${org}/${repo}"
else
  github_url="$repository_url"
fi

#####################################################
# Perform release
#####################################################

# Check that current branch is development branch
current_branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$current_branch" != "$development_branch" ]]; then
  echo "Error: You must be on the '$development_branch' branch to perform a release."
  echo "Release aborted. No changes made."
  exit 1
fi

# Check required files
[[ -f pyproject.toml ]] || error_exit "pyproject.toml not found."
[[ -f CHANGELOG.md ]] || error_exit "CHANGELOG.md not found."

# Check for uncommitted changes
if [[ -n $(git status --porcelain) ]]; then
  echo -e "${YELLOW}Warning: You have uncommitted changes. Please commit or stash them before releasing.${NC}"
  read -p "Continue anyway? (y/n): " continue_release
  [[ "$continue_release" == "y" ]] || exit 1
fi

# Save current branch to restore later
original_branch=$(git rev-parse --abbrev-ref HEAD)

# Update version in pyproject.toml
echo -e "Updating pyproject.toml"
sed -i "s/^version = \".*\"/version = \"$new_version\"/" pyproject.toml

# Update CHANGELOG.md
echo -e "Updating CHANGELOG.md"
today=$(date +%Y-%m-%d)
sed -i "0,/## \[unreleased\]/s/## \[unreleased\]/## [$new_version] - $today/" CHANGELOG.md
sed -i "/^\[unreleased\]:/c\\[$new_version]: $github_url/releases/tag/v$new_version" CHANGELOG.md

# Add and commit changes
git add pyproject.toml CHANGELOG.md
echo -e "\nChanges to be committed:"
git diff --cached
read -p "$(echo -e "\nCommit these changes to ${GREEN}$release_branch${NC} and create tag ${GREEN}v$new_version${NC}? (y/n): ")" confirm_commit
if [[ "$confirm_commit" != "y" ]]; then
  print_abort_commit
  exit 0
fi
git commit -m "Bump version to $new_version"

# Merge to release branch
if ! git checkout "$release_branch"; then
  error_exit "Failed to checkout branch '$release_branch'. Please resolve any issues and try again."
fi
if ! git merge "$development_branch"; then
  error_exit "Failed to merge branch '$development_branch' into '$release_branch'. Please resolve any issues and try again."
fi

# Create git tag
git tag "v$new_version"


######################################################
# Create GitHub release draft
######################################################

url_encoded_project_name=$(echo "$human_readable_project_name" | sed 's/ /%20/g')
release_draft_url="${github_url}/releases/new?tag=v${new_version}&title=${url_encoded_project_name}%20v${new_version}"

# Create body with latest entries in CHANGELOG.md
body=$(awk -v ver="$new_version" '
  $0 ~ "^## \\[" ver "\\]" {found=1; next}
  found && $0 ~ /^## \[/ {exit}
  found {print}
' CHANGELOG.md)

# Flatten wrapped list items into single lines while preserving headings and blank lines
body=$(echo "$body" | awk '
function flush_item() {
  if (item != "") {
    gsub(/[ \t\r\n]+/, " ", item)
    sub(/^ /, "", item)
    sub(/ $/, "", item)
    print item
    item=""
  }
}
{
  if ($0 ~ /^- /) {
    flush_item()
    item=$0
    next
  }

  if (item != "" && $0 ~ /^[[:space:]]+/ && $0 !~ /^### / && $0 !~ /^## / && $0 !~ /^- /) {
    line=$0
    sub(/^[[:space:]]+/, "", line)
    item=item " " line
    next
  }

  flush_item()
  print
}
END { flush_item() }
')

echo -e "\n${GREEN}Here's a GitHub release draft:${NC}\n"
if [[ -z "$body" ]]; then
  # Empty body case
  echo "$release_draft_url"
  echo -e "\n${YELLOW}WARNING: Failed to create a release description because no changelog entries were found for version $new_version.${NC}"
else
  # Encode body for URL
  body_escaped=$(echo "$body" | sed ':a;N;$!ba;s/\n/%0A/g' | sed 's/#/%23/g' | sed 's/ /%20/g' | sed 's/`/%60/g')
  release_draft_with_body="${release_draft_url}&body=${body_escaped}"
  echo "$release_draft_with_body"
  echo -e "\n${GREEN}If the above URL is not working, you can use this one and copy-paste the changelog manually:${NC}\n"
  echo -e "$release_draft_url\n"
  echo "$body"
  echo -e "\n------------------------------------------------------------\n"
fi

######################################################
# Prepare for next development version
######################################################

read -p "$(echo -e "\nProceed to prepare for next development version ${GREEN}$next_dev_version${NC}? (y/n): ")" confirm_next
if [[ "$confirm_next" != "y" ]]; then
  echo "Preparation for next development version aborted."
  echo "Release $new_version created."
  print_push_reminder_and_exit
fi
git checkout "$development_branch"

# Update version in pyproject.toml
echo -e "Updating pyproject.toml"
next_dev_version="$major.$((minor + 1)).0.dev"
sed -i "s/^version = \".*\"/version = \"$next_dev_version\"/" pyproject.toml

# Update CHANGELOG.md
echo -e "Updating CHANGELOG.md"
# Add new ## [unreleased] section above the latest version header
sed -i "/^## \[$new_version\]/i## [unreleased]\n" CHANGELOG.md
# Add link for new version at the bottom
escaped_github_url=$(echo "$github_url" | sed 's/\//\\\//g')
sed -i "/^\[$new_version\]:/i\\[unreleased]: ${escaped_github_url}\/compare/v$new_version...dev/" CHANGELOG.md

# Show git diff for confirmation
git add pyproject.toml CHANGELOG.md
echo -e "\nChanges to be committed for next development version:"
git diff --cached
read -p "$(echo -e "\nCommit these changes to ${GREEN}$development_branch${NC} for next development version? (y/n): ")" confirm_next
if [[ "$confirm_next" != "y" ]]; then
  print_abort_commit
  print_push_reminder_and_exit
fi
git commit -m "Prepare for next development version $next_dev_version"

echo -e "\n${GREEN}Success!${NC}"
echo -e "Release $new_version created and prepared for next development version $next_dev_version."
print_push_reminder_and_exit all


# Restore original branch
git checkout "$original_branch"
