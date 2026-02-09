---
name: insights-report
description: Generate a comprehensive cross-session insights report by analyzing all captured session logs in `.github/sessions/`.
version: 1.0.0
---

# Insights Report Skill

Generate a comprehensive insights report by analyzing all captured session logs.

## Usage

```bash
/insights-report
```

Optional: Specify date range
```bash
/insights-report --from 2026-02-01 --to 2026-02-09
```

---

## Instructions

You are analyzing all session logs in `.github/sessions/` to generate a comprehensive insights report (project-specific).

### Step 1: Discover Sessions

1. **Find all session files (PowerShell):**
   ```powershell
   Get-ChildItem -Path .github/sessions -Filter *.md -Recurse -File
   ```

2. **Count and categorize:**
   - Total sessions
   - Date range (earliest to latest)
   - Sessions per day/week

3. **If no sessions found:**
   - Tell user: "No session logs found in `.github/sessions/`. Run `/session-log end` to capture your first session!"
   - Stop here

### Step 2: Parse Session Data

For each session file, extract:

- **Session name** (from filename and/or title)
- **Date**
- **Duration** (if captured)
- **Primary goal** (from "Primary Goal" section)
- **Outcome** (from "Outcome" section: fully/mostly/unclear)
- **Files modified** (from "Files Modified" section)
- **Commands run** (from "Commands Executed" section)
- **Tool usage** (from "Tool Usage" section)
- **Challenges** (from "Challenges & Friction" section)
- **Insights** (from "Insights & Learnings" section)
- **What worked** (from "What Worked Well" section)
- **What didn't work** (from "What Didn't Work" section)
- **Incremental logs** (any challenge/insight/metric entries)

### Step 3: Analyze Patterns

Aggregate across all sessions:

#### Project Areas
- Group sessions by topic/goal similarity
- Identify major workstreams (e.g., "TypeScript type fixes", "UI development", "Backend work")
- Count sessions per area

#### Goals & Outcomes
- Most common goals (top 5-10)
- Outcome distribution (% fully/mostly/unclear achieved)
- Sessions with unclear outcomes (incomplete work)

#### Tool Usage Patterns
- Most-used tools across sessions
- Heavy read patterns (investigation-heavy sessions)
- Multi-file edit patterns (large refactoring sessions)
- Terminal-heavy sessions (command-line work)

#### Friction Points
- Most common challenges
- Recurring issues
- Patterns in what doesn't work
- Misunderstandings or clarifications needed

#### What Works
- Successful workflows
- Efficient approaches
- Patterns in fully-achieved sessions
- Insights that led to success

#### File & Command Patterns
- Most frequently modified files
- Common command sequences
- Test/typecheck/build patterns

#### Time Patterns
- Average session duration
- Long vs. short sessions
- Time-of-day patterns (if timestamps available)

### Step 4: Generate Insights Report

Create a comprehensive markdown report with these sections:

