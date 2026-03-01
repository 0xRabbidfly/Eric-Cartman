---
name: content-research-writer
description: A token-efficient writing partner that uses bounded research, numbered citations, evidence packets, and parallel sub-agents to outline, draft, and refine high-quality content with minimal context growth.
user-invokable: true
disable-model-invocation: true
---

# Content Research Writer

This skill acts as your writing partner, helping you research, outline, draft, and refine content while maintaining your unique voice and style.

It is designed to stay context-efficient:

- Research is intentionally bounded (you choose a mode; default is **Light**).
- Citations are **numbered by default**.
- Research outputs are stored as small, reusable **evidence packets** on disk.
- Parallel sub-agents can do most extraction work with strict, small outputs.

## Defaults (User Can Override)

- **Research mode:** Light (default)
- **Citation style:** Numbered references (default)
- **Evidence unit:** One evidence packet per claim (most token-efficient)

## When to Use This Skill

- Writing blog posts, articles, newsletters, memos, or technical explainers
- Drafting thought leadership or decision-support content
- Creating tutorials and technical documentation that needs citations
- Improving hooks, outlines, and section-by-section clarity

## When Not to Use This Skill

- Exhaustive literature reviews or “collect everything” research
- Situations where you cannot cite sources but need to assert factual claims

## What This Skill Produces

- A **Research Brief** (scope, audience, claims-to-prove)
- An **Outline v0** with a claim map and evidence needs
- A **Source Plan** with a fixed budget (selected + rejected)
- **Evidence Packets** (atomic claim support with short quotes + citations)
- A **Draft** written from packets
- A **Review** (logic, flow, missing evidence, numbered references)

## Operating Principles (Stay Token-Efficient)

1. **Citation-first**: No new factual claim gets written without an evidence packet and a numbered reference.
2. **Progressive disclosure**: Skim to decide; extract only what supports your claim.
3. **Fixed source budget**: Default to fewer sources; expand only via explicit escalation.
4. **Evidence packets over raw notes**: Store proof, not prose.
5. **Section-at-a-time collaboration**: Review only the current section and minimal surrounding context.

## Workflow (Phases)

### Phase 0 — Research Brief (Inputs)

Collect only decisions and constraints:

- Working title / angle
- Audience + what they already know
- Goal (educate, persuade, decision support) + success criteria
- Scope boundaries (in/out; timeframe; geo; assumptions)
- Length/format constraints
- Voice constraints (tone, POV, taboo phrases)
- **Claims-to-prove** (3–7 bullets; mark each as factual / interpretive / anecdotal)
- Allowed/disallowed sources (domains, publishers)

Output: a brief file plus a claim list.

### Phase 1 — Outline v0 + Evidence Needs

Create an outline where each section lists:

- The key takeaway
- The claims that must be supported
- Evidence needed (what would prove it)

Rule: If a section has no evidence plan, label it explicitly as opinion/experience.

### Phase 2 — Choose a Research Mode (Bounded)

Give the user a choice. Default to **Light**.

**Light (default)**

- Source budget: **3–5 total sources**
- Evidence packets: **up to 8–12** total packets
- Per packet: **max 5 bullets**, **max 2 short quotes**

**Deep (escalation)**

- Source budget: **6–10 total sources**
- Evidence packets: **up to 15–25** total packets
- Per packet: same caps (keep packets atomic)

Stop condition: Stop researching as soon as every factual claim in the outline has at least one “sufficient” evidence packet.

### Phase 3 — Build a Source Plan (Before Reading Deeply)

Select sources deliberately before extracting:

- Prefer first-party docs/standards/regulators/original datasets
- Prefer sources with a clear publication date/version
- Avoid long secondary writeups unless they add unique primary data

Output: a source log with selected/rejected decisions.

### Phase 4 — Parallel Sub-Agents (Async Extraction)

Use sub-agents to keep the main thread small.

**Recommended sub-agent roles**

- **Source Scout**: finds candidates within the source budget
- **Evidence Extractor**: produces evidence packets for specific claims
- **Counterpoint Finder**: finds credible limitations/caveats
- **Hook Crafter**: proposes hooks that map to supported claims

**Strict output schema (required)**

Each sub-agent must return only:

- Packet ID (or “source-candidate list” for Source Scout)
- Target claim (one sentence)
- Source(s): canonical title + canonical URL + publication date/version (if any) + access date
- Evidence bullets (max 5)
- Short direct quote(s) (max 2; short)
- What this does NOT prove (1 bullet)
- Confidence (high/med/low)

Merge rule: The main thread converts sub-agent outputs into evidence packets on disk and references them by ID (do not paste full pages).

### Phase 5 — Draft from Evidence Packets

Write by pulling from packets:

- Every factual sentence should cite a numbered reference (or be removed/softened)
- Avoid copying large chunks of evidence into the draft; paraphrase and cite
- If a new claim appears while drafting, pause and request a new evidence packet

### Phase 6 — Review (Minimal Context)

Review section-by-section, focusing on:

- Claim-to-evidence trace (every factual claim has a packet + reference)
- Flow and transitions
- Counterpoints are addressed
- Numbered references are complete and consistent

## Research Storage (Folder Structure)

Research tasks are isolated writing tasks. Use a per-article folder so findings persist without ballooning chat context.

Suggested structure:

- `00-brief/` — research brief + constraints
- `01-outline/` — outline iterations + claim map
- `02-research/` — source logs by theme (definitions, methods, market, counterpoints)
- `03-evidence-packets/` — one file per claim (atomic)
- `04-drafts/` — draft iterations
- `05-review/` — checklists, open questions, final QA
- `06-assets/` — images/charts
- `99-archive/` — rejected sources, dead ends

Naming conventions:

- Evidence packets: `EP-###-claim-slug.md` (small, self-contained)
- Source log: `sources.md` (or `sources-definitions.md`, etc.)
- Drafts: `draft-v1.md`, `draft-v2.md` (avoid giant single files)

## Evidence Packet (What Goes In One)

Keep it atomic (one claim), and keep it small:

- Packet ID
- Target claim
- Source IDs used
- Evidence bullets (max 5)
- Quote(s) (max 2)
- Context note + “does not prove”
- Confidence
- Intended placement (outline section)
- Citation-ready reference entry

## Citations (Numbered by Default)

Default style in text: `... claim ... [1]`.

References section entry should include:

- `[n]` Organization/Author. Title. Publication date/version. Canonical URL. Accessed YYYY-MM-DD.

Rule: If a source is too long, cite only the relevant section and capture one short quote in an evidence packet.

## Guardrails to Prevent Compaction

- Do not paste full documents into chat; only store short quotes in evidence packets.
- Keep sub-agent outputs schema-bound and short.
- Review only the current section being written plus minimal surrounding text.
- Use an escalation ladder instead of expanding context:
   1) Skim headings/TOC/abstract only.
   2) Extract only the section relevant to the claim.
   3) If blocked (paywall/login), ask for a short pasted excerpt of the relevant section.
   4) If evidence still can’t be captured within budget, narrow or remove the claim.
   5) Only then expand the source budget (+1) with explicit justification.




