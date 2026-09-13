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
import subprocess
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
DISCOVER_FILE = VAULT_PATH / "Research" / "discover.json"
REPORTS_DIR = VAULT_PATH / "Research" / "Reports"

CONFIG_DIR = Path.home() / ".config" / "last30days"
ENV_FILE = CONFIG_DIR / ".env"

XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_MODEL = "grok-4.5"

CLAUDE_CLI = r"C:\Users\nuno_\.local\bin\claude.exe"

PASS_NAMES = ["trend", "thesis", "blindspot", "bridge", "zeitgeist", "action", "predict", "discover", "cost"]

# Path to the daily research pipeline config (for must-follow list)
PIPELINE_MD = Path(r"Z:\Projects\Eric-Cartman\.github\skills\obsidian-daily-research\pipeline.md")


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


class _RunCost:
    """Measures what *this* brain run actually cost, instead of assuming it.

    Claude CLI calls run on the Max subscription and are charged at $0; xAI
    calls report an exact figure. Anything without a reported cost is counted
    as an unpriced call so the report can say so rather than quietly guess.
    """

    def __init__(self):
        self.calls: list[dict] = []

    def record(self, engine: str, model: str, cost: float | None,
               in_tok: int = 0, out_tok: int = 0) -> None:
        self.calls.append({"engine": engine, "model": model, "cost": cost,
                           "in": in_tok, "out": out_tok})

    @property
    def total(self) -> float:
        return sum(c["cost"] or 0.0 for c in self.calls)

    def summary(self) -> str:
        if not self.calls:
            return "no model calls"
        by = Counter(c["engine"] for c in self.calls)
        parts = [f"{n}× {e}" for e, n in by.most_common()]
        unpriced = sum(1 for c in self.calls if c["cost"] is None and c["engine"] != "claude-cli")
        if unpriced:
            parts.append(f"{unpriced} unpriced")
        return ", ".join(parts)


RUN_COST = _RunCost()


