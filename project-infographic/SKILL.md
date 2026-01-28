---
name: Project-Infographic
description: Generate a visually beautiful HTML infographic showing high-level project overview for sprint demos
---

You are a visual documentation specialist. Your task is to scan the codebase and design docs, then generate a polished single-page HTML infographic suitable for sprint demos and stakeholder presentations.

## When to Use This Skill

- Before sprint demos or stakeholder presentations
- When onboarding new team members visually
- When the user says "generate infographic", "create demo doc", or "visual overview"
- To complement technical documentation with executive-friendly visuals

## Target Audience

**NON-TECHNICAL STAKEHOLDERS**: Product owners, executives, business analysts. The output should communicate:

- What problem does this solve?
- How does the solution work at a high level?
- What's the current status?
- What are the key benefits/metrics?

**NOT FOR**: Deep technical dives, API documentation, or implementation details.

## Scan Process

### 1. Understand the Project Purpose

Scan these locations for the "why":

- `README.md` - project overview
- `spec.md` or similar - user stories, business goals
- Any `*.md` in spec/design folders

Extract:

- One-sentence project purpose
- 3-4 key pain points it solves
- 3-4 main features/capabilities

### 2. Map the High-Level Flow

Scan for architecture and process flows:

- `plan.md` or architecture docs
- `src/pipeline/` or similar orchestration code
- State machines, workflow definitions
- Entry points and outputs

Create a simplified flow with 4-7 nodes maximum:

- Input → Processing stages → Decision points → Outputs
- Use emojis as visual icons (📥 input, 🔍 search, 🚦 gate, 📊 report)

### 3. Gather Current Status

From code and docs:

- Phase/milestone completion from `tasks.md`
- Working features vs in-progress vs planned
- Key metrics (record counts, test coverage, etc.)

### 4. Identify Tech Stack

List 5-8 key technologies with emoji icons:

- Runtime/Framework (🦜 LangGraph, ⚛️ React)
- Language (📦 TypeScript, 🐍 Python)
- Key libraries (🔍 FAISS, ✅ Zod)
- Infrastructure (🐳 Docker, ☁️ AWS)

## Output: Single HTML File

Generate a self-contained HTML file with embedded CSS. NO external dependencies.

### Required Sections

```
1. HERO SECTION
   - Project name + tagline
   - 2-3 key stats (animated numbers are nice)
   - Gradient dark background with brand colors

2. THE CHALLENGE (optional but recommended)
   - 3-4 pain point cards with icons
   - Brief descriptions of problems solved

3. THE SOLUTION
   - High-level value proposition
   - Feature badges/pills

4. HOW IT WORKS
   - Visual pipeline/flow diagram using CSS boxes and arrows
   - 4-7 stages maximum
   - YES/NO branches if applicable
   - Hover effects for interactivity

5. CURRENT STATUS
   - Phase completion checklist (✅ 🚧 ⬜)
   - Key metrics cards

6. BENEFITS/IMPACT
   - 3-4 metric cards with big numbers
   - Business-oriented language

7. TECH STACK
   - Pill badges with emoji icons

8. FOOTER
   - Team/organization
   - Last updated date
```

### Visual Design System

Use this CSS design token pattern:

```css
:root {
  /* Brand colors - adapt to project */
  --brand-primary: #e31937; /* CGI red or project brand */
  --brand-secondary: #0066cc; /* Accent blue */

  /* Semantic colors */
  --success: #22c55e;
  --warning: #f59e0b;
  --error: #ef4444;
  --purple: #9333ea;

  /* Dark theme for hero */
  --dark: #1a1a2e;
  --dark-light: #2a2a40;

  /* Light sections */
  --surface: #ffffff;
  --surface-alt: #f8f9fa;
  --text-primary: #1a1a2e;
  --text-secondary: #666666;
}
```

### Interactive Elements

Include hover effects for:

- Cards: `transform: translateY(-4px); box-shadow: ...`
- Pipeline stages: highlight on hover
- Tech pills: subtle scale

### Responsive

- Flexbox/Grid layouts
- Stack on mobile (max-width: 768px)
- Readable on tablets for meeting rooms

## Architectural Diagram Style

For the "How It Works" section, create a **premium architectural diagram** with:

### System Boundary Container

- A labeled container box showing the "AI Agent Pipeline" or system boundary
- Gradient background with subtle border
- Floating title badge at the top

### Flow Nodes with Rich Styling

Each node should have:

- Icon (emoji)
- Label (bold)
- Sub-label (muted description)
- Color-coded border based on type (input=blue, process=gray, gate=amber, success=green, error=red)

### Side Panels for External Systems

