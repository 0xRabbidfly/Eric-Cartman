"""Phase 5 - Reading Recommendations.

Surfaces the top-N *newest* notes in the Research Library that best match the
user's demonstrated research interests, so the weekly lint doubles as a fresh
reading list.

Design (locked with the user 2026-06-06):
  - "Interests" = tag frequency across the Research Library (the user's
    demonstrated research interests). No manual upkeep, adapts as tagging shifts.
  - "Article pool" = the newest Library notes (a fresh reading list), ranked by
    how well their tags overlap the interest profile, with a boost for notes
    still marked unread.

Read-only: this phase never mutates the vault. It returns proposals that the
caller writes into the report / a companion file.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

_SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(_SCRIPT_DIR))
from obsidian import Obsidian, _extract_frontmatter_tags

LIBRARY_FOLDER = "Research/Library"
MOC_FOLDER = "Research/Library/00 MOC"

# How many of the newest notes form the candidate pool before interest ranking.
DEFAULT_RECENT_WINDOW = 25
# How many recommendations to emit.
DEFAULT_TOP_N = 3
# How many top tags define the "interest profile" used to explain a match.
TOP_INTEREST_TAGS = 20
# Multiplier applied to a note's interest score when it is still unread.
UNREAD_BOOST = 1.3

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Recommendation:
    rel_path: str
    slug: str
    title: str
    date_saved: Optional[str]
    status: str
    tags: List[str] = field(default_factory=list)
    matched_interests: List[str] = field(default_factory=list)
    url: str = ""
    score: float = 0.0


@dataclass
class RecommendResult:
    recommendations: List[Recommendation] = field(default_factory=list)
    interest_profile: List[tuple] = field(default_factory=list)  # (tag, count) desc
    pool_size: int = 0
    library_note_count: int = 0


def _split_frontmatter(text: str) -> str:
    """Return the raw YAML frontmatter block (between the leading --- fences)."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 4)
    if end < 0:
        return ""
    return text[4:end]


def _fm_field(fm: str, name: str) -> str:
    """Best-effort single-line scalar lookup in a frontmatter block."""
    for line in fm.splitlines():
        m = re.match(rf"^\s*{re.escape(name)}\s*:\s*(.*)$", line)
        if m:
            return m.group(1).strip().strip("\"'")
    return ""


def _note_date(fm: str, rel_path: str, abs_path: Path) -> Optional[str]:
    """Resolve a note's 'saved' date from, in order: frontmatter date_saved /
    date_found / date, a YYYY-MM-DD in the filename, then file mtime."""
    for key in ("date_saved", "date_found", "date", "created"):
        v = _fm_field(fm, key)
        m = _DATE_RE.search(v)
        if m:
            return m.group(1)
    m = _DATE_RE.search(rel_path)
    if m:
        return m.group(1)
    try:
        return datetime.fromtimestamp(abs_path.stat().st_mtime).date().isoformat()
    except Exception:
        return None


def _note_title(text: str, slug: str) -> str:
    m = _HEADING_RE.search(text)
    if m:
        return m.group(1).strip()
    return slug.replace("-", " ").replace("_", " ").strip()


def _note_tags(fm: str) -> List[str]:
    # Frontmatter tags are the curated signal; dedupe preserving order.
    seen = set()
    out = []
    for t in _extract_frontmatter_tags(fm):
        tl = t.strip()
        if tl and tl not in seen:
            seen.add(tl)
            out.append(tl)
    return out


