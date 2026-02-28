"""Vault Link Audit — gather thematic clusters and link opportunities."""

import json
import sys
sys.path.insert(0, ".github/skills/obsidian/scripts")
from obsidian import Obsidian

ob = Obsidian()

# --- Thematic cluster search ---
topics = ["agents", "skills", "mcp", "rag", "models", "copilot", "agentic", "complexity", "systems thinking", "prompt"]

for topic in topics:
    r = ob.search(topic, format="json")
    try:
        results = json.loads(r.text)
        count = len(results)
        print(f"=== {topic.upper()} ({count} notes) ===")
        for item in results[:15]:
            if isinstance(item, str):
                print(f"  {item}")
            elif isinstance(item, dict):
                name = item.get("path", item.get("file", str(item)))
                print(f"  {name}")
        if count > 15:
            print(f"  ... +{count - 15} more")
    except Exception:
        lines = r.lines()
        print(f"=== {topic.upper()} ({len(lines)} notes) ===")
        for l in lines[:15]:
            print(f"  {l}")
        if len(lines) > 15:
            print(f"  ... +{len(lines) - 15} more")
    print()