def xai_chat(api_key: str, system_prompt: str, user_prompt: str, effort: str = "medium") -> str:
    """Call xAI chat completions API and return the assistant message content."""
    payload = json.dumps({
        "model": XAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
        "reasoning_effort": effort,
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
    # xAI returns the exact charge as cost_in_usd_ticks (1 tick = 1e-10 USD).
    usage = data.get("usage") or {}
    ticks = usage.get("cost_in_usd_ticks")
    RUN_COST.record(
        "xai", XAI_MODEL,
        (ticks / 10_000_000_000) if ticks else None,
        usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
    )
    return data["choices"][0]["message"]["content"]


def claude_chat(system_prompt: str, user_prompt: str) -> str | None:
    """Call Claude via CLI (Max subscription, free). Returns None on failure."""
    import subprocess
    combined = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
    try:
        # Prompt goes over stdin: Windows caps a command line at ~32K chars,
        # and the blindspot/zeitgeist prompts are bigger than that.
        result = subprocess.run(
            [CLAUDE_CLI, "--print"],
            input=combined,
            capture_output=True, text=True, encoding="utf-8", timeout=300,
        )
        content = result.stdout.strip()
        if content and "Failed to authenticate" not in content:
            print("  [claude] OK")
            RUN_COST.record("claude-cli", "claude", 0.0)  # Max subscription: no per-call charge
            return content
        print(f"  [claude-cli] Failed, falling back to xAI: {result.stderr[:100]}")
    except Exception as e:
        print(f"  [claude-cli] Error ({e}), falling back to xAI")
    return None


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
    date_str = str(date_str).strip().strip('"').strip("'")
    # ISO datetimes with timezone (e.g. 2026-04-29T15:06:09Z, +00:00): keep the
    # date, drop the tz so comparisons with naive datetime.now() work.
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$", date_str)
    if m:
        date_str = m.group(1)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def note_date(fm: dict) -> datetime | None:
    """Best available date for a note. Library notes use date_saved/date_found,
    podcasts use date/published, and a few use plain date."""
    for key in ("date", "date_saved", "date_found", "published", "date_published", "created"):
        dt = parse_date(fm.get(key, ""))
        if dt:
            return dt
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
            "date": note_date(fm),
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
# Shared: structural vs topic tags
# ---------------------------------------------------------------------------

_STRUCTURAL_TAGS = {"research", "podcast", "library", "daily", "research-note",
                    "synthesis", "article", "x", "reference", "report"}


def structural_tags(vault: dict) -> set[str]:
    """Tags that describe the note rather than its topic: note types, and
    podcast show names slugified from the `show:` field. Cached on the vault."""
    if "_structural_tags" in vault:
        return vault["_structural_tags"]
    tags = set(_STRUCTURAL_TAGS)
    for n in vault["podcasts"]:
        show = n["frontmatter"].get("show", "")
        if show:
            tags.add(re.sub(r"[^a-z0-9]+", "-", show.lower()).strip("-"))
            # tag may be a truncated slug ("no-priors" for "No Priors: Artificial…")
            tags.add(re.sub(r"[^a-z0-9]+", "-", show.split(":")[0].lower()).strip("-"))
    vault["_structural_tags"] = tags
    return tags


def note_voice(note: dict) -> str:
    """Independent voice behind a note: podcast show, else author, else the
    note itself. `source:` is a *type* (x/article/podcast) and would make three
    X posts by the same person look like three independent sources."""
    fm = note["frontmatter"]
    who = (fm.get("show") or fm.get("author") or "").strip()
    if not who:
        return note["name"]
    # Collapse variants: "swyx / Latent Space" == "swyx (Shawn Wang) / Latent Space"
    who = re.sub(r"\(.*?\)", "", who)
    who = re.split(r"\s*[/|:]\s*", who)[0]
    return who.strip().lower().lstrip("@")


def is_daily(note: dict) -> bool:
    """Path-separator-safe check (str(path) has backslashes on Windows, so
    '"Research/Dailies" in str(path)' never matched)."""
    return "Dailies" in note["path"].parts


def last_report_section(today: datetime, heading: str) -> str:
    """Body of `## <heading>…` from the most recent weekly-brain report before
    today, or '' if none. Used to give passes week-over-week continuity."""
    if not REPORTS_DIR.exists():
        return ""
    candidates = []
    for fp in REPORTS_DIR.glob("weekly-brain-*.md"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", fp.name)
        dt = parse_date(m.group(1)) if m else None
        if dt and dt.date() < today.date():
            candidates.append((dt, fp))
    if not candidates:
        return ""
    _, fp = max(candidates)
    try:
        text = fp.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = re.search(rf"^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Pass 1: Trend Momentum
# ---------------------------------------------------------------------------

def pass_trend(vault: dict, api_key: str) -> str:
    """Identify rising tags and convergent discoveries."""
    print("\n[Pass 1/7] Trend Momentum...")
    now = datetime.now()

    # Build tag frequency per week for the last 8 weeks
    # Exclude dailies: they all share the same 5 tags (agents, skills, models,
    # sdd, sdlc), drowning out the more specific Library/Podcast tags.
    trend_notes = vault["library"] + vault["podcasts"]

    # Skip structural tags so "research" and "raoul-pal-the-journey-man"
    # don't show up as rising topics.
    _skip = structural_tags(vault)

    def _is_topic_tag(tag: str) -> bool:
        return tag.lower() not in _skip

    week_tags: dict[str, Counter] = defaultdict(Counter)
    for note in trend_notes:
        if not note["date"] or note["date"] < vault["cutoff_8w"]:
            continue
        wk = week_key(note["date"])
        for tag in note["tags"]:
            if _is_topic_tag(tag):
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
    # Exclude dailies — they all tag the same 5 topics so every daily adds noise
    convergent = []
    two_weeks_ago = now - timedelta(weeks=2)
    tag_sources: dict[str, set] = defaultdict(set)
    for note in trend_notes:
        if not note["date"] or note["date"] < two_weeks_ago:
            continue
        who = note_voice(note)
        for tag in note["tags"]:
            if _is_topic_tag(tag):
                tag_sources[tag].add(who)
    # A "discovery" is a topic that *newly* has several voices. Tags already on a
    # large share of the corpus (agents, workflow-design…) converge every week and
    # tell you nothing new, so cap by overall prevalence.
    corpus_tag_freq = Counter(t for n in trend_notes for t in n["tags"])
    ubiquitous = {t for t, c in corpus_tag_freq.items() if c / max(len(trend_notes), 1) > 0.12}
    for tag, sources in tag_sources.items():
        if len(sources) >= 3 and tag not in ubiquitous:
            convergent.append((tag, len(sources), sorted(sources)[:5]))
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

TRACKER_SCRIPT = Path(r"Z:\Projects\Eric-Cartman\.github\skills\obsidian-thesis-tracker\scripts\tracker.py")
THESIS_REFRESH_DAYS = 6       # re-cluster if theses.json is older than this
THESIS_FULL_DETAIL_MAX = 8    # theses shown with statement + links; rest as one-liners


def refresh_theses_if_stale(vault: dict) -> None:
    """Run the thesis tracker if theses.json is older than THESIS_REFRESH_DAYS.

    The tracker is what turns connections.json into theses; without this the
    weekly brain only ever re-reads whatever was last written by hand.
    Fail-soft: any error leaves the existing theses in place.
    """
    if not TRACKER_SCRIPT.exists():
        return
    try:
        age_days = (datetime.now() - datetime.fromtimestamp(THESES_FILE.stat().st_mtime)).days \
            if THESES_FILE.exists() else 10**6
    except OSError:
        age_days = 10**6
    if age_days < THESIS_REFRESH_DAYS:
        return
    print(f"  theses.json is {age_days}d old — running thesis tracker...")
    try:
        r = subprocess.run(
            [sys.executable, str(TRACKER_SCRIPT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
        )
        tail = "\n".join(r.stdout.strip().splitlines()[-3:])
        print(f"  tracker exit {r.returncode}: {tail}")
        if r.returncode == 0:
            fresh = load_json_safe(THESES_FILE)
            vault["theses"] = fresh if isinstance(fresh, list) else fresh.get("theses", [])
    except (subprocess.SubprocessError, OSError) as e:
        print(f"  WARNING: thesis tracker failed ({e}); using existing theses.json", file=sys.stderr)


def pass_thesis(vault: dict, api_key: str) -> str:
    """Assess health of tracked theses."""
    print("\n[Pass 2/7] Thesis Health Check...")
    refresh_theses_if_stale(vault)
    theses = vault["theses"]
    connections = vault["connections"]

    if not theses:
        return "_No theses tracked yet (Research/theses.json not found or empty)._\n"

    three_weeks_ago = datetime.now() - timedelta(weeks=3)
    lines = []
    rendered: list[tuple[int, list[str], str]] = []  # (evidence, detail_lines, one_liner)

    for thesis in theses:
        thesis_id = thesis.get("id", thesis.get("name", "unknown"))
        thesis_name = thesis.get("name", thesis.get("title", thesis_id))
        thesis_tags = thesis.get("tags", [])

        # Gather this thesis's note paths and embedded connections
        thesis_notes = set(thesis.get("notes", []))
        thesis_conns = thesis.get("connections", [])

        # Count supporting vs contradicting connections
        supporting = 0
        contradicting = 0
        latest_support_date = None

        # Use the thesis's own curated connection list for counts
        if thesis_conns:
            for conn in thesis_conns:
                rel = conn.get("relationship", conn.get("type", "")).lower()
                if "contradict" in rel or "against" in rel or "challenge" in rel:
                    contradicting += 1
                else:
                    supporting += 1

        # Match vault connections by thesis notes for dates (and counts
        # as fallback when the thesis has no embedded connections)
        for conn in connections:
            conn_source = conn.get("source", "")
            conn_target = conn.get("target", "")
            if conn_source not in thesis_notes and conn_target not in thesis_notes:
                continue
            rel = conn.get("relationship", conn.get("type", "")).lower()
            conn_date_str = conn.get("detected_at", conn.get("date", conn.get("created", "")))
            conn_date = parse_date(conn_date_str[:10]) if conn_date_str else None

            if not thesis_conns:
                # Fallback: count from vault connections
                if "contradict" in rel or "against" in rel or "challenge" in rel:
                    contradicting += 1
                else:
                    supporting += 1

            # Track latest supporting evidence date
            if not ("contradict" in rel or "against" in rel or "challenge" in rel):
                if conn_date and (latest_support_date is None or conn_date > latest_support_date):
                    latest_support_date = conn_date

        # Determine health status
        flags = []
        if thesis.get("status") == "orphaned":
            flags.append("ORPHANED")
        # Proportional: 5 contradictions against 296 supports is a healthy
        # thesis with interesting tensions, not a contradicted one.
        total = supporting + contradicting
        if contradicting >= 2 and total and contradicting / total >= 0.2:
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

        emoji = {"HEALTHY": "✅", "DECAYING": "⚠️", "CONTRADICTED": "❌", "UNSUPPORTED": "❓",
                 "FIELD-DRIFT": "🔀", "ORPHANED": "🪦"}
        status_emoji = emoji.get(flags[0], "⚠️") if flags else "✅"

        # --- What the thesis actually says, and where to go read about it ---
        statement = (thesis.get("statement") or "").strip()
        detail: list[str] = []
        detail.append(f"- {status_emoji} **{thesis_id}** — {status} "
                      f"({supporting} supporting, {contradicting} contradicting)")
        if statement:
            detail.append(f"  > {statement}")
        # Swap `lines` for this thesis's own buffer; collected at the end.
        _outer_lines, lines = lines, detail

        # Report link: report_path is stored as an absolute-ish Windows path;
        # reduce it to a vault-relative wikilink.
        report_path = thesis.get("report_path") or ""
        report_link = ""
        if report_path:
            rp = Path(report_path.replace("\\", "/"))
            try:
                rel = rp.relative_to(Path(str(VAULT_PATH).replace("\\", "/")))
            except ValueError:
                # Path stored without drive letter — match on the vault folder name
                parts = rp.parts
                if "Obsidian Vault" in parts:
                    rel = Path(*parts[parts.index("Obsidian Vault") + 1:])
                else:
                    rel = Path(rp.name)
            report_link = f"[[{rel.with_suffix('').as_posix()}]]"
        meta = []
        if report_link:
            meta.append(f"Report: {report_link}")
        if thesis.get("first_detected"):
            meta.append(f"detected {thesis['first_detected']}")
        if thesis.get("last_updated"):
            meta.append(f"last updated {thesis['last_updated']}")
        if meta:
            lines.append("  " + " · ".join(meta))

        # Anchor notes: the most-connected notes in the thesis cluster, as links.
        degree: Counter = Counter()
        for conn in thesis_conns:
            degree[conn.get("source", "")] += 1
            degree[conn.get("target", "")] += 1
        anchors = [p for p, _ in degree.most_common(3) if p]
        if anchors:
            anchor_links = ", ".join(f"[[{Path(p).name}]]" for p in anchors)
            lines.append(f"  Anchor notes: {anchor_links} ({len(thesis_notes)} notes in cluster)")

        # Evidence recency — makes DECAYING legible.
        if latest_support_date:
            age = (datetime.now() - latest_support_date).days
            lines.append(f"  Last new evidence: {latest_support_date:%Y-%m-%d} ({age}d ago)")

        # Tensions: the contradicting edges are the most interesting part of a
        # thesis, so show them rather than just counting them.
        tensions = [c for c in thesis_conns
                    if any(k in c.get("relationship", "").lower() for k in ("contradict", "against", "challenge"))]
        if tensions:
            # Pull explanations from the vault connections where available
            expl = {(c.get("source"), c.get("target")): c.get("explanation", "") for c in connections}
            lines.append(f"  Tensions ({len(tensions)}):")
            for c in tensions[:3]:
                s, t = c.get("source", ""), c.get("target", "")
                why = expl.get((s, t), "").strip()
                why = (" — " + (why if len(why) <= 160 else why[:157].rstrip() + "…")) if why else ""
                lines.append(f"    - [[{Path(s).name}]] ⟂ [[{Path(t).name}]]{why}")

        # Restore the section buffer and file this thesis for ranking.
        lines = _outer_lines
        short = statement if len(statement) <= 140 else statement[:137].rstrip() + "…"
        one_liner = (f"- {status_emoji} **{thesis_id}** ({supporting}/{contradicting}) "
                     f"{short}" + (f" — {report_link}" if report_link else ""))
        rendered.append((supporting, detail, one_liner))

    # Problem theses first (anything flagged), then by evidence.
    def _rank(item):
        _, detail_lines, _ = item
        flagged = "HEALTHY" not in detail_lines[0]
        return (0 if flagged else 1, -item[0])
    rendered.sort(key=_rank)

    full = rendered[:THESIS_FULL_DETAIL_MAX]
    rest = rendered[THESIS_FULL_DETAIL_MAX:]
    lines.append(f"**{len(theses)} theses tracked** · showing {len(full)} in detail"
                 + (f", {len(rest)} more below" if rest else "") + "\n")
    for _, detail_lines, _ in full:
        lines.extend(detail_lines)
    if rest:
        lines.append("\n**Also tracked** (support/contradict counts):")
        for _, _, one_liner in rest:
            lines.append(one_liner)

    stale = [t for t in theses if t.get("last_updated") and
             (parse_date(t["last_updated"]) or datetime.now()) < datetime.now() - timedelta(weeks=4)]
    if stale and len(stale) == len(theses):
        lines.append(
            f"\n_⚠️ theses.json last updated {max(t['last_updated'] for t in stale)} — "
            f"run `obsidian-thesis-tracker` to refresh clusters._"
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Pass 3: Blindspot Detection
# ---------------------------------------------------------------------------
#
# Goal (from SKILL.md): "missing subtopics, high consumption-to-synthesis
# ratios" — i.e. what do you keep *reading about* that your Library has no
# considered view on?  Word-count heuristics can't tell a topic from a phrase
# (and "open source 60x, 0 notes" is false when 26 notes are tagged
# open-weight-models), so this pass hands the model the actual evidence:
# recent reading vs Library coverage vs theses, and asks for judgement.

_BLINDSPOT_WEEKS = 3
_URL_RE = re.compile(r"https?://\S+")
_WIKILINK_RE = re.compile(r"\[\[[^\]]*\]\]")


def _daily_reading_items(note: dict, max_items: int = 14) -> list[str]:
    """Pull the headline-level items out of a daily research note: the POW
    paragraph, must-follow tweets, prominent-voice posts, news titles."""
    body = note["body"]
    pow_idx = body.find("## Today's POW")
    if pow_idx > 0:
        body = body[pow_idx:]
    items: list[str] = []

    # POW summary paragraph
    m = re.search(r"## Today's POW\s*\n+(.+?)(?:\n\s*\n|\n##)", body, re.DOTALL)
    if m:
        items.append("POW: " + m.group(1).strip().replace("\n", " ")[:400])

    pending_handle: str | None = None  # newer format: header line, text on next line
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", ">", "|---", "| Author")):
            pending_handle = None
            continue
        # newer format (Sep 2026+): "- **@handle** · 64127❤ · [open](url)" then
        # an indented line with the post text
        m = re.match(r"^-\s*\*\*(@\w+)\*\*", s)
        if m:
            pending_handle = m.group(1)
            continue
        if pending_handle and not s.startswith(("-", "|", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
            txt = _URL_RE.sub("", s).strip()
            if len(txt) > 15:
                items.append(f"{pending_handle}: {txt[:160]}")
            pending_handle = None
            continue
        pending_handle = None
        # older format: "- @handle (date): text [123❤️](url)"
        m = re.match(r"^-\s*(@\w+)\s*\([\d-]+\):\s*(.+?)\s*\[\d+", s)
        if m:
            items.append(f"{m.group(1)}: {m.group(2)[:160]}")
            continue
        # prominent-voices table rows: "| @handle | text | 123❤️ | [→](url) |"
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 2 and cells[0].startswith("@"):
                txt = _URL_RE.sub("", cells[1]).strip()
                if len(txt) > 15:
                    items.append(f"{cells[0]}: {txt[:160]}")
            continue
        # news items: "1. [Title - domain](url) — domain, date"
        m = re.match(r"^\d+\.\s*\[(.+?)\]\(", s)
        if m:
            items.append("news: " + m.group(1)[:160])
            continue
        # deep dives / other bullets with a link
        m = re.match(r"^-\s*(?:\[[ x]\]\s*)?\[(.+?)\]\(", s)
        if m:
            items.append("item: " + m.group(1)[:160])
        if len(items) >= max_items:
            break
    return items[:max_items]


def pass_blindspot(vault: dict, api_key: str) -> str:
    """What you keep reading that the Library has no considered view on."""
    print("\n[Pass 3/7] Blindspot Detection...")
    library = vault["library"]
    dailies = vault["dailies"]
    podcasts = vault["podcasts"]
    theses = vault.get("theses", [])
    cutoff = datetime.now() - timedelta(weeks=_BLINDSPOT_WEEKS)

    # ---- 1. What you've been reading -------------------------------------
    recent_dailies = sorted(
        [n for n in dailies if n["date"] and n["date"] >= cutoff],
        key=lambda n: n["date"],
    )
    reading_lines: list[str] = []
    for n in recent_dailies:
        items = _daily_reading_items(n)
        if items:
            reading_lines.append(f"[{n['date']:%Y-%m-%d}]")
            reading_lines.extend(f"  - {it}" for it in items)
    recent_pods = [n for n in podcasts if n["date"] and n["date"] >= cutoff]
    if recent_pods:
        reading_lines.append("[podcasts]")
        reading_lines.extend(
            f"  - {n['frontmatter'].get('show', '')}: {n['name'][:120]}" for n in recent_pods[:20]
        )
    if not reading_lines:
        return f"_No daily notes in the last {_BLINDSPOT_WEEKS} weeks to compare against the Library._\n"

    # ---- 2. What the Library covers --------------------------------------
    by_folder: dict[str, list[str]] = defaultdict(list)
    for n in library:
        try:
            folder = n["path"].relative_to(LIBRARY_DIR).parts[0] if n["path"].parent != LIBRARY_DIR else "(root)"
        except ValueError:
            folder = "(root)"
        by_folder[folder].append(n["name"])
    coverage_lines: list[str] = []
    for folder in sorted(by_folder):
        names = sorted(by_folder[folder])
        coverage_lines.append(f"{folder} ({len(names)} notes): " + "; ".join(names[:60]))
    tag_freq = Counter(t for n in library for t in n["tags"])
    tag_line = ", ".join(f"{t} ({c})" for t, c in tag_freq.most_common(45))

    # ---- 3. Theses --------------------------------------------------------
    thesis_lines = [f"- {t.get('id')}: {t.get('statement', '')}" for t in theses if t.get("statement")]

    # ---- 4. Stat hint: recurring phrases in dailies (evidence, not output) --
    phrase_counts: Counter = Counter()
    for n in recent_dailies:
        text = " ".join(_daily_reading_items(n, max_items=40))
        text = _WIKILINK_RE.sub(" ", _URL_RE.sub(" ", text))
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9.-]{3,}", text.lower())
        for i in range(len(words) - 1):
            phrase_counts[f"{words[i]} {words[i+1]}"] += 1
    phrase_hint = ", ".join(f"{p} ({c})" for p, c in phrase_counts.most_common(30) if c >= 3)

    prompt = (
        f"You are auditing a personal research vault for BLINDSPOTS: subjects the owner keeps "
        f"reading about (last {_BLINDSPOT_WEEKS} weeks of daily research digests and podcasts) "
        f"that the Library has no considered, synthesised view on.\n\n"
        "A blindspot is NOT:\n"
        "- a subject already covered by Library notes or tags below (check titles AND tags before claiming a gap);\n"
        "- a one-off news item; it must recur across several days or sources;\n"
        "- a pipeline artefact, a person's handle, or a generic phrase.\n\n"
        "Return at most 3 blindspots, ordered by how much reading attention they get. For each use exactly this shape:\n\n"
        "### <short topic name>\n"
        "- **Reading signal:** what keeps coming up — cite 2-3 specific items/dates from the reading list.\n"
        "- **Closest Library coverage:** the nearest existing notes/tags and why they don't actually cover it "
        "(or 'none').\n"
        "- **Note to write:** a concrete note title and a one-line scope.\n\n"
        "Then a final line: **Not blindspots:** 2-4 things that look hot in the reading but are already well "
        "covered (name the covering notes/tags), so the owner isn't tempted to duplicate.\n\n"
        "Prefer gaps that sit next to the tracked theses (a thesis with a hole in its evidence is more valuable "
        "than an unrelated curiosity). Be concrete and terse; no preamble.\n\n"
        "=== READING (recent) ===\n" + "\n".join(reading_lines) + "\n\n"
        "=== RECURRING PHRASES IN READING (counts; treat as hints, not truth) ===\n" + phrase_hint + "\n\n"
        "=== LIBRARY COVERAGE: folders and note titles ===\n" + "\n".join(coverage_lines) + "\n\n"
        "=== LIBRARY TAGS (count) ===\n" + tag_line + "\n\n"
        "=== TRACKED THESES ===\n" + ("\n".join(thesis_lines) if thesis_lines else "(none)") + "\n"
    )

    system = "You are a research librarian who is ruthless about distinguishing 'read about' from 'understood'."
    result = claude_chat(system, prompt)
    if result is None:
        result = xai_chat(api_key, system, prompt, effort="high")
    else:
        print("  [claude] Used for blindspot synthesis")
    return (result or "_Blindspot synthesis failed._").strip() + "\n"


# ---------------------------------------------------------------------------
# Pass 4: Cross-Domain Bridges
# ---------------------------------------------------------------------------
#
# Source: the `bridges` edges the connection detector already writes to
# connections.json (note-level, with confidence + explanation + detected_at).
# Only edges detected since the last weekly report count, so each week's
# bridges are new. The old tag-co-occurrence heuristic was structurally
# "agents x <rare tag>" because `agents` is on ~345 notes; it's gone.

_BRIDGE_MAX = 3
_BRIDGE_FALLBACK_WEEKS = 4


def _last_report_date(today: datetime) -> datetime | None:
    """Date of the most recent weekly-brain report before today, if any."""
    if not REPORTS_DIR.exists():
        return None
    dates = []
    for fp in REPORTS_DIR.glob("weekly-brain-*.md"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", fp.name)
        if m:
            dt = parse_date(m.group(1))
            if dt and dt.date() < today.date():
                dates.append(dt)
    return max(dates) if dates else None


def _note_index(vault: dict) -> dict[str, dict]:
    """Map vault-relative slug (as used in connections.json) -> note."""
    idx: dict[str, dict] = {}
    for n in vault["all_notes"]:
        try:
            rel = n["path"].relative_to(VAULT_PATH).with_suffix("").as_posix()
        except ValueError:
            continue
        idx[rel] = n
        idx[n["name"]] = n  # fallback: bare name
    return idx


def _note_excerpt(note: dict | None, slug: str, chars: int = 800) -> str:
    if not note:
        return f"(note not found: {slug})"
    body = note["body"]
    # skip a leading H1 and blank lines
    body = re.sub(r"^\s*#\s.*\n", "", body, count=1)
    body = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", body)  # unwrap wikilinks
    body = re.sub(r"https?://\S+", "", body)
    text = " ".join(body.split())[:chars]
    tags = ", ".join(note["tags"][:6])
    return f"[{tags}] {text}"


def pass_bridge(vault: dict, api_key: str) -> str:
    """New cross-domain bridges since the last report, from connections.json."""
    print("\n[Pass 4/7] Cross-Domain Bridges...")
    now = datetime.now()
    conns = vault["connections"]
    bridges = [c for c in conns if c.get("relationship") == "bridges"]
    if not bridges:
        return "_No bridge connections in connections.json yet (run obsidian-connection-detector)._\n"

    def _detected(c: dict) -> datetime | None:
        s = (c.get("detected_at") or c.get("date") or "")[:10]
        return parse_date(s) if s else None

    since = _last_report_date(now)
    window_label = f"since last report ({since:%Y-%m-%d})" if since else "last 2 weeks"
    if not since:
        since = now - timedelta(weeks=2)
    new = [b for b in bridges if (d := _detected(b)) and d >= since]

    widened = False
    if len(new) < 2:
        fb = now - timedelta(weeks=_BRIDGE_FALLBACK_WEEKS)
        new = [b for b in bridges if (d := _detected(b)) and d >= fb]
        widened = True
        window_label = f"last {_BRIDGE_FALLBACK_WEEKS} weeks (fewer than 2 new since last report)"

    if not new:
        return f"_No new bridges detected {window_label}._\n"

    # Highest confidence first; hand the model a few extra to choose from.
    new.sort(key=lambda b: -float(b.get("confidence", 0)))
    shortlist = new[: _BRIDGE_MAX * 2]

    idx = _note_index(vault)
    theses = vault.get("theses", [])
    thesis_of: dict[str, str] = {}
    for t in theses:
        for slug in t.get("notes", []):
            thesis_of[slug] = t.get("id", "")

    blocks = []
    for i, b in enumerate(shortlist, 1):
        s, t = b.get("source", ""), b.get("target", "")
        ns, nt = idx.get(s), idx.get(t)
        ts, tt = thesis_of.get(s, "-"), thesis_of.get(t, "-")
        blocks.append(
            f"--- Bridge {i} (confidence {b.get('confidence')}, detected {(_detected(b) or now):%Y-%m-%d}) ---\n"
            f"A: {Path(s).name}  [thesis: {ts}]\n   {_note_excerpt(ns, s)}\n"
            f"B: {Path(t).name}  [thesis: {tt}]\n   {_note_excerpt(nt, t)}\n"
            f"Detector's explanation: {b.get('explanation', '').strip()}\n"
        )
    thesis_lines = [f"- {t.get('id')}: {t.get('statement', '')[:220]}" for t in theses if t.get("statement")]

    prompt = (
        f"Below are cross-domain BRIDGES newly detected in a personal research vault: pairs of notes from "
        f"different domains that a connection detector judged to be linked. You have each note's opening "
        f"text and the detector's reasoning.\n\n"
        f"Pick the {_BRIDGE_MAX} most insightful (drop any that are coincidental or where the link is "
        f"trivial). For each, use exactly this shape:\n\n"
        "### <A short name> ⟷ <B short name>\n"
        "- **What each says:** one sentence per note, from the text given — not a guess.\n"
        "- **The bridge:** what follows from putting them together that neither says alone.\n"
        "- **Thesis link:** which tracked thesis this strengthens, challenges, or connects (name the id), "
        "or 'none'. A bridge between two thesis clusters is the most valuable kind — say so if it is.\n"
        "- **Do:** one concrete action — a note to write (give a title), a question to test, or a source to read.\n\n"
        "Use [[wikilinks]] with the exact note names given for A and B. Be terse; no preamble, no honourable mentions.\n\n"
        "=== TRACKED THESES ===\n" + ("\n".join(thesis_lines) if thesis_lines else "(none)") + "\n\n"
        "=== BRIDGES ===\n" + "\n".join(blocks)
    )

    system = "You are a research analyst who only asserts what the provided text supports."
    result = claude_chat(system, prompt)
    if result is None:
        result = xai_chat(api_key, system, prompt, effort="high")
    else:
        print("  [claude] Used for bridge synthesis")

    header = f"_{len(new)} new bridge{'s' if len(new) != 1 else ''} detected {window_label}._\n\n"
    return header + (result or "_Bridge synthesis failed._").strip() + "\n"


# ---------------------------------------------------------------------------
# Pass 5: Zeitgeist Snapshot
# ---------------------------------------------------------------------------

def pass_zeitgeist(vault: dict, api_key: str) -> str:
    """Synthesize the current mood and direction of the vault's sources."""
    print("\n[Pass 5/7] Zeitgeist Snapshot...")
    now = datetime.now()
    four_weeks_ago = now - timedelta(weeks=4)
    # Newest first, so the cap keeps the most recent material rather than
    # whatever happened to come first in directory order.
    recent_2w = sorted(vault["recent_2w"], key=lambda n: n["date"], reverse=True)

    if not recent_2w:
        return "_No notes from the last 2 weeks to generate a zeitgeist._\n"

    # Collect summaries from recent notes. Dailies go through the same
    # headline extractor Blindspots uses (POW + prominent voices + news) —
    # a 300-char slice from the POW heading threw away the strongest signal.
    note_summaries = []
    for note in recent_2w[:80]:  # Cap to avoid token overflow
        tags_str = ", ".join(t for t in note["tags"][:5]) if note["tags"] else "untagged"
        if "Dailies" in note["path"].parts:
            items = _daily_reading_items(note, max_items=8)
            if not items:
                continue
            note_summaries.append(f"- DAILY {note['date']:%Y-%m-%d}:\n" + "\n".join(f"    {it}" for it in items))
        else:
            body = re.sub(r"^\s*#\s.*\n", "", note["body"], count=1)
            body = re.sub(r"https?://\S+", "", body)
            snippet = " ".join(body.split())[:500]
            source = note["frontmatter"].get("show") or note["source"] or note["name"]
            note_summaries.append(f"- [{tags_str}] ({source}, {note['date']:%m-%d}): {snippet}")

    # Topics that were hot 4-6 weeks ago and have gone quiet. Structural/show
    # tags excluded; "now <= 1" rather than "now == 0" because 6 -> 1 is the
    # interesting case and exactly-zero is brittle.
    skip = structural_tags(vault)
    old_window = [
        n for n in vault["all_notes"]
        if n["date"] and four_weeks_ago - timedelta(weeks=2) <= n["date"] < four_weeks_ago
    ]
    old_tags = Counter(t for n in old_window for t in n["tags"] if t.lower() not in skip)
    recent_tags = Counter(t for n in recent_2w for t in n["tags"] if t.lower() not in skip)
    faded = [
        f"{tag} ({count} → {recent_tags.get(tag, 0)})"
        for tag, count in old_tags.most_common(30)
        if count >= 3 and recent_tags.get(tag, 0) <= 1
    ]

    # Last week's read, for continuity
    previous = last_report_section(now, "Zeitgeist")
    prev_block = (
        "=== LAST WEEK'S ZEITGEIST (for comparison — do not repeat it) ===\n" + previous + "\n\n"
        if previous else ""
    )

    prompt = (
        "You are analyzing a researcher's note collection from the last 2 weeks. "
        "Synthesize the zeitgeist — what the collective voice of these sources is saying.\n\n"
        "Produce 4-5 paragraphs, each starting with a short bold lead-in, covering:\n"
        "1. The dominant tension pair (e.g., 'speed vs safety') — what opposing forces are at play\n"
        "2. What everyone is talking about — the convergent themes\n"
        "3. What has gone quiet — these topics were active 4-6 weeks ago and have faded "
        f"(tag, mentions then → now): {', '.join(faded[:6]) if faded else 'none detected'}. "
        "Say whether each faded because it resolved, got absorbed into something bigger, or was just a spike.\n"
        "4. The overall mood/direction — optimistic, cautious, fragmented, etc.\n"
        + ("5. What shifted since last week — compare against last week's zeitgeist below: which tension "
           "moved, what new entered, what last week's read got wrong or right in hindsight. Be specific.\n"
           if previous else "")
        + "\nGround claims in the notes given: name sources and dates. "
        "Write in an analytical but engaging style. No bullet points, just prose.\n\n"
        + prev_block
        + f"=== RECENT NOTES ({len(note_summaries)}) ===\n"
        + "\n".join(note_summaries)
    )

    result = claude_chat(
        "You are an intellectual trends analyst synthesizing research notes into a zeitgeist narrative.",
        prompt,
    )
    if result is None:
        result = xai_chat(
            api_key,
            "You are an intellectual trends analyst synthesizing research notes into a zeitgeist narrative.",
            prompt,
            effort="high",
        )
    else:
        print("  [claude] Used for zeitgeist synthesis")
    return result + "\n"


# ---------------------------------------------------------------------------
# Pass 6: Actionable Insights
# ---------------------------------------------------------------------------

def pass_action(vault: dict, api_key: str) -> str:
    """Find convergence points and classify actions."""
    print("\n[Pass 6/7] Actionable Insights...")
    now = datetime.now()
    # Library + Podcast notes only: dailies all carry the same 5 tags and would
    # make every one of them a "convergence point". (The old check compared
    # against "Research/Dailies" with a forward slash, which never matched on
    # Windows, so dailies were in fact the main input until now.)
    recent_quality = sorted(
        [n for n in vault["recent"] if not is_daily(n)],
        key=lambda n: n["date"], reverse=True,
    )
    if not recent_quality:
        return "_No recent Library/Podcast notes to derive actionable insights._\n"

    skip = structural_tags(vault)

    # Convergence points: topic tags where 3+ distinct *voices* (author / show,
    # not the source-type field) have something to say in the window.
    tag_entries: dict[str, list] = defaultdict(list)
    for note in recent_quality:
        body = re.sub(r"^\s*#\s.*\n", "", note["body"], count=1)  # drop H1
        body = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", body)
        body = re.sub(r"https?://\S+", "", body)
        excerpt = " ".join(body.split())[:400]
        voice = note_voice(note)
        for tag in note["tags"]:
            if tag.lower() in skip:
                continue
            tag_entries[tag].append({
                "voice": voice,
                "note": note["name"],
                "date": f"{note['date']:%Y-%m-%d}",
                "excerpt": excerpt,
            })

    convergent = []
    for tag, entries in tag_entries.items():
        voices = {e["voice"] for e in entries}
        if len(voices) >= 3:
            # one entry per voice, newest first, so the model sees breadth not repetition
            seen, picked = set(), []
            for e in entries:
                if e["voice"] not in seen:
                    seen.add(e["voice"])
                    picked.append(e)
                if len(picked) == 5:
                    break
            convergent.append({"tag": tag, "voices": len(voices), "entries": picked})
    convergent.sort(key=lambda x: x["voices"], reverse=True)

    if not convergent:
        return "_No convergence points found (need 3+ independent voices on a topic)._\n"

    # Context: theses (so actions can be tied to them) and last week's actions
    # (so this week's aren't a repeat, and open items get a status).
    theses = vault.get("theses", [])
    thesis_lines = [f"- {t.get('id')}: {t.get('statement', '')[:240]}" for t in theses if t.get("statement")]
    previous = last_report_section(now, "Do This Week")

    convergence_data = json.dumps(convergent[:8], indent=2, ensure_ascii=False)
    prompt = (
        "Below are convergence points from a personal research vault — topics where 3+ independent "
        f"voices said something in the last {vault['weeks']} weeks — plus the vault's tracked theses "
        "and last week's recommendations.\n\n"
        "Classify each recommended action as one of:\n"
        "- LEARN — invest time understanding this deeper\n"
        "- BUILD — try this tool/technique hands-on\n"
        "- WATCH — monitor this company/trend passively\n"
        "- RECONSIDER — a previous assumption may be wrong\n\n"
        "Return EXACTLY 3 recommendations (hard cap). For each, as a numbered markdown item:\n"
        "1. Action type in bold, then what to do in 1-2 concrete sentences (a note title, a tool to try, "
        "a question to answer — not 'explore').\n"
        "2. *Why now:* one sentence on what converged.\n"
        "3. *Thesis:* which tracked thesis this feeds, tests, or challenges (by id), or 'none'.\n"
        "4. *Sources:* the supporting notes as [[wikilinks]] using the exact note names given.\n\n"
        "Rules: ground every claim in the excerpts; do not repeat last week's items unless the evidence "
        "changed materially (then say what changed); prefer actions that close a gap in a thesis over "
        "ones that merely restate its strongest cluster.\n\n"
        + ("After the three items, add one short paragraph headed **Carried over:** giving each of last "
           "week's items a status — done/superseded/still open — in one line each, based on what the "
           "recent notes show. If you can't tell, say 'no signal'.\n\n" if previous else "")
        + "=== TRACKED THESES ===\n" + ("\n".join(thesis_lines) if thesis_lines else "(none)") + "\n\n"
        + ("=== LAST WEEK'S DO THIS WEEK ===\n" + previous + "\n\n" if previous else "")
        + f"=== CONVERGENCE POINTS ===\n{convergence_data}"
    )

    result = claude_chat(
        "You are a research advisor turning data convergence into actionable weekly recommendations.",
        prompt,
    )
    if result is None:
        result = xai_chat(
            api_key,
            "You are a research advisor turning data convergence into actionable weekly recommendations.",
            prompt,
            effort="medium",
        )
    else:
        print("  [claude] Used for action synthesis")
    return result + "\n"


# ---------------------------------------------------------------------------
# Pass 7: Prediction Extraction + Resolution
# ---------------------------------------------------------------------------
#
# predictions.json entries:
#   id, prediction, who, timeframe (as stated), due (ISO date or null),
#   category, source_note, extracted_date, status
#   (open | resolved-true | resolved-false | unverifiable | expired),
#   resolved_date, resolution_note, corroborations (int)
#
# Extraction only scans notes newer than the last extraction, and the model
# is shown the open list so it skips duplicates (and marks corroborations
# instead). Resolution judges anything due within 2 weeks, or overdue,
# against the recent reading. Overdue-with-no-signal expires after 90 days.

_PREDICT_RESOLVE_HORIZON_DAYS = 14
_PREDICT_EXPIRE_DAYS = 90
_PREDICT_MAX_NOTES = 60


def _parse_json_block(raw: str | None):
    """Pull the first JSON array/object out of a model response."""
    if not raw:
        return None
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    text = m.group(1) if m else raw
    m = re.search(r"[\[{].*[\]}]", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _next_pred_id(preds: list[dict]) -> str:
    n = 0
    for p in preds:
        m = re.match(r"p-(\d+)$", str(p.get("id", "")))
        if m:
            n = max(n, int(m.group(1)))
    return f"p-{n + 1:03d}"


def _normalize_predictions(preds: list[dict]) -> bool:
    """Give legacy entries ids/status. Returns True if anything changed."""
    changed = False
    for p in preds:
        if not p.get("id"):
            p["id"] = _next_pred_id(preds)
            changed = True
        if not p.get("status"):
            p["status"] = "open"
            changed = True
        p.setdefault("due", None)
        p.setdefault("corroborations", 0)
    return changed


def _reading_lines(vault: dict, since: datetime, max_notes: int) -> list[str]:
    """Compact, newest-first view of notes dated after `since`."""
    notes = sorted(
        [n for n in vault["all_notes"] if n["date"] and n["date"] > since],
        key=lambda n: n["date"], reverse=True,
    )[:max_notes]
    out = []
    for n in notes:
        if is_daily(n):
            items = _daily_reading_items(n, max_items=12)
            if items:
                out.append(f"[[{n['name']}]] ({n['date']:%Y-%m-%d}, daily):\n" + "\n".join(f"    {it}" for it in items))
        else:
            body = re.sub(r"^\s*#\s.*\n", "", n["body"], count=1)
            body = re.sub(r"https?://\S+", "", body)
            excerpt = " ".join(body.split())[:600]
            out.append(f"[[{n['name']}]] ({n['date']:%Y-%m-%d}, {note_voice(n)}): {excerpt}")
    return out


def _resolution_reading(vault: dict, candidates: list[dict], now: datetime,
                        per_candidate: int = 8, recent: int = 30) -> list[str]:
    """Notes from [due-10d, due+14d] for each candidate, plus the newest notes
    from the last 2 weeks. Deduplicated, oldest first so the model reads
    chronologically."""
    picked: dict[str, dict] = {}
    dated = [n for n in vault["all_notes"] if n["date"]]
    for p in candidates:
        due = parse_date(p.get("due") or "")
        if not due:
            continue
        lo, hi = due - timedelta(days=10), due + timedelta(days=14)
        # nearest to the due date first, so the cap keeps the notes most likely to hold the outcome
        window = sorted((n for n in dated if lo <= n["date"] <= hi), key=lambda n: abs(n["date"] - due))
        for n in window[:per_candidate]:
            picked[n["name"]] = n
    for n in sorted((n for n in dated if n["date"] >= now - timedelta(weeks=2)),
                    key=lambda n: n["date"], reverse=True)[:recent]:
        picked[n["name"]] = n
    fake = {"all_notes": list(picked.values())}
    return _reading_lines(fake, datetime.min, len(picked))[::-1]


def _extract_predictions(api_key: str, reading: list[str], open_preds: list[dict], today: str) -> tuple[list[dict], dict[str, int]]:
    """One model call. Returns (new predictions, {existing_id: corroboration_count})."""
    open_list = "\n".join(f"- {p['id']}: {p['prediction'][:160]} ({p.get('who','?')})" for p in open_preds[:60])
    prompt = (
        "Scan these research notes for explicit PREDICTIONS: claims about what will happen, with an "
        "implicit or explicit timeframe ('will', 'by 2027', 'within months', 'I expect', 'is going to').\n\n"
        "Return ONLY a JSON object of the form:\n"
        '{"new": [ {"prediction": "...", "who": "...", "timeframe": "<as stated>", '
        f'"due": "<YYYY-MM-DD best-estimate resolution date, or null if truly open-ended; today is {today}>", '
        '"category": "<model-release|capability|market|policy|company|other>", '
        '"source_note": "<exact note name from the [[...]] given>"} ],\n'
        ' "corroborations": [ {"id": "<existing id>", "by": "<who>"} ] }\n\n'
        "Rules:\n"
        "- Skip anything that duplicates an ALREADY-OPEN prediction below (same claim, any wording). If a "
        "different person makes the same claim, list it under corroborations instead of new.\n"
        "- Skip vague aspiration ('AI will change everything'); keep claims that could be checked.\n"
        "- 'due' should be the date by which the claim can be judged (a release 'in 3-4 weeks' from a "
        "post dated 08-13 is due ~09-10). Be concrete; null only for genuinely open-ended claims.\n"
        "- Attribute to the person, not the note.\n\n"
        "=== ALREADY-OPEN PREDICTIONS ===\n" + (open_list or "(none)") + "\n\n"
        "=== NOTES ===\n" + "\n".join(reading)
    )
    system = "You are a prediction extractor. Return only valid JSON."
    raw = claude_chat(system, prompt)
    if raw is None:
        raw = xai_chat(api_key, system, prompt, effort="medium")
    else:
        print("  [claude] Used for prediction extraction")
    data = _parse_json_block(raw) or {}
    new = data.get("new", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    corr: dict[str, int] = defaultdict(int)
    if isinstance(data, dict):
        for c in data.get("corroborations", []):
            if isinstance(c, dict) and c.get("id"):
                corr[c["id"]] += 1
    cleaned = []
    for p in new:
        if not isinstance(p, dict) or not p.get("prediction"):
            continue
        due = p.get("due")
        p["due"] = due if (isinstance(due, str) and parse_date(due)) else None
        p["source_note"] = str(p.get("source_note", "")).strip("[] ")
        cleaned.append(p)
    return cleaned, corr


def _resolve_predictions(api_key: str, candidates: list[dict], reading: list[str], today: str) -> list[dict]:
    """One model call. Returns [{id, verdict, evidence}]."""
    if not candidates:
        return []
    cand = "\n".join(
        f"- {p['id']} (due {p.get('due') or 'n/a'}, by {p.get('who','?')}): {p['prediction']}"
        for p in candidates
    )
    prompt = (
        f"Today is {today}. Judge each prediction below against the recent notes.\n\n"
        "Return ONLY a JSON array: [{\"id\": \"...\", \"verdict\": \"resolved-true|resolved-false|still-open|unverifiable\", "
        "\"evidence\": \"<one sentence citing the note(s), or why no signal>\"}]\n\n"
        "Rules: 'resolved-true/false' only when the notes contain evidence, not from your own knowledge. "
        "'still-open' if the due date hasn't clearly passed or the outcome is pending. 'unverifiable' if the "
        "claim can't be checked from this vault (e.g. private internal metrics).\n\n"
        "=== PREDICTIONS TO JUDGE ===\n" + cand + "\n\n"
        "=== RECENT NOTES ===\n" + "\n".join(reading)
    )
    system = "You are a careful forecast resolver. Return only valid JSON."
    raw = claude_chat(system, prompt)
    if raw is None:
        raw = xai_chat(api_key, system, prompt, effort="medium")
    else:
        print("  [claude] Used for prediction resolution")
    data = _parse_json_block(raw)
    return [d for d in (data or []) if isinstance(d, dict) and d.get("id")]


def pass_predict(vault: dict, api_key: str):
    """Extract new predictions, resolve due ones, report the track record."""
    print("\n[Pass 7/7] Prediction Extraction...")
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    preds: list[dict] = vault["predictions"]
    if _normalize_predictions(preds):
        vault["_predictions_dirty"] = True

    # ---- window: only notes newer than the last extraction ----------------
    last_extracted = max((parse_date(p.get("extracted_date", "")) for p in preds if p.get("extracted_date")),
                         default=None)
    since = max(filter(None, [last_extracted, now - timedelta(weeks=2)]))
    reading = _reading_lines(vault, since, _PREDICT_MAX_NOTES)
    open_preds = [p for p in preds if p.get("status") == "open"]

    # ---- 1. extract (only if there is unscanned material) -------------------
    new_preds: list[dict] = []
    corr: dict[str, int] = {}
    if reading:
        new_preds, corr = _extract_predictions(api_key, reading, open_preds, today)
    else:
        print(f"  no notes newer than last extraction ({since:%Y-%m-%d}); skipping extraction")
    for p in new_preds:
        p["id"] = _next_pred_id(preds + new_preds[: new_preds.index(p)])
        p["extracted_date"] = today
        p["status"] = "open"
        p.setdefault("corroborations", 0)
    by_id = {p["id"]: p for p in preds}
    for pid, n in corr.items():
        if pid in by_id:
            by_id[pid]["corroborations"] = by_id[pid].get("corroborations", 0) + n
            vault["_predictions_dirty"] = True

    # ---- 2. resolve ---------------------------------------------------------
    horizon = now + timedelta(days=_PREDICT_RESOLVE_HORIZON_DAYS)
    candidates = []
    for p in open_preds:
        due = parse_date(p.get("due") or "")
        if due and due <= horizon:
            candidates.append(p)
    resolved_now: list[tuple[dict, str, str]] = []
    if candidates:
        # Evidence for a prediction clusters around its due date, which may be
        # weeks back: read a window around each due date plus the last 2 weeks.
        res_reading = _resolution_reading(vault, candidates, now)
        for r in _resolve_predictions(api_key, candidates, res_reading, today):
            p = by_id.get(r["id"])
            verdict = r.get("verdict", "still-open")
            if not p or verdict == "still-open":
                continue
            p["status"] = verdict
            p["resolved_date"] = today
            p["resolution_note"] = r.get("evidence", "")
            resolved_now.append((p, verdict, p["resolution_note"]))
            vault["_predictions_dirty"] = True
    # expire long-overdue open predictions with no signal
    expired_now = []
    for p in open_preds:
        due = parse_date(p.get("due") or "")
        if p.get("status") == "open" and due and (now - due).days > _PREDICT_EXPIRE_DAYS:
            p["status"] = "expired"
            p["resolved_date"] = today
            p["resolution_note"] = f"No evidence either way {_PREDICT_EXPIRE_DAYS}+ days past due."
            expired_now.append(p)
            vault["_predictions_dirty"] = True

    # ---- 3. report ----------------------------------------------------------
    all_preds = preds + new_preds
    counts = Counter(p.get("status") for p in all_preds)
    still_open = [p for p in all_preds if p.get("status") == "open"]
    overdue = [p for p in still_open if (d := parse_date(p.get("due") or "")) and d < now]
    due_soon = [p for p in still_open if (d := parse_date(p.get("due") or "")) and now <= d <= now + timedelta(days=30)]
    judged = counts["resolved-true"] + counts["resolved-false"]

    icon = {"resolved-true": "✅", "resolved-false": "❌", "unverifiable": "❔", "expired": "⌛"}

    def _fmt(p: dict, extra: str = "") -> str:
        src = p.get("source_note", "")
        link = f" ([[{src}]])" if src else ""
        due = f", due {p['due']}" if p.get("due") else ""
        corr_s = f" · corroborated ×{p['corroborations']}" if p.get("corroborations") else ""
        return f"- {p['prediction']} — _{p.get('who', '?')}_{due}{corr_s}{link}{extra}"

    lines = [
        f"**Track record:** {counts['resolved-true']} ✅ · {counts['resolved-false']} ❌"
        + (f" ({counts['resolved-true'] / judged:.0%} right)" if judged else "")
        + f" · {counts['unverifiable']} unverifiable · {counts['expired']} expired · "
        f"**{len(still_open)} open** ({len(overdue)} overdue)"
    ]
    if resolved_now or expired_now:
        lines.append("\n**Resolved this week:**")
        for p, verdict, ev in resolved_now:
            lines.append(f"- {icon.get(verdict, '•')} {p['prediction']} — _{p.get('who', '?')}_\n  ↳ {ev}")
        for p in expired_now:
            lines.append(f"- ⌛ {p['prediction']} — _{p.get('who', '?')}_ (expired, no signal)")
    if new_preds:
        lines.append(f"\n**{len(new_preds)} new this week:**")
        lines.extend(_fmt(p) for p in new_preds)
    else:
        lines.append("\n_No new predictions in notes since the last extraction._")
    if corr:
        lines.append("\n**Corroborated this week:** " + ", ".join(
            f"{by_id[i]['id']} (+{n})" for i, n in corr.items() if i in by_id))
    if overdue:
        lines.append("\n**Overdue, unresolved** (judge manually or wait for evidence):")
        lines.extend(_fmt(p) for p in sorted(overdue, key=lambda p: p["due"])[:8])
    if due_soon:
        lines.append("\n**Due in the next 30 days:**")
        lines.extend(_fmt(p) for p in sorted(due_soon, key=lambda p: p["due"])[:8])

    return "\n".join(lines) + "\n", new_preds


# ---------------------------------------------------------------------------
# One Thing synthesis + Report assembly
# ---------------------------------------------------------------------------

def synthesize_one_thing(api_key: str, sections: dict) -> str:
    """Use xAI to pick the single most important insight from all passes."""
    print("\n  Synthesizing The One Thing...")
    # Build a condensed version of all section outputs. The synthesized passes
    # (action, zeitgeist, bridge) carry the most judgement, so give them more room;
    # the stat-driven passes (blindspot, trend, thesis) are context, not the headline.
    _BUDGET = {"action": 2500, "zeitgeist": 2000, "bridge": 1500, "blindspot": 1500, "thesis": 1200}
    combined = ""
    for name, content in sections.items():
        limit = _BUDGET.get(name, 600)
        snippet = content[:limit].replace("\n", " ").strip()
        combined += f"\n[{name}]: {snippet}\n"

    prompt = (
        "Below are outputs from 7 analysis passes over a personal research vault. "
        "Pick the single most important, actionable insight across all passes and "
        "write 2-3 sentences a busy researcher should read first thing Sunday morning.\n\n"
        "Rules:\n"
        "- Lead with a concrete action the reader can take this week, and say why now.\n"
        "- Prefer insights from the [action], [zeitgeist], [bridge], and [blindspot] passes; the "
        "[trend] and [thesis] passes are supporting evidence, not the headline.\n"
        "- Do NOT restate raw counts (e.g. 'X mentioned 103 times'). Name topics, not stats.\n"
        "- Do NOT comment on the pipeline's own data quality or tokenizer artifacts.\n"
        "- Be specific: name the topic, the sources, and the deliverable.\n\n"
        f"{combined}"
    )

    result = claude_chat(
        "You are a research advisor distilling complex analysis into one key takeaway.",
        prompt,
    )
    if result is None:
        result = xai_chat(
            api_key,
            "You are a research advisor distilling complex analysis into one key takeaway.",
            prompt,
            effort="high",
        )
    else:
        print("  [claude] Used for One Thing synthesis")
    return result


# ---------------------------------------------------------------------------
# Pass 8: Cost Tracking
# ---------------------------------------------------------------------------

COST_LEDGER_PATH = VAULT_PATH / "Research" / "Reports" / "weekly-costs.md"
USD_TO_CAD = 1.37  # approximate; updated manually if needed


# ---------------------------------------------------------------------------
# Pass 8: Account Discovery
# ---------------------------------------------------------------------------
#
# Handles are ranked by WHERE they appear, not how often. A handle in the
# daily "Prominent Voices" table is just the scraper's own leaderboard —
# those posts already reach the vault every day at 500+ likes, so "discovering"
# them is circular. A handle cited inside a Library note or podcast is someone
# the reader (or a trusted source) chose to reference. That's a real signal.
#
# Recommendations are remembered in Research/discover.json so a handle isn't
# proposed twice, and a rejected one is never proposed again.

_DISCOVER_MAX = 3
_DISCOVER_MIN_SCORE = 4

# Groups that exist in pipeline.md. Lab groups get a dedicated X scan; the
# rest only earn a relevance boost + Prominent Voices coverage.
_PIPELINE_LAB_GROUPS = {"Anthropic", "OpenAI", "Google", "SpaceXAI", "Mistral", "Meta", "Moonshot"}
_PIPELINE_OTHER_GROUPS = {"Thought Leaders", "Researcher", "Tool Builder"}

_HANDLE_STOPLIST = {
    "x", "com", "ai", "the", "http", "https", "www", "bot", "grok", "claude",
    "chatgpt", "openai_", "here", "you", "me", "it", "gmail", "example",
}


def _load_discover_log() -> dict:
    """{handle: {status: suggested|added|rejected, first_suggested, times}}"""
    data = load_json_safe(DISCOVER_FILE)
    if isinstance(data, dict):
        return data.get("handles", data) if "handles" in data else data
    return {}


def _save_discover_log(log: dict) -> None:
    DISCOVER_FILE.parent.mkdir(parents=True, exist_ok=True)
    DISCOVER_FILE.write_text(json.dumps({"handles": log}, indent=2, ensure_ascii=False), encoding="utf-8")


def _daily_section_of(body: str, idx: int) -> str:
    """Which '## Section' of a daily note position `idx` falls in."""
    head = body.rfind("\n## ", 0, idx)
    if head < 0:
        return "other"
    line = body[head + 4: body.find("\n", head + 4)]
    return re.sub(r"[^A-Za-z ]", "", line).strip() or "other"


def _load_must_follow_handles() -> set:
    """Read pipeline.md and extract current must-follow handles."""
    handles = set()
    if not PIPELINE_MD.exists():
        return handles
    try:
        text = PIPELINE_MD.read_text(encoding="utf-8")
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("- @"):
                handle = line[3:].split(" ")[0].split("—")[0].split("–")[0].split("-")[0].strip()
                if handle:
                    handles.add(handle.lower())
    except Exception:
        pass
    return handles


def _extract_handles_from_text(text: str) -> list:
    """Extract @handles from note text."""
    return re.findall(r'@(\w{2,30})', text)


def pass_discover(vault: dict, api_key: str) -> str:
    """Discover X accounts worth following, weighted by where they're cited."""
    print("\n[Pass 8/9] Account Discovery...")
    now = datetime.now()
    followed = _load_must_follow_handles()
    log = _load_discover_log()
    print(f"  Currently following {len(followed)}; {len(log)} handles previously seen")

    # score weights by provenance
    W_LIBRARY, W_PODCAST, W_DAILY_BODY, W_PROMINENT = 4, 4, 2, 1

    score: Counter = Counter()
    notes_for: dict[str, set] = defaultdict(set)
    quotes: dict[str, list] = defaultdict(list)
    provenance: dict[str, Counter] = defaultdict(Counter)

    for note in vault["recent"]:
        text, body = note["text"], note["body"]
        daily = is_daily(note)
        # authors of Library notes count as strong citations
        author = note["frontmatter"].get("author", "")
        for m in re.finditer(r"@(\w{2,30})", text):
            h = m.group(1).lower()
            if h in followed or h in _HANDLE_STOPLIST or h.isdigit():
                continue
            if log.get(h, {}).get("status") in ("added", "rejected"):
                continue
            if daily:
                sec = _daily_section_of(body, m.start())
                if "Prominent Voices" in sec or "Lab Pulse" in sec:
                    w, tag = W_PROMINENT, "prominent-voices"
                else:
                    w, tag = W_DAILY_BODY, "daily-body"
            elif "Podcasts" in note["path"].parts:
                w, tag = W_PODCAST, "podcast"
            else:
                w, tag = W_LIBRARY, "library"
            score[h] += w
            provenance[h][tag] += 1
            notes_for[h].add(note["name"])
            if len(quotes[h]) < 4:
                s, e = max(0, m.start() - 160), min(len(text), m.start() + 260)
                snip = " ".join(text[s:e].split())
                snip = re.sub(r"https?://\S+", "", snip)
                quotes[h].append(f"({note['name']}, {note['date']:%m-%d}) …{snip}…")
            if author and h in author.lower():
                score[h] += 3
                provenance[h]["note-author"] += 1

    candidates = [
        h for h, s in score.most_common(40)
        if s >= _DISCOVER_MIN_SCORE and len(notes_for[h]) >= 2
        and provenance[h].get("prominent-voices", 0) < sum(provenance[h].values())  # not *only* the scraper table
    ]
    if not candidates:
        return "_No handles cleared the bar this week (need 2+ notes and a citation outside the Prominent Voices table)._\n"

    blocks = []
    for h in candidates[:12]:
        prov = ", ".join(f"{k}×{v}" for k, v in provenance[h].most_common())
        seen_before = log.get(h, {})
        prior = (f" [previously suggested {seen_before.get('first_suggested')}, "
                 f"{seen_before.get('times', 1)}x]") if seen_before else ""
        blocks.append(
            f"@{h} — score {score[h]}, {len(notes_for[h])} notes, provenance: {prov}{prior}\n"
            + "\n".join(f"    {q}" for q in quotes[h])
        )

    prompt = (
        "You are recommending X/Twitter accounts for an AI practitioner to follow. Their interests: "
        "AI agents and harnesses, SDLC transformation, frontier models, evals, MCP, crypto/macro, space economy.\n\n"
        "Below are handles that appeared in their research vault recently and are NOT already followed. "
        "Provenance matters more than volume:\n"
        "- `library` / `podcast` / `note-author` = cited inside curated notes. Strong signal: someone chose to reference them.\n"
        "- `prominent-voices` = they appeared in the daily scraper's high-engagement table. Weak signal: "
        "the reader already sees these posts daily, so following adds little.\n\n"
        f"Return at most {_DISCOVER_MAX} recommendations — fewer, or none, if nothing is genuinely worth it. "
        "Returning zero is a valid and useful answer. For each, use exactly:\n\n"
        "### @handle — Display Name\n"
        "- **Who:** one line. Say plainly if you cannot identify them with confidence.\n"
        "- **Why:** what they add that the current follow list doesn't, citing the quotes below.\n"
        "- **Group:** one of Thought Leaders / Researcher / Tool Builder, or a lab name "
        "(Anthropic, OpenAI, Google, SpaceXAI, Mistral, Meta, Moonshot) if they post as that org.\n"
        "- **org:** yes/no — is this an official company/product account rather than a person?\n\n"
        "Then a line `**Skip:** @a (reason), @b (reason)` for candidates you rejected — keep reasons to a few words.\n\n"
        "Reject: bots, brand accounts with no original content, news aggregators, engagement-bait, and anyone "
        "whose only provenance is `prominent-voices`. Do not invent identities — 'unidentified' is fine.\n\n"
        "=== CANDIDATES ===\n" + "\n\n".join(blocks)
    )

    system = "You are a research assistant recommending high-signal X accounts. You never invent identities."
    result = claude_chat(system, prompt)
    if result is None:
        result = xai_chat(api_key, system, prompt, effort="medium")
    else:
        print("  [claude] Used for account discovery")
    result = (result or "_Could not evaluate candidates._").strip()

    # Paste-ready lines built from the MODEL'S picks (the old version pasted the
    # raw heuristic top-5, which is how a rejected handle ended up in the block).
    picked = []
    heads = list(re.finditer(r"^###\s*@(\w+)\s*(?:—|-)\s*(.+)$", result, re.MULTILINE))
    for i, m in enumerate(heads):
        h, name = m.group(1), m.group(2).strip()
        # read to the next heading, not a fixed window: a long "Why" would
        # otherwise push the Group line out of range and silently default it
        end = heads[i + 1].start() if i + 1 < len(heads) else len(result)
        tail = result[m.end(): end]
        gm = re.search(r"\*\*Group:\*\*\s*([^\n]+)", tail)
        om = re.search(r"\*\*org:\*\*\s*(yes|no)", tail, re.IGNORECASE)
        group = (gm.group(1).strip().rstrip(".") if gm else "Thought Leaders")
        picked.append((h, name, group, bool(om and om.group(1).lower() == "yes")))

    out = result + "\n"
    if picked:
        out += "\n**To add to `pipeline.md`** (format per its own spec — no `(solo)` flag):\n\n"
        by_group: dict[str, list] = defaultdict(list)
        for h, name, group, is_org in picked:
            by_group[group].append(f"- @{h} — {name}{' (org)' if is_org else ''}")
        for group, lines_ in by_group.items():
            note = ""
            if group in _PIPELINE_OTHER_GROUPS:
                note = "  <!-- not scanned: earns a +20 relevance boost and reaches notes via Prominent Voices -->"
            elif group in _PIPELINE_LAB_GROUPS:
                note = "  <!-- lab group: gets a dedicated X scan with no engagement floor -->"
            out += f"```markdown\n## {group}{note}\n" + "\n".join(lines_) + "\n```\n"

    # remember, so next week doesn't repeat these
    today = now.strftime("%Y-%m-%d")
    for h, _, _, _ in picked:
        entry = log.setdefault(h, {"status": "suggested", "first_suggested": today, "times": 0})
        entry["times"] = entry.get("times", 0) + 1
        entry["last_suggested"] = today
    skip_line = re.search(r"\*\*Skip:\*\*(.+)", result)
    if skip_line:
        picked_handles = {h.lower() for h, _, _, _ in picked}
        # Only the handle that *opens* each comma-separated item is the skipped
        # one; handles inside a reason ("overlaps @nrehiew_ on architecture")
        # are references, not rejections.
        for chunk in re.split(r",\s*(?=@)", skip_line.group(1)):
            m = re.match(r"\s*@(\w{2,30})", chunk)
            if not m:
                continue
            h = m.group(1).lower()
            if h in picked_handles:
                continue
            entry = log.setdefault(h, {"first_suggested": today, "times": 0})
            entry["status"] = "rejected"
            entry["last_suggested"] = today
    _save_discover_log(log)

    out += ("\n_Edit `Research/discover.json` to mark a handle `added` or `rejected`; "
            "either way it won't be suggested again._\n")
    return out


def _ledger_rows() -> list[dict]:
    """Parse historical rows out of weekly-costs.md: [{date, usd, cad, breakdown}]."""
    rows = []
    if not COST_LEDGER_PATH.exists():
        return rows
    for line in COST_LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*\$?([\d.]+)\s*\|\s*\$?([\d.]+)\s*\|(.*)\|", line)
        if m:
            rows.append({"date": m.group(1), "usd": float(m.group(2)),
                         "cad": float(m.group(3)), "breakdown": m.group(4).strip()})
    return rows


def track_weekly_costs(vault: dict, today: str) -> str:
    """Report what the knowledge system actually cost this week.

    Every figure is either measured (parsed from a tool's own recorded spend)
    or explicitly marked as an estimate. The previous version hardcoded the
    brain's cost at $0.05 and priced connections at a flat $0.01 each, which
    produced $10-14 spikes for weeks that in fact ran free on the Claude CLI.
    """
    now = datetime.strptime(today, "%Y-%m-%d")
    week_start = now - timedelta(days=7)
    cost_re = re.compile(r"\*\*\$(\d+\.\d+)\*\*")
    estimates: list[str] = []

    # 1. Daily research — exact: each daily note records its own API spend.
    research_cost, research_days = 0.0, 0
    for note in vault.get("dailies", []):
        if not note["date"] or note["date"] <= week_start:
            continue
        m = cost_re.search(note["text"][:1500])  # cost header sits just under frontmatter
        if m:
            research_cost += float(m.group(1))
            research_days += 1

    # 2. This brain run — measured via RUN_COST (claude-cli calls are $0 on Max).
    brain_cost = RUN_COST.total
    brain_detail = RUN_COST.summary()

    # 3. Connection detector — sum its recorded per-call cost when present.
    conn_cost, conn_calls, conn_engines = 0.0, 0, Counter()
    conn_priced = True
    raw = load_json_safe(CONNECTIONS_FILE)
    raw = raw if isinstance(raw, dict) else {"connections": raw}
    runs = raw.get("run_costs") or []
    week_iso = week_start.strftime("%Y-%m-%d")
    if runs:
        for r in runs:
            if str(r.get("at", ""))[:10] > week_iso:
                conn_calls += 1
                conn_engines[r.get("engine", "?")] += 1
                if r.get("cost_usd") is None:
                    conn_priced = False
                else:
                    conn_cost += r["cost_usd"]
    else:
        # Legacy data: no per-call record. Count kept connections and flag it.
        recent = [c for c in raw.get("connections", []) if str(c.get("detected_at", ""))[:10] > week_iso]
        for c in recent:
            conn_calls += 1
            conn_engines[c.get("engine", "unrecorded")] += 1
            if c.get("cost_usd") is not None:
                conn_cost += c["cost_usd"]
            else:
                conn_priced = False
        if recent and not conn_priced:
            estimates.append(
                f"Connections: {len(recent)} edges have no recorded cost (detector ran before cost "
                f"logging); shown as $0.00 rather than guessed. Re-run the detector to start tracking."
            )

    # 4. Synthesis reports — count files *created* this week, not merely touched.
    report_cost, report_files = 0.0, []
    if REPORTS_DIR.exists():
        for f in REPORTS_DIR.glob("*.md"):
            if f.name.startswith(("weekly-brain", "weekly-costs")):
                continue
            try:
                head = f.read_text(encoding="utf-8", errors="replace")[:600]
            except OSError:
                continue
            cm = re.search(r"^created:\s*(\d{4}-\d{2}-\d{2})", head, re.MULTILINE)
            created = parse_date(cm.group(1)) if cm else None
            if created and created > week_start:
                report_files.append(f.stem)
                report_cost += 0.15
    if report_files:
        estimates.append(f"Reports: {len(report_files)} × $0.15 assumed (obsidian-vault-report records no spend)")

    total_usd = research_cost + brain_cost + conn_cost + report_cost
    total_cad = total_usd * USD_TO_CAD

    # ---- trend against the ledger ----
    history = [r for r in _ledger_rows() if r["date"] < today]
    prev = history[-1] if history else None
    last4 = history[-4:]
    avg4 = sum(r["usd"] for r in last4) / len(last4) if last4 else None
    month = [r for r in history if r["date"][:7] == today[:7]]
    mtd = sum(r["usd"] for r in month) + total_usd

    trend = ""
    if prev:
        delta = total_usd - prev["usd"]
        pct = (delta / prev["usd"] * 100) if prev["usd"] else 0
        arrow = "▲" if delta > 0.005 else ("▼" if delta < -0.005 else "▬")
        trend = f" · {arrow} ${abs(delta):.2f} ({pct:+.0f}%) vs {prev['date']}"

    breakdown = [f"Research ${research_cost:.2f} ({research_days}d)"]
    breakdown.append(f"Brain ${brain_cost:.2f} ({brain_detail})")
    if conn_calls:
        eng = ", ".join(f"{n}× {e}" for e, n in conn_engines.most_common(2))
        breakdown.append(f"Connections ${conn_cost:.2f} ({conn_calls} calls: {eng})")
    if report_cost:
        breakdown.append(f"Reports ~${report_cost:.2f}")

    lines = [f"**${total_usd:.2f} USD / ${total_cad:.2f} CAD**{trend}", "", " · ".join(breakdown)]
    tail = []
    if avg4:
        tail.append(f"4-week average ${avg4:.2f}")
    tail.append(f"{today[:7]} to date ${mtd:.2f}")
    if research_days:
        tail.append(f"${research_cost / research_days:.3f}/day research")
    lines.append("")
    lines.append("_" + " · ".join(tail) + "_")
    if estimates:
        lines.append("")
        lines.append("**Estimated, not measured:** " + "; ".join(estimates))

    print(f"  Weekly cost: ${total_usd:.2f} USD (${total_cad:.2f} CAD) — {brain_detail}")
    track_weekly_costs._last = {
        "usd": total_usd, "cad": total_cad,
        "breakdown": " · ".join(breakdown),
    }
    return "\n".join(lines)


track_weekly_costs._last = None


def append_cost_ledger(today: str, cost_section: str):
    """Upsert this week's row in weekly-costs.md (re-running on the same day
    replaces the row rather than appending a duplicate)."""
    data = track_weekly_costs._last
    if not data:
        return

    header = (
        "---\n"
        "type: cost-tracker\n"
        "tags: [cost-tracker, weekly]\n"
        "status: published\n"
        "---\n\n"
        "# Weekly Cost Ledger\n\n"
        "> Automated cost tracking for the Obsidian knowledge system.\n"
        "> Updated every Sunday by the weekly brain digest.\n\n"
        "| Week | USD | CAD | Breakdown |\n"
        "|------|-----|-----|-----------|\n"
    )
    if not COST_LEDGER_PATH.exists():
        COST_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        COST_LEDGER_PATH.write_text(header, encoding="utf-8")
        print(f"  Created cost ledger: {COST_LEDGER_PATH}")

    row = f"| {today} | ${data['usd']:.2f} | ${data['cad']:.2f} | {data['breakdown']} |"
    text = COST_LEDGER_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    out, replaced = [], False
    for line in lines:
        if line.startswith(f"| {today} |"):
            if not replaced:
                out.append(row)
                replaced = True
            continue  # drop any duplicates of the same week
        out.append(line)
    if not replaced:
        out.append(row)
    COST_LEDGER_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"  {'Updated' if replaced else 'Appended'} ledger row: ${data['usd']:.2f} USD")


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

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

## Discover 🔭

{sections.get('discover', '_Skipped._')}

## Weekly Cost 💰

{sections.get('cost', '_Skipped._')}

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
    "discover": pass_discover,
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
        if pass_name == "cost":
            continue  # handled separately after other passes
        func = PASS_FUNCS.get(pass_name)
        if not func:
            continue
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

    # Pass 8: Cost Tracking
    run_all = not args.single_pass
    if "cost" in passes_to_run or run_all:
        print("\n[Pass 8/8] Cost Tracking...")
        try:
            cost_summary = track_weekly_costs(vault, today)
            sections["cost"] = cost_summary
        except Exception as e:
            print(f"  ERROR in cost tracking: {e}", file=sys.stderr)

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

        # Update predictions.json if anything changed (new, resolved, corroborated)
        if new_predictions or vault.get("_predictions_dirty"):
            all_predictions = vault["predictions"] + new_predictions
            PREDICTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PREDICTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(all_predictions, f, indent=2, ensure_ascii=False)
            print(f"  predictions.json: +{len(new_predictions)} new, {len(all_predictions)} total")

        # Append cost row to weekly-costs.md ledger
        if "cost" in sections:
            try:
                append_cost_ledger(today, sections["cost"])
            except Exception as e:
                print(f"  ERROR appending cost ledger: {e}", file=sys.stderr)

    print(f"\n=== Done. {len(sections)} passes completed. ===")


if __name__ == "__main__":
    main()
