# Session Log Skill

Capture session insights and metrics for later analysis.

## Usage

**Checkpoint logging** (auto-extracts insights during session):
```
/session-log checkpoint
```
→ I analyze recent conversation and automatically extract/categorize insights, challenges, metrics, etc.

**Manual end-of-session** (comprehensive summary):
```
/session-log end
```
→ Full analysis of entire session with comprehensive report

**Optional: Manual logging** (if you want to add something specific):
```
/session-log "Hit 39 TypeScript errors in auth module"
```
→ I'll categorize it and log it for you

---

## Instructions

You are logging insights about this Claude Code session to `.github/sessions/<date>/<session-name>.md`.

### Determine the Mode

**If the user says "checkpoint":**
- This is **checkpoint mode** - analyze recent conversation and auto-extract insights

**If the user says "end" or provides no arguments:**
- This is **end-of-session summary** mode

**If the user provides a message (without category):**
- This is **manual logging** mode - analyze their message, categorize it, and log it

---

## Mode 1: Checkpoint (Auto-Extract)

When the user calls `/session-log checkpoint`:

1. **Determine session file:**
   - Check if `.github/sessions/<today>/*.md` exists from today
   - If multiple files, ask which session (show list of filenames)
   - If none exist, ask for session name and create it

2. **Analyze recent conversation:**

   Look at the conversation since the last checkpoint (or session start) and identify:

   - **Insights**: Learnings, discoveries, "aha" moments, patterns found
     - Example: "Running typecheck after each file is faster than batch fixing"
     - Example: "The auth module's type errors were all related to missing User interface properties"

   - **Challenges**: Problems encountered, blockers, errors
     - Example: "Hit 39 TypeScript errors in the auth module"
     - Example: "Third-party library missing type definitions"

   - **Metrics**: Quantifiable outcomes, counts, measurements
     - Example: "Fixed 39 type errors across 12 files"
     - Example: "Reduced bundle size by 15%"

   - **Issues**: Bugs, problems to investigate, technical debt
     - Example: "Authentication flow has race condition with session storage"

   - **Friction**: Misunderstandings, missing context, back-and-forth needed
     - Example: "Had to clarify which project to run typecheck on"

   - **Learnings**: Knowledge gained, patterns understood
     - Example: "Learned that the project uses Zod for runtime validation"

   - **What Worked**: Successful approaches
     - Example: "Using task agents to parallelize fixes across files was very efficient"

   - **What Didn't Work**: Failed approaches, dead ends
     - Example: "Tried fixing types top-down but bottom-up was more effective"

3. **Create timestamped entries:**

   For each item found, create an entry:
   ```markdown
   ## [10:34 AM] Challenge
   Hit 39 TypeScript errors in the auth module. Errors primarily related to missing type annotations on User interface and session handling.

   ## [10:45 AM] Insight
   Running typecheck after each file fix is faster than batch fixing all files then rechecking.

   ## [11:02 AM] Metric
   Fixed 39 type errors across 12 files in approximately 45 minutes.

   ## [11:15 AM] What Worked
   Using task agents to parallelize fixes across different modules was highly efficient.
   ```

4. **Append to session file:**
   - Add all entries with current timestamps
   - Preserve existing content

5. **Confirm:**
   - Tell user: "Checkpoint logged to `.github/sessions/2026-02-09/fix-auth-types.md`"
   - Summarize what was captured: "Captured 2 insights, 1 challenge, 1 metric"

---

## Mode 2: Manual Logging

When the user provides a message without a category:

1. **Determine session file:**
   - Check if `.github/sessions/<today>/*.md` exists from today
   - If multiple files, ask which session (show list of filenames)
   - If none exist, ask for session name: "What should we call this session?" (suggest a name based on recent work)

2. **Create or append entry:**
   - Format: `## [HH:MM AM/PM] <Category>: <Title>`
   - Add the user's message as content
   - If this is a new file, create header first (see template below)

3. **Append to file:**
   ```markdown
   ## [10:34 AM] Challenge: TypeScript errors in auth module
   Hit 39 TypeScript errors across authentication files. Need to systematically fix type issues with user model and session handling.
   ```

4. **Confirm:** "Logged to `.github/sessions/2026-02-09/fix-auth-types.md`"

---

1. **Analyze the message:**
   - Determine what category it belongs to (challenge, insight, metric, issue, friction, learning, etc.)
   - Extract a concise title

2. **Follow checkpoint Mode 1 steps** to append the entry

3. **Confirm:**
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
   - **Commands Run**: Key bash commands executed
   - **Tasks**: Tasks created, updated, or completed
   - **Tools Used**: Read, Edit, Write, Bash, Grep, Glob counts
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
**Model:** Claude Sonnet 4.5
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
- **Bash:** 8 commands
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

*Generated by Claude Code `/session-log` skill*
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
**Model:** Claude Sonnet 4.5

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

5. **Criteria to capture** (based on /insights patterns):
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
Claude: Analyzing recent conversation...
Checkpoint logged to .github/sessions/2026-02-09/fix-auth-types.md
Captured: 2 insights, 1 challenge, 1 metric, 1 learning
```

**Manual logging:**
```
User: /session-log "Hit 39 TypeScript errors in the auth module"
Claude: Logged as Challenge to .github/sessions/2026-02-09/fix-auth-types.md
```

**End of session:**
```
User: /session-log end
Claude: Analyzing session... [generates comprehensive report]
Session logged to .github/sessions/2026-02-09/fix-auth-types.md

Would you like me to commit this to git?
```
