"""Tag-to-library promotion for daily research pipeline.

Scans daily notes for items tagged #keep — extracts them and appends
to per-topic library files. Replaces #keep with #kept in the original
daily so items aren't reprocessed.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# vault module is injected by run.py when loaded via importlib
# For standalone use, import directly:
try:
    from . import vault
except ImportError:
    vault = None  # Will be set by run.py


@dataclass
class PromotedItem:
    """An item promoted from daily to library."""
    title: str
    url: str
    summary: str
    topic_slug: str
    date_found: str
    source: str  # "Reddit", "X", etc.


def scan_for_keeps(dailies_dir: Path) -> List[Tuple[Path, List[dict]]]:
    """Scan all daily notes for items tagged #keep.

    Returns list of (filepath, [item_dicts]) tuples.
    Each item_dict has: title, url, summary, line_number, raw_line
    """
    results = []

    if not dailies_dir.exists():
        return results

    for md_file in sorted(dailies_dir.glob("*.md")):
        items = []
        try:
            lines = md_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        for i, line in enumerate(lines):
            if "#keep" not in line:
                continue
            # Already promoted?
            if "#kept" in line:
                continue

            # Parse the line: expect "- [ ] [Title](url) — summary #keep #topic"
            # or "- [Title](url) — summary #keep"
            link_match = re.search(r'\[([^\]]+)\]\((https?://[^\)]+)\)', line)
            if not link_match:
                continue

            title = link_match.group(1)
            url = link_match.group(2)

            # Extract summary (text between ) and #keep)
            after_link = line[link_match.end():]
            summary_match = re.match(r'\s*[—–-]\s*(.+?)(?:\s+#\w+)*\s*$', after_link)
            summary = summary_match.group(1).strip() if summary_match else ""

            # Extract topic tag (e.g., #agents, #models)
            topic_tags = re.findall(r'#(agents|skills|models|mcp|rag)', line)
            topic_slug = topic_tags[0] if topic_tags else "general"

            # Extract date from filename
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', md_file.stem)
            date_found = date_match.group(1) if date_match else ""

            items.append({
                "title": title,
                "url": url,
                "summary": summary,
                "topic_slug": topic_slug,
                "date_found": date_found,
                "line_number": i,
                "raw_line": line,
            })

        if items:
            results.append((md_file, items))

    return results


def promote_items(config: dict, dry_run: bool = False) -> List[dict]:
    """Run the full promote pass.

    1. Scan dailies for #keep items
    2. Append to Research/Library/{topic}.md
    3. Replace #keep → #kept in originals

    Returns list of promoted item dicts.
    """
    _, dailies, library = vault.get_vault_paths(config)
    library.mkdir(parents=True, exist_ok=True)

    all_promoted = []
    keeps = scan_for_keeps(dailies)

    for filepath, items in keeps:
        if dry_run:
            all_promoted.extend(items)
            continue

        # Read the file for modification
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for item in items:
            # Append to library file
            lib_file = library / f"{item['topic_slug']}.md"
            _append_to_library(lib_file, item)

            # Replace #keep with #kept in the daily
            content = content.replace(
                item["raw_line"],
                item["raw_line"].replace("#keep", "#kept"),
                1,  # Replace only first occurrence
            )

            all_promoted.append(item)

        # Write back the modified daily
        filepath.write_text(content, encoding="utf-8")

    return all_promoted


def _append_to_library(lib_file: Path, item: dict):
    """Append an item to a per-topic library file."""
    # Create file with frontmatter if it doesn't exist
    if not lib_file.exists():
        topic_name = {
            "agents": "Agent Development",
            "skills": "Agent Skills & Tools",
            "models": "Frontier Model Releases",
            "mcp": "MCP & Tool Use",
            "rag": "RAG & AI Search",
            "general": "General",
        }.get(item["topic_slug"], item["topic_slug"].title())

        header = f"""---
type: research-library
topic: {item['topic_slug']}
updated: {datetime.now().strftime('%Y-%m-%d')}
---

# {topic_name} — Library

"""
        lib_file.write_text(header, encoding="utf-8")

    # Append the item
    entry = f"""
## {item['title']}
- **Date found**: {item['date_found']}
- **Link**: [{item['title']}]({item['url']})
- **Summary**: {item['summary']}
- **My notes**: 

---
"""
    with open(lib_file, "a", encoding="utf-8") as f:
        f.write(entry)

    # Update the 'updated' date in frontmatter
    try:
        content = lib_file.read_text(encoding="utf-8")
        today = datetime.now().strftime('%Y-%m-%d')
        content = re.sub(
            r'^updated: \d{4}-\d{2}-\d{2}',
            f'updated: {today}',
            content,
            count=1,
            flags=re.MULTILINE,
        )
        lib_file.write_text(content, encoding="utf-8")
    except OSError:
        pass
