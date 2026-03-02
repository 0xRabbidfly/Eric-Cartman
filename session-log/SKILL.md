---
name: session-log
description: Capture Copilot Chat session insights and end-of-session summaries into `.github/sessions/` for later analysis. Use at end of session, when asked to log progress, or when capturing decisions.
user-invokable: true
disable-model-invocation: false
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Session Log Skill

Capture session insights and metrics for later analysis.

## Usage

**Checkpoint logging** (auto-extracts insights during session):
```
/session-log checkpoint
```
→ Analyze recent conversation and automatically extract/categorize insights, challenges, metrics, etc.

**Manual end-of-session** (comprehensive summary):
```
/session-log end
```
→ Full analysis of the entire session with a comprehensive report

**Optional: manual logging** (add a specific note):
```
/session-log "Hit 39 TypeScript errors in auth module"
```
→ Categorize it and log it to the current session file

---

## Instructions

You are logging insights about this Copilot Chat session to `.github/sessions/<date>/<session-name>.md`.

### Determine the Mode

**If the user says "checkpoint":**
- This is **checkpoint mode** — analyze recent conversation and auto-extract insights

**If the user says "end" or provides no arguments:**
- This is **end-of-session summary** mode

**If the user provides a message (without a category):**
- This is **manual logging** mode — analyze their message, categorize it, and log it

---

## Mode 1: Checkpoint (Auto-Extract)

When the user calls `/session-log checkpoint`:

1. **Determine session file:**
   - Check if `.github/sessions/<today>/*.md` exists from today
   - If multiple files, ask which session (show list of filenames)
   - If none exist, ask for session name and create it

2. **Analyze recent conversation:**

   Look at the conversation since the last checkpoint (or session start) and identify:

   - **Insights**: learnings, discoveries, “aha” moments, patterns found
   - **Challenges**: problems encountered, blockers, errors
   - **Metrics**: quantifiable outcomes, counts, measurements
   - **Issues**: bugs, problems to investigate, technical debt
   - **Friction**: misunderstandings, missing context, back-and-forth needed
   - **Learnings**: knowledge gained, patterns understood
   - **What Worked**: successful approaches
   - **What Didn’t Work**: failed approaches, dead ends

3. **Create timestamped entries:**

   For each item found, create an entry:
   ```markdown
   ## [10:34 AM] Challenge
   Hit 39 TypeScript errors in the auth module. Errors primarily related to missing type annotations on the User interface and session handling.

   ## [10:45 AM] Insight
   Running typecheck after each file fix is faster than batch fixing all files then rechecking.

   ## [11:02 AM] Metric
   Fixed 39 type errors across 12 files in approximately 45 minutes.

   ## [11:15 AM] What Worked
   Parallelizing fixes across modules was highly efficient.
   ```

4. **Append to the session file:**
   - Add all entries with current timestamps
   - Preserve existing content

5. **Confirm:**
   - Tell user: "Checkpoint logged to `.github/sessions/2026-02-09/fix-auth-types.md`"
   - Summarize what was captured (e.g., "Captured 2 insights, 1 challenge, 1 metric")

---

## Mode 2: Manual Logging (Message)

When the user provides a message without a category:

1. **Determine session file:**
   - Check if `.github/sessions/<today>/*.md` exists from today
   - If multiple files, ask which session (show list of filenames)
   - If none exist, ask for session name: "What should we call this session?" (suggest a name based on recent work)

2. **Analyze the message:**
   - Determine what category it belongs to (challenge, insight, metric, issue, friction, learning, etc.)
   - Extract a concise title

3. **Append an entry:**
   - Format: `## [HH:MM AM/PM] <Category>: <Title>`
   - Include the user’s message as the entry body

   Example:
   ```markdown
   ## [10:34 AM] Challenge: TypeScript errors in auth module
   Hit 39 TypeScript errors across authentication files. Need to systematically fix type issues with user model and session handling.
   ```

4. **Confirm:**
   - Tell user what category it was logged as
   - Example: "Logged as Challenge to `.github/sessions/2026-02-09/fix-auth-types.md`"

---

## Mode 3: End-of-Session Summary

When the user wants a comprehensive summary:

1. **Get session name if new:**
   - If no session file exists for today, ask: "What should we call this session?"
   - Suggest a name based on conversation (e.g., "fix-typescript-errors", "ui-review-challenges-page")

