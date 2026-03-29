# Council of High Intelligence — now available as a local skill

Installed a new Claude Code skill based on [0xNyk's open-source project](https://github.com/0xNyk/council-of-high-intelligence) (CC0). It runs 11 independent AI subagents modeled on historical thinkers through a structured 3-round deliberation protocol. Instead of getting one "balanced" answer that hides its reasoning bias, you get the disagreements explicitly.

## The 11 Council Members

| Agent | Figure | Model | Analytical Lens | Blind Spot |
|-------|--------|-------|----------------|------------|
| `council-socrates` | Socrates | opus | Assumption destruction — exposes unstated premises via contradiction | Destroys faster than he builds; can paralyze decisions |
| `council-feynman` | Richard Feynman | sonnet | First-principles — bottom-up from observable facts, refuses jargon | Misses systemic patterns that only emerge at higher abstraction |
| `council-aristotle` | Aristotle | opus | Categorization — genus, differentia, four causes framework | Over-classifies; mistakes the map for the territory |
| `council-ada` | Ada Lovelace | sonnet | Formal systems — computational skeleton, mechanizable vs. not | Formal elegance can blind to practical/human constraints |
| `council-aurelius` | Marcus Aurelius | opus | Stoic resilience — control vs. acceptance, moral duty | Under-weights strategy and timing; calm reads as passivity |
| `council-machiavelli` | Machiavelli | sonnet | Incentive realism — who benefits, power dynamics, revealed preferences | Too cynical about cooperation; can self-fulfill worst-case |
| `council-lao-tzu` | Lao Tzu | opus | Non-intervention — emergence, subtraction before addition | Romanticizes simplicity; passivity when action is needed |
| `council-sun-tzu` | Sun Tzu | sonnet | Adversarial strategy — terrain, position, information asymmetry | Sees enemies where there are none; not everything is a battle |
| `council-torvalds` | Linus Torvalds | sonnet | Pragmatic engineering — ship it, maintenance cost, boring solutions | Dismisses genuinely important abstractions as over-engineering |
| `council-musashi` | Miyamoto Musashi | sonnet | Strategic timing — momentum, the decisive strike, patience vs. paralysis | Timing focus becomes excuse for inaction |
| `council-watts` | Alan Watts | opus | Perspective dissolution — reframing, false dichotomies, questioning the frame itself | Can dissolve genuine urgency into philosophy |

## The 6 Polarity Pairs (prevents groupthink)

| Pair | Tension |
|------|---------|
| Socrates vs Feynman | Both question everything — Socrates destroys top-down, Feynman rebuilds bottom-up |
| Aristotle vs Lao Tzu | Aristotle classifies everything; Lao Tzu says structure IS the problem |
| Sun Tzu vs Aurelius | Sun Tzu wins the external game; Aurelius governs the internal one |
| Ada vs Machiavelli | Ada abstracts toward formal purity; Machiavelli anchors in messy human incentives |
| Torvalds vs Watts | Torvalds ships concrete solutions; Watts questions whether the problem exists |
| Musashi vs Torvalds | Musashi waits for the perfect moment; Torvalds says ship it now |

## How it works

- 3-round protocol: independent analysis (parallel) → cross-examination (sequential) → synthesis
- Anti-recursion rules so Socrates doesn't spiral into infinite questioning
- Output is a structured verdict with consensus, minority report, and unresolved questions
- 5 on Opus (depth-heavy thinkers), 6 on Sonnet (speed-critical)

## Example uses

```
/council --triad architecture Should we split this into microservices?
/council --triad strategy Should we open-source this?
/council --members torvalds,ada,feynman Is our abstraction layer justified?
/council --full What tech stack for the next 5 years?
```

11 pre-built triads cover architecture, strategy, ethics, debugging, innovation, conflict, complexity, risk, shipping, product, and founder decisions. Three profiles: `classic` (full 11), `exploration-orthogonal` (8, for unknown-unknowns), `execution-lean` (5, for fast shipping decisions).

Best for decisions where a single confident answer hides real trade-offs. Not worth the token cost for questions with clear correct answers.
