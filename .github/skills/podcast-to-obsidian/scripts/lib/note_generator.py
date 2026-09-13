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

CLAUDE_CLI = r"C:\Users\nuno_\.local\bin\claude.exe"


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def _yaml_str(value: Any) -> str:
    """Return a YAML-safe single-quoted scalar (quotes included).

    Single-quoted YAML needs no backslash escaping: an embedded double quote is
    literal, and only ``'`` is escaped (by doubling). This is deliberate — notes
    are written through the Obsidian CLI, which interprets backslash escapes
    (``\\n``, ``\\t``, ``\\"``) in content values and would strip the escaping
    from a double-quoted scalar, recorrupting titles like
    ``Creator of Claude Code: "At Anthropic ..."``. Newlines/tabs are flattened.
    """
    s = str(value)
    for ws in ("\r\n", "\n", "\r", "\t"):
        s = s.replace(ws, " ")
    return "'" + s.replace("'", "''") + "'"


def _loads_llm_json(text: str) -> Dict[str, Any]:
    """Parse a JSON object out of an LLM response, repairing common glitches.

    Handles: surrounding prose / markdown code fences, and trailing commas
    before ``}`` or ``]`` — the usual cause of "Expecting property name
    enclosed in double quotes". Raises ``json.JSONDecodeError`` if it still
    can't parse after repair.
    """
    s = (text or "").strip()
    if s.startswith("```"):
        nl = s.find("\n")
        s = s[nl + 1:] if nl != -1 else s
    if s.endswith("```"):
        s = s[: s.rfind("```")]
    s = s.strip()
    # Narrow to the outermost {...} object if the model added prose around it.
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end > start:
        s = s[start:end + 1]
    # Drop trailing commas before a closing brace/bracket.
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    return json.loads(s)


# ---------------------------------------------------------------------------
# Note template
# ---------------------------------------------------------------------------

NOTE_TEMPLATE = """\
---
tags: [podcast, {show_slug}{extra_tags}]
type: podcast-note
show: {show_name_yaml}
episode: {episode_title_yaml}
published: {published}
duration: {duration_yaml}
source: podcast-to-obsidian
created: {created}
---

# {episode_title}

**Show:** [[{parent_folder}/{show_name}]] · 📅 {published} · ⏱ {duration}

---

{tldr}

---

## 💡 Key Ideas

{key_ideas}

---

## 🧠 Deep Dives

{deep_dives}

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
show: {show_name_yaml}
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
    parent_folder: str = "Podcasts",
) -> str:
    """Generate a structured Obsidian note from episode metadata + transcript.

    ``parent_folder`` is the vault folder the note will actually be written to
    ("Podcasts" for RSS episodes, the clips folder for ``--url`` mode).  The
    show backlink is built from it, so it must match the real write path or the
    link dead-ends.
    """
    show_name = episode.get("show_name", "Unknown Show")
    show_slug = _slugify(show_name)
    episode_title = episode.get("title", "Untitled Episode")
    published = episode.get("published", "")
    duration = episode.get("duration", "")

    extra_tags = ""
    if ai_summary:
        tldr = _format_tldr_callout(ai_summary.get("tldr", ""))
        key_ideas = _format_key_ideas(ai_summary.get("key_ideas", []))
        deep_dives = _format_deep_dives(ai_summary.get("deep_dives", []))
        # Fallback: if AI returned old "detailed_summary" key, convert it
        if not ai_summary.get("deep_dives") and ai_summary.get("detailed_summary"):
            deep_dives = ai_summary["detailed_summary"]
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
        deep_dives = "_Add your OpenAI API key to `.env` as `OPENAI_API_KEY` to auto-generate deep dives._"
        actionables = "- [ ] Review transcript and extract action items"
        quotes = "> _Add your OpenAI API key to `.env` as `OPENAI_API_KEY` to auto-extract key quotes._"
        backlinks = f"[[{parent_folder}/{show_name}]]"

    return NOTE_TEMPLATE.format(
        show_slug=show_slug,
        extra_tags=extra_tags,
        show_name=show_name,
        parent_folder=parent_folder,
        show_name_yaml=_yaml_str(show_name),
        episode_title=episode_title,
        episode_title_yaml=_yaml_str(episode_title),
        published=published,
        duration=duration,
        duration_yaml=_yaml_str(duration),
        created=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        tldr=tldr,
        key_ideas=key_ideas,
        deep_dives=deep_dives,
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
        show_name_yaml=_yaml_str(show_name),
        episode_list="\n".join(lines) if lines else "_No episodes processed yet._",
    )


# ---------------------------------------------------------------------------
# AI Summary (OpenAI-compatible API)
# ---------------------------------------------------------------------------

SUMMARIZE_SYSTEM_PROMPT = """\
You are an expert podcast summarizer. Given a transcript, produce a structured JSON summary.

