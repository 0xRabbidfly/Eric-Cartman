"""Turn exercises.md into exercises.json so the gym tracker can show how-tos and videos.

exercises.md is the source of truth. Re-run this after editing it:

    python build_exercises.py
"""
import json
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIELDS = {"Why": "why", "How": "how", "Cues": "cues", "Video": "video"}
HEADING_RE = re.compile(r"^(#{2,3})\s+(.*?)\s*$")
FIELD_RE = re.compile(r"^-\s+\*\*(\w+):\*\*\s*(.*)$")
CONTINUATION_RE = re.compile(r"^\s{2,}(\S.*)$")


def slugify(name: str) -> str:
    """Match GitHub's heading-anchor algorithm, so keys equal exercises.md anchors."""
    text = unicodedata.normalize("NFKD", name).lower()
    text = re.sub(r"[^\w\s-]", "", text)          # drop punctuation and symbols
    text = re.sub(r"[\s_]+", "-", text.strip())   # whitespace to hyphens
    return re.sub(r"-{2,}", "-", text)


def parse_exercises(markdown: str) -> dict:
    """Read `### Name` blocks under `## Group` headings into keyed entries.

    Field values wrap across lines in the source; each is rejoined into one
    string so the app can render it as a paragraph.
    """
    exercises = {}
    group = ""
    current = None
    field = None

    def flush_field():
        if current is not None and field is not None:
            current[field] = " ".join(current[field].split())

    for line in markdown.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            flush_field()
            level, title = heading.group(1), heading.group(2)
            field = None
            if level == "##":
                group = title
                current = None
            else:
                current = {"key": slugify(title), "name": title, "group": group,
                           "why": "", "how": "", "cues": "", "video": ""}
                exercises[current["key"]] = current
            continue

        if current is None:
            continue

        match = FIELD_RE.match(line)
        if match and match.group(1) in FIELDS:
            flush_field()
            field = FIELDS[match.group(1)]
            current[field] = match.group(2)
            continue

        continuation = CONTINUATION_RE.match(line)
        if continuation and field is not None:
            current[field] += " " + continuation.group(1)
            continue

        flush_field()
        field = None

    flush_field()
    return exercises


def render(exercises: dict) -> str:
    """The exact text written to exercises.json, so a test can check it is current."""
    return json.dumps(exercises, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    source = (HERE / "exercises.md").read_text(encoding="utf-8")
    exercises = parse_exercises(source)
    target = HERE / "exercises.json"
    target.write_text(render(exercises), encoding="utf-8")
    print(f"Wrote {len(exercises)} exercises to {target}")


if __name__ == "__main__":
    main()
