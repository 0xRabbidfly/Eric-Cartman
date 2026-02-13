# GitHub Copilot Custom Skills

This directory contains custom skills for GitHub Copilot Chat to enhance development workflows specific to the AI Hub Portal project.

## What are Custom Skills?

Custom skills extend GitHub Copilot Chat with project-specific knowledge and workflows. They allow you to create reusable AI-powered commands that understand your codebase, architecture, and standards.

**Documentation**:
- [How to Create Custom Skills](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
- [VS Code Agent Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills)

## Available Skills

### 🔍 Code Review (`code-review.md`)

**Purpose**: Comprehensive constitutional code review against project standards

**Triggers**: When you ask Copilot to:
- "Review the code"
- "Check code quality"
- "Validate against constitution"
- "What needs fixing"
- "Run code review against copilot-instructions.md"

**What it does**:
1. ✅ Loads constitutional documents (copilot-instructions.md, plan.md, design docs)
2. 🔍 Systematically analyzes codebase for violations:
   - TypeScript strict mode compliance
   - Security vulnerabilities (no localStorage, no secrets in code)
   - Logging standards (structured logging, no console.*)
   - React/Next.js best practices (Server Components default)
   - Internationalization (bilingual EN/FR support)
   - Code quality (imports, naming, styles, ARIA labels)
3. 🏃 Runs validation commands (type-check, tests, build)
4. 📊 Classifies issues by priority (P0 Critical → P3 Low)
5. 📋 Generates actionable sprint plans
6. 📝 Checks if design documentation needs updates
7. 💬 Offers interactive remediation options

**Example Usage**:
```
You: "Review the code against our standards"

Copilot: [Performs comprehensive analysis]

## Code Review Summary
Constitution Compliance: 75%

Issues Discovered: 15 total
- P0 Critical: 3 (TypeScript any, console.log, no tests)
- P1 High: 4 (hardcoded strings, unnecessary client components)
- P2 Medium: 5 (missing return types, relative imports)
- P3 Low: 3 (prettierignore, error boundaries)

Ready to start Sprint 1 (P0 critical fixes)?
```

**Expected Outcome**:
- Detailed issue report with file paths and line numbers
- Prioritized sprint plans (Sprint 1-4)
- Design document update checklist
- Constitutional compliance score
- Interactive remediation workflow

---

### ✅ Branch Wrapup (`branch-wrapup/`)

**Purpose**: Pre-PR quality gate with 7 verification phases

**Triggers**: When you ask Copilot to:
- "Run verification before PR"
- "Check if code is ready for pull request"
- "Run the verification loop"
- "Validate build and tests"

**What it does**:
1. 🔨 **Build** - Verifies `npm run build` succeeds
2. 📘 **Types** - Runs `npm run type-check` for TypeScript errors
3. 🔍 **Lint** - Checks ESLint rules pass
4. 🧪 **Tests** - Runs test suite with coverage
5. 🔒 **Security** - Scans for constitutional violations (localStorage, secrets, console.log)
6. 🧹 **Hygiene** - Checks imports, styles, ARIA labels
7. 📋 **Diff** - Reviews changed files

**PowerShell Script**:
```powershell
# Run full wrapup (verify + commit)
.\.github\skills\branch-wrapup\verify.ps1

# Quick check (build + types + lint only)
.\.github\skills\branch-wrapup\verify.ps1 -Quick

# Verify only, skip commit
.\.github\skills\branch-wrapup\verify.ps1 -NoCommit
```

**Output Format**:
```
╔══════════════════════════════════════════════════════════════╗
║  Build:      [PASS]                                          ║
║  Types:      [PASS] (0 errors)                               ║
║  Tests:      [PASS] (42/42 passed, 85% coverage)             ║
║  Security:   [FAIL] (2 constitutional violations)            ║
║  Overall:    [NOT READY] for PR                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

### 🧠 Session Learning (`session-learning/`)

**Purpose**: Extract reusable patterns from coding sessions

**Triggers**: When you ask Copilot to:
- "What did we learn this session?"
- "Extract patterns from this session"
- "Save learnings from today's work"
- "Use session-learning skill"

**What it does**:
1. Analyzes the conversation for patterns:
   - Repeated corrections you made
   - Error resolutions discovered
   - Framework workarounds found
   - New conventions established
2. Classifies each pattern by type and recurrence likelihood
3. Recommends where to save (instructions, skills, or copilot-instructions.md)
4. Generates artifact content ready to paste

**Pattern Types**:
| Type | Example | Save Location |
|------|---------|---------------|
| Error Resolution | "ENOENT in Docker means wrong build context" | Instructions file |
| User Correction | "Don't use any types, use unknown" | copilot-instructions.md |
| Workaround | "Fluent Button needs as='a' for links" | New skill |
| Convention | "All API routes return { success: boolean }" | copilot-instructions.md |

**Example Output**:
```markdown
## Session Learning Analysis

### Patterns Detected

1. **Fluent UI Button Link Workaround**
   - Type: Workaround
   - Recurrence: High
   - Recommended: Create .github/skills/fluent-ui-quirks/SKILL.md

2. **Server Components Default**
   - Type: User Correction (repeated 3x)
   - Recommended: Strengthen rule in copilot-instructions.md
```

---

## How to Use Custom Skills

### Method 1: Chat Invocation
Simply ask Copilot in natural language:
```
"Review the code"
"Check if we're following copilot-instructions.md"
"What constitutional violations exist?"
```

Copilot will automatically detect and use the relevant skill based on your request.

### Method 2: Explicit Reference
Mention the skill directly:
```
"Use the code-review skill to analyze the codebase"
```

### Method 3: Follow-up Commands
After a review, use follow-up commands:
```
"Start Sprint 1"
"Show details for issue X"
"Update design docs"
"Create GitHub issues"
```

## Skill Configuration

### Location
Skills must be placed in `.github/skills/` directory (this folder).

### Format
Each skill is a markdown file with:
- **Title**: Clear, descriptive name
- **Description**: What the skill does
- **When to Use**: Trigger phrases and scenarios
- **Instructions**: Step-by-step execution guide
- **Best Practices**: Guidelines for effective use

### VS Code Setup

1. **Enable Skills** (if not already enabled):
   - Open VS Code Settings (Ctrl+,)
   - Search for "GitHub Copilot Skills"
   - Ensure skills are enabled

2. **Verify Skill Detection**:
   - Open GitHub Copilot Chat (Ctrl+Shift+I)
   - Type: "What skills are available?"
   - Copilot should list custom skills from this directory

3. **Refresh Skills** (after adding new ones):
   - Reload VS Code window (Ctrl+Shift+P → "Reload Window")
   - Or restart VS Code

## Adding New Skills

To create a new custom skill:

1. Create a new markdown file in `.github/skills/`:
   ```
   .github/skills/your-new-skill.md
   ```

2. Use this template:
   ```markdown
   # Skill Name
   
   Brief description of what the skill does.
   
   ## Description
   Detailed explanation of the skill's purpose.
   
   ## When to Use
   - User asks "trigger phrase 1"
   - User asks "trigger phrase 2"
   - [Scenarios when this skill is relevant]
   
   ## Instructions
   Step-by-step guide for Copilot to execute the skill:
   1. Load context...
   2. Analyze...
   3. Generate output...
   
   ## Best Practices
   - Guidelines for using this skill effectively
   
   ## Example Usage
   Show concrete examples of input/output
   ```

3. Reload VS Code to detect the new skill

## Skill Ideas for Future

Consider creating skills for:

- **Architecture Review**: Validate system architecture against design docs
- **Security Audit**: Deep security analysis (OWASP Top 10, Azure best practices)
- **Performance Analysis**: Identify performance bottlenecks and optimization opportunities
- **Test Coverage**: Analyze test gaps and generate test plans
- **Documentation Sync**: Check if code changes require doc updates
- **Dependency Audit**: Review npm packages for vulnerabilities and updates
- **API Contract Validation**: Ensure API implementations match OpenAPI specs
- **Accessibility Audit**: WCAG 2.1 AA compliance check
- **Deployment Checklist**: Pre-deployment validation workflow
- **Refactoring Assistant**: Guide major refactoring with safety checks

## Constitutional Alignment

All skills in this directory are designed to enforce the principles in:
- `.github/copilot-instructions.md` - Project constitution
- `specs/001-portal-mvp/plan.md` - Technical specification
- `design/` - Architecture and design documentation

Skills act as **automated constitutional guardians**, ensuring code changes align with project standards and architectural decisions.

## Troubleshooting

**Skill not detected?**
- Check file is in `.github/skills/` directory
- Verify markdown syntax is valid
- Reload VS Code window

**Skill not triggering?**
- Use more explicit language ("use code-review skill")
- Check "When to Use" section for correct trigger phrases
- Try asking "What skills are available?" to confirm detection

**Skill behavior incorrect?**
- Review the "Instructions" section in the skill file
- Update instructions to be more specific
- Test with explicit step-by-step prompts

## Contributing

When adding or updating skills:
1. Keep instructions clear and actionable
2. Include concrete examples
3. Reference constitutional documents
4. Test the skill with various phrasings
5. Document expected outcomes
6. Update this README with new skills

## Version History

- **v1.0** (Jan 17, 2026): Initial skill: code-review.md
  - Comprehensive constitutional code review
  - Sprint-based remediation workflow
  - Design documentation validation