- RAG/Vector Store panel on the side
- Connector lines showing data flow
- External integrations (JIRA, Email, etc.)

### Branch Visualization

For decision points (YES/NO gates):

- Split into two columns
- Labeled badges (✓ YES / ✗ NO)
- Different colored output cards for each path

### Example Architecture CSS Pattern

```css
/* System boundary container */
.agent-container {
  background: linear-gradient(135deg, rgba(227, 25, 55, 0.04), rgba(227, 25, 55, 0.08));
  border: 2px solid rgba(227, 25, 55, 0.25);
  border-radius: 16px;
  padding: 20px;
  position: relative;
}

.agent-container-title {
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark));
  color: #fff;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  padding: 4px 16px;
  border-radius: 20px;
}

/* Flow nodes */
.flow-node {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: #ffffff;
  border: 2px solid;
  border-radius: 14px;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.08);
}

.flow-node.input {
  border-color: var(--brand-secondary);
}
.flow-node.process {
  border-color: rgba(100, 100, 120, 0.4);
}
.flow-node.gate {
  border-color: var(--warning);
}
.flow-node.output-yes {
  border-color: var(--success);
}
.flow-node.output-no {
  border-color: var(--error);
}

/* Side panel for RAG */
.rag-panel {
  background: linear-gradient(180deg, rgba(147, 51, 234, 0.08), rgba(147, 51, 234, 0.15));
  border: 2px solid rgba(147, 51, 234, 0.3);
  border-radius: 12px;
  padding: 16px;
}

/* Gate split */
.gate-split {
  display: flex;
  gap: 16px;
  justify-content: center;
}

.gate-branch {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.gate-label {
  font-size: 11px;
  font-weight: 800;
  padding: 4px 12px;
  border-radius: 10px;
}

.gate-label.yes {
  background: rgba(34, 197, 94, 0.15);
  color: var(--success);
}
.gate-label.no {
  background: rgba(239, 68, 68, 0.15);
  color: var(--error);
}
```

### Example Architecture HTML Structure

```html
<div class="architecture-diagram">
  <!-- Main Flow -->
  <div class="flow-main">
    <div class="flow-node input">
      <span class="flow-icon">📄</span>
      <div class="flow-content">
        <span class="flow-label">Input Request</span>
        <span class="flow-sub">JIRA · Email · Form</span>
      </div>
    </div>

    <div class="flow-arrow">▼</div>

    <!-- System Boundary -->
    <div class="agent-container">
      <span class="agent-container-title">🤖 AI Agent Pipeline</span>

      <div class="flow-node process">
        <span class="flow-icon">🚪</span>
        <div class="flow-content">
          <span class="flow-label">Front Door</span>
          <span class="flow-sub">Parse · Normalize · Validate</span>
        </div>
      </div>

      <div class="flow-arrow">▼</div>

      <div class="flow-node gate">
        <span class="flow-icon">⚖️</span>
        <div class="flow-content">
          <span class="flow-label">Gate Decision</span>
          <span class="flow-sub">Quality check</span>
        </div>
      </div>

      <!-- YES/NO Split -->
      <div class="gate-split">
        <div class="gate-branch">
          <span class="gate-label no">✗ NO</span>
          <div class="output-card error">
            <span>📋</span>
            <span>Gap Report</span>
          </div>
        </div>
        <div class="gate-branch">
          <span class="gate-label yes">✓ YES</span>
          <div class="output-card success">
            <span>📊</span>
            <span>Analysis</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Side RAG Panel -->
  <div class="rag-panel">
    <span class="rag-title">Vector Store</span>
    <div class="rag-item">📚 Past Intakes</div>
    <div class="rag-item">📄 Documents</div>
    <div class="rag-connector">◀── Semantic Search</div>
  </div>
</div>
```

## Output Location

Save the generated HTML to:

- `001-*/project-infographic.html` (if spec folder exists)
- Or `docs/project-infographic.html`
- Or root `project-infographic.html`

Include a timestamp in the footer: `Generated: YYYY-MM-DD`

## Important Rules

1. **KEEP IT HIGH-LEVEL** - No code snippets, no API details, no implementation specifics
2. **VISUAL FIRST** - Every section should have visual elements (icons, cards, flows)
3. **SINGLE FILE** - All CSS embedded, no external dependencies
4. **DEMO-READY** - Should look polished in a meeting room screen share
5. **SCANNABLE** - 30 seconds to understand the project at a glance
6. **ACCURATE** - Cross-reference with actual code/docs, don't invent features

## Sample Invocation Phrases

- "Generate project infographic"
- "Create a visual overview for the demo"
- "Make a stakeholder presentation page"
- "Build an executive summary HTML"
- "Sprint demo visual"
