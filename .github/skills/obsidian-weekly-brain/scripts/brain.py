#!/usr/bin/env python3
"""
obsidian-weekly-brain — Weekly intelligence digest from the Obsidian vault.

Performs 7 analysis passes over the vault corpus and produces a single
analytical markdown report combining trends, thesis health, blindspots,
cross-domain bridges, zeitgeist, actionable insights, and predictions.

Usage:
    python brain.py                    # Full weekly digest
    python brain.py --pass trend       # Run only one pass
    python brain.py --dry-run          # Analyze but don't write to vault
    python brain.py --weeks 2          # Lookback window (default 4)
"""

import argparse
import io
import json
import os
import re
import ssl
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Force UTF-8 encoding for stdout/stderr on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VAULT_PATH = Path(r"C:\Users\nuno_\Documents\Obsidian Vault")
LIBRARY_DIR = VAULT_PATH / "Research" / "Library"
DAILIES_DIR = VAULT_PATH / "Research" / "Dailies"
PODCASTS_DIR = VAULT_PATH / "Podcasts"
CONNECTIONS_FILE = VAULT_PATH / "Research" / "connections.json"
THESES_FILE = VAULT_PATH / "Research" / "theses.json"
PREDICTIONS_FILE = VAULT_PATH / "Research" / "predictions.json"
REPORTS_DIR = VAULT_PATH / "Research" / "Reports"

CONFIG_DIR = Path.home() / ".config" / "last30days"
ENV_FILE = CONFIG_DIR / ".env"

XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_MODEL = "grok-4.3"

PASS_NAMES = ["trend", "thesis", "blindspot", "bridge", "zeitgeist", "action", "predict"]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def load_env() -> dict:
    """Load .env file and return dict of key=value pairs."""
    env = {}
    if not ENV_FILE.exists():
        return env
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                if key and value:
                    env[key] = value
    return env


def get_api_key() -> str:
    """Get xAI API key from env file or environment."""
    key = os.environ.get("XAI_API_KEY")
    if key:
        return key
    env = load_env()
    key = env.get("XAI_API_KEY", "")
    if not key:
        print("ERROR: XAI_API_KEY not found in ~/.config/last30days/.env or environment.", file=sys.stderr)
        sys.exit(1)
    return key