```markdown
# Project Insights Report

**Generated:** 2026-02-09
**Sessions Analyzed:** 42
**Date Range:** 2026-01-15 to 2026-02-09
**Total Duration:** ~84 hours

---

## Executive Summary

<2-3 paragraphs summarizing the key findings>

**What's working:** <Brief summary>

**What's hindering:** <Brief summary>

**Top recommendation:** <One actionable suggestion>

---

## Project Areas

You've been working in these main areas:

### 1. TypeScript Type System Fixes (18 sessions)
Description of work done, patterns observed, outcomes

### 2. UI Development (12 sessions)
Description of work done, patterns observed, outcomes

### 3. Backend & API Work (8 sessions)
Description of work done, patterns observed, outcomes

<Additional areas as discovered>

---

## Top Goals

Your most common objectives across sessions:

1. **Fix TypeScript type errors** (18 occurrences)
   - Outcome: 12 fully achieved, 4 mostly achieved, 2 unclear
   - Average duration: ~2.5 hours

2. **Review and improve UI** (12 occurrences)
   - Outcome: 7 fully achieved, 3 mostly achieved, 2 unclear
   - Average duration: ~1.5 hours

3. **Debug authentication issues** (6 occurrences)
   - Outcome: 4 fully achieved, 2 mostly achieved
   - Average duration: ~3 hours

<Continue for top 5-10 goals>

---

## What's Working Well

### Impressive Workflows

#### 1. Systematic Type Error Fixing
<Description of what makes this work well>

**Example sessions:**
- 2026-02-05: fix-typescript-errors.md
- 2026-02-07: resolve-auth-types.md

#### 2. <Another successful pattern>
<Description>

### Successful Patterns
- <Pattern that appears in fully-achieved sessions>
- <Another effective approach>
- <Efficient workflow observed>

---

## Where Things Go Wrong

### Friction Categories

#### 1. Sessions Ending Before Verification (8 sessions)
<Description of the pattern>

**Examples:**
- 2026-02-03: typecheck-auth.md - Fixed 39 errors but no final verification
- 2026-02-06: ui-review.md - Investigation started but no resolution

**Suggestion:** <How to improve>

#### 2. <Another friction pattern>
<Description>

**Examples:**
<Specific sessions>

**Suggestion:** <How to improve>

### Common Challenges
- **TypeScript type errors** (mentioned in 15 sessions)
- **Missing dependencies** (mentioned in 8 sessions)
- **UI styling issues** (mentioned in 12 sessions)

---

## Tool Usage Patterns

- **Most-used tool:** Read (1,234 times) - Heavy investigation work
- **Multi-file edits:** Edit used 456 times across 89 files
- **Command-line work:** Terminal used 234 times

**Patterns:**
- Sessions with >20 Read calls tend to have unclear outcomes (investigation-heavy)
- Sessions with <10 Edit calls more likely to be fully achieved (focused work)
- Typecheck commands run in 85% of sessions

---

## File Patterns

### Most Modified Files
1. `src/auth/login.ts` (12 sessions)
2. `src/models/user.ts` (10 sessions)
3. `src/components/Dashboard.tsx` (9 sessions)
<Continue for top 10>

### Common Command Sequences
1. `npx tsc --noEmit` → fix files → `npx tsc --noEmit` (typecheck loop)
2. `git status` → file changes → `git add` → `git commit` (commit flow)
3. `npm test` → fix tests → `npm test` (test-driven fixes)

---

## Key Insights & Learnings

Aggregated from your session logs:

- "<Insight from session X>"
- "<Learning from session Y>"
- "<Pattern discovered in session Z>"

<List top 10-15 insights>

---

## Suggestions

### Quick Wins

#### 1. <Actionable suggestion based on friction>
**Why:** <Explanation based on data>
**How:** <Specific steps>
**Expected impact:** <What improves>

#### 2. <Another suggestion>
<Details>

### Process Improvements

#### 1. <Workflow improvement>
**Current pattern:** <What happens now>
**Suggested pattern:** <What should happen>
**Example:** <How to implement>

#### 2. <Another improvement>
<Details>

### .github/copilot-instructions.md Additions

Based on your patterns, add these to `.github/copilot-instructions.md`:

```markdown
## <Section suggestion 1>
<Recommended content based on session patterns>
```

```markdown
## <Section suggestion 2>
<Recommended content>
```

### Features to Try

#### 1. <Copilot / VS Code feature recommendation>
**Why for you:** <Based on your usage patterns>
**How to use:** <Specific example>

#### 2. <Another feature>
<Details>

---

## Session Outcomes

- ✅ **Fully Achieved:** 28 sessions (67%)
- ⚠️ **Mostly Achieved:** 10 sessions (24%)
- ❓ **Unclear:** 4 sessions (9%)

**Characteristics of fully-achieved sessions:**
- <Pattern 1>
- <Pattern 2>
- <Pattern 3>

**Characteristics of unclear-outcome sessions:**
- <Pattern 1>
- <Pattern 2>

---

## Timeline

### Sessions by Week
- Week of 2026-01-15: 8 sessions
- Week of 2026-01-22: 12 sessions
- Week of 2026-01-29: 15 sessions
- Week of 2026-02-05: 7 sessions

### Most Active Days
1. 2026-01-28: 5 sessions
2. 2026-02-02: 4 sessions
3. 2026-01-23: 4 sessions

---

## Appendix

### All Sessions
<Chronological list of all session files analyzed>

---

*Generated by Copilot Chat `/insights-report` skill*
*Analyzed {N} sessions from `.github/sessions/`*

```
