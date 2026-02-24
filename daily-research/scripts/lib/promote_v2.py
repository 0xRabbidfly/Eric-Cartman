"""Tag-to-library promotion for daily research pipeline.

Scans daily notes for items tagged #keep:
1. Fetches the URL content
2. Generates a structured summary with an LLM (OpenAI gpt-4o-mini)
3. Creates a standalone research note in Research/Library/
4. Replaces #keep with #kept in the original daily

Falls back to a basic note (title + URL + summary) when no API key
is provided or when enrichment fails.

Uses the Obsidian CLI via vault_v2 for all file operations.
"""

import html
import importlib.util
import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# Load vault_v2 from the same directory (avoids 'lib' package name clash
# with last30days when loaded via importlib from run.py)
_VAULT_V2_PATH = Path(__file__).resolve().parent / "vault_v2.py"
_spec = importlib.util.spec_from_file_location("dr_vault_v2", str(_VAULT_V2_PATH))
vault = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vault)


# ---------------------------------------------------------------------------
# Scanning — find #keep items in dailies
# ---------------------------------------------------------------------------


def scan_for_keeps(dailies_folder: str) -> List[Tuple[str, List[dict]]]:
    """Scan all daily notes for items tagged #keep.

    Returns list of (filepath, [item_dicts]) tuples.
    Each item_dict has: title, url, summary, line_number, raw_line, topic_slug, date_found
    """
    results = []
    md_files = sorted(vault.list_md_files(dailies_folder))

    for filepath in md_files:
        text = vault.read_file(filepath)
        if not text or "#keep" not in text:
            continue

        items = []
        lines = text.splitlines()

        for i, line in enumerate(lines):
            if "#keep" not in line:
                continue
            if "#kept" in line:
                continue

            # Parse: "- [ ] [Title](url) — summary #keep #topic"
            link_match = re.search(r'\[([^\]]+)\]\((https?://[^\)]+)\)', line)
            if not link_match:
                continue

            title = link_match.group(1)
            url = link_match.group(2)

            # Extract summary (text between — and the first #tag)
            after_link = line[link_match.end():]
            summary_match = re.match(r'\s*[—–-]\s*(.+?)(?:\s+#\w+)*\s*$', after_link)
            summary = summary_match.group(1).strip() if summary_match else ""

            # Extract topic tag
            topic_tags = re.findall(r'#(agents|skills|models|mcp|rag)', line)
            topic_slug = topic_tags[0] if topic_tags else "general"

            # Extract date from filename (path like Research/Dailies/2026-02-23.md)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filepath)
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
            results.append((filepath, items))

    return results


# ---------------------------------------------------------------------------
# URL fetching
# ---------------------------------------------------------------------------


