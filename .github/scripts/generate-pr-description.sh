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
done < <(git log main..HEAD --pretty=format:"%H|%s|%an" --no-merges)

echo "✅ Processed $commit_count commits"
if [[ "$GH_AUTHENTICATED" == "true" ]]; then
    echo "📊 Found PR information for $pr_found_count commits"
fi

# Get unique contributors from commits for acknowledgements (use email to extract GitHub username)
CONTRIBUTORS=$(git log main..HEAD --pretty=format:"%ae" --no-merges | sort -u | sed 's/@.*$//' | sed 's/^/* @/' | tr '\n' '\n')

# If no commits, use a default message
if [ -z "$COMMITS" ]; then
    COMMITS="- Version update to $RELEASE_TAG"
    CONTRIBUTORS="* @github_actions_lisa"
fi

echo "📝 Found commits:"
echo -e "$COMMITS"
echo ""
echo "👥 Contributors: $CONTRIBUTORS"
echo ""

# Create a prompt for Bedrock to generate PR description matching LISA's changelog format
PROMPT="Please create a professional pull request description for the LISA software release that follows this EXACT format template:

# $RELEASE_TAG

## Key Features

### [Feature Name 1]
[Description of the feature and its capabilities]
**[Subcategory if needed]:**
- **[Component]**: [Description of enhancement]
- **[Component]**: [Description of enhancement]

### [Feature Name 2]  
[Description of the feature]

## Key Changes
- **[Category]**: [Description of change]
- **[Category]**: [Description of change]
- **[Category]**: [Description of change]

## Acknowledgements
$CONTRIBUTORS

**Full Changelog**: https://github.com/awslabs/LISA/compare/[previous-version]..$RELEASE_TAG

---

Based on these commits from the release:
$COMMITS

Requirements:
1. Use the EXACT format template above with # for version header
2. Group related commits into logical Key Features sections with descriptive subsection names
3. List implementation details in Key Changes as bullet points with bold category labels
4. Use professional, concise language appropriate for a software release
5. Focus on user-facing improvements and system enhancements
6. Include the contributors list and changelog link as shown
7. If there are only version/build commits, create a simple 'System Updates' feature section

Generate the description now:"

# Call Bedrock to generate description
echo "🤖 Generating PR description with Bedrock Claude 3 Haiku..."

# Use jq to properly construct the JSON payload to avoid escaping issues
BEDROCK_PAYLOAD=$(jq -n \
  --arg prompt "$PROMPT" \
  '{
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 1500,
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

**Full Changelog**: https://github.com/awslabs/LISA/compare/[previous-version]..$RELEASE_TAG"
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