Output JSON with these exact keys:
{{
  "tldr": "2-3 sentence TL;DR",
  "key_ideas": [
    {{"idea": "Bold idea title", "explanation": "1-2 sentence explanation"}}
  ],
  "deep_dives": [
    {{"title": "Concept Title", "body": "2-4 paragraph mini-essay analyzing this concept in depth — implications, connections, what wasn't said, why it matters beyond the podcast"}}
  ],
  "actionables": ["Action item 1", "Action item 2"],
  "quotes": [
    {{"text": "Exact quote from transcript", "speaker": "Speaker name if identifiable"}}
  ],
  "backlinks": {{
    "people": ["Person Name 1", "Person Name 2"],
    "topics": ["Topic 1", "Topic 2"],
    "companies": ["Company 1"]
  }}
}}

Rules:
- Key ideas: {n_key_ideas} items, each with a bold-worthy title and concise 1-2 sentence explanation
- Deep dives: {n_deep_dives} items. Pick the most important/surprising concepts and go DEEP.
  Each deep dive is a mini-essay (2-4 paragraphs) that goes beyond summarizing — analyze
  implications, draw connections between ideas, note what was left unsaid, explain why it
  matters to the listener. Do NOT repeat the key ideas — add new depth and perspective.
- Actionables: {n_actionables} concrete, actionable takeaways (not vague)
- Quotes: {n_quotes} memorable/impactful quotes with speaker attribution if possible
- Backlinks: 8-25 total across people/topics/companies
- Be specific, not generic. Reference actual content from the transcript.
- If you can't identify speakers, use "Host" or "Guest"

COVERAGE REQUIREMENTS (critical — this episode runs about {minutes} minutes):
- Cover the ENTIRE episode, start to finish. Distribute key ideas and quotes across the
  whole runtime, not just the opening. Summaries reliably under-cover the final third —
  do not make that mistake.
- Before you answer, identify every distinct segment or topic change in the material and
  make sure each one is represented by at least one key idea.
- The closing segments (Q&A / AMA, listener questions, final stories, closing predictions)
  are real content and must be covered, not dropped as filler.
- Ad reads, sponsor spots and event promos are NOT content — skip those.
- At least one deep dive must draw on material from the back half of the episode.
"""


# Per-chunk extraction prompt used in the map phase of long-transcript handling.
MAP_SEGMENT_PROMPT = """\
You are analyzing ONE SEGMENT of a longer podcast transcript. This is segment {i} of {n},
covering roughly the {position} of the episode.

Extract what this segment actually contains. Do not summarize the whole episode — you are
only seeing part of it, and another pass will combine your notes with the other segments.

Output JSON with these exact keys:
{{
  "segment_summary": "3-5 sentence summary of what happens in THIS segment",
  "topics_covered": ["Short label for each distinct topic or story in this segment"],
  "key_ideas": [
    {{"idea": "Bold idea title", "explanation": "1-2 sentence explanation"}}
  ],
  "quotes": [
    {{"text": "Exact quote from this segment", "speaker": "Speaker name if identifiable"}}
  ],
  "backlinks": {{
    "people": ["Person Name"],
    "topics": ["Topic"],
    "companies": ["Company"]
  }}
}}

