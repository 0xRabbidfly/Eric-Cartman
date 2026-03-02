---
name: session-skill-forge
description: Turn any productive workflow into a reusable skill. Use at the end of a session when you've built something worth repeating — this skill writes the SOP, creates the SKILL.md, and wires it into the project.
user-invokable: true
disable-model-invocation: true
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Session Skill Forge

## Purpose

After any productive workflow, automatically extract it into a **permanent, callable skill**. This is the skill that creates other skills.

From the article: _"You run a workflow with Claude, then at the end of the session you ask it to write an SOP for the process. You save that SOP as a skill file. From that point on, you type /skill-name and the entire process runs automatically."_

The difference from `session-learning`: that skill extracts **rules and corrections** (defensive). Skill-forge extracts **workflows and capabilities** (generative). Session-learning says "don't do X again." Skill-forge says "here's how to do Y every time."

## When to Use

- You just completed a multi-step workflow that worked well
- You find yourself repeating the same sequence of actions across sessions
- You want to formalize a process before you forget the steps
- After a demo or showing someone a workflow — capture it while it's fresh
- When you say: "make this a skill", "save this workflow", "forge a skill", "create an SOP"

---

## Workflow

### Phase 1: Workflow Capture

Analyze the current session (or a described workflow) to extract:

1. **Trigger** — What prompt or situation initiates this workflow?
2. **Inputs** — What does the user provide? (topic, file path, URL, etc.)
3. **Steps** — The exact sequence of actions performed
4. **Tools used** — Which tools/skills/commands were invoked?
5. **Decision points** — Where did human judgment intervene?
6. **Output** — What was the final deliverable?
7. **Quality criteria** — How do you know the output is good?

Present this as a structured capture:

```markdown
## Workflow Capture

**Name**: [descriptive-kebab-case]
**Trigger**: "[typical user prompt]"
**Category**: [research / content / code / vault / automation / analysis]

### Inputs
- [input 1]: [description] (required/optional)
- [input 2]: [description] (required/optional)

### Steps (as performed)
1. [Action] → [Tool/command used] → [Output]
2. [Action] → [Tool/command used] → [Output]
3. [Decision point]: if X then A, else B
4. ...

### Output
- Format: [markdown / file / vault note / terminal output]
- Destination: [where it goes]

### Quality Criteria
- [ ] [Criterion 1]
- [ ] [Criterion 2]
```

### Phase 2: SOP Design

Transform the raw capture into a clean SOP with:

1. **Generalization** — Replace specific values with parameters
2. **Error handling** — Add fallback paths for common failures
3. **Checkpoints** — Add verification steps between phases
4. **Idempotency** — Ensure the skill can be re-run safely
5. **Scope boundaries** — Define what the skill does and does NOT do

### Phase 3: Skill Classification

Determine the skill archetype:

| Type | Has Scripts? | When to Use |
|------|:-----------:|-------------|
| **Prompt-only** | No | Workflow is entirely AI reasoning + existing tools |
| **Script-backed** | Yes | Workflow needs custom Python/PowerShell logic |
| **Composable** | Imports others | Workflow chains existing skills together |

### Phase 4: Generate Skill Artifacts

#### A. SKILL.md (always)

Create `.github/skills/{name}/SKILL.md` following the project template:

```markdown
````skill
---
name: {kebab-case-name}
description: {One-line description — used for trigger matching}
version: 1.0.0
user-invokable: true
---

# {Skill Title}

## Purpose
{What this skill does and why}

## When to Use
{Trigger phrases and situations}

## Workflow
### Phase 1: {Phase Name}
{Steps with actionable detail}

### Phase 2: {Phase Name}
{Steps with checkpoints}

## Output Format
{Template of expected output}

## Rules
{Do's and don'ts}

## Example Invocations
{3 example prompts}

## Related Skills
{Cross-references}
````
```

#### B. Scripts (if script-backed)

Create `.github/skills/{name}/scripts/{name}.py` with:
- Argument parsing (argparse)
- Config via `config.json` (if needed)
- Proper error handling and exit codes
- UTF-8 encoding support

#### C. VS Code Task (optional)

If the skill can be parameterized as a shell command, suggest a task entry:

```json
{
  "label": "{Skill Name}",
  "type": "shell",
  "command": "python .github/skills/{name}/scripts/{name}.py ${input:topic}",
  "isBackground": false
}
```

### Phase 5: Registration & Wiring

1. **Add to copilot settings** — Ensure the skill description in frontmatter is discoverable
2. **Cross-reference** — Add to Related Skills sections in connected skills
3. **Test invocation** — Simulate the trigger phrase to verify the skill works
4. **Announce** — Brief summary of what was created

---

## Skill Quality Checklist

Before finalizing any forged skill:

- [ ] **Name** is kebab-case, descriptive, 2-3 words
- [ ] **Description** in frontmatter doubles as trigger phrase
- [ ] **Purpose** section explains the "why" in 2-3 sentences
- [ ] **When to Use** has both situations AND trigger phrases
- [ ] **Workflow** has numbered phases with clear checkpoints
- [ ] **Output** format is templated (user knows what to expect)
- [ ] **Rules** section has at least 3 guardrails
- [ ] **Examples** section has at least 2 invocation examples
- [ ] **Related Skills** cross-references are bidirectional
- [ ] Skill doesn't duplicate an existing skill's purpose

---

## Meta: Forging This Skill

This skill was itself forged from the pattern described in Noah Vincent's article on AI Second Brains. The workflow:

1. Read article about skills-as-slash-commands pattern
2. Identified the meta-pattern: "skill that creates skills"
3. Generalized across our existing skill library's conventions
4. Created SKILL.md following established template

---

## Example Invocations

```
That research workflow we just did was great — forge it into a reusable skill.
```

```
Make this a skill I can repeat. Use session-skill-forge.
```

```
I keep doing this same process for API testing — create a skill for it.
```

```
Forge a skill from this session. Call it "content-brief".
```

---

## Related Skills

- `session-learning` — Extracts rules/corrections; skill-forge extracts workflows
- `session_context_optimizer` — Optimizes existing context; skill-forge adds new capabilities
- `project-scaffold` — Initial project setup; skill-forge grows the skill library over time
