"""Regenerate a summary for an existing transcript and report coverage.

Verification only — writes JSON to .work/summaries/, never touches the vault.
Usage: python _regen_check.py "<transcript stem substring>"
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import note_generator as ng  # noqa: E402

SKILL = Path(__file__).parent.parent
TRANSCRIPTS = SKILL / ".work" / "transcripts"
OUT = SKILL / ".work" / "summaries"

needle = sys.argv[1] if len(sys.argv) > 1 else "MOONSHOTS 288"
matches = [p for p in TRANSCRIPTS.glob("*.txt") if needle.lower() in p.stem.lower()]
if not matches:
    print(f"No transcript matching {needle!r}")
    sys.exit(1)

path = matches[0]
text = path.read_text(encoding="utf-8")
words = text.split()
print(f"Transcript: {path.name}")
print(f"Words: {len(words):,}")
print(f"Old code would have sent: 12,000 words ({12000 / len(words):.0%} of the episode)")
print(f"New code sends: all {len(words):,} words "
      f"in {len(ng._chunk_transcript(text))} segments\n")

summary = ng.generate_ai_summary(
    transcript_text=text,
    episode_title=path.stem,
    show_name="Moonshots with Peter Diamandis",
)

if not summary:
    print("\nFAILED: no summary produced")
    sys.exit(1)

OUT.mkdir(parents=True, exist_ok=True)
dest = OUT / (path.stem + ".regen.json")
dest.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"\n--- Result ---")
print(f"key_ideas:   {len(summary.get('key_ideas', []))}")
print(f"deep_dives:  {len(summary.get('deep_dives', []))}")
print(f"quotes:      {len(summary.get('quotes', []))}")
print(f"actionables: {len(summary.get('actionables', []))}")
bl = summary.get("backlinks", {}) or {}
print(f"backlinks:   {sum(len(v) for v in bl.values() if isinstance(v, list))}")
print(f"\nSaved: {dest}")

# Coverage probe: do any items mention material that only appears in the
# back third of the transcript? These were entirely absent from the note the
# old truncating code produced today.
tail_markers = [
    "UK", "AI Security Institute", "Matt Clifford", "Christiano",
    "GDP", "Atlanta Fed", "labor share", "universal basic",
    "Insilico", "rentosertib", "AlphaGenome", "aging clock",
    "longevity escape", "RoboCurve", "lookup table",
]
blob = json.dumps(summary, ensure_ascii=False).lower()
hits = [m for m in tail_markers if m.lower() in blob]
print(f"\nBack-third coverage probe: {len(hits)}/{len(tail_markers)} markers present")
print(f"  found:   {hits}")
print(f"  missing: {[m for m in tail_markers if m not in hits]}")

for i, ki in enumerate(summary.get("key_ideas", []), 1):
    title = ki.get("idea") if isinstance(ki, dict) else str(ki)
    print(f"  {i:>2}. {title}")