Rules:
- key_ideas: 4-10 items drawn ONLY from this segment
- quotes: 3-6 verbatim quotes from this segment
- topics_covered: list every distinct topic, story or question handled here
- Skip ad reads, sponsor spots and event promotion — they are not content
- Be specific. Use real names, numbers and claims from the text.
- If you can't identify a speaker, use "Host" or "Guest"

Respond with ONLY valid JSON. No markdown code fences, no explanation.

---

Podcast: {show_name} — {episode_title}
Segment {i} of {n} ({position} of the episode):

{chunk}
"""


# Reduce prompt: combines per-segment notes into the final structured summary.
REDUCE_PROMPT = """\
{system_prompt}

---

You are combining per-segment notes from a single {minutes}-minute podcast episode into
one final summary. The segment notes below were produced by reading the episode in order,
and together they cover the ENTIRE episode.

Your job is to synthesize, not to select a favourite segment. Every segment below must be
represented in the output. Check explicitly that the final segments are covered before you
answer — that is where summaries usually fail.

Podcast: {show_name} — {episode_title}

SEGMENT NOTES (in chronological order):

{segment_notes}

---

Respond with ONLY valid JSON matching the schema above. No markdown code fences, no explanation.
"""


# ---------------------------------------------------------------------------
# Long-transcript handling: chunking + coverage targets
# ---------------------------------------------------------------------------

# Words per chunk in the map phase. ~9k words is roughly 12k tokens, which keeps
# each request comfortably inside every backend's context window while needing
# only a handful of chunks for even a 3-hour episode.
CHUNK_WORDS = 9000
CHUNK_OVERLAP_WORDS = 200

# Average speaking rate used to estimate episode length when the real duration
# isn't available. Conversational podcasts run faster than prose narration;
# measured against this vault's Moonshots episodes, ~175 wpm is close.
WORDS_PER_MINUTE = 175


def _estimate_minutes(word_count: int, duration_seconds: float = 0) -> int:
    """Episode runtime in minutes — from real duration when known, else estimated."""
    if duration_seconds and duration_seconds > 0:
        return max(1, round(duration_seconds / 60))
    return max(1, round(word_count / WORDS_PER_MINUTE))


def _coverage_targets(word_count: int, duration_seconds: float = 0) -> Dict[str, Any]:
    """Scale requested item counts to episode length.

    A three-hour panel show and a twenty-minute interview should not get the
    same 5-15 key ideas. Counts grow with runtime so long episodes get
    proportionate coverage instead of a summary of their first half.
    """
    minutes = _estimate_minutes(word_count, duration_seconds)

    n_ideas_lo = max(6, min(24, round(minutes / 9)))
    n_ideas_hi = max(10, min(32, round(minutes / 6)))

    if minutes < 45:
        deep_dives = "3-4"
    elif minutes < 90:
        deep_dives = "4-5"
    elif minutes < 150:
        deep_dives = "5-6"
    else:
        deep_dives = "6-7"

    n_quotes_lo = max(4, min(12, round(minutes / 18)))
    n_quotes_hi = max(8, min(18, round(minutes / 10)))

    n_act_lo = 3 if minutes < 60 else 4
    n_act_hi = 5 if minutes < 60 else 8

    return {
        "minutes": minutes,
        "n_key_ideas": f"{n_ideas_lo}-{n_ideas_hi}",
        "n_deep_dives": deep_dives,
        "n_quotes": f"{n_quotes_lo}-{n_quotes_hi}",
        "n_actionables": f"{n_act_lo}-{n_act_hi}",
    }


def _build_system_prompt(word_count: int, duration_seconds: float = 0) -> str:
    """Fill the summarizer prompt with length-scaled coverage targets."""
    return SUMMARIZE_SYSTEM_PROMPT.format(
        **_coverage_targets(word_count, duration_seconds))


def _chunk_transcript(
    text: str,
    chunk_words: int = CHUNK_WORDS,
    overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> List[str]:
    """Split a transcript into overlapping word-count chunks, preserving lines.

    Splits on line boundaries so sentences and speaker turns stay intact, and
    carries a small overlap between chunks so an idea spanning a boundary isn't
    lost. Returns a single-element list when the transcript already fits.
    """
    lines = text.splitlines()
    total_words = sum(len(ln.split()) for ln in lines)
    if total_words <= chunk_words:
        return [text]

    chunks: List[str] = []
    current: List[str] = []
    current_words = 0

    for line in lines:
        lw = len(line.split())
        if current_words + lw > chunk_words and current:
            chunks.append("\n".join(current))
            # Carry the tail of this chunk into the next for continuity.
            tail: List[str] = []
            tail_words = 0
            for prev in reversed(current):
                pw = len(prev.split())
                if tail_words + pw > overlap_words:
                    break
                tail.insert(0, prev)
                tail_words += pw
            current = tail
            current_words = tail_words
        current.append(line)
        current_words += lw

    if current:
        chunks.append("\n".join(current))
    return chunks


def _position_label(i: int, n: int) -> str:
    """Human-readable description of where a chunk sits in the episode."""
    if n == 1:
        return "whole"
    if i == 1:
        return "opening"
    if i == n:
        return "final portion"
    frac = (i - 0.5) / n
    if frac < 0.4:
        return "early-middle"
    if frac < 0.65:
        return "middle"
    return "late-middle"


REQUIRED_SUMMARY_KEYS = ("tldr", "key_ideas", "deep_dives", "quotes", "backlinks")


def _validate_summary(summary: Any) -> List[str]:
    """Return a list of problems with a parsed summary. Empty list means OK.

    Guards against a response that was cut off by an output-token limit and
    then salvaged into valid-but-incomplete JSON by ``_loads_llm_json``.
    """
    problems: List[str] = []
    if not isinstance(summary, dict):
        return ["response was not a JSON object"]
    for key in REQUIRED_SUMMARY_KEYS:
        value = summary.get(key)
        if value is None:
            problems.append(f"missing '{key}'")
        elif isinstance(value, (list, dict, str)) and len(value) == 0:
            problems.append(f"empty '{key}'")
    if isinstance(summary.get("key_ideas"), list) and len(summary["key_ideas"]) < 3:
        problems.append("suspiciously few key_ideas (<3) — response may be truncated")
    return problems


# ---------------------------------------------------------------------------
# xAI API key loading
# ---------------------------------------------------------------------------

def _load_xai_api_key() -> Optional[str]:
    """Load XAI_API_KEY from environment, skill .env, or global config.

    Checks in order:
    1. XAI_API_KEY environment variable
    2. Skill-level .env (podcast-to-obsidian/.env)
    3. Global config (~/.config/last30days/.env)
    """
    key = os.environ.get("XAI_API_KEY", "")
    if key:
        return key
    # Check skill-level .env
    skill_env = Path(__file__).resolve().parents[2] / ".env"
    for env_path in [skill_env, Path.home() / ".config" / "last30days" / ".env"]:
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("XAI_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
            except Exception:
                pass
    return None


# ---------------------------------------------------------------------------
# xAI API summary (replaces Claude CLI)
# ---------------------------------------------------------------------------

def _call_xai_chat(api_key: str, model: str, prompt: str, max_tokens: int = 4096) -> Optional[str]:
    """Call xAI chat completions API directly. Returns content text or None."""
    import urllib.request
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "reasoning_effort": "medium",
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.x.ai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def _backend_xai(prompt: str, model: str = "grok-4.5") -> Optional[str]:
    """Raw xAI call. Returns response text, or None if unavailable/failed."""
    api_key = _load_xai_api_key()
    if not api_key:
        return None
    try:
        # 16k output budget: a long episode's summary (20+ key ideas, 6 deep
        # dives, 15 quotes) does not fit in the old 4096-token ceiling, and
        # overflow used to be silently salvaged into a truncated note.
        return _call_xai_chat(api_key, model, prompt, max_tokens=16384)
    except Exception as e:
        print(f"  [warn] xAI API call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# OpenAI API summary (fallback)
# ---------------------------------------------------------------------------

def _backend_openai(
    prompt: str,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    base_url: str = "https://api.openai.com/v1",
) -> Optional[str]:
    """Raw OpenAI-compatible call. Returns response text, or None."""
    api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 16384,
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
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        choice = result["choices"][0]
        # A response cut off by the token cap must not be treated as complete.
        if choice.get("finish_reason") == "length":
            print("  [warn] OpenAI response hit the output token limit")
        return choice["message"]["content"]
    except Exception as e:
        print(f"  [warn] OpenAI API call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Unified summary entrypoint
# ---------------------------------------------------------------------------

def _backend_claude(prompt: str, timeout: int = 600) -> Optional[str]:
    """Raw Claude CLI call. Returns response text, or None.

    Unlike the previous implementation this checks ``returncode`` — a CLI that
    errored out mid-stream used to have its partial stdout accepted as a
    successful response.
    """
    import subprocess

    if not Path(CLAUDE_CLI).exists():
        return None

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "--print"],
            input=prompt,
            capture_output=True, text=True, encoding="utf-8", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"  [warn] Claude CLI timed out after {timeout}s")
        return None
    except Exception as e:
        print(f"  [warn] Claude CLI call failed: {e}")
        return None

    content = (result.stdout or "").strip()
    if result.returncode != 0:
        err = (result.stderr or "").strip()[:200]
        print(f"  [warn] Claude CLI exited {result.returncode}: {err}")
        return None
    if not content or "Failed to authenticate" in content:
        print(f"  [claude-cli] Failed: {(result.stderr or '')[:100]}")
        return None
    return content


# ---------------------------------------------------------------------------
# Map-reduce summarization
# ---------------------------------------------------------------------------

def _summarize_with_backend(
    call_fn,
    label: str,
    transcript_text: str,
    episode_title: str,
    show_name: str,
    duration_seconds: float = 0,
) -> Optional[Dict[str, Any]]:
    """Summarize a transcript of any length using one backend.

    Short transcripts go through a single call. Long ones are chunked and
    processed map-reduce style: each chunk is read on its own, then the
    per-segment notes are synthesized into the final summary. This replaces the
    old behaviour of slicing the transcript to its first 12k words, which
    silently discarded the back half of long episodes.
    """
    word_count = len(transcript_text.split())
    targets = _coverage_targets(word_count, duration_seconds)
    system_prompt = _build_system_prompt(word_count, duration_seconds)
    chunks = _chunk_transcript(transcript_text)

    def _parse(raw: Optional[str], what: str) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        try:
            return _loads_llm_json(raw)
        except json.JSONDecodeError as e:
            print(f"  [warn] {label} returned invalid JSON for {what}: {e}")
            return None

    # --- Single-call path (transcript already fits) ---------------------
    if len(chunks) == 1:
        print(f"  [ai] Generating summary with {label} "
              f"({word_count:,} words, ~{targets['minutes']}min, single pass)...")
        prompt = (
            f"{system_prompt}\n\n"
            f"---\n\n"
            f"Podcast: {show_name} — {episode_title}\n\n"
            f"Transcript:\n\n{transcript_text}\n\n"
            f"---\n\n"
            f"Respond with ONLY valid JSON. No markdown code fences, no explanation."
        )
        summary = _parse(call_fn(prompt), "summary")
        if summary is None:
            return None
        problems = _validate_summary(summary)
        if problems:
            print(f"  [warn] {label} summary incomplete: {'; '.join(problems)}")
            return None
        print(f"  [ai] [{label}] Summary generated successfully")
        return summary

    # --- Map phase ------------------------------------------------------
    n = len(chunks)
    print(f"  [ai] Generating summary with {label} "
          f"({word_count:,} words, ~{targets['minutes']}min, {n} segments)...")

    segment_notes: List[str] = []
    for i, chunk in enumerate(chunks, start=1):
        position = _position_label(i, n)
        print(f"  [ai] [{label}] Reading segment {i}/{n} ({position})...")
        prompt = MAP_SEGMENT_PROMPT.format(
            i=i, n=n, position=position,
            show_name=show_name, episode_title=episode_title,
            chunk=chunk,
        )
        note = _parse(call_fn(prompt), f"segment {i}/{n}")
        if note is None:
            # A dropped segment means a hole in coverage — which is the exact
            # failure this rewrite exists to prevent. Fail loudly instead.
            print(f"  [warn] {label} failed on segment {i}/{n} — aborting this backend")
            return None
        segment_notes.append(
            f"### Segment {i} of {n} ({position})\n"
            + json.dumps(note, ensure_ascii=False, indent=2)
        )

    # --- Reduce phase ---------------------------------------------------
    print(f"  [ai] [{label}] Synthesizing {n} segments into final summary...")
    reduce_prompt = REDUCE_PROMPT.format(
        system_prompt=system_prompt,
        minutes=targets["minutes"],
        show_name=show_name,
        episode_title=episode_title,
        segment_notes="\n\n".join(segment_notes),
    )
    summary = _parse(call_fn(reduce_prompt), "final synthesis")
    if summary is None:
        return None
    problems = _validate_summary(summary)
    if problems:
        print(f"  [warn] {label} synthesis incomplete: {'; '.join(problems)}")
        return None

    print(f"  [ai] [{label}] Summary generated successfully "
          f"({len(summary.get('key_ideas', []))} key ideas, "
          f"{len(summary.get('deep_dives', []))} deep dives, "
          f"{len(summary.get('quotes', []))} quotes across {n} segments)")
    return summary


def generate_ai_summary(
    transcript_text: str,
    episode_title: str = "",
    show_name: str = "",
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    base_url: str = "https://api.openai.com/v1",
    duration_seconds: float = 0,
) -> Optional[Dict[str, Any]]:
    """Generate a structured summary. Tries Claude CLI first, then xAI, then OpenAI.

    The full transcript is always used — long episodes are chunked and
    map-reduced rather than truncated. ``duration_seconds``, when known, is
    used to scale how much coverage is requested.

    Returns:
        Parsed summary dict, or None on failure.
    """
    backends = [
        ("claude", _backend_claude),
        ("xai", lambda p: _backend_xai(p, model="grok-4.5")),
        ("openai", lambda p: _backend_openai(
            p, api_key=api_key, model=model, base_url=base_url)),
    ]

    for label, call_fn in backends:
        summary = _summarize_with_backend(
            call_fn, label, transcript_text, episode_title, show_name,
            duration_seconds=duration_seconds,
        )
        if summary:
            return summary

    print("  [warn] No AI backend available")
    print("  [hint] Claude CLI (Max), xAI API, or OpenAI API are all unavailable.")
    return None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_deep_dives(dives: List[Dict[str, str]]) -> str:
    """Format deep dives as mini-essay sections with headers."""
    if not dives:
        return "_No deep dives generated._"
    sections = []
    for dive in dives:
        if isinstance(dive, dict):
            title = dive.get("title", "Untitled")
            body = dive.get("body", "")
            sections.append(f"### {title}\n\n{body}")
        elif isinstance(dive, str):
            sections.append(dive)
    return "\n\n---\n\n".join(sections)


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
