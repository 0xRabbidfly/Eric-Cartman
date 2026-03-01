"""Note generator — transforms podcast transcripts into structured Obsidian notes.

Generates YAML frontmatter, TL;DR, key ideas, actionable takeaways,
memorable quotes, and structured backlinks from a transcript.

Two modes:
1. AI-assisted (uses OpenAI/compatible API for summarization)
2. Template-only (generates structure without AI summaries)
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Try OpenAI for AI-assisted summaries
# ---------------------------------------------------------------------------

_HAS_OPENAI = False
try:
    import urllib.request
    _HAS_OPENAI = True  # We'll use raw HTTP, no pip dependency
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Note template
# ---------------------------------------------------------------------------

NOTE_TEMPLATE = """\
---
tags: [podcast, {show_slug}{extra_tags}]
type: podcast-note
show: "{show_name}"
episode: "{episode_title}"
published: {published}
duration: "{duration}"
source: podcast-to-obsidian
created: {created}
---

# {episode_title}

**Show:** [[Podcasts/{show_name}]] · 📅 {published} · ⏱ {duration}

---

{tldr}

---

## 💡 Key Ideas

{key_ideas}

---

## 📝 Summary

{detailed_summary}

---

## ✅ Actionable Takeaways

{actionables}

---

## 💬 Key Quotes

{quotes}

---

## 🔗 People & Topics

{backlinks}
"""

SHOW_INDEX_TEMPLATE = """\
---
tags: [podcast, {show_slug}, index]
type: podcast-index
show: "{show_name}"
source: podcast-to-obsidian
---

# {show_name}

Podcast episodes from **{show_name}**.

## Episodes

{episode_list}
"""


# ---------------------------------------------------------------------------
# Note generation
# ---------------------------------------------------------------------------

def generate_note(
    episode: Dict[str, str],
    transcript_text: str,
    ai_summary: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a structured Obsidian note from episode metadata + transcript."""
    show_name = episode.get("show_name", "Unknown Show")
    show_slug = _slugify(show_name)
    episode_title = episode.get("title", "Untitled Episode")
    published = episode.get("published", "")
    duration = episode.get("duration", "")

    extra_tags = ""
    if ai_summary:
        tldr = _format_tldr_callout(ai_summary.get("tldr", ""))
        key_ideas = _format_key_ideas(ai_summary.get("key_ideas", []))
        detailed_summary = ai_summary.get("detailed_summary", "_No detailed summary available._")
        actionables = _format_actionables(ai_summary.get("actionables", []))
        quotes = _format_quotes(ai_summary.get("quotes", []))
        backlinks = _format_backlinks(ai_summary.get("backlinks", {}))
        # Build extra tags from AI-extracted topics
        topics = ai_summary.get("backlinks", {}).get("topics", [])
        if topics:
            extra_tags = ", " + ", ".join(_slugify(t) for t in topics[:6])
    else:
        # Template-only mode
        tldr = _format_tldr_callout(_extract_basic_tldr(episode, transcript_text))
        key_ideas = "- _Add your OpenAI API key to `.env` as `OPENAI_API_KEY` to auto-generate key ideas._"
        detailed_summary = "_Add your OpenAI API key to `.env` as `OPENAI_API_KEY` to auto-generate a summary._"
        actionables = "- [ ] Review transcript and extract action items"
        quotes = "> _Add your OpenAI API key to `.env` as `OPENAI_API_KEY` to auto-extract key quotes._"
        backlinks = f"[[Podcasts/{show_name}]]"

    return NOTE_TEMPLATE.format(
        show_slug=show_slug,
        extra_tags=extra_tags,
        show_name=show_name,
        episode_title=episode_title,
        published=published,
        duration=duration,
        created=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        tldr=tldr,
        key_ideas=key_ideas,
        detailed_summary=detailed_summary,
        actionables=actionables,
        quotes=quotes,
        backlinks=backlinks,
    )


def generate_show_index(show_name: str, episodes: List[Dict[str, str]]) -> str:
    """Generate or update a show index note listing all processed episodes."""
    show_slug = _slugify(show_name)

    # Sort episodes by published date, newest first
    sorted_eps = sorted(episodes, key=lambda e: e.get("published", ""), reverse=True)

    lines = []
    for ep in sorted_eps:
        title = ep.get("title", "Untitled")
        published = ep.get("published", "")
        note_path = ep.get("note_path", "")
        if note_path:
            lines.append(f"- [[{note_path}|{published} — {title}]]")
        else:
            lines.append(f"- {published} — {title}")

    return SHOW_INDEX_TEMPLATE.format(
        show_slug=show_slug,
        show_name=show_name,
        episode_list="\n".join(lines) if lines else "_No episodes processed yet._",
    )


# ---------------------------------------------------------------------------
# AI Summary (OpenAI-compatible API)
# ---------------------------------------------------------------------------

SUMMARIZE_SYSTEM_PROMPT = """\
You are an expert podcast summarizer. Given a transcript, produce a structured JSON summary.

Output JSON with these exact keys:
{
  "tldr": "2-3 sentence TL;DR",
  "key_ideas": [
    {"idea": "Bold idea title", "explanation": "1-2 sentence explanation"}
  ],
  "detailed_summary": "3-5 paragraph detailed summary",
  "actionables": ["Action item 1", "Action item 2"],
  "quotes": [
    {"text": "Exact quote from transcript", "speaker": "Speaker name if identifiable"}
  ],
  "backlinks": {
    "people": ["Person Name 1", "Person Name 2"],
    "topics": ["Topic 1", "Topic 2"],
    "companies": ["Company 1"]
  }
}

Rules:
- Key ideas: 3-7 items, each with a bold-worthy title and concise explanation
- Actionables: 2-5 concrete, actionable takeaways (not vague)
- Quotes: 3-5 memorable/impactful quotes with speaker attribution if possible
- Backlinks: 5-15 total across people/topics/companies
- Be specific, not generic. Reference actual content from the transcript.
- If you can't identify speakers, use "Host" or "Guest"
"""


