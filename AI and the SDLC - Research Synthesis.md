---
tags: [ai, sdlc, research-synthesis, consulting-firms, agentic-ai, software-engineering]
status: complete
date: 2026-04-11
type: research-synthesis
---

# AI & the SDLC: How It Must Change

**Research Synthesis from Top Consulting Firms & Think Tanks**

## Research Decomposition

To answer this question comprehensively, five sub-questions were investigated:

1. What is the core argument each firm is making about SDLC change?
2. Where are the real productivity gains, and where are they being wasted?
3. What structural/process changes do firms say are required?
4. What are the role/talent implications?
5. What is the emerging "agentic" SDLC horizon firms are pointing to?

---

## Primary Source Citations by Firm

### McKinsey -- February 2025

**"How an AI-enabled software product development life cycle will fuel innovation"**
Authors: Chandra Gnanasambandam, Martin Harrysson, Rikki Singh, Aditi Chawla
[Source](https://www.mckinsey.com/industries/technology-media-and-telecommunications/our-insights/how-an-ai-enabled-software-product-development-life-cycle-will-fuel-innovation)

**Core Argument:**

> AI has the potential to fundamentally transform the development of software products, increasing the pace of the process and the quality of the final output.

McKinsey frames this not as a productivity upgrade but as a full redesign of the Product Development Life Cycle (PDLC): this technological shift has the potential to "accelerate the process, improve product quality, increase customer adoption and satisfaction, and spur greater innovation."

**Five Critical Shifts McKinsey Identifies:**

1. **Significantly faster time to market** -- AI automates time-consuming tasks such as project management, market analysis, performance testing, and feedback analysis, freeing PMs and engineers to focus on higher-value creative work. As Reddit CPO Pali Bhat is quoted: "New feature definition, prototyping, and testing are all happening in parallel and faster than ever before. Our teams can now dream up an idea one day and have a functional prototype the next."
2. **Products deliver customer value sooner** -- AI stitches together fragmented customer data -- telemetry, service tickets, social media sentiment, competitive research -- so teams build to customer value from the outset, not after several release cycles.
3. **More good ideas see the light of day** -- AI eliminates the strict dividing line between discovery and viability, enabling quick prototyping and automated A/B testing. This also reduces "HiPPO bias" (highest-paid person's opinion) in prioritization.
4. **PMs become "mini-CEOs"** -- AI now makes meaningful contributions to every phase of the lifecycle, which means you'll need to rethink the lifecycle from the ground up, across requirements gathering, architecture creation, code generation and cross-repository awareness. McKinsey specifically projects that PM roles may subsume PMM, PO, TPM, and UX roles as AI handles those tasks.
5. **Quality, risk, compliance, and accessibility move left** -- Instead of being addressed late, quality and security testing must be embedded earlier in discovery.

> Increased Volume: AI tools are enabling developers to produce significantly more code and applications than ever before... but for your security team, the workload is multiplying while your resources remain constrained.

**On Developer Productivity:**

> McKinsey research has found that AI can improve developer productivity by up to 45% -- but code generation is only one part of the story. AI is already starting to have a positive influence on SDLC from end to end, collapsing stages, automating workflows and integrating intelligence throughout.

**On Organizational Transformation:**

> "Just as agile tools didn't enable PMs to create business value faster, and DevOps tools didn't allow engineers to release more frequent updates without adopting new roles and operating models, merely adopting AI tools isn't enough to transform the software PDLC."

---

### Bain & Company -- September 2025

**"From Pilots to Payoff: Generative AI in Software Development"**
Part of Bain's Technology Report 2025
Authors: Purna Doddapaneni, Bill Radzevych, Steven Breeden, Bharat Bansal, Tanvee Rao
[Source](https://www.bain.com/insights/from-pilots-to-payoff-generative-ai-in-software-development-technology-report-2025/)

**Core Argument -- The Productivity Paradox:**

> Generative AI arrived on the scene with sky-high expectations, and many companies rushed into pilot projects. Yet the results haven't lived up to the hype. Two out of three software firms have rolled out generative AI tools, and among those, developer adoption is low. Teams using AI assistants see 10% to 15% productivity boosts, but often the time saved isn't redirected toward higher-value work. So even those modest gains don't translate into positive returns. Without a plan to turn interest into habit, initial gains quickly evaporate, leaving leaders asking, "Where's the payoff?"

**Why Code-Only AI Fails -- The Bottleneck Problem:**

> "Speeding up these (coding) steps does little to reduce time to market if others remain bottlenecked."

The root cause: writing and testing code only accounts for about 25% to 35% of the time from initial idea to product launch.

> The software development lifecycle, for example, includes more than 40 discrete use cases. With less than half of developer time spent "hands on keyboard," copilots alone are insufficient. Meaningful productivity gains require coordinated changes across design, testing, code review, and planning.

**What Leaders Do Differently:**

> Leading adopters treat generative AI as a fundamental transformation of their software development life cycle rather than a one-off project. They take a future-back approach to rearchitect their end-to-end software development life cycle around generative AI, embedding it deeply into workflows and scaling it enterprise-wide.

Bain's case study: Goldman Sachs integrated AI into its internal development platform and fine-tuned it on the bank's codebase, extending benefits from autocomplete to automated testing and code generation. These companies didn't just add AI to existing workflows, they rebuilt workflows around AI. The Bain Technology Report 2025 shows these organizations are achieving 25-30% productivity gains, far above the 10% from basic code assistants, because they addressed the entire lifecycle, not just coding.

**Common Roadblocks Bain Identifies:**

- No measurement framework: "tough to prove generative AI's value without clear KPIs."
- 73% said they use AI in software development, up from 66% a year earlier
- Executives say that 80% of generative AI use cases met or exceeded expectations, but only 23% can tie initiatives to new revenue or lower costs.

**On Bain's 2024 Tech Report (Earlier Findings):**

> Some developer organizations are already saving 15% to 40% on code generation and documentation, and 30% to 50% or more on refactoring, select testing, and debugging use cases by utilizing the specific patterns and rich datasets that exist beyond the code base.

---

### BCG (Boston Consulting Group) -- May 2024 + April 2025

**"The Art of Scaling GenAI in Software"** (May 2024)
Authors: Pranay Ahlawat, Julie Bedard, Sankalp Damani, Ben Feldman, et al.
[Source](https://www.bcg.com/publications/2024/the-art-of-scaling-genai-in-software)

**"AI-Enabled Engineering Excellence"** (April 2025 Executive Perspectives)
[Source](https://www.bcg.com/assets/2025/executive-perspectives-ai-enabled-engineering-excellence-23april.pdf)

**Core Argument -- Organizational Transformation, Not Tool Deployment:**

> While everyone is experimenting, most organizations struggle to realize impact. To unlock full value, GenAI must go beyond code copilot tool deployments: It must be embedded into core engineering strategies. This means tackling platform, tooling, process, and talent.

BCG's April 2025 survey-based report finds:

> Human-AI collaboration can double SDLC productivity... Industry turning point: >80% of companies now use GenAI for coding, yielding early gains (~5-10% cost savings, ~15% performance boost). However, value remains spotty and limited to pockets.

Their model shows 30% productivity from maximizing AI code generation tools, an additional 20% from extending tools to non-coding stages (including via agents), with a 2x multiplier if working on a modern technology stack.

**Coding Accounts for Only 10-15% of Development Lead Time:**

> Coding accounts for only 10% to 15% of the time from when an idea joins the queue to when the product gets into customers' hands.

Release activities (new product introduction, sales enablement, pricing changes) account for 30-40% of the development lifecycle.

**Six Barriers BCG Identifies:**

- 50% of CIOs struggle to quantify GenAI's impact
- Outdated systems and poor DevOps severely dampen GenAI's impact
- GenAI tools evolve rapidly -- engineers get change fatigue with "tool churn" unless a stable platform exists

**BCG's "Generative Engineering" Principles:**

> These risks aren't reasons to avoid Generative Engineering. They're reasons to evolve your software development lifecycle (SDLC) and coding practices. Generative Engineering tools can yield complete, high-quality solutions much faster--but it does require intentionality and discipline. One practical approach: Treat AI-generated output as a pull request. Encourage a "lead engineer" mindset at every level.

**BCG on AI Maturity and Real Returns:**

> According to a new report from Boston Consulting Group, only 5% of companies in its 2025 study of more than 1,250 global firms are seeing real returns on AI. Meanwhile, 60% of companies have seen little to no benefit, reporting only minimal increases in revenue and cost savings despite making substantial investments.

---

### Deloitte -- March 2026

**"The Future of Software Engineering: The Unconstrained AI Era"**
Authors: Kavitha Prabhakar, Akash Tayal, Daniel Grayson, Heather Walker, Drew Davidson
[Source](https://www.deloitte.com/us/en/services/consulting/articles/future-of-software-engineering.html)

**"AI Software Development and Engineering Roles are Being Rewritten"**
[Source](https://www.deloitte.com/us/en/Industries/tmt/articles/ai-software-development-engineering-roles-being-rewritten.html)

**Core Argument -- The "Unconstrained Engineering" Thesis:**

Deloitte's most recent (March 2026) piece makes the most sweeping claim of any firm: Software engineering is "becoming the defining core of the enterprise" and is shifting from being "measured by capacity and productivity to becoming a self-compounding capital asset."

> Agents can accelerate the software development life cycle (SDLC) by becoming co-creators, force multipliers, technology accelerators and self-evolving platforms. In traditional models, greenfield development is constrained by human throughput: ideation cycles, backlog refinement, architectural debate and manual experimentation. Agentic engineering collapses these constraints.

> The most profound shift in the SDLC model occurs when agents are no longer confined to applications but begin shaping the engineering system itself. This is where unconstrained engineering fully emerges. The engineering system becomes self-improving--continuously adapting how products and platforms are built, tested, deployed and operated without requiring constant human intervention.

**Three Future Scenarios Deloitte Outlines:**

> Engineering shifts from execution to intent, enabled by autonomous agents. Humans define intent and outcomes, constraints and guardrails. AI agents become capable of executing complex engineering tasks end to end, such as refactoring, greenfield development and on-going run of the tech stack.

1. Self-Driving Engineering Core
2. Assisted Execution
3. Agent Rejection (backlash scenario)

Deloitte says the most likely outcome is the first, with human stewardship.

**Role Transformation -- Deloitte's SDLC Role-by-Role Analysis:**

> As AI-enabled solutions enter the market, the greatest value has been realized when GenAI is embedded throughout the entire SDLC, rather than focusing solely on coding.

Effects on roles:
- Product managers use GenAI to transform business requirements into user stories
- Software architects can easily edit, update, and publish diagrams generated by LLMs
- GenAI improves development and quality by creating initial designs directly from stories
- GenAI is revolutionizing data engineering by automating processes, optimizing data pipelines, and enhancing data quality

> "Agentic" does not imply replacing people but rather elevating them--transforming product managers into intent-setters, developers into reviewers and security teams into independent responders.

**Governance Warning:**

> The 2024 DORA Accelerate State of DevOps Report provides a warning: AI use was associated with a 7% decrease in stability when not paired with systemic safeguards (small batch sizes and testing), despite roughly a 2% increase in individual productivity.

---

### Forrester -- 2024/2025

**"The Future Is Now: TuringBots Will Collapse the SDLC Silos"** (May 2024)
VP Principal Analyst Diego Lo Giudice
[Source](https://www.forrester.com/blogs/the-future-is-now-turingbots-will-collapse-the-software-development-life-cycle-siloes/)

**"AI Is Rewriting Software Work: What It Means For Your Team"** (2025)
[Source](https://www.forrester.com/blogs/ai-is-rewriting-software-work-what-it-means-for-your-team/)

**Core Argument -- TuringBots and SDLC Silo Collapse:**

> Thanks to TuringBots (AI and generative AI for software development), software development is on the cusp of a transformative change, one that promises to redefine the way development teams collaborate, create, and deploy applications.

> The software development lifecycle (SDLC) is being accelerated and reimagined as a process happening in real time. By 2028, the SDLC will become less visible and development will become real-time, with all collaboration and assets generated on the fly, tested, and checked over by a TuringBot that operates behind the scenes. A new breed of AI-infused platforms enabling fast iteration for top-down and ground-up application generation will rise: AppGen platforms.

**Forrester's Workforce Study:**

> Predictive, generative, and agentic AI are catalyzing the most dramatic workforce shift that the SDLC has seen in years -- with hours moving from repetitive artifact production toward higher-leverage activities such as workflow orchestration, architecture validation, controls, and customer value realization.

> AI isn't replacing developers; it's changing what developers (and their teammates) do day to day. As AI takes on more of the artifact creation (code, tests, docs), human roles expand toward orchestration, systems thinking, governance, and business alignment.

> According to Forrester's November 2025 guidance, the convergence of roles is now a best practice: Smaller, cross-functional pods can steer agents more efficiently than fragmented teams developed in the pre-GenAI era.

**Forrester's Prescriptions:**

- Reskill -- don't downsize. The fastest ROI comes from upskilling existing teams to apply AI across the whole SDLC (not just coding).
- Shift measurement from activity metrics to outcomes, such as customer value, cycle time to impact, reliability, and risk posture.
- Institutionalize "governance by design" principles. As agentic patterns spread, treat "governance as code" and "observability as code" as first-class artifacts.

---

### Gartner -- July 2025

**"Top Strategic Trends in Software Engineering for 2025 and Beyond"**
[Source](https://www.gartner.com/en/newsroom/press-releases/2025-07-01-gartner-identifies-the-top-strategic-trends-in-software-engineering-for-2025-and-beyond)

**Core Findings:**

> AI-native software engineering is transforming the software development life cycle (SDLC) by embedding AI into every phase, from design to deployment. These practices enable AI to autonomously or semi-autonomously handle a significant share of tasks across SDLC.

- Gartner predicts that by 2028, 90% of enterprise software engineers will use AI code assistants, up from less than 14% in early 2024.
- The role of developers will shift from implementation to orchestration, focusing on problem solving and system design.
- Only 39% of IT leaders believe their current development processes are agile enough to support modern business growth objectives.

---

### PwC (Bonus Citation)

**"Responsible AI in the Software Development Lifecycle: Building Trust Into the Code"**
[Source](https://www.pwc.com/us/en/tech-effect/ai-analytics/responsible-ai-sdlc.html)

> AI is reshaping the SDLC, driving faster, more consistent delivery as agentic AI expands developer capabilities and impact. Responsible AI provides the governance, transparency, and human oversight to help scale these technologies with confidence.

> Emerging agentic AI systems can add another layer of risk: unexpected or cascading behaviors, infrastructure incompatibility, and accountability gaps that can lead to security vulnerabilities or unmaintainable code.

---

## Cross-Firm Synthesis: The 7 Required Changes to the SDLC

Based on all sources read in full, here is where there is strong consensus across firms:

| Change | Firms Aligned |
|--------|---------------|
| 1. Stop treating AI as a code-generation point tool; embed across entire SDLC | McKinsey, Bain, BCG, Deloitte, Forrester |
| 2. Shift left on quality, security, and compliance | McKinsey, Bain, Deloitte |
| 3. Kill sequential phase gates; move to parallel, continuous workflows | McKinsey, BCG, Forrester |
| 4. Rebuild measurement frameworks (DORA + AI-specific KPIs) | Bain, BCG, Gartner, Forrester |
| 5. Converge PM, design, and engineering roles | McKinsey, Deloitte, BCG |
| 6. Modernize the underlying tech stack (you can't AI-enable legacy) | BCG, Bain, Deloitte |
| 7. Govern for agents, not just copilots | Deloitte, Forrester, PwC, Gartner |

---

## Confidence & Gaps

### High Confidence

- The "coding is only 10-35% of SDLC" finding is cited consistently across McKinsey, Bain, and BCG (with slightly different numbers: McKinsey says 10-15% of lead time; Bain says 25-35% of development time; BCG agrees). The difference is definitional but the directional conclusion is the same.
- The "10-15% productivity gain is the floor, not the ceiling" finding appears in both Bain 2024 and 2025 reports independently and is corroborated by BCG survey data.

### Conflicting Signals

- BCG's April 2025 report claims >80% of companies use GenAI for coding. Bain's survey says only 2/3 of firms have rolled out GenAI tools. These may differ by survey framing or industry mix -- neither is directly contradicted by the other, but readers should note both when quoting adoption figures.
- Productivity gain estimates vary widely: McKinsey cites 45% developer productivity gains; Bain observes only 10-15% in practice. The McKinsey figure appears to be a ceiling under optimal conditions; Bain's is the observed average. The METR randomized controlled trial (July 2025) found experienced developers were actually 19% slower with AI tools, challenging the narrative of universal AI productivity gains.

### Gaps in Coverage

- None of the Big 3 consulting firms have published deeply on the security implications of AI-native SDLCs (PwC is slightly better here). Governance of agentic systems is acknowledged but not operationally detailed.
- The measurement/instrumentation challenge is raised by every firm but none yet provides a definitive KPI framework.
- Small/mid-size company guidance is largely absent -- all case studies (Goldman Sachs, Netflix, Intuit, Reddit) are enterprise-scale.

