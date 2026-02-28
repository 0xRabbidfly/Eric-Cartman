# Vault Link Analysis Report

**Vault**: Obsidian Vault | **Notes**: 3,836 | **Date**: 2026-02-27

---

## Health Metrics

| Metric | Count | % of Vault | Status |
|--------|------:|:----------:|:------:|
| Total notes | 3,836 | — | — |
| Orphaned notes (no backlinks) | 1,697 | 44% | 🔴 |
| Dead-end notes (no outgoing links) | 3,188 | 83% | 🔴 |
| Unresolved (broken) links | 43 | — | 🟡 |
| Unique tags | 88 | — | — |

> **Critical finding**: 83% of notes are dead-ends (no outgoing links) and 44% are fully orphaned. The vault's connective tissue is severely underdeveloped.

---

## 🔴 Orphan Density by Subject Area

| Area | Orphaned / Total | % | Status |
|------|------------------:|:-:|:------:|
| Philosophy | 55 / 55 | 100% | 🔴 |
| Social Complexity | 61 / 61 | 100% | 🔴 |
| Systems Thinking | 24 / 24 | 100% | 🔴 |
| Agile | 219 / 219 | 100% | 🔴 |
| Cycling | 353 / 353 | 100% | 🔴 |
| Crypto | 190 / 190 | 100% | 🔴 |
| NFTs | 248 / 249 | 100% | 🔴 |
| Books | 80 / 103 | 78% | 🔴 |
| Research/Library | 10 / 11 | 91% | 🔴 |

> Every major subject area is essentially a disconnected silo. Notes exist in isolation within their folder structure — folders are doing the work that links should be doing.

---

## 🔗 Missing Link Opportunities (Top 20)

### Cluster 1: AI / Agents / Skills (High Priority)

All 11 Research/Library notes are islands — zero cross-links despite covering the same domain.

1. **[[ai-second-brain-obsidian-claude-code]]** ↔ **[[complete-guide-building-skills-for-claude]]**
   - Relationship: Both cover building AI skills for Obsidian/Claude workflows
   - Confidence: **High**
   - Suggested: Add `See also [[complete-guide-building-skills-for-claude|Complete Guide to Building Skills]]` to the Second Brain note

2. **[[agent-skills-vscode-docs]]** ↔ **[[vscode-custom-agents]]**
   - Relationship: Both are VS Code Copilot documentation — skills vs. agents
   - Confidence: **High**
   - Suggested: Add mutual links under a "Related VS Code Docs" section

3. **[[agent-skills-vscode-docs]]** ↔ **[[custom-instructions-vscode-docs]]**
   - Relationship: Skills vs. Instructions — complementary VS Code customization mechanisms
   - Confidence: **High**
   - Suggested: Cross-link to clarify when to use skills vs. instructions

4. **[[vscode-agent-hooks]]** ↔ **[[vscode-custom-agents]]**
   - Relationship: Hooks extend custom agent behavior — direct dependency
   - Confidence: **High**
   - Suggested: Link hooks as a capability of custom agents

5. **[[best-practices-claude-code]]** ↔ **[[complete-guide-building-skills-for-claude]]**
   - Relationship: Best practices for the tool that runs skills
   - Confidence: **High**
   - Suggested: Cross-reference under "Workflow" sections

6. **[[skillsbench-benchmarking-agent-skills]]** ↔ **[[agent-skills-vscode-docs]]**
   - Relationship: Academic benchmarking of the skills concept documented in VS Code docs
   - Confidence: **High**
   - Suggested: Link SkillsBench as evidence/evaluation framework for skills

7. **[[delete-your-agents-md-vs-add-evals]]** ↔ **[[custom-instructions-vscode-docs]]**
   - Relationship: Debate about instructions.md quality — docs provide the official guidance
   - Confidence: **High**
   - Suggested: Link official docs as counterpoint to the "delete" argument

8. **[[rag-pipeline-explained]]** ↔ **[[ai-second-brain-obsidian-claude-code]]**
   - Relationship: RAG is one retrieval approach; the "second brain" article offers an alternative (agent-based)
   - Confidence: **Medium**
   - Suggested: Cross-link under "Alternative Approaches" sections

9. **[[every-saas-is-now-an-api]]** ↔ **[[vscode-agent-hooks]]**
   - Relationship: APIs as agent tools; hooks as integration points
   - Confidence: **Medium**
   - Suggested: Link as a "why this matters" reference from hooks

### Cluster 2: Daily Notes → Library (High Priority)

10. **All 5 Daily Notes** (2026-02-23 through 2026-02-27) → **Research/Library**
    - Relationship: Dailies contain AI research summaries that directly reference Library topics but use zero `[[wikilinks]]`
    - Confidence: **High**
    - Suggested: Add `[[library-note-name]]` links wherever topics are discussed in dailies

### Cluster 3: Complexity / Systems Thinking (Medium Priority)

61 notes discuss BOTH complexity and systems thinking but have zero cross-links.

