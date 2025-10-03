#!/bin/bash

# GitHub Actions script to generate AI-powered PR descriptions using Amazon Bedrock
# This script analyzes commit history and generates formatted PR descriptions matching LISA's changelog format

set -e  # Exit on any error

RELEASE_TAG="$1"

if [ -z "$RELEASE_TAG" ]; then
    echo "Error: Release tag is required as first argument"
    exit 1
fi

echo "🔍 Fetching commit history and PR details for release branch (comparing against main)..."

# Function to check if GitHub CLI is properly authenticated
check_gh_auth() {
    if ! command -v gh >/dev/null 2>&1; then
        return 1
    fi

    # Check authentication status with timeout
    if timeout 10s gh auth status >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to get PR info for a commit
get_commit_pr_info() {
    local commit_hash="$1"
    local commit_subject="$2"
    local commit_author="$3"

    # Try to find associated PRs using GitHub CLI (only if authenticated)
    if [[ "$GH_AUTHENTICATED" == "true" ]]; then
        # Use timeout to prevent hanging and suppress errors
        local pr_info=$(timeout 15s gh pr list --search "$commit_hash" --state merged --json number,title,body --limit 1 2>/dev/null || echo "[]")

        if [[ "$pr_info" != "[]" ]] && [[ -n "$pr_info" ]] && [[ "$pr_info" != *"error"* ]]; then
            local pr_number=$(echo "$pr_info" | jq -r '.[0].number // empty' 2>/dev/null)
            local pr_title=$(echo "$pr_info" | jq -r '.[0].title // empty' 2>/dev/null)
            local pr_body=$(echo "$pr_info" | jq -r '.[0].body // empty' 2>/dev/null)

            if [[ -n "$pr_number" && -n "$pr_title" && "$pr_number" != "null" ]]; then
                echo "- $commit_subject ($commit_author)"
                echo "  PR #$pr_number: $pr_title"

                if [[ -n "$pr_body" && "$pr_body" != "null" ]]; then
                    # Truncate very long PR descriptions and clean up formatting
                    local cleaned_body=$(echo "$pr_body" | head -c 500 | tr '\n' ' ' | tr -s ' ')
                    echo "  $cleaned_body"
                fi
                return 0
            fi
        fi
    fi

    # Fallback to commit message only
    echo "- $commit_subject ($commit_author)"
    return 1
}

# Check GitHub CLI authentication status
if check_gh_auth; then
    echo "✅ GitHub CLI authenticated - will attempt PR lookups"
    GH_AUTHENTICATED="true"
else
    echo "⚠️  GitHub CLI not available or not authenticated - using commit messages only"
    echo "   To enable PR lookups, run: gh auth login"
    GH_AUTHENTICATED="false"
fi

# Get commits with PR information
COMMITS=""
commit_count=0
pr_found_count=0
echo "📡 Looking up commit information..."

# Determine the correct main branch reference
MAIN_REF=""
if git rev-parse --verify main >/dev/null 2>&1; then
    MAIN_REF="main"
elif git rev-parse --verify origin/main >/dev/null 2>&1; then
    MAIN_REF="origin/main"
elif git rev-parse --verify refs/remotes/origin/main >/dev/null 2>&1; then
    MAIN_REF="refs/remotes/origin/main"
else
    echo "❌ Cannot find main branch reference. Available branches:"
    git branch -a 2>/dev/null || echo "No branches found"
    echo "Using develop branch as fallback for commit analysis"
    MAIN_REF="HEAD~50"  # Fallback to last 50 commits
fi

echo "🔍 Using main branch reference: $MAIN_REF"

while IFS='|' read -r hash subject author; do
    if [[ -n "$hash" ]]; then
        # Get commit info and handle return code properly with set -e
        commit_info=$(get_commit_pr_info "$hash" "$subject" "$author") || commit_return_code=$?

        # Check if PR info was found (return code 0 means PR found)
        if [[ -z "$commit_return_code" ]]; then
            pr_found_count=$((pr_found_count + 1))
        fi

        if [[ -n "$COMMITS" ]]; then
            COMMITS="$COMMITS"$'\n'"$commit_info"
        else
            COMMITS="$commit_info"
        fi
        commit_count=$((commit_count + 1))

        # Show progress for long-running operations
        if [[ $((commit_count % 3)) -eq 0 ]]; then
            echo "   ... processed $commit_count commits"
        fi

        # Reset the return code variable for next iteration
        unset commit_return_code
    fi
done < <(git log $MAIN_REF..HEAD --pretty=format:"%H|%s|%an" --no-merges 2>/dev/null || echo "")

echo "✅ Processed $commit_count commits"
if [[ "$GH_AUTHENTICATED" == "true" ]]; then
    echo "📊 Found PR information for $pr_found_count commits"
fi

# Get unique contributors from commits for acknowledgements (use email to extract GitHub username)
CONTRIBUTORS=$(git log $MAIN_REF..HEAD --pretty=format:"%ae" --no-merges 2>/dev/null | sort -u | sed 's/@.*$//' | sed 's/^/* @/' | tr '\n' '\n' || echo "")

# Get the current version from VERSION file to use as previous version in changelog
if [ -f "VERSION" ]; then
    PREVIOUS_VERSION="v$(cat VERSION)"
else
    # Fallback to git tag if VERSION file doesn't exist
    PREVIOUS_VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "unknown")
