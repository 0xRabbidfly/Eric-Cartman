# Project Guide — Interaction Template

Copy and adapt this template when starting a guided exploration session.

---

## 🗺️ Project Overview: [Project Name]

**What it is**: [One sentence describing the project's purpose]

**Built with**: [Primary tech stack — language, framework, key dependencies]

**Runs on**: [Hosting environment — cloud provider, container, serverless, etc.]

**Audience**: [Who uses this — internal team, customers, developers, etc.]

---

### Folder Structure

```
[project-root]/
├── [folder]/          # [Purpose]
├── [folder]/          # [Purpose]
│   ├── [subfolder]/   # [Purpose]
│   └── [subfolder]/   # [Purpose]
├── [folder]/          # [Purpose]
└── [config files]     # [Purpose]
```

---

### Key Entry Points

| Entry Point | Purpose | When It Runs |
|-------------|---------|--------------|
| `[path/to/file]` | [What it does] | [Startup, on-demand, scheduled] |
| `[path/to/file]` | [What it does] | [Startup, on-demand, scheduled] |
| `[path/to/file]` | [What it does] | [Startup, on-demand, scheduled] |

---

### Architecture Snapshot

```
[Insert appropriate diagram from diagram-patterns.md]
```

---

### Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| [Category] | [Technology] | [Why this was chosen] |
| [Category] | [Technology] | [Why this was chosen] |
| [Category] | [Technology] | [Why this was chosen] |

---

### Important Patterns

| Pattern | Where Used | Why It Matters |
|---------|------------|----------------|
| [Pattern name] | [Files/modules] | [Significance] |
| [Pattern name] | [Files/modules] | [Significance] |

---

### Known Complexity

| Area | Complexity Level | Notes |
|------|------------------|-------|
| [Subsystem] | 🟢 Low | [Brief note] |
| [Subsystem] | 🟡 Medium | [Brief note] |
| [Subsystem] | 🔴 High | [Brief note — why it's complex] |

---

## 🧭 Where to Next?

Based on this overview, you might want to explore:

1. **[Area/Question 1]**  
   _This would help you understand [benefit]_

2. **[Area/Question 2]**  
   _This is relevant if you need to [use case]_

3. **[Area/Question 3]**  
   _This would be useful for [scenario]_

Which direction interests you? Or ask about something else entirely.

---

# 🔍 Deep Dive Template

Use this when exploring a specific area in depth.

---

## 🔍 Deep Dive: [Area Name]

### Where We Are

```
[Simple diagram showing where this fits]

    ┌─────────────────────────────────────────┐
    │              System                     │
    │                                         │
    │    ┌─────────────────────────┐         │
    │    │  ★ THIS AREA ★         │         │
    │    └─────────────────────────┘         │
    │                                         │
    └─────────────────────────────────────────┘
```

_[One sentence placing this in the architecture]_

---

### Why It Exists

**Problem**: [What problem does this solve?]

**Solution**: [How does it solve it?]

**Alternatives Considered**: [What else could have been done?]

---

### How It Works

#### High-Level Flow

```
[Sequence or flow diagram]
```

#### Key Concepts

| Concept | Definition | Example |
|---------|------------|---------|
| [Term 1] | [Plain English definition] | [Concrete example] |
| [Term 2] | [Plain English definition] | [Concrete example] |

#### Code Walkthrough

**Step 1: [Action]**

```[language]
// [path/to/file.ext]
// [Annotated code snippet]
```

**Step 2: [Action]**

```[language]
// [path/to/file.ext]
// [Annotated code snippet]
```

---

### Key Files

| File | Responsibility | Lines |
|------|---------------|-------|
| `[path/to/file]` | [What it does] | ~[X] |
| `[path/to/file]` | [What it does] | ~[X] |
| `[path/to/file]` | [What it does] | ~[X] |

---

### Watch Out For

- ⚠️ **[Gotcha 1]**: [Explanation and how to handle it]
- ⚠️ **[Gotcha 2]**: [Explanation and how to handle it]
- 💡 **[Pro tip]**: [Helpful insight]

---

### Connections

**Depends on**:
- [Component/service] — for [purpose]
- [Component/service] — for [purpose]

**Used by**:
- [Component/service] — when [scenario]
- [Component/service] — when [scenario]

**Data flows**:
```
[Upstream] ──▶ [This Area] ──▶ [Downstream]
```

---

## 🧭 Where to Next?

Based on what we covered, you might want to explore:

1. **[Follow-up question about adjacent area]**  
   _This would help you understand [connection]_

2. **[Follow-up question about deeper mechanism]**  
   _This is relevant if you need to [use case]_

3. **[Follow-up question about practical application]**  
   _This would be useful for [scenario]_

Which direction interests you?

---

# Guidance Notes

## Calibrating Depth

| User Signal | Adjust To |
|-------------|-----------|
| "I'm new to this" | More diagrams, define terms, go slower |
| "I've worked on similar projects" | Skip basics, focus on what's unique |
| "Just the overview" | Stay high-level, offer to drill down |
| "Show me the code" | More snippets, less prose |
| "Why was it built this way?" | Focus on decisions and trade-offs |

## Phrasing Questions

**Good follow-up questions**:
- Build on what was just discussed
- Offer different directions (breadth vs. depth)
- Connect to practical use cases

**Examples**:
- "Want to see how this connects to [related area]?"
- "Curious about what happens when [edge case]?"
- "Should we trace a real [request/event] through this?"
- "Interested in how this gets tested?"
- "Want to understand why [decision] was made?"

## Handling "I Don't Know"

When exploring an unfamiliar codebase together:

1. Be honest: "Let me investigate this..."
2. Explore together: "Let's look at [file] to find out..."
3. Form hypotheses: "Based on [evidence], I think..."
4. Validate: "Let me confirm by checking [source]..."