11. **[[🧠 MOC - Complexity & Systems Thinking]]** → **All 24 Systems Thinking notes**
    - Relationship: The MOC exists but the orphan data shows the Systems Thinking folder is 100% orphaned — the MOC either doesn't link to them or uses folder references instead of wikilinks
    - Confidence: **High**
    - Suggested: Expand the MOC with `[[Note Name]]` links to all 24 notes

12. **[[Complex Responsive Processes in Organizations - Ralph D. Stacey]]** ↔ **[[Cynefin Framework]]**
    - Relationship: Both address complexity in organizations from different theoretical frameworks
    - Confidence: **High**
    - Suggested: Cross-link under "Theoretical Frameworks" in both

13. **[[Cilliers on Organizations]]** ↔ **[[Complex Adaptive Systems - CAS -]]**
    - Relationship: Cilliers's work is foundational to CAS theory
    - Confidence: **High**
    - Suggested: Link Cilliers as a key author in the CAS note

14. **[[Thinking in Systems - Donella Meadows (2008)]]** ↔ **[[8 System Archetypes]]**
    - Relationship: Meadows defines system archetypes — direct source material
    - Confidence: **High**
    - Suggested: Link as source reference

15. **[[The Fifth Discipline - Peter Senge]]** ↔ **[[Systems Thinking Definition]]**
    - Relationship: Senge popularized systems thinking in management — key reference
    - Confidence: **High**
    - Suggested: Link Senge under "Key Authors"

### Cluster 4: IDEAS/Raven Project (Medium Priority)

All 18 Raven notes are orphaned with zero backlinks.

16. **[[Raven lore]]** ↔ **[[Spec-kit]]**
    - Relationship: Outgoing links exist from Raven lore, but Spec-kit doesn't link back
    - Confidence: **High**
    - Suggested: Add backlink from Spec-kit to Raven lore

17. **[[Workflow]]** (Raven) ↔ **[[ai-second-brain-obsidian-claude-code]]**
    - Relationship: Raven Workflow mentions Copilot; Library note covers same domain
    - Confidence: **Medium**
    - Suggested: Cross-link between Raven's workflow and the Library research

### Cluster 5: Books → Subject Notes (Medium Priority)

80 orphaned book notes could link to their subject areas.

18. **[[Flow - Mihaly Csikszentmihalyi]]** ↔ **[[Complex Adaptive Systems - CAS -]]**
    - Relationship: Flow state connects to emergent behavior in complex systems
    - Confidence: **Medium**
    - Suggested: Link under "Related Concepts"

19. **[[Predictably Irrational - Dan Ariely (2008)]]** ↔ **[[Cynefin Framework]]**
    - Relationship: Ariely's behavioral economics connects to Cynefin's decision-making in complex domains
    - Confidence: **Medium**
    - Suggested: Cross-reference under cognitive biases

