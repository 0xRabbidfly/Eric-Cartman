---
name: code-review
description: Comprehensive constitutional code review against project standards, design specifications, and best practices. Use when reviewing code quality, before major releases, after significant refactoring, or when technical debt assessment is needed.
version: 1.0.0
---

# Skill Instructions

Perform a comprehensive constitutional code review against project standards, design specifications, and best practices.

## Description

This skill conducts a systematic code quality review of the AI Hub Portal codebase, checking compliance with constitutional rules, architectural design, and coding standards. It identifies issues, ranks them by priority, and creates actionable sprint plans for remediation.

## When to Use

- User requests "code review", "review the code", "check code quality"
- User asks to "check against constitution", "validate against standards"
- Before major releases or deployments
- After significant feature additions or refactoring
- When technical debt assessment is needed
- User asks "what needs fixing" or "are we following best practices"

## Instructions

### Phase 1: Load Constitutional Documents

Read and analyze the project's constitutional documents to establish review criteria:

1. **Primary Constitution**: `.github/copilot-instructions.md`
   - Core principles and non-negotiables
   - Tech stack requirements
   - Security mandates
   - Code style conventions
   - Architecture patterns

2. **Technical Specification**: `specs/001-portal-mvp/plan.md`
   - Agreed architecture decisions
   - Technology selections
   - File structure requirements
   - API contracts
   - Data models

3. **Design Documentation**: `design/` or `docs/` directory
   - Architecture documentation
   - Component catalog
   - Content structure specifications
   - Information architecture
   - Requirements baseline

### Phase 2: Systematic Codebase Analysis

Analyze code against constitutional requirements:

#### TypeScript & Type Safety
- [ ] Search for `any` types: `grep_search` for `: any` or `as any`
- [ ] Verify strict mode enabled in `tsconfig.json`
- [ ] Check all exported functions have explicit return types
- [ ] Validate no `@ts-ignore` or `@ts-nocheck` comments

#### Security & Authentication
- [ ] Search for `localStorage`, `sessionStorage` usage (forbidden)
- [ ] Verify no secrets in code: search for `password`, `secret`, `key`, `token` in string literals
- [ ] Check auth implementation uses server-side sessions
- [ ] Verify Microsoft Graph calls use delegated tokens (On-Behalf-Of)
- [ ] Check security headers in `next.config.js` (CSP, HSTS, X-Frame-Options)

#### Logging & Error Handling
- [ ] Search for `console.log`, `console.error`, `console.warn` in production code
- [ ] Verify structured logging with logger utility
- [ ] Check error messages don't expose stack traces to client
- [ ] Validate no sensitive data in logs (tokens, PII, raw documents)

#### React & Next.js Best Practices
- [ ] Verify Server Components by default (check for unnecessary `'use client'`)
- [ ] Check data fetching happens server-side when possible
- [ ] Validate proper use of Next.js App Router patterns
- [ ] Check for client-side waterfalls

#### Internationalization (i18n)
- [ ] Search for hardcoded user-visible strings in components
- [ ] Verify all UI text uses `useTranslations()` or `getTranslations()`
- [ ] Check `messages/en.json` and `messages/fr.json` have matching keys
- [ ] Validate no English text in JSX without translation keys

#### Code Quality
- [ ] Check for relative imports (`../`) vs @ alias (`@/`)
- [ ] Verify consistent naming conventions (PascalCase components, camelCase functions)
- [ ] Check for inline styles with hardcoded values (should use CSS variables)
- [ ] Validate ARIA labels on interactive elements

#### Testing & Validation
- [ ] Run `npm run type-check` to verify TypeScript compilation
- [ ] Run `npm test` to execute test suite
- [ ] Run `npm run build` to verify production build
- [ ] Check test coverage meets minimum thresholds

#### Environment & Configuration
- [ ] Verify `.env.local.example` exists with all required variables
- [ ] Check environment variable validation (if implemented)
- [ ] Validate no `.env` files committed to git
- [ ] Check `.gitignore` properly excludes sensitive files

#### Deployment Readiness
- [ ] Verify `Dockerfile` exists for containerization
- [ ] Check `next.config.js` has `output: 'standalone'` for Docker
- [ ] Validate `.dockerignore` excludes unnecessary files
- [ ] Check production environment requirements documented

### Phase 3: Issue Classification & Ranking

Classify all discovered issues using this priority framework:

**P0 - Critical (Blocking)**: Constitutional violations that break security, functionality, or core principles
- Security vulnerabilities (exposed secrets, auth bypass)
- TypeScript `any` types in strict mode codebase
- Missing required environment variables
- Production logging to console instead of structured logger
- Hardcoded credentials or secrets

**P1 - High Priority**: Significant issues impacting quality, maintainability, or user experience
- Missing internationalization (hardcoded strings)
- Unnecessary client components (performance impact)
- Missing deployment infrastructure (Dockerfile)
- Incomplete security headers
- Auth implementation not using delegated tokens