def generate_ai_summary(
    transcript_text: str,
    episode_title: str = "",
    show_name: str = "",
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    base_url: str = "https://api.openai.com/v1",
) -> Optional[Dict[str, Any]]:
    """Call OpenAI-compatible API to generate a structured summary.

    Args:
        transcript_text: Full transcript text.
        episode_title: Episode title for context.
        show_name: Show name for context.
        api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
        model: Model to use.
        base_url: API base URL (for local/alternative APIs).

    Returns:
        Parsed summary dict, or None on failure.
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("  [warn] No OPENAI_API_KEY — using template-only mode (no AI summaries)")
        return None

    # Truncate transcript if too long (keep ~12k words for context window)
    words = transcript_text.split()
    if len(words) > 12000:
        truncated = " ".join(words[:12000])
        user_msg = (
            f"Podcast: {show_name} — {episode_title}\n\n"
            f"Transcript (truncated to 12k words of {len(words)} total):\n\n"
            f"{truncated}"
        )
    else:
        user_msg = (
            f"Podcast: {show_name} — {episode_title}\n\n"
            f"Transcript:\n\n{transcript_text}"
        )

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")

    url = f"{base_url.rstrip('/')}/chat/completions"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        print(f"  [ai] Generating summary with {model}...")
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        content = result["choices"][0]["message"]["content"]
        summary = json.loads(content)
        print("  [ai] Summary generated successfully")
        return summary

    except Exception as e:
        print(f"  [warn] AI summary failed: {e}")
        print("  [warn] Falling back to template-only mode")
        return None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_tldr_callout(text: str) -> str:
    """Wrap TL;DR text in an Obsidian callout block."""
    if not text:
        text = "_No summary available._"
    lines = text.strip().split("\n")
    body = "\n".join(f"> {line}" if line.strip() else ">" for line in lines)
    return f"> [!abstract]+ TL;DR\n{body}"


def _format_key_ideas(ideas: List[Dict[str, str]]) -> str:
    """Format key ideas as a numbered list with bold titles."""
    if not ideas:
        return "- _No key ideas extracted._"
    lines = []
    for i, idea in enumerate(ideas, 1):
        if isinstance(idea, dict):
            title = idea.get("idea", "")
            explanation = idea.get("explanation", "")
            lines.append(f"{i}. **{title}** — {explanation}")
        elif isinstance(idea, str):
            lines.append(f"{i}. {idea}")
    return "\n".join(lines)


def _format_actionables(items: List[str]) -> str:
    """Format actionable takeaways as checkboxes."""
    if not items:
        return "- [ ] _No actionables extracted._"
    return "\n".join(f"- [ ] {item}" for item in items)


def _format_quotes(quotes: List[Dict[str, str]]) -> str:
    """Format memorable quotes as Obsidian callout blocks."""
    if not quotes:
        return "> [!quote]\n> _No quotes extracted._"
    blocks = []
    for q in quotes:
        if isinstance(q, dict):
            text = q.get("text", "")
            speaker = q.get("speaker", "")
            header = f'> [!quote] "{text}"'
            if speaker:
                blocks.append(f"{header}\n> — **{speaker}**")
            else:
                blocks.append(header)
        elif isinstance(q, str):
            blocks.append(f'> [!quote] "{q}"')
    return "\n\n".join(blocks)


def _format_backlinks(links: Dict[str, List[str]]) -> str:
    """Format backlinks grouped by category with Obsidian wiki links."""
    parts = []
    people = links.get("people", [])
    topics = links.get("topics", [])
    companies = links.get("companies", [])
    if people:
        wiki = " · ".join(f"[[People/{p}]]" for p in people)
        parts.append(f"**People:** {wiki}")
    if topics:
        wiki = " · ".join(f"[[Topics/{t}]]" for t in topics)
        parts.append(f"**Topics:** {wiki}")
    if companies:
        wiki = " · ".join(f"[[Companies/{c}]]" for c in companies)
        parts.append(f"**Companies:** {wiki}")
    if not parts:
        return "_No backlinks generated._"
    return "\n\n".join(parts)


def _extract_basic_tldr(episode: Dict[str, str], transcript: str) -> str:
    """Generate a basic TL;DR from episode description or transcript start."""
    desc = episode.get("description", "")
    if desc and len(desc) > 50:
        # Use first 2-3 sentences of description
        sentences = re.split(r'(?<=[.!?])\s+', desc)
        return " ".join(sentences[:3])
    # Fall back to first 200 words of transcript
    words = transcript.split()[:200]
    return " ".join(words) + "..."


def _extract_basic_summary(transcript: str) -> str:
    """Extract basic summary from transcript (first ~500 words)."""
    words = transcript.split()
    if len(words) <= 500:
        return transcript
    return " ".join(words[:500]) + "\n\n_[Transcript continues — run with AI summarization for complete summary]_"


def _slugify(text: str) -> str:
    """Convert text to a URL/tag-friendly slug."""
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = slug.strip('-')
    return slug