def recommend_reading(
    top_n: int = DEFAULT_TOP_N,
    recent_window: int = DEFAULT_RECENT_WINDOW,
    verbose: bool = False,
) -> RecommendResult:
    ob = Obsidian()
    result = RecommendResult()

    library_notes = ob.files(folder=LIBRARY_FOLDER, ext="md").lines()
    content_notes = [n for n in library_notes if not n.startswith(MOC_FOLDER + "/")]
    result.library_note_count = len(content_notes)

    if verbose:
        print(f"[recommend] Library content notes: {len(content_notes)}")

    # First pass: read each note once, capture metadata + build interest profile.
    from collections import Counter
    profile = Counter()
    notes = []  # list of dicts
    for rel in content_notes:
        try:
            text = ob.read(path=rel)
        except Exception:
            continue
        fm = _split_frontmatter(text)
        tags = _note_tags(fm)
        for t in tags:
            profile[t] += 1
        slug = rel.rsplit("/", 1)[-1][:-3] if rel.endswith(".md") else rel.rsplit("/", 1)[-1]
        notes.append({
            "rel": rel,
            "slug": slug,
            "title": _note_title(text, slug),
            "date": _note_date(fm, rel, Path(ob.vault_path) / rel),
            "status": (_fm_field(fm, "status") or "").lower(),
            "tags": tags,
            "url": _fm_field(fm, "url"),
        })

    result.interest_profile = profile.most_common(TOP_INTEREST_TAGS)
    top_interest = {t for t, _ in result.interest_profile}

    if verbose and result.interest_profile:
        top5 = ", ".join(f"{t}({c})" for t, c in result.interest_profile[:5])
        print(f"[recommend] Top interests: {top5}")

    # Candidate pool: the newest notes (those with a resolvable date), most
    # recent first. Notes without any date fall to the back.
    dated = [n for n in notes if n["date"]]
    dated.sort(key=lambda n: n["date"], reverse=True)
    pool = dated[:recent_window] if recent_window else dated
    result.pool_size = len(pool)

    if verbose:
        print(f"[recommend] Candidate pool (newest {len(pool)} dated notes)")

    # Score each pooled note by interest overlap, boosting unread notes.
    for n in pool:
        matched = [t for t in n["tags"] if t in top_interest]
        # Weight by how prominent each matched interest is in the Library.
        base = sum(profile[t] for t in matched)
        is_unread = n["status"] in ("", "unread", "to-read", "toread", "new")
        score = base * (UNREAD_BOOST if is_unread else 1.0)
        n["matched"] = sorted(matched, key=lambda t: profile[t], reverse=True)
        n["score"] = score
        n["is_unread"] = is_unread

    # Rank: interest score desc, then recency desc as tiebreak. A note with no
    # matched interests scores 0 and only appears if the pool is sparse.
    pool.sort(key=lambda n: (n["score"], n["date"] or ""), reverse=True)

    for n in pool[:top_n]:
        result.recommendations.append(Recommendation(
            rel_path=n["rel"],
            slug=n["slug"],
            title=n["title"],
            date_saved=n["date"],
            status=n["status"] or "unread",
            tags=n["tags"],
            matched_interests=n["matched"][:4],
            url=n["url"],
            score=round(n["score"], 2),
        ))

    return result


def format_recommendations(result: RecommendResult, run_date: str) -> str:
    """Standalone companion-file body (Research/Logs/vault-lint-DATE-reading.md)."""
    lines = [
        f"# Reading Recommendations - {run_date}",
        "",
        "Top picks from the **newest** notes in `Research/Library`, ranked by how "
        "well they match your demonstrated research interests (tag frequency across "
        "the Library). Unread notes are favored.",
        "",
    ]
    lines += _render_recommendations(result)
    if result.interest_profile:
        lines += ["", "---", "", "## Interest profile (top Library tags)", ""]
        lines.append(
            ", ".join(f"`{t}` ({c})" for t, c in result.interest_profile[:12])
        )
    lines += ["", f"*Generated: {run_date}*"]
    return "\n".join(lines)


def render_report_section(result: RecommendResult) -> List[str]:
    """Lines for the '## Reading Recommendations' section of the main report."""
    lines = [
        "",
        "## Reading Recommendations",
        "*Top newest Library notes matching your research interests.*",
        "",
    ]
    lines += _render_recommendations(result)
    return lines


def _render_recommendations(result: RecommendResult) -> List[str]:
    if not result.recommendations:
        return ["_No recommendations — no dated Library notes matched your interests._"]
    out = []
    for i, r in enumerate(result.recommendations, 1):
        meta = []
        if r.date_saved:
            meta.append(f"saved {r.date_saved}")
        meta.append(r.status)
        meta_str = " · ".join(meta)
        out.append(f"{i}. **[[{r.slug}|{r.title}]]** — {meta_str}")
        if r.matched_interests:
            out.append(f"   - Matches your interests: {', '.join(r.matched_interests)}")
        if r.url:
            out.append(f"   - Source: {r.url}")
    return out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reading recommendations from the vault Library")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--window", type=int, default=DEFAULT_RECENT_WINDOW)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    res = recommend_reading(top_n=args.top, recent_window=args.window, verbose=args.verbose)
    print(format_recommendations(res, date.today().isoformat()))
