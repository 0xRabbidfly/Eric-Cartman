import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_exercises

SAMPLE = """# Exercise Library

Intro prose that must be ignored.

---

## Lower body — bilateral

### Back squat
- **Why:** the single biggest driver of leg force for pedalling. Trains quads, glutes and
  trunk under load.
- **How:** bar on upper traps, feet shoulder width.
- **Cues:** "spread the floor", knees out.
- **Video:** https://www.youtube.com/watch?v=8PMjqgR8Wa8

### Romanian deadlift (RDL)
- **Why:** hamstring and glute strength.
- **How:** bar at the hips, soft knees.
- **Cues:** "hips to the wall behind you".
- **Video:** https://www.youtube.com/watch?v=5bJEigM5iVg

## Power

### Farmer's carry
- **Why:** total-body bracing under load.
- **How:** heavy dumbbells, stand tall.
- **Cues:** "walk like you're proud".
- **Video:** https://www.youtube.com/watch?v=vi4X2iSOyiA
"""


def test_parses_every_heading():
    result = build_exercises.parse_exercises(SAMPLE)
    assert set(result) == {"back-squat", "romanian-deadlift-rdl", "farmers-carry"}


def test_carries_group_from_the_preceding_h2():
    result = build_exercises.parse_exercises(SAMPLE)
    assert result["back-squat"]["group"] == "Lower body — bilateral"
    assert result["farmers-carry"]["group"] == "Power"


def test_joins_wrapped_field_lines_into_one_string():
    why = build_exercises.parse_exercises(SAMPLE)["back-squat"]["why"]
    assert why == ("the single biggest driver of leg force for pedalling. "
                   "Trains quads, glutes and trunk under load.")
    assert "\n" not in why


def test_extracts_name_key_and_video():
    entry = build_exercises.parse_exercises(SAMPLE)["romanian-deadlift-rdl"]
    assert entry["name"] == "Romanian deadlift (RDL)"
    assert entry["key"] == "romanian-deadlift-rdl"
    assert entry["video"] == "https://www.youtube.com/watch?v=5bJEigM5iVg"
    assert entry["how"] == "bar at the hips, soft knees."
    assert entry["cues"] == '"hips to the wall behind you".'


def test_slugify_matches_github_anchors():
    assert build_exercises.slugify("Romanian deadlift (RDL)") == "romanian-deadlift-rdl"
    assert build_exercises.slugify("45° back extension") == "45-back-extension"
    assert build_exercises.slugify("Farmer's carry") == "farmers-carry"


def _library():
    source = (build_exercises.HERE / "exercises.md").read_text(encoding="utf-8")
    return build_exercises.parse_exercises(source)


def test_library_entries_are_complete():
    result = _library()
    assert len(result) >= 42
    for key, entry in result.items():
        assert entry["key"] == key
        for field in ("name", "group", "why", "how", "cues"):
            assert entry[field], f"{key} is missing {field}"
        assert entry["video"].startswith("https://www.youtube.com/watch?v="), f"{key} has no video"


def test_exercises_json_is_in_sync_with_the_markdown():
    # Compare parsed JSON, not text: a Windows checkout may turn the file's line endings to CRLF.
    built = json.loads((build_exercises.HERE / "exercises.json").read_text(encoding="utf-8"))
    assert built == _library(), "run python build_exercises.py"