fi

# If no commits, use a default message
if [ -z "$COMMITS" ]; then
    COMMITS="- Version update to $RELEASE_TAG"
    CONTRIBUTORS="* @github_actions_lisa"
fi

echo "📝 Found commits:"
echo -e "$COMMITS"
echo ""
echo "👥 Contributors: $CONTRIBUTORS"
echo "🏷️ Previous version: $PREVIOUS_VERSION"
echo ""

# Create a prompt for Bedrock to generate PR description matching LISA's changelog format
PROMPT="Please create a comprehensive pull request description for the LISA software release that covers ALL commits and PRs provided. Use this format structure:

# $RELEASE_TAG

## Key Features

### [Feature Name - create as many sections as needed]
[Description of the feature and its capabilities]
**[Subcategory if applicable]:**
- **[Component]**: [Description of enhancement]
- **[Component]**: [Description of enhancement]

### [Another Feature Name - repeat for each major feature/PR]
[Description and details]

### [Continue for ALL features found in the commits]
[Ensure every significant commit/PR is represented]

## Key Changes
- **[Category]**: [Description of change]
- **[Category]**: [Description of change]
- **[Category]**: [Description of change]
[Include ALL significant changes, not just a few examples]

## Acknowledgements
$CONTRIBUTORS

**Full Changelog**: https://github.com/awslabs/LISA/compare/$PREVIOUS_VERSION..$RELEASE_TAG

---

IMPORTANT: You MUST analyze and include ALL of the following commits/PRs in your response:
$COMMITS

Requirements:
1. Create a separate Key Features section for EVERY major feature, enhancement, or significant PR listed above
2. Do NOT limit yourself to just 2-3 features - cover ALL significant changes
3. Group related smaller commits together into logical feature sections
4. Use descriptive, professional language for each feature section
5. Ensure every PR mentioned above gets appropriate coverage in the description
6. List ALL significant changes in the Key Changes section
7. If there are many commits, prioritize PRs with detailed descriptions first, then group commits by theme

Generate a comprehensive description that covers ALL the provided commits and PRs now:"

# Call Bedrock to generate description
echo "🤖 Generating PR description with Bedrock Claude 3 Haiku..."

# Use jq to properly construct the JSON payload to avoid escaping issues
BEDROCK_PAYLOAD=$(jq -n \
  --arg prompt "$PROMPT" \
  '{
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 3000,
    "messages": [
      {
        "role": "user",
        "content": $prompt
      }
    ]
  }')

RESPONSE=$(aws bedrock-runtime invoke-model \
    --model-id "anthropic.claude-3-haiku-20240307-v1:0" \
    --body "$BEDROCK_PAYLOAD" \
    --cli-binary-format raw-in-base64-out \
    /tmp/bedrock_response.json)

# Extract the generated description from the response
DESCRIPTION=$(jq -r '.content[0].text' /tmp/bedrock_response.json)

# Fallback description if Bedrock fails - use LISA changelog format
if [ -z "$DESCRIPTION" ] || [ "$DESCRIPTION" = "null" ]; then
    echo "⚠️  Bedrock response failed, using fallback description"
    DESCRIPTION="# $RELEASE_TAG

## Key Features

### System Updates
This release includes version updates and system improvements to enhance LISA's stability and performance.

## Key Changes
- **Version Management**: Updated version numbers across all package files
- **Release Process**: Automated release branch creation and versioning
- **System Maintenance**: General system updates and improvements

## Acknowledgements
$CONTRIBUTORS

**Full Changelog**: https://github.com/awslabs/LISA/compare/$PREVIOUS_VERSION..$RELEASE_TAG"
else
    echo "✅ Successfully generated PR description with Bedrock"
fi

echo ""
echo "📋 Generated PR description:"
echo "----------------------------------------"
echo "$DESCRIPTION"
echo "----------------------------------------"

# Save description to GitHub Actions output
{
    echo 'DESCRIPTION<<EOF'
    echo "$DESCRIPTION"
    echo 'EOF'
} >> $GITHUB_OUTPUT
