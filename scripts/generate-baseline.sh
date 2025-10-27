#!/bin/bash
# Generate baseline templates from a specific release tag

set -e

RELEASE_TAG=${1:-$(git describe --tags --abbrev=0)}
BASELINE_DIR="test/cdk/stacks/__baselines__"

echo "Generating baselines from release: $RELEASE_TAG"

# Stash current changes
git stash push -m "Temporary stash for baseline generation"

# Checkout release tag
git checkout "$RELEASE_TAG"

# Install dependencies and build
npm ci
npm run build

# Generate templates
mkdir -p "$BASELINE_DIR"
npm test -- test/cdk/stacks/snapshot.test.ts --testNamePattern="is compatible with baseline"

# Return to previous branch
git checkout -

# Restore stashed changes
git stash pop || true

echo "Baselines generated in $BASELINE_DIR"
