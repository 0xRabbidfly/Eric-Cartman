"""Self-checks for the podcast-to-obsidian fixes. Run: python _selftest.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib import rss, note_generator as ng  # noqa: E402
from lib import manifest as mf  # noqa: E402
import pipeline  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        failures.append(name)


print("\n[1] RSS charset decoding")
# Raw cp1252 byte 0x92 = right single quotation mark. Invalid as UTF-8.
cp = (b'<?xml version="1.0" encoding="ISO-8859-1"?><rss><title>OpenAI'
      b'\x92s Week</title></rss>')
out = rss._decode_feed(cp)
check("declared cp1252 keeps curly apostrophe", "’" in out and "�" not in out, repr(out[40:70]))

u8 = '<?xml version="1.0" encoding="UTF-8"?><rss><title>OpenAI’s</title></rss>'.encode("utf-8")
check("utf-8 feed still decodes", "’" in rss._decode_feed(u8))

bare = b"Jensen\x92s AGI"  # no declaration, not valid utf-8
check("undeclared cp1252 falls back cleanly", "�" not in rss._decode_feed(bare), repr(rss._decode_feed(bare)))

check("http charset header is honoured",
      "’" in rss._decode_feed(b"OpenAI\x92s", "windows-1252"))


print("\n[2] Summary validation catches truncated responses")
good = {"tldr": "x", "key_ideas": [1, 2, 3], "deep_dives": [1], "quotes": [1],
        "backlinks": {"people": ["a"]}}
check("complete summary passes", ng._validate_summary(good) == [])
# backlinks is the last key in the schema, so it's what a token-cap cutoff loses
lost_tail = dict(good); lost_tail.pop("backlinks")
check("missing trailing key rejected", ng._validate_summary(lost_tail) != [])
check("too-few key_ideas rejected", ng._validate_summary({**good, "key_ideas": [1]}) != [])
check("non-dict rejected", ng._validate_summary("nope") != [])


print("\n[3] Chunking covers the whole transcript")
sample = "\n".join(f"line {i} " + " ".join(["word"] * 20) for i in range(3000))
total_words = len(sample.split())
chunks = ng._chunk_transcript(sample)
check("long transcript is split", len(chunks) > 1, f"got {len(chunks)}")
check("first line in first chunk", sample.splitlines()[0] in chunks[0])
check("LAST line in LAST chunk", sample.splitlines()[-1] in chunks[-1])
joined_words = sum(len(c.split()) for c in chunks)
check("no content dropped", joined_words >= total_words, f"{joined_words} vs {total_words}")
check("short transcript stays single", len(ng._chunk_transcript("a b c")) == 1)


print("\n[4] Coverage targets scale with runtime")
short = ng._coverage_targets(3000)                      # ~17 min
long_ = ng._coverage_targets(29299)                     # ~167 min
check("short episode gets fewer ideas", short["n_key_ideas"] != long_["n_key_ideas"],
      f"{short['n_key_ideas']} vs {long_['n_key_ideas']}")
check("long episode gets more deep dives", long_["n_deep_dives"] > short["n_deep_dives"],
      f"{short['n_deep_dives']} vs {long_['n_deep_dives']}")
check("real duration overrides estimate",
      ng._coverage_targets(29299, duration_seconds=164 * 60)["minutes"] == 164)
check("system prompt formats with no leftovers",
      "{" not in ng._build_system_prompt(29299).split("Output JSON")[0])


print("\n[5] Manifest merge preserves a concurrent run's episodes")
import json, tempfile, os
tmpdir = Path(tempfile.mkdtemp())
path = tmpdir / "m.json"
m1 = mf.Manifest(path)
m1._data = {"version": 1, "shows": {"s": {"name": "S", "episodes": {"a": {"status": "completed"}},
                                          "latest_published": "2026-01-01"}}}
m1.save()
# Simulate a second process that loaded earlier and adds a different episode
m2 = mf.Manifest(path)
m2._data["shows"]["s"]["episodes"]["b"] = {"status": "completed"}
m2._data["shows"]["s"]["latest_published"] = "2026-02-01"
# Meanwhile process 1 records another episode and saves with its stale snapshot
m1._data["shows"]["s"]["episodes"]["c"] = {"status": "completed"}
m1.save()
m2.save()
final = json.loads(path.read_text(encoding="utf-8"))
eps = final["shows"]["s"]["episodes"]
check("episode from run A survives", "c" in eps, str(sorted(eps)))
check("episode from run B survives", "b" in eps, str(sorted(eps)))
check("original episode survives", "a" in eps, str(sorted(eps)))
check("watermark moves forward only",
      final["shows"]["s"]["latest_published"] == "2026-02-01",
      final["shows"]["s"]["latest_published"])


print("\n[6] Run lock")
lockpath = tmpdir / "pipeline.lock"
l1 = pipeline.RunLock(lockpath)
check("first acquire succeeds", l1.acquire())
l2 = pipeline.RunLock(lockpath)
check("second acquire refused", l2.acquire() is False)
l1.release()
check("lock removed on release", not lockpath.exists())
l3 = pipeline.RunLock(lockpath)
check("acquire works after release", l3.acquire())
l3.release()
# Stale lock from a dead PID must be reclaimable
lockpath.write_text(json.dumps({"pid": 999999, "started_at": 0}), encoding="utf-8")
check("stale lock reclaimed", pipeline.RunLock(lockpath).acquire())
# A BOM (PowerShell Set-Content writes one) must not make the lock invisible
lockpath.write_bytes(b"\xef\xbb\xbf" + json.dumps(
    {"pid": os.getpid(), "started_at": __import__("time").time()}).encode())
check("BOM-prefixed lock still honoured", pipeline.RunLock(lockpath).acquire() is False)
# An unreadable lock must fail SAFE (block), not fail open
lockpath.write_text("{garbage", encoding="utf-8")
check("corrupt lock blocks rather than fails open",
      pipeline.RunLock(lockpath).acquire() is False)
# ...but ages out eventually
os.utime(lockpath, (0, 0))
check("corrupt lock aged out is discarded", pipeline.RunLock(lockpath).acquire())
lockpath.unlink(missing_ok=True)


print("\n[7] Orphan audio sweep")
adir = tmpdir / "audio"
adir.mkdir()
fresh = adir / "fresh.mp3"; fresh.write_bytes(b"x" * 100)
old = adir / "old.m4a"; old.write_bytes(b"x" * 100)
part = adir / "half.mp3.part"; part.write_bytes(b"x" * 100)
os.utime(old, (0, 0))
os.utime(part, (0, 0))
n, _ = pipeline.sweep_orphan_audio(adir)
check("old audio swept", not old.exists())
check("stale .part swept", not part.exists())
check("recent audio kept", fresh.exists())
check("non-mp3 formats covered", n == 2, f"removed {n}")

print()
if failures:
    print(f"FAILED: {len(failures)} check(s): {failures}")
    sys.exit(1)
print("All self-checks passed.")
