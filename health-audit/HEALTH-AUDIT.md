# Skill Health Audit Guide

Regular audit checklist for maintaining quality across all skills in the AI-HUB-Portal.

## When to Run

- **Quarterly**: Review all skills for accuracy and relevance
- **After major changes**: When project tech stack or patterns change
- **Before onboarding**: Ensure documentation is current for new team members
- **Post-incident**: If production issues reveal documentation gaps

## Quick Health Check

Run automated validation:

```bash
# Validate YAML frontmatter
node .github/skills/health-audit/validate-frontmatter.js

# Check cross-references
node .github/skills/health-audit/check-cross-refs.js

# Count tokens in skills
node .github/skills/health-audit/count-tokens.js
```

## Manual Audit Checklist

### 1. YAML Frontmatter Validation

For each skill, verify:

- [ ] Has `name` field (lowercase, hyphens, max 64 chars)
- [ ] Has `description` field (clear, includes "when to use", max 1024 chars)
- [ ] Has `version` field (semantic versioning: 1.0.0)
- [ ] Description mentions trigger scenarios
- [ ] Name matches directory name

**Auto-check**: `node health-audit/validate-frontmatter.js`

### 2. Structure Quality

Each SKILL.md should have:

- [ ] "When to Use" section with 3-5 specific scenarios
- [ ] "Quick Start" or similar with minimal example
- [ ] "Related Skills" section referencing 2-5 other skills
- [ ] "Workflow Integration" or similar showing skill in context
- [ ] "Supporting Files" section listing referenced documents
- [ ] "Best Practices" (DO/DON'T) section

### 3. Size Compliance

- [ ] Main SKILL.md is 150-250 lines (~200-325 tokens)
- [ ] Supporting files properly extracted for on-demand loading
- [ ] No single file exceeds 5,000 tokens unless it's a reference doc

**Auto-check**: `node health-audit/count-tokens.js`

### 4. Cross-Reference Integrity

All referenced files exist:

- [ ] Supporting files in same directory exist
- [ ] Referenced config files (e.g., `vitest.config.ts`) exist
- [ ] Links to other skills are valid
- [ ] External docs (specs, design docs) haven't moved

**Auto-check**: `node health-audit/check-cross-refs.js`

### 5. Content Accuracy

- [ ] Code examples use current project patterns
- [ ] Commands match actual npm scripts in package.json
- [ ] File paths reflect current project structure
- [ ] Technology versions are up-to-date
- [ ] No references to deprecated tools or practices

### 6. Progressive Disclosure

- [ ] Metadata (name/description) is concise
- [ ] Main SKILL.md has essential info only
- [ ] Detailed patterns extracted to separate files
- [ ] Templates and examples in supporting files
- [ ] Clear "See: filename.md" references

### 7. Practical Usefulness

- [ ] Examples are copy-pasteable
- [ ] Commands can be run as-is
- [ ] Troubleshooting covers real issues
- [ ] "When to Use" matches actual scenarios

## Skill-Specific Checks

### Testing Skills (testing, api-testing, i18n)

- [ ] Test examples run without errors
- [ ] Mock patterns match current auth setup
- [ ] Test file paths reflect actual structure

### Infrastructure Skills (ci-cd, deployment, monitoring)

- [ ] Secrets/env vars match current setup
- [ ] Azure resource names are current
- [ ] Alert thresholds match SLAs

### Database Skill

- [ ] Entity schemas match data-model.md
- [ ] Connection strings format is correct
- [ ] Seed data is realistic

## Coverage Analysis

### Required Skills Present

- [ ] Testing (unit/integration)
- [ ] E2E testing (Playwright)
- [ ] API testing
- [ ] Code review
- [ ] Deployment
- [ ] Monitoring
- [ ] CI/CD
- [ ] Database/data layer
- [ ] i18n validation

### Skill Gaps

Identify missing skills based on:

- Production incidents without runbooks
- Repeated questions in team chat
- Undocumented workflows
- New technologies added to stack

## Quality Metrics

### Per Skill

| Metric | Target | How to Check |
|--------|--------|--------------|
| Main file size | 150-250 lines | `wc -l SKILL.md` |
| Token count | 200-325 tokens | `count-tokens.js` |
| Has frontmatter | Yes | `validate-frontmatter.js` |
| Cross-refs valid | 100% | `check-cross-refs.js` |
| Last updated | < 6 months | `git log SKILL.md` |

### Overall

| Metric | Target | How to Check |
|--------|--------|--------------|
| Total skills | 8-15 | `ls -1 .github/skills` |
| Skills with "Related Skills" | 100% | Manual grep |
| Skills with examples | 100% | Manual review |
| Broken references | 0 | `check-cross-refs.js` |

## Remediation

### Outdated Content

1. Review git log to see what changed
2. Update code examples to current patterns
3. Update file paths if structure changed
4. Bump version number (patch for minor fixes)

### Missing Skills

1. Identify gap from production issues
2. Create skill using existing templates
3. Link from related skills
4. Add to README.md skill list

### Oversized Skills

1. Identify extractable content (patterns, examples, reference)
2. Create supporting files
3. Update main SKILL.md with references
4. Verify token reduction

## Audit Log Template

Document audit results:

```markdown
# Skill Health Audit - YYYY-MM-DD

**Auditor**: [Name]
**Scope**: [All skills | Specific skills]

## Summary

- Total skills audited: X
- Issues found: Y
- Issues fixed: Z

## Issues Found

### Critical
- [Skill name]: [Issue description]

### Minor
- [Skill name]: [Issue description]

## Actions Taken

- [Action 1]
- [Action 2]

## Recommendations

- [Recommendation 1]
- [Recommendation 2]

## Next Audit

Scheduled for: [Date]
```

## Automation

### Pre-commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Validate skills before commit

node .github/skills/health-audit/validate-frontmatter.js
if [ $? -ne 0 ]; then
  echo "❌ Skill frontmatter validation failed"
  exit 1
fi

node .github/skills/health-audit/check-cross-refs.js
if [ $? -ne 0 ]; then
  echo "❌ Cross-reference validation failed"
  exit 1
fi

echo "✅ Skill validation passed"
```

### CI/CD Integration

Add to `.github/workflows/validate-skills.yml`:

```yaml
name: Validate Skills

on:
  pull_request:
    paths:
      - '.github/skills/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Validate frontmatter
        run: node .github/skills/health-audit/validate-frontmatter.js
      - name: Check cross-references
        run: node .github/skills/health-audit/check-cross-refs.js
      - name: Count tokens
        run: node .github/skills/health-audit/count-tokens.js
```

## Best Practices

### DO:
✅ Run automated checks before committing skill changes
✅ Update skills when tech stack changes
✅ Version skills with semantic versioning
✅ Document audit findings
✅ Fix critical issues immediately

### DON'T:
❌ Skip audits for "small" changes
❌ Let skills go > 6 months without review
❌ Ignore broken cross-references
❌ Add skills without following templates
❌ Forget to update related skills when one changes