2. **Analyze the conversation:**

   Extract from our conversation history:
   - **Primary Goal**: What was the main objective?
   - **Files Modified**: All files read, edited, or written (from tool calls)
   - **Commands Run**: Key terminal commands executed
   - **Tasks**: Tasks created, updated, or completed
   - **Tools Used**: Read, Edit, Write, Terminal, Grep, Glob counts
   - **Outcome**: Was the goal fully achieved, mostly achieved, or unclear?
   - **Challenges**: Problems encountered (errors, blockers, confusion)
   - **Friction**: Misunderstandings, missing context, clarifications needed
   - **Insights**: Learnings, patterns discovered, "aha" moments
   - **What Worked**: Successful approaches, efficient workflows
   - **What Didn't**: Failed approaches, dead ends, inefficiencies
   - **Duration**: Estimate based on message timestamps

3. **Generate comprehensive report:**

```markdown
# Session: <session-name>

**Date:** 2026-02-09
**Duration:** ~2 hours
**Model:** GPT-5.2
**Outcome:** ✅ Fully Achieved | ⚠️ Mostly Achieved | ❓ Unclear

---

## Primary Goal

<What was the main objective of this session?>

---

## What Was Done

### Files Modified
- `src/auth/login.ts` - Fixed type errors in authentication flow
- `src/models/user.ts` - Added missing type annotations
- `src/utils/session.ts` - Resolved session handling types

### Commands Executed
```bash
npx tsc --noEmit
npm run typecheck
git status
```

### Tasks
- [x] Run typecheck and identify all errors
- [x] Fix type errors in auth module
- [ ] Add tests for fixed functionality

### Tool Usage
- **Read:** 45 files
- **Edit:** 12 files
- **Write:** 3 files
- **Terminal:** 8 commands
- **Grep:** 6 searches

---

## Outcome

<Describe whether the goal was achieved and the current state>

---

## Challenges & Friction

### Challenges Encountered
<Technical problems, errors, blockers - include any logged during session>

### Friction Points
<Misunderstandings, missing context, clarifications needed>

---

## Insights & Learnings

### What Worked Well
<Successful approaches, efficient workflows>

### What Didn't Work
<Failed approaches, dead ends, inefficiencies>

### Key Learnings
<Patterns discovered, insights to remember for future sessions>

---

## Conversation Summary

<High-level narrative of what happened in this session - the story of how we went from start to finish>

---

## Next Steps

<What should happen next? Any follow-up needed?>

---

*Generated by Copilot Chat `/session-log` skill*
```

4. **Save and confirm:**
   - Save to `.github/sessions/<date>/<session-name>.md`
   - Tell user: "Session logged to `.github/sessions/2026-02-09/fix-auth-types.md`"
   - Ask: "Would you like me to commit this to git?"

---

## Session File Template (for new sessions)

When creating a new session file, start with this header:

```markdown
# Session: <session-name>

**Date:** <date>
**Started:** <time>
**Model:** GPT-5.2

---

## Session Log

<Incremental entries will be appended here>
```

---

## Additional Guidelines

1. **Session naming:** Use kebab-case, descriptive names (e.g., "fix-typescript-errors", "ui-review-dashboard")

2. **Date folders:** Always use YYYY-MM-DD format for folder names

3. **Multiple sessions per day:** Totally fine - each gets its own markdown file

4. **Appending vs. Overwriting:**
   - Incremental mode: Always **append** entries
   - End-of-session mode: **Replace** the entire file with comprehensive summary (preserving any incremental logs in the "Session Log" section)

5. **Criteria to capture** (based on insights patterns):
   - **Goals:** What the user is trying to accomplish
   - **Outcomes:** Fully/mostly/unclear achievement
   - **Friction:** Misunderstandings, missing context, back-and-forth
   - **Tool patterns:** Heavy Read usage, multi-file edits, task orchestration
   - **Session characteristics:** Duration, message count, complexity
   - **Satisfaction signals:** User saying "thanks", "that worked", "perfect"
   - **Incomplete work:** Sessions ending before verification

6. **Be concise:** Incremental logs should be brief. End-of-session summaries should be comprehensive but scannable.

---

## Examples

**Checkpoint (auto-extract):**
```
User: /session-log checkpoint
Copilot: Analyzing recent conversation...
Checkpoint logged to .github/sessions/2026-02-09/fix-auth-types.md
Captured: 2 insights, 1 challenge, 1 metric, 1 learning
```

**Manual logging (message):**
```
User: /session-log "Hit 39 TypeScript errors in the auth module"
Copilot: Logged as Challenge to .github/sessions/2026-02-09/fix-auth-types.md
```

**End of session:**
```
User: /session-log end
Copilot: Analyzing session... [generates comprehensive report]
Session logged to .github/sessions/2026-02-09/fix-auth-types.md

Would you like me to commit this to git?
```