def _fetch_url_content(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch a URL and extract text content from HTML.

    Returns plain text (up to ~8000 chars) or None on failure.
    Works for blogs, Reddit, GitHub. X/Twitter posts may return
    limited content due to JS rendering — the LLM handles that
    gracefully using the title + summary hint.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        # Strip scripts, styles, then all HTML tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text[:8000] if len(text) > 100 else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# LLM enrichment
# ---------------------------------------------------------------------------


def _summarize_with_llm(
    api_key: str,
    title: str,
    url: str,
    page_content: Optional[str],
    summary_hint: str,
    topic_slug: str,
) -> Optional[dict]:
    """Call OpenAI gpt-4o-mini to produce a structured research note summary.

    Returns a dict with: title, slug, author, source, summary,
    key_insights, actionable_takeaways, relevance, tags.
    Returns None on failure.
    """
    content_block = ""
    if page_content and len(page_content) > 100:
        content_block = f"\n\nPAGE CONTENT (extracted text — may be noisy, focus on the substance):\n{page_content[:6000]}"

    prompt = f"""You are a research analyst. Create a structured summary for this content.

TITLE: {title}
URL: {url}
TOPIC AREA: {topic_slug}
EXISTING SUMMARY: {summary_hint}
{content_block}

Return a JSON object:
{{
  "title": "Clear, descriptive title for the note",
  "slug": "kebab-case-filename-slug (3-6 words, no special chars)",
  "author": "@handle or Author Name (if identifiable from content/URL, else 'Unknown')",
  "source": "x|reddit|blog|article|github",
  "summary": "2-4 sentence executive summary. Be specific — mention names, tools, numbers.",
  "key_insights": ["insight 1 (specific, actionable)", "insight 2", "insight 3"],
  "actionable_takeaways": ["concrete takeaway 1", "concrete takeaway 2"],
  "relevance": "1-2 sentences on why this matters for AI/enterprise software development",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}

RULES:
- slug: lowercase, hyphens only, 3-6 words max
- tags: lowercase, hyphens in multi-word tags, 4-6 tags, topically relevant
- key_insights: 2-4 specific insights (not generic platitudes)
- actionable_takeaways: 1-3 concrete takeaways a developer could act on
- source: detect from URL (x.com→x, reddit.com→reddit, github.com→github, else→article)
- author: extract from page content or URL if possible
- Output ONLY valid JSON, no markdown fences"""

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        content = result["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        print(f"  [warn] LLM enrichment failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Note rendering
# ---------------------------------------------------------------------------


def _render_enriched_note(enrichment: dict, item: dict) -> str:
    """Render a standalone research note with full frontmatter and structure."""
    tags_yaml = ", ".join(enrichment.get("tags", [item["topic_slug"]]))
    today = datetime.now().strftime("%Y-%m-%d")
    source = enrichment.get("source", "article")
    author = enrichment.get("author", "Unknown")
    title = enrichment.get("title", item["title"])

    lines = [
        "---",
        "type: research-note",
        f"source: {source}",
        f'author: "{author}"',
        f"url: {item['url']}",
        f"date_found: {item['date_found']}",
        f"date_saved: {today}",
        f"tags: [{tags_yaml}]",
        f"topic: {item['topic_slug']}",
        "status: unread",
        "---",
        "",
        f"# {title}",
        "",
        f"> **Author**: {author}",
        f"> **Source**: [{item['url']}]({item['url']})",
        f"> **Found**: {item['date_found']}",
        "",
        "## Summary",
        "",
        enrichment.get("summary", item.get("summary", "")),
        "",
    ]

    insights = enrichment.get("key_insights", [])
    if insights:
        lines.extend(["## Key Insights", ""])
        for insight in insights:
            lines.append(f"- {insight}")
        lines.append("")

    takeaways = enrichment.get("actionable_takeaways", [])
    if takeaways:
        lines.extend(["## Actionable Takeaways", ""])
        for t in takeaways:
            lines.append(f"- {t}")
        lines.append("")

    relevance = enrichment.get("relevance", "")
    if relevance:
        lines.extend(["## Relevance", "", relevance, ""])

    lines.extend(["## My Notes", "", "", ""])

    return "\n".join(lines)


def _render_basic_note(item: dict) -> str:
    """Create a basic note without LLM enrichment (fallback)."""
    today = datetime.now().strftime("%Y-%m-%d")
    return "\n".join([
        "---",
        "type: research-note",
        f"url: {item['url']}",
        f"date_found: {item['date_found']}",
        f"date_saved: {today}",
        f"tags: [{item['topic_slug']}]",
        "status: unread",
        "---",
        "",
        f"# {item['title']}",
        "",
        f"> **Link**: [{item['title']}]({item['url']})",
        f"> **Found**: {item['date_found']}",
        "",
        "## Summary",
        "",
        item.get("summary", ""),
        "",
        "## My Notes",
        "",
        "",
        "",
    ])


# ---------------------------------------------------------------------------
# Slug generation
# ---------------------------------------------------------------------------


def _slugify(title: str) -> str:
    """Convert a title to a kebab-case filename slug."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:60] if slug else "untitled"


# ---------------------------------------------------------------------------
# Main promote pass
# ---------------------------------------------------------------------------


def promote_items(
    config: dict,
    *,
    api_key: Optional[str] = None,
    dry_run: bool = False,
) -> List[dict]:
    """Run the full promote pass.

    1. Scan dailies for #keep items
    2. Fetch URL content and generate structured summary (if api_key provided)
    3. Create standalone research notes in Research/Library/
    4. Replace #keep → #kept in originals

    Args:
        config: Pipeline config dict.
        api_key: OpenAI API key for LLM enrichment. If None, creates basic
                 notes with just the title/URL/summary from the daily.
        dry_run: If True, scan and return items without writing anything.

    Returns list of promoted item dicts (each gets a 'library_path' key).
    """
    dailies_folder = config.get("dailies_folder", "Research/Dailies")
    library_folder = config.get("library_folder", "Research/Library")

    all_promoted = []
    keeps = scan_for_keeps(dailies_folder)

    for filepath, items in keeps:
        if dry_run:
            all_promoted.extend(items)
            continue

        content = vault.read_file(filepath)
        if not content:
            continue

        for item in items:
            slug = None
            note_content = None

            if api_key:
                # Enriched path: fetch URL → summarize with LLM → standalone note
                print(f"  [enrich] Fetching {item['url']}...")
                page_content = _fetch_url_content(item["url"])

                print(f"  [enrich] Summarizing with LLM...")
                enrichment = _summarize_with_llm(
                    api_key,
                    item["title"],
                    item["url"],
                    page_content,
                    item.get("summary", ""),
                    item["topic_slug"],
                )

                if enrichment:
                    slug = enrichment.get("slug", _slugify(item["title"]))
                    note_content = _render_enriched_note(enrichment, item)
                else:
                    # LLM failed — fall back to basic note
                    slug = _slugify(item["title"])
                    note_content = _render_basic_note(item)
            else:
                # No API key — basic note only
                slug = _slugify(item["title"])
                note_content = _render_basic_note(item)

            # Pick a unique path in the library folder
            lib_path = f"{library_folder}/{slug}.md"
            if vault.file_exists(lib_path):
                i = 2
                while vault.file_exists(f"{library_folder}/{slug}-{i}.md"):
                    i += 1
                lib_path = f"{library_folder}/{slug}-{i}.md"

            vault.write_file(lib_path, note_content)
            item["library_path"] = lib_path
            print(f"  [promote] Created {lib_path}")

            # Replace #keep with #kept in the daily
            content = content.replace(
                item["raw_line"],
                item["raw_line"].replace("#keep", "#kept"),
                1,
            )

            all_promoted.append(item)

        # Write back the modified daily with #keep → #kept
        vault.write_file(filepath, content)

    return all_promoted

    # Update the 'updated' date in frontmatter
    content = vault.read_file(lib_path)
    if content:
        today = datetime.now().strftime('%Y-%m-%d')
        updated = re.sub(
            r'^updated: \d{4}-\d{2}-\d{2}',
            f'updated: {today}',
            content,
            count=1,
            flags=re.MULTILINE,
        )
        if updated != content:
            vault.write_file(lib_path, updated)
