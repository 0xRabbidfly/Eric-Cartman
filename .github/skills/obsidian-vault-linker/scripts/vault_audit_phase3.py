"""Phase 3: Deep link opportunity analysis across clusters."""
import json
import re
import sys
sys.path.insert(0, ".github/skills/obsidian/scripts")
from obsidian import Obsidian

ob = Obsidian()
MASTER_MOC_PATH = "Research/Library/00 MOC/🗺️ MOC - Research Library.md"
TOPIC_MOC_PATHS = {
    "AI Agent Development": "Research/Library/00 MOC/🤖 MOC - AI Agent Development.md",
}


def extract_wikilink_targets(content: str):
    return set(match.split("|", 1)[0].strip() for match in re.findall(r"\[\[([^\]]+)\]\]", content))

# --- Check Dailies for references to Library notes ---
print("=" * 60)
print("DAILY NOTES — Do they link to Library?")
print("=" * 60)

dailies = ob.files(folder="Research/Dailies", ext="md").lines()
print(f"Total daily notes: {len(dailies)}")

for daily in dailies:
    content = ob.read(path=daily)
    if "[[" in content:
        # Extract wikilinks
        links = re.findall(r'\[\[([^\]|]+)', content)
        lib_links = [l for l in links if "Library" in l or "Research" in l]
        if lib_links:
            print(f"  {daily}: links to {lib_links}")
        else:
            print(f"  {daily}: has [[links]] but none to Library ({len(links)} links)")
    else:
        print(f"  {daily}: no [[wikilinks]]")

# --- Check Raven/IDEAS cluster ---
print("\n" + "=" * 60)
print("IDEAS/Raven CLUSTER")
print("=" * 60)

raven_notes = ob.files(folder="Project Domains/IDEAS/Raven", ext="md").lines()
print(f"Total Raven notes: {len(raven_notes)}")

# Check orphan status
orphan_set = set(ob.orphans().lines())
for n in raven_notes:
    is_orphan = "🏝️" if n in orphan_set else "✅"
    bl = ob.backlinks(path=n, total=True).text
    ol = ob.links(path=n, total=True).text
    name = n.rsplit("/", 1)[-1]
    print(f"  {is_orphan} {name}: backlinks={bl}, outgoing={ol}")

# --- Tag duplicate detection ---
print("\n" + "=" * 60)
print("TAG SIMILARITY CHECK")
print("=" * 60)

tags_data = ob.tags(sort="count", format="tsv").lines()
tag_names = []
for line in tags_data:
    parts = line.split("\t")
    if parts:
        tag_names.append((parts[0].strip(), parts[1].strip() if len(parts) > 1 else "0"))

# Look for similar tags
from difflib import SequenceMatcher
seen_pairs = set()
for i, (t1, c1) in enumerate(tag_names):
    for j, (t2, c2) in enumerate(tag_names):
        if i >= j:
            continue
        # Normalize for comparison
        t1n = t1.lower().replace("-", "").replace("_", "").replace("#", "")
        t2n = t2.lower().replace("-", "").replace("_", "").replace("#", "")
        ratio = SequenceMatcher(None, t1n, t2n).ratio()
        if ratio > 0.7 and (t1, t2) not in seen_pairs:
            seen_pairs.add((t1, t2))
            print(f"  Similar: {t1} ({c1}) ↔ {t2} ({c2}) — similarity: {ratio:.0%}")

# --- Research MOC audit ---
print("\n" + "=" * 60)
print("MASTER AND TOPIC MOC AUDIT")
print("=" * 60)

library_notes = [
    line for line in ob.files(folder="Research/Library", ext="md").lines()
    if not line.startswith("Research/Library/00 MOC/")
]
library_slug_map = {path.rsplit("/", 1)[-1].replace(".md", ""): path for path in library_notes}

master_moc_content = ob.read(path=MASTER_MOC_PATH)
master_moc_targets = extract_wikilink_targets(master_moc_content)
missing_from_master_moc = [
    path for path in library_notes
    if path.rsplit("/", 1)[-1].replace(".md", "") not in master_moc_targets
]

print(f"Master MOC path: {MASTER_MOC_PATH}")
print(f"Research notes not referenced by master MOC: {len(missing_from_master_moc)}")
for path in missing_from_master_moc[:15]:
    print(f"  ➕ {path}")
if len(missing_from_master_moc) > 15:
    print(f"  ... +{len(missing_from_master_moc) - 15} more")

print("\nTopic MOC summaries:")
for moc_name, moc_path in TOPIC_MOC_PATHS.items():
    topic_targets = extract_wikilink_targets(ob.read(path=moc_path))
    topic_linked_notes = [path for slug, path in library_slug_map.items() if slug in topic_targets]
    print(f"  {moc_name}: {len(topic_linked_notes)} referenced library notes")
    print("    Scoped topic MOCs are not expected to cover the entire library.")

# --- Complexity cluster — MOC candidates ---
print("\n" + "=" * 60)
print("SUGGESTED MOCs — Complexity/Systems Thinking")
print("=" * 60)

# Check if MOC notes exist
moc_search = ob.search("MOC", format="json")
try:
    moc_results = json.loads(moc_search.text)
    print(f"Existing MOC notes: {len(moc_results)}")
    for m in moc_results:
        if isinstance(m, str):
            print(f"  📋 {m}")
        elif isinstance(m, dict):
            print(f"  📋 {m.get('path', m)}")
except Exception:
    print("  No MOC notes found")

# Count orphans in key subject areas
subjects = {
    "Philosophy": "Personal - Nuno/Work/Sciences/Philosophy",
    "Social Complexity": "Personal - Nuno/Work/Sciences/Social Complexity",
    "Systems Thinking": "Personal - Nuno/Work/Sciences/Systems Thinking",
    "Agile": "Personal - Nuno/Work/Agile",
    "Books": "Personal - Nuno/Books",
    "Cycling": "Personal - Nuno/Cycling",
    "Crypto": "Personal - Nuno/Private/Crypto-Main",
    "NFTs": "Personal - Nuno/Private/Crypto-NFTs",
}

print("\nOrphan density by subject area:")
for label, folder in subjects.items():
    all_files = ob.files(folder=folder, ext="md").lines()
    orphans_in = [f for f in all_files if f in orphan_set]
    pct = (len(orphans_in) / len(all_files) * 100) if all_files else 0
    status = "🔴" if pct > 60 else ("🟡" if pct > 30 else "🟢")
    print(f"  {status} {label}: {len(orphans_in)}/{len(all_files)} orphaned ({pct:.0f}%)")