20. **[[Essential Deming]]** ↔ **[[POOGI]]** (Goldratt's Process of Ongoing Improvement)
    - Relationship: Deming's continuous improvement and Goldratt's POOGI are parallel frameworks
    - Confidence: **High**
    - Suggested: Cross-link under "Continuous Improvement Philosophy"

---

## 🏝️ Orphaned Notes Worth Connecting (Priority Clusters)

### Research/Library (10 orphaned)
These are your most recent, highest-value AI research notes — all disconnected:

| Note | Topic | Should Link To |
|------|-------|---------------|
| `ai-second-brain-obsidian-claude-code` | Obsidian+Claude workflow | `complete-guide-building-skills-for-claude`, `best-practices-claude-code` |
| `skillsbench-benchmarking-agent-skills` | Agent skill evaluation | `agent-skills-vscode-docs`, `complete-guide-building-skills-for-claude` |
| `complete-guide-building-skills-for-claude` | Building Claude skills | `agent-skills-vscode-docs`, `best-practices-claude-code` |
| `agent-skills-vscode-docs` | VS Code skills docs | `custom-instructions-vscode-docs`, `vscode-custom-agents` |
| `rag-pipeline-explained` | RAG architecture | `ai-second-brain-obsidian-claude-code` |
| `vscode-agent-hooks` | Hook automation | `vscode-custom-agents`, `agent-skills-vscode-docs` |
| `vscode-custom-agents` | Custom agents | `agent-skills-vscode-docs`, `vscode-agent-hooks` |
| `custom-instructions-vscode-docs` | Instructions docs | `agent-skills-vscode-docs`, `vscode-custom-agents` |
| `best-practices-claude-code` | Claude Code tips | `complete-guide-building-skills-for-claude` |
| `every-saas-is-now-an-api` | SaaS→API trend | `vscode-agent-hooks` |

### IDEAS/Raven (18 orphaned)
Every note in this project is disconnected. The `Raven lore` note has 5 outgoing links but receives none back.

### Books (80 orphaned)
Book notes don't link to the theoretical concepts they discuss (Philosophy, Systems Thinking, Complexity).

---

## 🗺️ Suggested MOC (Map of Content) Notes

### 1. **[[MOC - AI Agent Development]]** (NEW)
Would connect all 11 Research/Library notes + relevant Raven notes + Daily references:
- `[[ai-second-brain-obsidian-claude-code]]`
- `[[skillsbench-benchmarking-agent-skills]]`
- `[[complete-guide-building-skills-for-claude]]`
- `[[agent-skills-vscode-docs]]`
- `[[vscode-custom-agents]]`
- `[[vscode-agent-hooks]]`
- `[[custom-instructions-vscode-docs]]`
- `[[best-practices-claude-code]]`
- `[[rag-pipeline-explained]]`
- `[[every-saas-is-now-an-api]]`
- `[[delete-your-agents-md-vs-add-evals]]`

> **Impact**: Instantly connects 11 isolated notes into a navigable knowledge hub.

### 2. **[[MOC - Raven Project]]** (NEW)
The 18 Raven notes have zero connective tissue:
- `[[Raven lore]]`, `[[Spec-kit]]`, `[[Workflow]]`, `[[PEPEDAWN]]`
- `[[Deployment Steps]]`, `[[Ethereum Network Details]]`
- All sub-notes under Spec-kit and Raven lore

### 3. **[[🧠 MOC - Complexity & Systems Thinking]]** (EXISTS — needs expansion)
Currently exists but ~48 complexity/systems thinking notes are still orphaned despite it. The MOC likely needs to be audited and expanded with explicit `[[wikilinks]]` to:
- All 24 Systems Thinking folder notes
- All 61 Social Complexity folder notes
- Key book notes (Meadows, Senge, Stacey, Cilliers, Deming, Ackoff)

### 4. **[[MOC - Agile & Lean]]** (NEW)
219 orphaned Agile notes — zero incoming links. Would connect:
- Transformation models, Practices, Blog posts
- Lean principles (7 lean principles)
- Book notes (Goldratt, Ambler, Apello)

---

## 🔴 Broken Links (Unresolved)

| Broken Link | Referenced In | Suggestion |
|-------------|--------------|------------|
| `ˈvɛltʔanˌʃaʊ.ʊŋ` | `Weltanschaung.md` | Fix → `[[Weltanschaung]]` (IPA pronunciation used as link) |
| `Books` | `🧠 MOC - Complexity & Systems Thinking.md` | Create `[[Books]]` index or link to specific book folder |
| `Work` | `🧠 MOC - Complexity & Systems Thinking.md` | Create `[[Work]]` index or link to specific work folder |
| `f` | `Cynefin Framework.md` | Likely a typo — remove or fix to intended target |
| `KAIA_Personal_Details_image_1.webp` | `KAIA Personal Details.md` | Missing image file — re-add or remove reference |
| Numbered/coordinate links (1–30) | Multiple Philosophy & Excalidraw notes | Canvas/Excalidraw artifacts — likely not real broken links |

> 37 of the 43 "unresolved" links are Excalidraw canvas coordinate artifacts, not real broken links. **Only 6 genuine broken links** need attention.

---

## 🏷️ Tag Cleanup Opportunities

### High-Confidence Duplicates (merge recommended)

| Keep | Merge Into It | Combined Count |
|------|--------------|:--------------:|
| `#agents` (25) | `#AIagents` (2), `#LLM-agents` (1), `#AGENTS-md` (2), `#agent-md` (1) | 31 |
| `#skills` (14) | `#agent-skills` (3), `#SKILL-md` (3), `#SkillsBench` (1), `#agentskills-io` (1) | 22 |
| `#claude-code` (2) | `#CLAUDE-md` (2), `#claude` (1) | 5 |
| `#instructions` | `#instructions-md` (2), `#custom-instructions` (1), `#copilot-instructions-md` (1), `#copilot-instructions` (1) | 5 |
| `#machine-learning` (1) | `#MachineLearning` (2) | 3 |
| `#systems-thinking` (1) | `#systemsthinking` (1) | 2 |

### Suggested New Tags (for under-tagged clusters)
- `#complexity-theory` — for the 61 Social Complexity notes (currently only 4 use `#complexity`)
- `#book-notes` — for the 103 Books notes (no shared tag)
- `#cycling` — for the 353 Cycling notes (no shared tag)

---

## 📊 Priority Actions (Recommended Order)

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 1 | Create **MOC - AI Agent Development** linking all 11 Library notes | High — connects your most active research | Low (~5 min) |
| 2 | Add `[[wikilinks]]` from Daily Notes to Library notes they discuss | High — connects dailies to permanent notes | Medium (~15 min) |
| 3 | Cross-link all 11 Research/Library notes to each other | High — creates a navigable AI research graph | Medium (~15 min) |
| 4 | Expand **🧠 MOC - Complexity & Systems Thinking** with explicit links | High — connects 100+ orphaned notes | Medium (~20 min) |
| 5 | Merge duplicate tags (`#agents` family, `#skills` family) | Medium — cleaner taxonomy | Low (~10 min) |
| 6 | Fix 6 genuine broken links | Low — cosmetic cleanup | Low (~5 min) |
| 7 | Create **MOC - Agile & Lean** for 219 orphaned Agile notes | Medium — rescues the largest orphan cluster | Medium (~20 min) |
| 8 | Create **MOC - Raven Project** for 18 orphaned project notes | Medium — project context recovery | Low (~10 min) |

---

*Report generated by `obsidian-vault-linker` skill — 2026-02-27*