def xai_chat(api_key: str, system_prompt: str, user_prompt: str) -> str:
    """Call xAI chat completions API and return the assistant message content."""
    payload = json.dumps({
        "model": XAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
    }).encode("utf-8")

    req = urllib.request.Request(
        XAI_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def parse_frontmatter(text: str) -> dict:
    """Extract YAML-ish frontmatter from a markdown note. Returns dict with common keys."""
    fm = {}
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return fm
    block = m.group(1)
    for line in block.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if key == "tags":
                # Handle both [tag1, tag2] and tag1, tag2
                val = val.strip("[]")
                fm["tags"] = [t.strip().strip("'\"") for t in val.split(",") if t.strip()]
            elif key == "date" or key == "created":
                fm["date"] = val.strip("'\"")
            elif key == "source" or key == "author":
                fm[key] = val.strip("'\"")
            else:
                fm[key] = val.strip("'\"")
    return fm


def body_after_frontmatter(text: str) -> str:
    """Return the markdown body after the frontmatter block."""
    m = re.match(r"^---\s*\n.*?\n---\s*\n?", text, re.DOTALL)
    if m:
        return text[m.end():]
    return text


def parse_date(date_str: str) -> datetime | None:
    """Try to parse a date string into a datetime. Returns None on failure."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def week_key(dt: datetime) -> str:
    """Return ISO year-week string like '2026-W30'."""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def load_json_safe(path: Path) -> list | dict:
    """Load a JSON file, returning empty list/dict on missing or invalid file."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


# ---------------------------------------------------------------------------
# Vault reading
# ---------------------------------------------------------------------------

def read_md_files(directory: Path, recurse: bool = True, skip_dirs: set | None = None) -> list[dict]:
    """Read all .md files from a directory. Returns list of dicts with path, text, frontmatter, body."""
    notes = []
    if not directory.exists():
        return notes
    skip = skip_dirs or set()
    pattern = "**/*.md" if recurse else "*.md"
    for fp in directory.glob(pattern):
        # Skip directories in the skip set
        if any(part.lower() in skip for part in fp.relative_to(directory).parts):
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = parse_frontmatter(text)
        body = body_after_frontmatter(text)
        notes.append({
            "path": fp,
            "name": fp.stem,
            "text": text,
            "frontmatter": fm,
            "body": body,
            "tags": fm.get("tags", []),
            "date": parse_date(fm.get("date", "")),
            "source": fm.get("source", fm.get("author", "")),
        })
    return notes


def load_vault(weeks: int = 4) -> dict:
    """Load all relevant vault data. Returns a context dict."""
    print("  Loading vault data...")
    cutoff = datetime.now() - timedelta(weeks=weeks)
    cutoff_8w = datetime.now() - timedelta(weeks=8)

    library = read_md_files(LIBRARY_DIR)
    dailies = read_md_files(DAILIES_DIR)
    podcasts = read_md_files(PODCASTS_DIR, skip_dirs={"transcripts"})
    connections = load_json_safe(CONNECTIONS_FILE)
    theses = load_json_safe(THESES_FILE)
    predictions = load_json_safe(PREDICTIONS_FILE)

    all_notes = library + dailies + podcasts

    # Notes within the lookback window
    recent = [n for n in all_notes if n["date"] and n["date"] >= cutoff]
    recent_2w = [n for n in all_notes if n["date"] and n["date"] >= datetime.now() - timedelta(weeks=2)]

    print(f"  Loaded {len(library)} library, {len(dailies)} dailies, {len(podcasts)} podcasts")
    print(f"  {len(recent)} notes in last {weeks} weeks, {len(recent_2w)} in last 2 weeks")

    return {
        "library": library,
        "dailies": dailies,
        "podcasts": podcasts,
        "all_notes": all_notes,
        "recent": recent,
        "recent_2w": recent_2w,
        "connections": connections if isinstance(connections, list) else connections.get("connections", []),
        "theses": theses if isinstance(theses, list) else theses.get("theses", []),
        "predictions": predictions if isinstance(predictions, list) else predictions.get("predictions", []),
        "cutoff": cutoff,
        "cutoff_8w": cutoff_8w,
        "weeks": weeks,
    }


# ---------------------------------------------------------------------------
# Pass 1: Trend Momentum
# ---------------------------------------------------------------------------

def pass_trend(vault: dict, api_key: str) -> str:
    """Identify rising tags and convergent discoveries."""
    print("\n[Pass 1/7] Trend Momentum...")
    now = datetime.now()

    # Build tag frequency per week for the last 8 weeks
    week_tags: dict[str, Counter] = defaultdict(Counter)
    for note in vault["all_notes"]:
        if not note["date"] or note["date"] < vault["cutoff_8w"]:
            continue
        wk = week_key(note["date"])
        for tag in note["tags"]:
            week_tags[wk][tag] += 1

    # Sort weeks chronologically
    sorted_weeks = sorted(week_tags.keys())
    if len(sorted_weeks) < 2:
        return "_Not enough weekly data to detect trends._\n"

    # Collect all tags seen
    all_tags = set()
    for wk_counter in week_tags.values():
        all_tags.update(wk_counter.keys())

    # Score tags by rising trajectory
    # Compare first half vs second half of the 8-week window
    mid = len(sorted_weeks) // 2
    early_weeks = sorted_weeks[:mid]
    late_weeks = sorted_weeks[mid:]

    tag_scores = []
    for tag in all_tags:
        early_count = sum(week_tags[w][tag] for w in early_weeks)
        late_count = sum(week_tags[w][tag] for w in late_weeks)
        if late_count > early_count and late_count >= 2:
            momentum = late_count - early_count
            tag_scores.append((tag, early_count, late_count, momentum))

    tag_scores.sort(key=lambda x: x[3], reverse=True)
    top_trends = tag_scores[:5]

    # Convergent discovery: topics appearing in 3+ independent sources within 2 weeks
    convergent = []
    two_weeks_ago = now - timedelta(weeks=2)
    tag_sources: dict[str, set] = defaultdict(set)
    for note in vault["all_notes"]:
        if not note["date"] or note["date"] < two_weeks_ago:
            continue
        src = note["source"] or note["name"]
        for tag in note["tags"]:
            tag_sources[tag].add(src)
    for tag, sources in tag_sources.items():
        if len(sources) >= 3:
            convergent.append((tag, len(sources), list(sources)[:5]))
    convergent.sort(key=lambda x: x[1], reverse=True)

    # Format output
    lines = []
    if top_trends:
        for tag, early, late, momentum in top_trends:
            arrow = "+" * min(momentum, 5)
            lines.append(f"- **{tag}** — {early} mentions (early) -> {late} mentions (recent) [{arrow}]")
    else:
        lines.append("- _No rising trends detected in the last 8 weeks._")

    if convergent:
        lines.append("\n**Convergent Discoveries** (3+ independent sources):")
        for tag, count, sources in convergent[:5]:
            lines.append(f"- **{tag}** — {count} independent sources: {', '.join(sources)}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Pass 2: Thesis Health Check
# ---------------------------------------------------------------------------

def pass_thesis(vault: dict, api_key: str) -> str:
    """Assess health of tracked theses."""
    print("\n[Pass 2/7] Thesis Health Check...")
    theses = vault["theses"]
    connections = vault["connections"]

    if not theses:
        return "_No theses tracked yet (Research/theses.json not found or empty)._\n"

    three_weeks_ago = datetime.now() - timedelta(weeks=3)
    lines = []

    for thesis in theses:
        thesis_id = thesis.get("id", thesis.get("name", "unknown"))
        thesis_name = thesis.get("name", thesis.get("title", thesis_id))
        thesis_tags = thesis.get("tags", [])

        # Count supporting vs contradicting connections
        supporting = 0
        contradicting = 0
        latest_support_date = None

        for conn in connections:
            conn_thesis = conn.get("thesis_id", conn.get("thesis", ""))
            if str(conn_thesis) != str(thesis_id) and conn_thesis != thesis_name:
                continue
            rel = conn.get("relationship", conn.get("type", "")).lower()
            conn_date_str = conn.get("date", conn.get("created", ""))
            conn_date = parse_date(conn_date_str)

            if "contradict" in rel or "against" in rel or "challenge" in rel:
                contradicting += 1
            else:
                supporting += 1
                if conn_date and (latest_support_date is None or conn_date > latest_support_date):
                    latest_support_date = conn_date

        # Determine health status
        flags = []
        if contradicting >= 2:
            flags.append("CONTRADICTED")
        if latest_support_date and latest_support_date < three_weeks_ago:
            flags.append("DECAYING")
        elif latest_support_date is None and supporting == 0:
            flags.append("UNSUPPORTED")

        # Check if the field is moving away: recent notes in same tags but not referencing thesis
        if thesis_tags:
            related_recent = [
                n for n in vault["recent"]
                if any(t in n["tags"] for t in thesis_tags)
            ]
            mentions_thesis = sum(
                1 for n in related_recent
                if thesis_name.lower() in n["body"].lower()
            )
            if len(related_recent) >= 3 and mentions_thesis == 0:
                flags.append("FIELD-DRIFT")

        if not flags:
            status = "HEALTHY"
        else:
            status = " | ".join(flags)

        emoji = {"HEALTHY": "✅", "DECAYING": "⚠️", "CONTRADICTED": "❌", "UNSUPPORTED": "❓", "FIELD-DRIFT": "🔀"}
        status_emoji = emoji.get(flags[0], "⚠️") if flags else "✅"
        lines.append(
            f"- {status_emoji} **{thesis_name}** — {status} "
            f"({supporting} supporting, {contradicting} contradicting)"
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Pass 3: Blindspot Detection
# ---------------------------------------------------------------------------

def pass_blindspot(vault: dict, api_key: str) -> str:
    """Detect gaps in vault coverage."""
    print("\n[Pass 3/7] Blindspot Detection...")
    library = vault["library"]
    dailies = vault["dailies"]

    # 1. Subfolder distribution in Library
    subfolder_counts: Counter = Counter()
    if LIBRARY_DIR.exists():
        for child in LIBRARY_DIR.iterdir():
            if child.is_dir():
                count = len(list(child.glob("**/*.md")))
                subfolder_counts[child.name] = count

    # 2. Consumption-to-synthesis ratio
    # Count daily note mentions of topics vs Library notes covering them
    daily_topic_mentions: Counter = Counter()
    for note in dailies:
        # Extract 2-word phrases from the body as rough topic indicators
        words = re.findall(r"[a-zA-Z]{3,}", note["body"][:2000])
        for i in range(len(words) - 1):
            phrase = f"{words[i].lower()} {words[i+1].lower()}"
            daily_topic_mentions[phrase] += 1

    library_topic_coverage: Counter = Counter()
    for note in library:
        words = re.findall(r"[a-zA-Z]{3,}", note["name"].lower())
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            library_topic_coverage[phrase] += 1

    # Find high-mention topics with low Library coverage
    blindspots_ratio = []
    for phrase, daily_count in daily_topic_mentions.most_common(200):
        lib_count = library_topic_coverage.get(phrase, 0)
        if daily_count >= 5 and lib_count == 0:
            blindspots_ratio.append((phrase, daily_count, lib_count))
    blindspots_ratio.sort(key=lambda x: x[1], reverse=True)

    # 3. Missing subtopics heuristic
    # Extract all 2-word phrases from note titles across Library
    title_phrases: Counter = Counter()
    for note in library:
        words = re.findall(r"[a-zA-Z]{3,}", note["name"].lower())
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            title_phrases[phrase] += 1

    # Phrases in 3+ note titles but no dedicated Library note with that exact title
    library_names_lower = {n["name"].lower() for n in library}
    missing_subtopics = []
    for phrase, count in title_phrases.most_common(100):
        if count >= 3:
            # Check if there's a note specifically about this phrase
            has_dedicated = any(phrase in name for name in library_names_lower)
            if not has_dedicated:
                missing_subtopics.append((phrase, count))

    # Format output
    lines = []

    if blindspots_ratio:
        lines.append("**High consumption, low synthesis:**")
        for phrase, daily_c, lib_c in blindspots_ratio[:3]:
            lines.append(f"- **\"{phrase}\"** — mentioned {daily_c}x in dailies, {lib_c} Library notes")

    if missing_subtopics:
        lines.append("\n**Recurring phrases with no dedicated note:**")
        for phrase, count in missing_subtopics[:3]:
            lines.append(f"- **\"{phrase}\"** — appears in {count} note titles")

    if subfolder_counts:
        # Flag imbalanced subfolders
        if subfolder_counts:
            avg = sum(subfolder_counts.values()) / len(subfolder_counts)
            thin = [(name, c) for name, c in subfolder_counts.items() if c < avg * 0.3 and c >= 1]
            if thin:
                lines.append("\n**Under-represented Library folders:**")
                for name, count in sorted(thin, key=lambda x: x[1]):
                    lines.append(f"- `{name}/` — only {count} notes (avg {avg:.0f})")

    if not lines:
        lines.append("_No obvious blindspots detected._")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Pass 4: Cross-Domain Bridges
# ---------------------------------------------------------------------------

def pass_bridge(vault: dict, api_key: str) -> str:
    """Find unexpected tag co-occurrences across domains."""
    print("\n[Pass 4/7] Cross-Domain Bridges...")
    all_notes = vault["all_notes"]

    # Build tag frequency and co-occurrence
    tag_freq: Counter = Counter()
    tag_cooccur: Counter = Counter()
    tag_pair_notes: dict[tuple, list] = defaultdict(list)

    for note in all_notes:
        tags = note["tags"]
        for t in tags:
            tag_freq[t] += 1
        # All pairs in this note
        for i, t1 in enumerate(tags):
            for t2 in tags[i + 1:]:
                pair = tuple(sorted([t1, t2]))
                tag_cooccur[pair] += 1
                tag_pair_notes[pair].append(note)

    if not tag_cooccur:
        return "_Not enough tagged notes to detect cross-domain bridges._\n"

    # Find unusual co-occurrences: low pair count relative to individual frequencies
    bridge_candidates = []
    for pair, pair_count in tag_cooccur.items():
        t1, t2 = pair
        f1 = tag_freq[t1]
        f2 = tag_freq[t2]
        if f1 < 3 or f2 < 3:
            continue  # Skip rare tags
        expected = (f1 * f2) / len(all_notes)
        if pair_count <= 2 and expected > 3:
            # Surprising co-occurrence: these tags rarely appear together
            notes_list = tag_pair_notes[pair]
            summaries = []
            for n in notes_list[:3]:
                snippet = n["body"][:200].replace("\n", " ").strip()
                summaries.append(f"  - {n['name']}: {snippet}")
            bridge_candidates.append({
                "pair": pair,
                "pair_count": pair_count,
                "freq": (f1, f2),
                "summaries": summaries,
                "note_names": [n["name"] for n in notes_list[:3]],
            })

    bridge_candidates.sort(key=lambda x: x["freq"][0] + x["freq"][1], reverse=True)
    top_bridges = bridge_candidates[:6]  # Get a few extra for xAI to filter

    if not top_bridges:
        return "_No surprising cross-domain bridges found._\n"

    # Use xAI to assess which bridges are genuinely insightful
    bridge_data = []
    for b in top_bridges:
        bridge_data.append({
            "tags": list(b["pair"]),
            "co_occurrences": b["pair_count"],
            "individual_frequencies": b["freq"],
            "bridging_notes": b["note_names"],
            "snippets": b["summaries"],
        })

    prompt = (
        "Below are unusual tag co-occurrences from a research vault — tags that individually "
        "appear often but rarely appear together in the same note. For each, assess whether the "
        "bridge represents a genuinely insightful cross-domain connection or is merely coincidental.\n\n"
        "Return the top 3 most insightful bridges. For each, give:\n"
        "- The two tags\n"
        "- Why this connection is interesting\n"
        "- What research direction it suggests\n\n"
        "Format as markdown bullet points.\n\n"
        f"Bridges:\n{json.dumps(bridge_data, indent=2)}"
    )

    result = xai_chat(api_key, "You are a research analyst identifying cross-domain insights.", prompt)
    return result + "\n"


# ---------------------------------------------------------------------------
# Pass 5: Zeitgeist Snapshot
# ---------------------------------------------------------------------------

def pass_zeitgeist(vault: dict, api_key: str) -> str:
    """Synthesize the current mood and direction of the vault's sources."""
    print("\n[Pass 5/7] Zeitgeist Snapshot...")
    recent_2w = vault["recent_2w"]
    four_weeks_ago = datetime.now() - timedelta(weeks=4)

    if not recent_2w:
        return "_No notes from the last 2 weeks to generate a zeitgeist._\n"

    # Collect summaries from recent notes
    note_summaries = []
    for note in recent_2w[:80]:  # Cap to avoid token overflow
        snippet = note["body"][:200].replace("\n", " ").strip()
        tags_str = ", ".join(note["tags"][:5]) if note["tags"] else "untagged"
        source = note["source"] or "unknown"
        note_summaries.append(f"- [{tags_str}] ({source}): {snippet}")

    # Also find topics that were hot 4 weeks ago but disappeared
    old_window = [
        n for n in vault["all_notes"]
        if n["date"] and four_weeks_ago - timedelta(weeks=2) <= n["date"] < four_weeks_ago
    ]
    old_tags = Counter(t for n in old_window for t in n["tags"])
    recent_tags = Counter(t for n in recent_2w for t in n["tags"])
    disappeared = [
        tag for tag, count in old_tags.most_common(20)
        if count >= 3 and recent_tags.get(tag, 0) == 0
    ]

    prompt = (
        "You are analyzing a researcher's note collection from the last 2 weeks. "
        "Synthesize the zeitgeist — what the collective voice of these sources is saying.\n\n"
        "Produce 3-4 paragraphs covering:\n"
        "1. The dominant tension pair (e.g., 'speed vs safety') — what opposing forces are at play\n"
        "2. What everyone is talking about — the convergent themes\n"
        "3. What nobody is talking about — note these topics were hot 4 weeks ago but disappeared: "
        f"{', '.join(disappeared[:5]) if disappeared else 'none detected'}\n"
        "4. The overall mood/direction — optimistic, cautious, fragmented, etc.\n\n"
        "Write in an analytical but engaging style. No bullet points, just prose.\n\n"
        f"Recent note summaries ({len(note_summaries)} notes):\n"
        + "\n".join(note_summaries)
    )

    result = xai_chat(
        api_key,
        "You are an intellectual trends analyst synthesizing research notes into a zeitgeist narrative.",
        prompt,
    )
    return result + "\n"


# ---------------------------------------------------------------------------
# Pass 6: Actionable Insights
# ---------------------------------------------------------------------------

def pass_action(vault: dict, api_key: str) -> str:
    """Find convergence points and classify actions."""
    print("\n[Pass 6/7] Actionable Insights...")
    recent = vault["recent"]

    if not recent:
        return "_No recent notes to derive actionable insights._\n"

    # Find convergence points: tags where 3+ notes from different sources agree
    tag_source_notes: dict[str, list] = defaultdict(list)
    for note in recent:
        src = note["source"] or note["name"]
        for tag in note["tags"]:
            tag_source_notes[tag].append({
                "source": src,
                "name": note["name"],
                "snippet": note["body"][:150].replace("\n", " ").strip(),
            })

    convergent_tags = []
    for tag, entries in tag_source_notes.items():
        unique_sources = set(e["source"] for e in entries)
        if len(unique_sources) >= 3:
            convergent_tags.append({
                "tag": tag,
                "source_count": len(unique_sources),
                "entries": entries[:5],
            })
    convergent_tags.sort(key=lambda x: x["source_count"], reverse=True)

    if not convergent_tags:
        return "_No convergence points found (need 3+ sources agreeing on a topic)._\n"

    # Use xAI to classify and produce recommendations (batch into one call)
    convergence_data = json.dumps(convergent_tags[:8], indent=2)
    prompt = (
        "Below are convergence points from a research vault — topics where 3+ independent sources "
        "are saying similar things in the last few weeks.\n\n"
        "For each, classify the recommended action as one of:\n"
        "- LEARN — invest time understanding this deeper\n"
        "- BUILD — try this tool/technique hands-on\n"
        "- WATCH — monitor this company/trend passively\n"
        "- RECONSIDER — a previous assumption may be wrong\n\n"
        "Return EXACTLY 3 actionable recommendations (anti-annoyance cap). For each:\n"
        "1. Action type in bold (e.g., **LEARN**)\n"
        "2. What to do, in 1-2 sentences\n"
        "3. Source notes that support this\n\n"
        "Format as numbered markdown list.\n\n"
        f"Convergence data:\n{convergence_data}"
    )

    result = xai_chat(
        api_key,
        "You are a research advisor turning data convergence into actionable weekly recommendations.",
        prompt,
    )
    return result + "\n"


# ---------------------------------------------------------------------------
# Pass 7: Prediction Extraction
# ---------------------------------------------------------------------------

def pass_predict(vault: dict, api_key: str) -> str:
    """Extract and track predictions from recent notes."""
    print("\n[Pass 7/7] Prediction Extraction...")
    recent_2w = vault["recent_2w"]
    existing_predictions = vault["predictions"]

    if not recent_2w:
        return "_No recent notes to scan for predictions._\n"

    # Collect note content for prediction extraction
    note_content = []
    for note in recent_2w[:60]:
        snippet = note["body"][:400].replace("\n", " ").strip()
        source = note["source"] or "unknown"
        note_content.append(f"[{note['name']}] (source: {source}): {snippet}")

    # Single xAI call to extract predictions
    prompt = (
        "Scan these research notes for explicit predictions — statements about what will happen "
        "in the future with some timeframe (implicit or explicit). Look for phrases like "
        "'will become', 'by 2027', 'in the next year', 'I expect', 'is going to', 'within months'.\n\n"
        "For each prediction found, return a JSON array with objects containing:\n"
        "- \"prediction\": what was predicted (1-2 sentences)\n"
        "- \"who\": who made the prediction\n"
        "- \"timeframe\": when they expect it (e.g., '2027', '6 months', 'end of year')\n"
        "- \"source_note\": the note name in brackets\n\n"
        "Return ONLY the JSON array, no other text. If no predictions found, return [].\n\n"
        f"Notes:\n" + "\n".join(note_content)
    )

    raw = xai_chat(
        api_key,
        "You are a prediction extractor. Return only valid JSON arrays.",
        prompt,
    )

    # Parse predictions from xAI response
    new_predictions = []
    try:
        # Try to extract JSON from the response (may be wrapped in markdown)
        json_match = re.search(r"\[.*\]", raw, re.DOTALL)
        if json_match:
            new_predictions = json.loads(json_match.group())
    except (json.JSONDecodeError, AttributeError):
        pass

    # Stamp each new prediction with extraction date
    today = datetime.now().strftime("%Y-%m-%d")
    for pred in new_predictions:
        pred["extracted_date"] = today

    # Check existing predictions for approaching deadlines or resolution
    approaching = []
    now = datetime.now()
    for pred in existing_predictions:
        tf = pred.get("timeframe", "")
        # Simple heuristic: check if year mentioned is current or next year
        year_match = re.search(r"20\d{2}", tf)
        if year_match:
            pred_year = int(year_match.group())
            if pred_year <= now.year:
                approaching.append(pred)

    # Format output
    lines = []
    if new_predictions:
        lines.append(f"**{len(new_predictions)} new predictions extracted:**")
        for pred in new_predictions:
            who = pred.get("who", "unknown")
            tf = pred.get("timeframe", "unspecified")
            src = pred.get("source_note", "")
            lines.append(f"- {pred.get('prediction', '?')} — _{who}_, timeframe: {tf} ({src})")
    else:
        lines.append("_No new predictions found in recent notes._")

    if approaching:
        lines.append(f"\n**{len(approaching)} predictions approaching their timeframe:**")
        for pred in approaching:
            lines.append(
                f"- {pred.get('prediction', '?')} — timeframe: {pred.get('timeframe', '?')} "
                f"(extracted {pred.get('extracted_date', '?')})"
            )

    return "\n".join(lines) + "\n", new_predictions


# ---------------------------------------------------------------------------
# One Thing synthesis + Report assembly
# ---------------------------------------------------------------------------

def synthesize_one_thing(api_key: str, sections: dict) -> str:
    """Use xAI to pick the single most important insight from all passes."""
    print("\n  Synthesizing The One Thing...")
    # Build a condensed version of all section outputs
    combined = ""
    for name, content in sections.items():
        # Take first 300 chars of each section
        snippet = content[:300].replace("\n", " ").strip()
        combined += f"\n[{name}]: {snippet}\n"

    prompt = (
        "Below are summaries from 7 analysis passes over a research vault. "
        "Pick the single most important, actionable insight across all passes. "
        "Write 2-3 sentences that a busy researcher should read first thing Sunday morning. "
        "Be specific and concrete, not vague. Reference the specific topic or finding.\n\n"
        f"{combined}"
    )

    return xai_chat(
        api_key,
        "You are a research advisor distilling complex analysis into one key takeaway.",
        prompt,
    )


def build_report(date_str: str, sections: dict, one_thing: str, vault: dict) -> str:
    """Assemble the final markdown report."""
    total_notes = len(vault["all_notes"])
    connections_count = len(vault["connections"])
    theses_count = len(vault["theses"])

    report = f"""---
type: weekly-brain
date: {date_str}
tags: [weekly-brain, report]
status: published
---

# Weekly Brain Digest — {date_str}

> Your vault analyzed {total_notes} notes this week. Here's what it's thinking.

---

## The One Thing

{one_thing}

---

## Trend Momentum 📈

{sections.get('trend', '_Skipped._')}

## Thesis Health 🧬

{sections.get('thesis', '_Skipped._')}

## Blindspots 🔍

{sections.get('blindspot', '_Skipped._')}
"""
    return report


def build_report_part2(sections: dict, vault: dict) -> str:
    """Second half of the report."""
    total_notes = len(vault["all_notes"])
    connections_count = len(vault["connections"])
    theses_count = len(vault["theses"])

    report = f"""
## Cross-Domain Bridges 🌉

{sections.get('bridge', '_Skipped._')}

## Zeitgeist 🌊

{sections.get('zeitgeist', '_Skipped._')}

## Do This Week ✅

{sections.get('action', '_Skipped._')}

## Predictions 🔮

{sections.get('predict', '_Skipped._')}

---

> Generated from {total_notes} vault notes, {connections_count} connections, {theses_count} tracked theses.
"""
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PASS_FUNCS = {
    "trend": pass_trend,
    "thesis": pass_thesis,
    "blindspot": pass_blindspot,
    "bridge": pass_bridge,
    "zeitgeist": pass_zeitgeist,
    "action": pass_action,
    "predict": pass_predict,
}


def main():
    parser = argparse.ArgumentParser(description="Obsidian Weekly Brain Digest")
    parser.add_argument("--pass", dest="single_pass", choices=PASS_NAMES, default=None,
                        help="Run only a single analysis pass")
    parser.add_argument("--dry-run", action="store_true",
                        help="Analyze but don't write report to vault")
    parser.add_argument("--weeks", type=int, default=4,
                        help="Lookback window in weeks (default: 4)")
    args = parser.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"=== Obsidian Weekly Brain Digest — {today} ===\n")

    # Load API key
    api_key = get_api_key()

    # Load vault
    vault = load_vault(weeks=args.weeks)

    # Determine which passes to run
    if args.single_pass:
        passes_to_run = [args.single_pass]
    else:
        passes_to_run = PASS_NAMES

    # Run passes
    sections = {}
    new_predictions = []

    for pass_name in passes_to_run:
        func = PASS_FUNCS[pass_name]
        try:
            result = func(vault, api_key)
            # pass_predict returns a tuple (text, predictions_list)
            if pass_name == "predict" and isinstance(result, tuple):
                sections[pass_name] = result[0]
                new_predictions = result[1]
            else:
                sections[pass_name] = result
        except Exception as e:
            print(f"  ERROR in {pass_name}: {e}", file=sys.stderr)
            sections[pass_name] = f"_Error during {pass_name} analysis: {e}_\n"

    # Synthesize "The One Thing" (only if multiple passes ran)
    one_thing = ""
    if len(sections) >= 3:
        try:
            one_thing = synthesize_one_thing(api_key, sections)
        except Exception as e:
            print(f"  ERROR synthesizing One Thing: {e}", file=sys.stderr)
            one_thing = "_Could not synthesize — see individual sections below._"
    elif len(sections) == 1:
        one_thing = list(sections.values())[0][:300]

    # Build report
    report = build_report(today, sections, one_thing, vault)
    report += build_report_part2(sections, vault)

    if args.dry_run:
        print("\n--- DRY RUN — Report preview ---\n")
        print(report)
        print("--- End of dry run ---")
    else:
        # Write report to vault
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / f"weekly-brain-{today}.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"\n  Report written to: {report_path}")

        # Update predictions.json if new predictions were found
        if new_predictions:
            all_predictions = vault["predictions"] + new_predictions
            PREDICTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PREDICTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(all_predictions, f, indent=2, ensure_ascii=False)
            print(f"  Added {len(new_predictions)} predictions to {PREDICTIONS_FILE}")

    print(f"\n=== Done. {len(sections)} passes completed. ===")


if __name__ == "__main__":
    main()