**P2 - Medium Priority**: Code quality issues that should be addressed
- Missing explicit return types
- Inconsistent import patterns (relative vs @alias)
- Inline styles with magic numbers
- Missing ARIA labels
- No environment variable validation

**P3 - Low Priority**: Nice-to-have improvements
- Missing .prettierignore
- Lack of granular error boundaries
- Limited telemetry/monitoring
- Documentation gaps

### Phase 4: Generate Sprint Plan

Create actionable sprint plans for remediation:

1. **Issue Summary Table**:
   ```
   | Priority | Count | Examples |
   |----------|-------|----------|
   | P0       | X     | Issue1, Issue2 |
   | P1       | Y     | Issue3, Issue4 |
   | P2       | Z     | Issue5, Issue6 |
   ```

2. **Sprint Breakdown**:
   - **Sprint 1 (P0)**: Critical fixes (estimate 1-2 hours)
   - **Sprint 2 (P1)**: High priority (estimate 2-4 hours)
   - **Sprint 3 (P2)**: Medium priority (estimate 1-2 hours)
   - **Sprint 4 (P3)**: Low priority (estimate 1-2 hours)

3. **Task List for Each Sprint**:
   ```markdown
   ### Sprint 1: Critical Fixes
   - [ ] Fix TypeScript any types in logger.ts (11 occurrences)
   - [ ] Replace all console.* calls with logger utility (20+ files)
   - [ ] Set up test infrastructure with Vitest
   ```

4. **Design Documentation Update Check**:
   - Compare current architecture with `design/AI-HUB-Architecture.md`
   - Check if new components need adding to `design/AI-HUB-component-inventory.md`
   - Verify routes match `design/AI-HUB-IA-routemap.md`
   - If mismatches found, create design update todo list:
     ```markdown
     ### Design Documentation Updates Needed
     - [ ] Update architecture diagram with new Azure services
     - [ ] Add new components to inventory (EnvironmentValidator)
     - [ ] Document new API endpoints in contracts
     ```

### Phase 5: Report Generation

Generate a comprehensive review report:

```markdown
## Code Review Summary

**Review Date**: [Date]
**Constitution Version**: [Version from copilot-instructions.md]
**Codebase Status**: [Pass/Fail percentage]

### Constitutional Compliance
- ✅ TypeScript Strict Mode: [Status]
- ⚠️ Bilingual Support: [Status with details]
- ✅ Security Headers: [Status]
- ❌ Logging Standards: [Status with violation count]

### Issues Discovered: [Total Count]
[Detailed breakdown by priority]

### Sprint Plan
[Sprint 1, 2, 3, 4 task lists]

### Design Document Status
[List of design docs that need updating]

### Next Steps
1. [Immediate action items]
2. [Follow-up recommendations]
```

### Phase 6: Interactive Options

After presenting the report, offer these options:

1. **"Start Sprint X"**: Execute the sprint plan for the specified priority level
2. **"Show details for [Issue]"**: Provide deep dive into specific issue
3. **"Update design docs"**: Help update outdated design documentation
4. **"Generate test plan"**: Create test cases for identified gaps
5. **"Create GitHub issues"**: Generate issue tickets for tracking

## Best Practices

- Always run tests and type-check before declaring completion
- Batch independent changes for efficiency (use multi_replace_string_in_file)
- Commit changes after each sprint completion
- Include constitutional compliance percentage in reports
- Flag breaking changes that need design review
- Suggest architectural improvements when patterns violate principles
- Be specific with file paths and line numbers in issue reports

## Example Usage

**User**: "Review the code against our standards"

**Expected Flow**:
1. Load constitutional documents (.github/copilot-instructions.md, plan.md, design docs)
2. Systematically analyze codebase (TypeScript, security, i18n, etc.)
3. Classify issues (P0: 3, P1: 4, P2: 5, P3: 3)
4. Generate sprint plans with specific tasks
5. Check if design docs need updates
6. Present comprehensive report
7. Ask: "Ready to start Sprint 1 (P0 critical fixes)?"

## Related Skills

- `testing` - Use to create tests for identified coverage gaps
- `deployment` - Use after code review passes to deploy changes
- `ci-cd` - Integrate code review checks into automated workflows
- `monitoring` - Review production errors to identify code quality issues

## Workflow Integration

Typical code review workflow:

1. **Code complete** → Run this skill for constitutional validation
2. **Issues found** → Fix P0/P1 issues before proceeding
3. **Tests needed** → Use `testing` skill to add coverage
4. **Review passes** → Use `deployment` skill to deploy
5. **Monitor** → Use `monitoring` skill to track production health

## Notes

- This skill combines static analysis with runtime validation
- Respects the constitution as source of truth
- Prioritizes security and type safety over convenience
- Emphasizes actionable, concrete remediation steps
- Maintains traceability to constitutional requirements
