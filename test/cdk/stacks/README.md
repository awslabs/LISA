# Migration Testing

## Overview

The snapshot tests compare current stack templates against baseline templates from previous releases to detect breaking changes.

## Usage

### 1. Generate Baselines from Previous Release

```bash
# Generate from latest release tag
npm run generate-baseline

# Generate from specific release
npm run generate-baseline -- v5.3.0
```

### 2. Run Migration Tests

```bash
npm test -- test/cdk/stacks/snapshot.test.ts
```

### 3. Review Failures

If tests fail, they'll report:

- Removed resources (potential data loss)
- Changed resource types (will cause replacement)

### 4. Update Baselines After Approved Changes

```bash
# Regenerate baselines from current code
npm test -- test/cdk/stacks/snapshot.test.ts
```

## CI/CD Integration

Add to your pipeline:

```yaml
- name: Migration Test
  run: |
    npm run generate-baseline -- ${{ github.event.pull_request.base.ref }}
    npm test -- test/cdk/stacks/snapshot.test.ts
```
