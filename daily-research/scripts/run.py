#!/usr/bin/env python3
"""
daily-research — Lightweight daily research pipeline.

Scans 5 topic tracks (agents, skills, models, MCP, RAG) using the
last30days lib in 'scan' mode, deduplicates against your Obsidian vault,
and writes a structured daily note.

Usage:
    python run.py                      # Full daily pipeline
    python run.py --topic agents       # Single topic only
    python run.py --dry-run            # Fetch + score, print to stdout
    python run.py --promote-only       # Just run #keep → Library pass
    python run.py --show-dedup         # Dump seen URLs from vault
    python run.py --costs              # Show token cost estimate after run

Scheduled via Windows Task Scheduler (see schedule.ps1).
"""

import argparse
import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Resolve paths
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent
CONFIG_FILE = SCRIPT_DIR / "config.json"

# Add last30days scripts dir to path FIRST so its 'lib' package is primary
LAST30DAYS_SCRIPTS = (SKILL_DIR.parent / "last30days" / "scripts").resolve()
sys.path.insert(0, str(LAST30DAYS_SCRIPTS))

# Import our own modules via direct file import (avoids 'lib' name clash)
import importlib.util

def _load_local_module(name: str, filepath: Path):
    """Load a module from the daily-research scripts/lib/ directory."""
    spec = importlib.util.spec_from_file_location(name, str(filepath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_local_lib = SCRIPT_DIR / "lib"
topics_mod = _load_local_module("dr_topics", _local_lib / "topics.py")
vault = _load_local_module("dr_vault", _local_lib / "vault_v2.py")
promote = _load_local_module("dr_promote", _local_lib / "promote_v2.py")


def load_config() -> dict:
    """Load pipeline config from config.json."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback defaults
    return {
        "vault_path": str(Path.home() / "Documents" / "Obsidian Vault"),
        "dailies_folder": "Research/Dailies",
        "library_folder": "Research/Library",
        "keep_tag": "#keep",
        "kept_tag": "#kept",
        "items_per_topic": 8,
        "reading_list_max": 15,
        "depth": "scan",
    }


def run_topic_scan(
    topic: topics_mod.Topic,
    config: dict,
    l30_config: dict,
    selected_models: dict,
    from_date: str,
    to_date: str,
    seen_urls: set,
    seen_titles: set,
) -> dict:
    """Run a single topic scan. Returns a result dict.

    Uses last30days lib modules directly in scan mode.
    """
    from lib import (
        openai_reddit,
        xai_x,
        normalize,
        score,
        dedupe,
        schema,
    )

    result = {
        "topic": topic,
        "reddit_items": [],
        "x_items": [],
        "errors": [],
    }

    combined_query = topic.display_name

    # --- Reddit scan ---
    if l30_config.get("OPENAI_API_KEY"):
        try:
            # web_search tool requires a model that supports it (gpt-4o or higher)
            # gpt-4o-mini doesn't support web_search in Responses API
            model = selected_models.get("openai", "gpt-4o")
            raw = openai_reddit.search_reddit(
                l30_config["OPENAI_API_KEY"],
                model,
                combined_query,
                from_date,
                to_date,
                depth="scan",
            )
            items = openai_reddit.parse_reddit_response(raw)
            # Normalize
            normalized = normalize.normalize_reddit_items(items, from_date, to_date)
            filtered = normalize.filter_by_date_range(normalized, from_date, to_date)
            # Score
            scored = score.score_reddit_items(filtered)
            sorted_items = score.sort_items(scored)
            # Dedupe internally
            deduped = dedupe.dedupe_reddit(sorted_items)
            result["reddit_items"] = deduped
        except Exception as e:
            result["errors"].append(f"Reddit/{topic.slug}: {e}")

    # --- X scan ---
    if l30_config.get("XAI_API_KEY"):
        try:
            model = l30_config.get("xai_model", "grok-4-1-fast")
            raw = xai_x.search_x(
                l30_config["XAI_API_KEY"],
                model,
                combined_query,
                from_date,
                to_date,
                depth="scan",
            )
            items = xai_x.parse_x_response(raw)
            normalized = normalize.normalize_x_items(items, from_date, to_date)
            filtered = normalize.filter_by_date_range(normalized, from_date, to_date)
            scored = score.score_x_items(filtered)
            sorted_items = score.sort_items(scored)
            deduped = dedupe.dedupe_x(sorted_items)
            result["x_items"] = deduped
        except Exception as e:
            result["errors"].append(f"X/{topic.slug}: {e}")

    # --- Vault dedup: remove items already seen ---
    result["reddit_items"] = [
        item for item in result["reddit_items"]
        if item.url not in seen_urls
        and not vault.title_is_seen(item.title, seen_titles)
    ]
    result["x_items"] = [
        item for item in result["x_items"]
        if item.url not in seen_urls
    ]

    return result


def synthesize_all(
    api_key: str,
    topic_results: list,
    from_date: str,
    to_date: str,
) -> dict:
    """Single batched synthesis call across all topics.

    Sends one gpt-4o-mini call with combined data instead of 5 separate calls.
    """
    from lib import http

    # Build per-topic summaries
    sections = []
    for tr in topic_results:
        topic = tr["topic"]
        reddit_lines = []
        for item in tr["reddit_items"][:5]:
            eng = ""
            if item.engagement:
                parts = []
                if item.engagement.score is not None:
                    parts.append(f"{item.engagement.score}pts")
                if item.engagement.num_comments is not None:
                    parts.append(f"{item.engagement.num_comments}cmt")
                eng = f" [{', '.join(parts)}]" if parts else ""
            reddit_lines.append(f"  - r/{item.subreddit}: \"{item.title}\"{eng}")

        x_lines = []
        for item in tr["x_items"][:5]:
            eng = ""
            if item.engagement:
                parts = []
                if item.engagement.likes is not None:
                    parts.append(f"{item.engagement.likes}likes")
                eng = f" [{', '.join(parts)}]" if parts else ""
            text = item.text[:120] + "..." if len(item.text) > 120 else item.text
            x_lines.append(f"  - @{item.author_handle}{eng}: \"{text}\"")

        section = f"### {topic.display_name}\n"
        if reddit_lines:
            section += "Reddit:\n" + "\n".join(reddit_lines) + "\n"
        if x_lines:
            section += "X:\n" + "\n".join(x_lines) + "\n"
        if not reddit_lines and not x_lines:
            section += "(No new results)\n"
        sections.append(section)

    prompt = f"""You are a research analyst creating a daily briefing.

DATE: {from_date} to {to_date}

## SOURCE DATA
{chr(10).join(sections)}

## YOUR TASK
Generate a JSON synthesis covering ALL topics above:

{{
  "briefing": "3-5 sentence executive summary of today's most important findings across all topics. Be specific — mention names, numbers, tools.",
  "topics": [
    {{
      "slug": "topic-slug",
      "headline": "One bold sentence summarizing this topic's news",
      "key_points": ["point1", "point2"]
    }}
  ]
}}

RULES:
- briefing should highlight the MOST actionable/interesting items
- Each topic should have 1-3 key_points (short, specific)
- If a topic had no results, say "No new activity detected"
- Output ONLY valid JSON"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.5,
    }

    try:
        resp = http.post(
            "https://api.openai.com/v1/chat/completions",
            payload,
            headers=headers,
            timeout=60,
        )
        if "choices" in resp and resp["choices"]:
            content = resp["choices"][0].get("message", {}).get("content", "{}")
            return json.loads(content)
    except Exception as e:
        return {"briefing": f"Synthesis failed: {e}", "topics": [], "error": str(e)}

    return {"briefing": "", "topics": []}


def render_daily_note(
    date_str: str,
    topic_results: list,
    synthesis: dict,
    config: dict,
) -> str:
    """Render the full daily note markdown."""
    topic_slugs = [tr["topic"].slug for tr in topic_results]
    total_reddit = sum(len(tr["reddit_items"]) for tr in topic_results)
    total_x = sum(len(tr["x_items"]) for tr in topic_results)

    lines = [
        "---",
        f"date: {date_str}",
        "type: daily-research",
        f"topics: [{', '.join(topic_slugs)}]",
        "status: unread",
        f"reddit_items: {total_reddit}",
        f"x_items: {total_x}",
        "---",
        "",
        f"# Daily Research — {_format_date(date_str)}",
        "",
    ]

    # Briefing
    briefing = synthesis.get("briefing", "")
    if briefing:
        lines.extend([
            "## Key Briefing",
            "",
            briefing,
            "",
        ])

    # Reading list (top items across all topics, ranked by score)
    reading_list = _build_reading_list(topic_results, config)
    if reading_list:
        lines.extend([
            "## Reading List",
            "",
        ])
        for item in reading_list:
            source_tag = f"#{item['topic_slug']}"
            lines.append(
                f"- [ ] [{item['title']}]({item['url']}) — {item['summary']} {source_tag}"
            )
        lines.append("")

    # Per-topic sections
    topic_synths = {t.get("slug", ""): t for t in synthesis.get("topics", [])}
    for tr in topic_results:
        topic = tr["topic"]
        synth = topic_synths.get(topic.slug, {})

        lines.extend([
            "---",
            "",
            f"## {topic.display_name}",
            "",
        ])

        # Topic headline
        headline = synth.get("headline", "")
        if headline:
            lines.extend([f"**{headline}**", ""])

        # Key points
        key_points = synth.get("key_points", [])
        if key_points:
            for kp in key_points:
                lines.append(f"- {kp}")
            lines.append("")

        # Sources table — Reddit
        if tr["reddit_items"]:
            lines.extend([
                "### Reddit",
                "",
                "| # | Title | Subreddit | Score | Link |",
                "|---|-------|-----------|-------|------|",
            ])
            for i, item in enumerate(tr["reddit_items"][:8], 1):
                score_val = item.score if hasattr(item, "score") else 0
                title_short = item.title[:60] + "..." if len(item.title) > 60 else item.title
                lines.append(
                    f"| {i} | {title_short} | r/{item.subreddit} | {score_val} | [→]({item.url}) |"
                )
            lines.append("")

        # Sources table — X
        if tr["x_items"]:
            lines.extend([
                "### X",
                "",
                "| # | Post | Author | Likes | Link |",
                "|---|------|--------|-------|------|",
            ])
            for i, item in enumerate(tr["x_items"][:8], 1):
                likes = item.engagement.likes if item.engagement and item.engagement.likes else 0
                text_short = item.text[:60] + "..." if len(item.text) > 60 else item.text
                lines.append(
                    f"| {i} | {text_short} | @{item.author_handle} | {likes} | [→]({item.url}) |"
                )
            lines.append("")

        if not tr["reddit_items"] and not tr["x_items"]:
            lines.extend(["*No new results for this topic today.*", ""])

    # Footer
    lines.extend([
        "---",
        "",
        "## Promote to Library",
        "",
        "> Add `#keep` to any reading list item above to promote it to",
        f"> `{config.get('library_folder', 'Research/Library')}/` on the next run.",
        "",
    ])

    return "\n".join(lines)


def _build_reading_list(topic_results: list, config: dict) -> list:
    """Build a merged, ranked reading list across all topics."""
    max_items = config.get("reading_list_max", 15)
    all_items = []

    for tr in topic_results:
        topic = tr["topic"]
        for item in tr["reddit_items"]:
            all_items.append({
                "title": item.title,
                "url": item.url,
                "summary": item.why_relevant or f"r/{item.subreddit}",
                "topic_slug": topic.slug,
                "score": item.score * topic.weight,
                "source": "reddit",
            })
        for item in tr["x_items"]:
            all_items.append({
                "title": item.text[:80] + "..." if len(item.text) > 80 else item.text,
                "url": item.url,
                "summary": item.why_relevant or f"@{item.author_handle}",
                "topic_slug": topic.slug,
                "score": item.score * topic.weight,
                "source": "x",
            })

    # Sort by weighted score descending
    all_items.sort(key=lambda x: x["score"], reverse=True)
    return all_items[:max_items]


def _format_date(date_str: str) -> str:
    """Format YYYY-MM-DD as 'Feb 23, 2026'."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%b %d, %Y")
    except ValueError:
        return date_str


def main():
    parser = argparse.ArgumentParser(description="Daily research pipeline → Obsidian")
    parser.add_argument("--topic", help="Run only this topic slug (e.g., agents)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + score, print to stdout only")
    parser.add_argument("--promote-only", action="store_true", help="Only run #keep → Library pass")
    parser.add_argument("--show-dedup", action="store_true", help="Show all seen URLs from vault")
    parser.add_argument("--costs", action="store_true", help="Show estimated token costs after run")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    # Load config
    config = load_config()
    today = datetime.now().strftime("%Y-%m-%d")

    # --show-dedup: just dump URLs and exit
    if args.show_dedup:
        seen = vault.load_seen_urls(config)
        print(f"Seen URLs in vault: {len(seen)}")
        for url in sorted(seen):
            print(f"  {url}")
        return

    # --promote-only: just run promotion pass and exit
    if args.promote_only:
        # Load API key for LLM enrichment
        from lib import env as l30_env
        l30_config = l30_env.get_config()
        openai_key = l30_config.get("OPENAI_API_KEY")
        if not openai_key:
            print("[warn] No OPENAI_API_KEY — will create basic notes without summaries")

        promoted = promote.promote_items(
            config, api_key=openai_key, dry_run=args.dry_run,
        )
        if promoted:
            print(f"Promoted {len(promoted)} items to Library:")
            for item in promoted:
                path = item.get('library_path', item['topic_slug'])
                print(f"  [{item['topic_slug']}] {item['title']} → {path}")
        else:
            print("No #keep items found to promote.")
        return

    # Enable debug
    if args.debug:
        os.environ["LAST30DAYS_DEBUG"] = "1"

    # Run promote pass first (tag-to-library for previous dailies)
    # Load API key early so promote can do LLM enrichment
    from lib import env as l30_env
    l30_config = l30_env.get_config()
    openai_key = l30_config.get("OPENAI_API_KEY")

    promoted = promote.promote_items(config, api_key=openai_key)
    if promoted:
        print(f"[promote] Enriched & moved {len(promoted)} items to Library")

    if not l30_config.get("OPENAI_API_KEY") and not l30_config.get("XAI_API_KEY"):
        print("Error: No API keys found. Set them in ~/.config/last30days/.env", file=sys.stderr)
        sys.exit(1)

    # Load topics
    all_topics = topics_mod.load_topics(config)
    if args.topic:
        topic = topics_mod.get_topic_by_slug(all_topics, args.topic)
        if not topic:
            print(f"Error: Unknown topic '{args.topic}'. Available: {[t.slug for t in all_topics]}", file=sys.stderr)
            sys.exit(1)
        all_topics = [topic]

    # Load vault dedup set (zero tokens — pure filesystem)
    print(f"[dedup] Scanning vault for seen URLs...")
    seen_urls = vault.load_seen_urls(config)
    seen_titles = vault.load_seen_titles(config)
    print(f"[dedup] Found {len(seen_urls)} seen URLs, {len(seen_titles)} seen titles")

    # Date range: last 7 days for daily scan (not 30)
    from lib import dates
    from_date, _ = dates.get_date_range(7)
    to_date = today

    # Select models (reuse last30days model selection with caching)
    from lib import models as l30_models
    selected_models = l30_models.get_models(l30_config)

    # Run topic scans sequentially (to stay within rate limits)
    print(f"\n[scan] Starting {len(all_topics)} topic scans (scan mode)...")
    topic_results = []
    total_errors = []

    for topic in all_topics:
        print(f"  [{topic.slug}] Scanning...", end=" ", flush=True)
        result = run_topic_scan(
            topic, config, l30_config, selected_models,
            from_date, to_date, seen_urls, seen_titles,
        )
        r_count = len(result["reddit_items"])
        x_count = len(result["x_items"])
        print(f"→ {r_count}R + {x_count}X items (new)")
        topic_results.append(result)
        total_errors.extend(result["errors"])

        # Add found URLs to seen set to dedup across topics
        for item in result["reddit_items"]:
            seen_urls.add(item.url)
        for item in result["x_items"]:
            seen_urls.add(item.url)

    # Show errors if any
    if total_errors:
        print(f"\n[warn] {len(total_errors)} errors during scan:")
        for err in total_errors:
            print(f"  ! {err}")

    # Synthesize (single batched call)
    synthesis = {}
    if l30_config.get("OPENAI_API_KEY"):
        total_items = sum(
            len(tr["reddit_items"]) + len(tr["x_items"])
            for tr in topic_results
        )
        if total_items > 0:
            print(f"\n[synth] Synthesizing {total_items} items across {len(all_topics)} topics...")
            synthesis = synthesize_all(
                l30_config["OPENAI_API_KEY"],
                topic_results,
                from_date,
                to_date,
            )
            if synthesis.get("briefing"):
                print(f"[synth] Briefing: {synthesis['briefing'][:120]}...")
        else:
            print("\n[synth] No new items to synthesize")
            synthesis = {"briefing": "No new research results today.", "topics": []}

    # Render daily note
    note_content = render_daily_note(today, topic_results, synthesis, config)

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN — would write this to vault:")
        print("=" * 60)
        print(note_content)
        return

    # Write to vault via Obsidian CLI
    filepath = vault.write_daily_note(config, today, note_content)
    print(f"\n[vault] Written → {filepath}")

    # Cost summary
    if args.costs:
        n_topics = len(all_topics)
        est_cost = n_topics * 0.03  # ~$0.03 per topic in scan mode
        print(f"\n[costs] Estimated run cost: ~${est_cost:.2f}")
        print(f"  {n_topics} Reddit scans (gpt-4o-mini + web_search)")
        print(f"  {n_topics} X scans (grok-4-1-fast + x_search)")
        print(f"  1 synthesis call (gpt-4o-mini)")

    # Final summary
    total_reddit = sum(len(tr["reddit_items"]) for tr in topic_results)
    total_x = sum(len(tr["x_items"]) for tr in topic_results)
    print(f"\nDone! {total_reddit}R + {total_x}X new items across {len(all_topics)} topics.")


if __name__ == "__main__":
    main()
