#!/usr/bin/env python3
"""
podcast-to-obsidian — Podcast → Transcript → Obsidian pipeline.

Detects new podcast episodes via Spotify MCP or RSS feeds,
downloads audio, transcribes locally using faster-whisper,
generates structured Obsidian notes, and writes to the vault.

Usage:
    python pipeline.py                         # Full pipeline
    python pipeline.py --check-only            # Detection only
    python pipeline.py --show "Show Name"      # Process specific show
    python pipeline.py --dry-run               # Preview without writing
    python pipeline.py --add-show --name "X" --rss "URL"  # Add show
    python pipeline.py --list-shows            # List tracked shows
    python pipeline.py --model large-v3        # Whisper model override
    python pipeline.py --retry-failed          # Retry failed episodes
    python pipeline.py --no-ai                 # Skip AI summaries
"""

import argparse
import importlib.util
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# UTF-8 on Windows
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent
CONFIG_DIR = SKILL_DIR / "config"
CONFIG_FILE = SCRIPT_DIR / "config.json"

# Add script dir to path for local imports
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


# ---------------------------------------------------------------------------
# Run logging
#
# Unattended runs (scheduled tasks, detached processes) previously left no
# artifact to debug from -- if the caller's shell redirection buffered or the
# session died, the run was invisible.  Every run now tees stdout/stderr to
# .work/logs/<timestamp>.log regardless of how the process was launched.
# ---------------------------------------------------------------------------

_LOG_RETENTION = 30  # keep the most recent N run logs


class _Tee:
    """Write to the original stream and a log file simultaneously."""

    def __init__(self, stream, log_handle):
        self._stream = stream
        self._log = log_handle

    def write(self, data):
        try:
            self._stream.write(data)
        except Exception:
            pass
        try:
            self._log.write(data)
            self._log.flush()
        except Exception:
            pass
        return len(data)

    def flush(self):
        for target in (self._stream, self._log):
            try:
                target.flush()
            except Exception:
                pass

    def isatty(self):
        # Delegate so downstream progress rendering still detects a real
        # terminal when one is present.
        try:
            return self._stream.isatty()
        except Exception:
            return False

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _prune_old_logs(log_dir: Path, keep: int = _LOG_RETENTION) -> None:
    """Delete all but the most recent `keep` run logs."""
    try:
        logs = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in logs[keep:]:
            stale.unlink(missing_ok=True)
    except Exception:
        pass  # logging must never break the run


def _start_run_log() -> Optional[Path]:
    """Tee stdout/stderr to a timestamped file under .work/logs/.

    Returns the log path, or None if logging could not be set up (in which
    case the run continues normally with console output only).
    """
    try:
        config = load_config()
        work_dir = SKILL_DIR / config.get("work_dir", ".work")
        log_dir = work_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        log_path = log_dir / f"{stamp}.log"

        handle = open(log_path, "w", encoding="utf-8", buffering=1)
        sys.stdout = _Tee(sys.stdout, handle)
        sys.stderr = _Tee(sys.stderr, handle)

        _prune_old_logs(log_dir)
        return log_path
    except Exception as e:
        print(f"  [warn] Could not open run log: {e}")
        return None


# ---------------------------------------------------------------------------
# Load .env (OPENAI_API_KEY, SPOTIFY_CLIENT_SECRET, etc.)
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    """Load key=value pairs from .env into os.environ (no external deps).

    Checks skill-level .env first, then project root .env as fallback.
    Existing env vars are never overwritten.
    """
    env_files = [
        SKILL_DIR / ".env",
        SKILL_DIR.parents[2] / ".env",  # project root
    ]
    for env_file in env_files:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

_load_dotenv()


# ---------------------------------------------------------------------------
# Local module loading (avoids name clashes)
# ---------------------------------------------------------------------------

def _load_module(name: str, filepath: Path):
    """Import a Python module by file path."""
    spec = importlib.util.spec_from_file_location(name, str(filepath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_lib = SCRIPT_DIR / "lib"
manifest_mod = _load_module("p2o_manifest", _lib / "manifest.py")
rss_mod = _load_module("p2o_rss", _lib / "rss.py")
downloader_mod = _load_module("p2o_downloader", _lib / "downloader.py")
note_gen_mod = _load_module("p2o_note_generator", _lib / "note_generator.py")

# yt_downloader is loaded lazily (only when --url is used; needs yt-dlp)
_yt_downloader_mod = None


def _get_yt_downloader():
    global _yt_downloader_mod
    if _yt_downloader_mod is None:
        _yt_downloader_mod = _load_module("p2o_yt_downloader", _lib / "yt_downloader.py")
    return _yt_downloader_mod

# Transcriber is loaded lazily (requires faster-whisper)
_transcriber_mod = None


def _get_transcriber():
    global _transcriber_mod
    if _transcriber_mod is None:
        _transcriber_mod = _load_module("p2o_transcriber", _lib / "transcriber.py")
    return _transcriber_mod


# Obsidian wrapper from vendor
_obsidian_mod = _load_module(
    "p2o_obsidian",
    SCRIPT_DIR / "vendor" / "obsidian" / "obsidian.py",
)
Obsidian = _obsidian_mod.Obsidian

# Classes / functions
Manifest = manifest_mod.Manifest
parse_feed = rss_mod.parse_feed
Episode = rss_mod.Episode
download_audio = downloader_mod.download_audio
generate_note = note_gen_mod.generate_note
generate_ai_summary = note_gen_mod.generate_ai_summary
generate_show_index = note_gen_mod.generate_show_index


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> Dict[str, Any]:
    """Load config.json with defaults."""
    defaults = {
        "vault_path": "",
        "podcasts_folder": "Podcasts",
        "transcripts_folder": "transcripts",
        "whisper_model": "large-v3",
        "whisper_device": "auto",
        "whisper_language": None,
        "max_episodes": 5,
        "detection_window": 50,
        "only_new_releases": True,
        "max_age_days": 30,
        "audio_format": "mp3",
        "note_template": "default",
        "work_dir": ".work",
        "shows": {},
    }
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user = json.load(f)
        defaults.update(user)
    return defaults


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def step_detect_episodes(
    config: Dict[str, Any],
    manifest: Manifest,
    show_filter: Optional[str] = None,
) -> Dict[str, List[Episode]]:
    """Detect new episodes across all tracked shows.

    Returns: {show_id: [Episode, ...]} for episodes not in manifest.
    """
    print("\n=== Step 1: Detect New Episodes ===\n")
    new_episodes: Dict[str, List[Episode]] = {}

    # Get shows from config (RSS-only mode)
    shows = config.get("shows", {})

    for show_id, show_data in shows.items():
        if show_id.startswith("_"):  # Skip comment keys
            continue
        if not isinstance(show_data, dict):  # Skip non-dict entries
            continue
        if not show_data.get("enabled", True):
            continue
        if show_filter:
            name_match = show_data.get("name", "").lower() == show_filter.lower()
            id_match = show_id.lower() == show_filter.lower()
            partial_match = show_filter.lower() in show_data.get("name", "").lower() or show_filter.lower() in show_id.lower()
            if not (name_match or id_match or partial_match):
                continue

        show_name = show_data.get("name", show_id)
        rss_url = show_data.get("rss_url", "")

        if not rss_url:
            print(f"  [skip] {show_name} — no RSS URL configured")
            continue

        print(f"  [fetch] {show_name}: {rss_url[:60]}...")

        # Register show in manifest
        manifest.add_show(
            show_id=show_id,
            name=show_name,
            rss_url=rss_url,
            spotify_id=show_data.get("spotify_id", ""),
        )

        try:
            # Detection window is deliberately decoupled from max_episodes.
            # Previously this was `max_episodes * 2`, which meant --max-episodes 1
            # only ever looked at the 2 most recent entries -- if a show published
            # several episodes between runs, the older ones fell outside the window
            # and were never detected, on this run or any later one.
            window = config.get("detection_window", 50)
            episodes = parse_feed(rss_url, max_episodes=window)
            print(f"  [found] {len(episodes)} episodes in feed (newest {window})")

            # Recency gate: only genuinely new releases, never the archive.
            #
            # The watermark is the newest publish date already processed for
            # this show.  Anything at or below it is historical by definition
            # and is skipped even if it never made it into the manifest --
            # backfill is a deliberate manual act, not something a scheduled
            # run should ever start doing on its own.
            only_new = config.get("only_new_releases", True)
            max_age_days = config.get("max_age_days", 30)
            backfill_since = config.get("backfill_since", "")

            watermark = ""
            age_cutoff = ""
            if backfill_since:
                # Explicit manual backfill: a date floor replaces both gates.
                age_cutoff = backfill_since
            elif only_new:
                # Both gates apply together.  The watermark stops re-processing
                # and the age cutoff stops the archive: an episode from three
                # months ago that was never picked up is still historical, even
                # though it is technically "newer than" a stale watermark.
                watermark = manifest.get_watermark(show_id)
                if max_age_days:
                    age_cutoff = (
                        datetime.now(timezone.utc) - timedelta(days=max_age_days)
                    ).strftime("%Y-%m-%d")

            gating = bool(watermark or age_cutoff)

            # Filter to new episodes only (match by key, rss_guid, or
            # title+published so Spotify-keyed entries aren't reprocessed)
            new = []
            skipped_historical = 0
            skipped_undated = 0
            for ep in episodes:
                if manifest.is_processed(show_id, ep.id, title=ep.title, published=ep.published):
                    continue
                if gating and not ep.published:
                    # No publish date means recency cannot be established, so
                    # it cannot be confirmed as a new release.  Skipping is the
                    # safe default -- otherwise undated feed entries silently
                    # bypass every gate and drag in the whole back catalogue.
                    skipped_undated += 1
                    continue
                if watermark and ep.published <= watermark:
                    skipped_historical += 1
                    continue
                if age_cutoff and ep.published < age_cutoff:
                    skipped_historical += 1
                    continue
                new.append(ep)
                ep.show_name = show_name

            if skipped_historical:
                gates = []
                if watermark:
                    gates.append(f"newer than {watermark}")
                if age_cutoff:
                    label = "on/after" if backfill_since else f"within {max_age_days}d —"
                    gates.append(f"published {label} {age_cutoff}")
                print(
                    f"  [recency] {skipped_historical} older episodes skipped "
                    f"(taking only releases {' and '.join(gates)})"
                )
            if skipped_undated:
                print(
                    f"  [recency] {skipped_undated} episodes skipped — no publish date "
                    f"in feed, cannot confirm as new releases"
                )

            if new:
                # Respect max_episodes limit (processing cap, not detection cap)
                max_ep = config.get("max_episodes", 5)
                found_count = len(new)
                new = new[:max_ep]
                new_episodes[show_id] = new
                if found_count > len(new):
                    print(
                        f"  [new] {found_count} new episodes detected, "
                        f"processing {len(new)} (max_episodes={max_ep}); "
                        f"{found_count - len(new)} deferred to a later run"
                    )
                else:
                    print(f"  [new] {len(new)} new episodes to process")
            else:
                print(f"  [uptodate] No new episodes")

        except Exception as e:
            print(f"  [error] Failed to fetch {show_name}: {e}")

    total = sum(len(eps) for eps in new_episodes.values())
    print(f"\n  Total new episodes: {total}")
    return new_episodes


def step_download(
    episodes: List[Episode],
    work_dir: Path,
) -> List[Tuple[Episode, Path]]:
    """Download audio for episodes.

    Returns: [(Episode, audio_path), ...] for successful downloads.
    """
    print("\n=== Step 2: Download Audio ===\n")
    audio_dir = work_dir / "audio"
    results = []

    for ep in episodes:
        try:
            filename = ep.safe_filename()
            audio_path = download_audio(
                audio_url=ep.audio_url,
                output_dir=audio_dir,
                filename=filename,
            )
            results.append((ep, audio_path))
        except Exception as e:
            print(f"  [error] Failed to download '{ep.title}': {e}")

    print(f"\n  Downloaded: {len(results)}/{len(episodes)}")
    return results


def step_transcribe(
    downloaded: List[Tuple[Episode, Path]],
    work_dir: Path,
    model: str = "large-v3",
    device: str = "auto",
    language: Optional[str] = None,
) -> List[Tuple[Episode, Path, Path, dict]]:
    """Transcribe downloaded audio files.

    Returns: [(Episode, audio_path, transcript_path, meta), ...]
    """
    print("\n=== Step 3: Transcribe ===\n")
    transcriber = _get_transcriber()
    transcript_dir = work_dir / "transcripts"
    results = []

    engine = transcriber.get_engine()
    print(f"  Engine: {engine}")
    print(f"  Model: {model}")
    print(f"  Device: {device}\n")

    for ep, audio_path in downloaded:
        try:
            transcript_path, meta = transcriber.transcribe(
                audio_path=audio_path,
                output_dir=transcript_dir,
                model_name=model,
                device=device,
                language=language,
            )
            results.append((ep, audio_path, transcript_path, meta))
        except Exception as e:
            print(f"  [error] Failed to transcribe '{ep.title}': {e}")

    print(f"\n  Transcribed: {len(results)}/{len(downloaded)}")
    return results


def step_generate_notes(
    transcribed: List[Tuple[Episode, Path, Path, dict]],
    config: Dict[str, Any],
    work_dir: Path,
    use_ai: bool = True,
) -> List[Tuple[Episode, str, str, Path]]:
    """Generate Obsidian notes from transcripts.

    Checks .work/summaries/<name>.json for a pre-generated summary first
    (written by the orchestrator/AI).  Falls back to template-only if absent.

    Returns: [(Episode, note_content, vault_path, transcript_path), ...]
    """
    print("\n=== Step 4: Generate Notes ===\n")
    results = []
    skipped_no_ai = []
    podcasts_folder = config.get("podcasts_folder", "Podcasts")
    summaries_dir = work_dir / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)

    for ep, audio_path, transcript_path, meta in transcribed:
        try:
            # Read transcript
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript_text = f.read()

            print(f"  [generate] {ep.title}")

            # 1. Check for orchestrator-generated summary JSON first
            summary_path = summaries_dir / (transcript_path.stem + ".json")
            ai_summary = None
            if summary_path.exists():
                try:
                    with open(summary_path, "r", encoding="utf-8") as f:
                        ai_summary = json.load(f)
                    print(f"  [summary] Loaded from {summary_path.name}")
                except Exception as e:
                    print(f"  [warn] Could not load summary JSON: {e}")

            # 2. If no pre-generated summary and use_ai, try Claude CLI then OpenAI API
            if ai_summary is None and use_ai:
                api_key = os.environ.get("OPENAI_API_KEY")
                ai_summary = generate_ai_summary(
                    transcript_text=transcript_text,
                    episode_title=ep.title,
                    show_name=ep.show_name,
                    api_key=api_key,
                )

            if use_ai and ai_summary is None:
                print(
                    "  [error] AI summary unavailable; refusing to write a template-only note. "
                    "Install/configure Claude CLI or explicitly pass --no-ai if you truly want a skeleton note."
                )
                skipped_no_ai.append(ep)
                continue

            # Generate note
            note_content = generate_note(
                episode=ep.to_dict(),
                transcript_text=transcript_text,
                ai_summary=ai_summary,
            )

            # Vault path
            safe_show = re.sub(r'[<>:"/\\|?*]', '', ep.show_name).strip()
            vault_path = f"{podcasts_folder}/{safe_show}/{ep.safe_filename()}.md"

            results.append((ep, note_content, vault_path, transcript_path))
            print(f"  [ok] → {vault_path}")

        except Exception as e:
            print(f"  [error] Failed to generate note for '{ep.title}': {e}")

    print(f"\n  Generated: {len(results)}/{len(transcribed)}")
    if skipped_no_ai:
        print(
            f"  Skipped (AI unavailable): {len(skipped_no_ai)} — "
            "left unprocessed for retry once Claude CLI is configured:"
        )
        for ep in skipped_no_ai:
            print(f"    - {ep.title}")
    return results


def _cli_failed(result) -> bool:
    """True when an Obsidian CLI call failed.

    The CLI can print "Error: ..." while still exiting 0 (observed with
    append to a missing file), so the exit code alone is not trustworthy.
    """
    if not result.ok:
        return True
    combined = f"{result.stdout}\n{result.stderr}"
    return "Error:" in combined


def _vault_write_large(ob, path: str, text: str, chunk_chars: int = 8000):
    """Write potentially large content to the vault via the Obsidian CLI.

    Constraints discovered the hard way:
    - The CLI takes content as a command-line argument and Windows caps a
      process command line at ~32K chars → create with the first chunk,
      append the rest in line-boundary pieces (inline=True reconstructs the
      original text exactly).
    - The CLI is a notes tool: non-.md paths are silently created as .md,
      so callers MUST pass a .md path (asserted here).
    - Failed appends can exit 0 while printing "Error: ..." → every step is
      checked with _cli_failed, and the final content length is verified by
      reading the note back.
    - The CLI rejects a content argument whose FIRST LINE contains a colon
      (exit -1, no output — observed with "[00:00:12] ..." transcript
      timestamps and any "a: b" text). Workaround: every chunk after the
      first starts with the newline it would otherwise end on, and the first
      chunk gets a leading newline prepended if its first line has a colon
      (Obsidian strips a leading blank line harmlessly).

    Returns (ok: bool, detail: str).
    """
    if not path.endswith(".md"):
        return False, f"vault writes must target .md paths, got: {path}"

    pieces = []
    for line in text.splitlines(keepends=True):
        while len(line) > chunk_chars:
            pieces.append(line[:chunk_chars])
            line = line[chunk_chars:]
        pieces.append(line)

    chunks, buf = [], ""
    for piece in pieces:
        if buf and len(buf) + len(piece) > chunk_chars:
            chunks.append(buf)
            buf = ""
        buf += piece
    if buf:
        chunks.append(buf)
    if not chunks:
        chunks = [""]

    # Colon-in-first-line workaround: shift each chunk's trailing newline to
    # the START of the next chunk so appended chunks begin with an empty
    # first line, which the CLI parses safely.
    for i in range(1, len(chunks)):
        if chunks[i - 1].endswith("\n") and not chunks[i].startswith("\n"):
            chunks[i - 1] = chunks[i - 1][:-1]
            chunks[i] = "\n" + chunks[i]
        elif ":" in chunks[i].split("\n", 1)[0]:
            # hard-split fragment starting with a colon-bearing line and no
            # newline to shift — prepend one (introduces a line break; only
            # possible for single lines longer than chunk_chars)
            chunks[i] = "\n" + chunks[i]
    if ":" in chunks[0].split("\n", 1)[0]:
        chunks[0] = "\n" + chunks[0]

    def _call_with_retry(fn, what):
        r = fn()
        if _cli_failed(r):
            time.sleep(1.0)
            r = fn()
        if _cli_failed(r):
            return f"{what} failed: {r.stderr or r.stdout or 'no output'}"
        return None

    def _verify():
        """Read back and compare length; the app applies writes async, so
        allow it a few seconds to settle before declaring a mismatch.
        ob.read strips leading/trailing whitespace, so compare stripped."""
        expected = len(text.strip())
        written = ""
        for _ in range(4):
            try:
                written = ob.read(path=path)
            except Exception:
                written = ""
            if abs(len(written) - expected) <= 2:
                return None
            time.sleep(1.5)
        return f"read-back length mismatch: wrote {expected} chars, note has {len(written)}"

    last_err = "unknown"
    for _attempt in range(2):  # full-rewrite retry if verification fails
        err = _call_with_retry(
            lambda: ob.create(path=path, content=chunks[0], overwrite=True), "create"
        )
        if err is None:
            for chunk in chunks[1:]:
                err = _call_with_retry(
                    lambda c=chunk: ob.append(c, path=path, inline=True), "append"
                )
                if err:
                    break
        if err is None:
            err = _verify()
        if err is None:
            return True, "ok"
        last_err = err
        time.sleep(1.0)
    return False, last_err


def step_write_to_vault(
    notes: List[Tuple[Episode, str, str, Path]],
    config: Dict[str, Any],
    manifest: Manifest,
    show_id: str,
    dry_run: bool = False,
) -> int:
    """Write generated notes (and their transcripts) to Obsidian vault.

    Returns: Number of successfully written notes.
    """
    print("\n=== Step 5: Write to Vault ===\n")
    success = 0

    if dry_run:
        for ep, content, vault_path, transcript_src in notes:
            print(f"  [dry-run] Would write: {vault_path}")
            print(f"            ({len(content)} chars)")
        return len(notes)

    try:
        ob = Obsidian()
        print(f"  Vault: {ob.vault_name if hasattr(ob, 'vault_name') else 'connected'}")
    except Exception as e:
        print(f"  [error] Cannot connect to Obsidian: {e}")
        print("  [hint] Make sure Obsidian is running with CLI enabled")
        return 0

    podcasts_folder = config.get("podcasts_folder", "Podcasts")

    transcripts_folder = config.get("transcripts_folder", "transcripts")

    for ep, content, vault_path, transcript_src in notes:
        try:
            print(f"  [write] {vault_path}")
            result = ob.create(path=vault_path, content=content, overwrite=True)

            if result.ok:
                # Copy the transcript into the vault so the manifest path is
                # real (previously the manifest recorded a vault path but the
                # transcript was never written out of .work/). Stored as .md —
                # the Obsidian CLI silently converts other extensions anyway.
                safe_show = re.sub(r'[<>:"/\\|?*]', '', ep.show_name).strip()
                transcript_path = ""
                try:
                    transcript_text = Path(transcript_src).read_text(encoding="utf-8")
                    t_vault_path = (
                        f"{podcasts_folder}/{safe_show}/{transcripts_folder}/"
                        f"{ep.safe_filename()}.md"
                    )
                    t_ok, t_detail = _vault_write_large(ob, t_vault_path, transcript_text)
                    if t_ok:
                        transcript_path = t_vault_path
                        print(f"  [transcript] → {t_vault_path}")
                    else:
                        print(f"  [warn] Transcript vault write failed: {t_detail}")
                except (OSError, TypeError) as te:
                    print(f"  [warn] Could not copy transcript to vault: {te}")
                if not transcript_path:
                    # Record the real on-disk location rather than a fiction
                    transcript_path = str(transcript_src) if transcript_src else ""

                # Update manifest ONLY after successful write
                manifest.mark_episode(
                    show_id=show_id,
                    episode_id=ep.id,
                    title=ep.title,
                    published=ep.published,
                    audio_url=ep.audio_url,
                    transcript_path=transcript_path,
                    note_path=vault_path,
                    status="completed",
                )
                manifest.save()
                success += 1
                print(f"  [ok] Written + manifest updated")
            else:
                print(f"  [error] Obsidian write failed: {result.stderr}")
                manifest.mark_episode(
                    show_id=show_id,
                    episode_id=ep.id,
                    title=ep.title,
                    published=ep.published,
                    audio_url=ep.audio_url,
                    status="failed",
                    error=result.stderr,
                )
                manifest.save()

        except Exception as e:
            print(f"  [error] Failed to write '{ep.title}': {e}")
            manifest.mark_episode(
                show_id=show_id,
                episode_id=ep.id,
                title=ep.title,
                published=ep.published,
                status="failed",
                error=str(e),
            )
            manifest.save()

    # Update show index
    if success > 0:
        try:
            show_data = manifest.get_show(show_id)
            if show_data:
                show_name = show_data.get("name", show_id)
                all_eps = [
                    ep_data for ep_data in show_data.get("episodes", {}).values()
                    if ep_data.get("status") == "completed"
                ]
                index_content = generate_show_index(show_name, all_eps)
                safe_show = re.sub(r'[<>:"/\\|?*]', '', show_name).strip()
                index_path = f"{podcasts_folder}/{safe_show}/{safe_show}.md"
                ob.create(path=index_path, content=index_content, overwrite=True)
                print(f"  [index] Updated show index: {index_path}")
        except Exception as e:
            print(f"  [warn] Could not update show index: {e}")

    print(f"\n  Written: {success}/{len(notes)}")
    return success


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def step_cleanup(
    work_dir: Path,
    written_episodes: List[Any],
    keep_audio: bool = False,
) -> None:
    """Purge audio files and intermediate build artifacts after a successful run.

    Audio files are large (100+ MB) and not needed once the transcript exists.
    Intermediate .md files (pre-transcript) are superseded by .final.md.
    """
    print("\n=== Cleanup ===")
    audio_dir = work_dir / "audio"
    notes_dir = work_dir / "notes"
    removed = 0
    freed_mb = 0.0

    if not keep_audio and audio_dir.exists():
        for mp3 in audio_dir.glob("*.mp3"):
            size_mb = mp3.stat().st_size / (1024 * 1024)
            try:
                mp3.unlink()
                removed += 1
                freed_mb += size_mb
                print(f"  [purge] {mp3.name} ({size_mb:.1f} MB)")
            except OSError as e:
                print(f"  [warn] Could not remove {mp3.name}: {e}")

    # Remove intermediate .md files (keep .final.md only)
    if notes_dir.exists():
        for md in notes_dir.glob("*.md"):
            if not md.name.endswith(".final.md"):
                try:
                    md.unlink()
                    removed += 1
                    print(f"  [purge] intermediate {md.name}")
                except OSError as e:
                    print(f"  [warn] Could not remove {md.name}: {e}")

    if removed:
        print(f"  Cleaned {removed} files, freed {freed_mb:.1f} MB")
    else:
        print("  Nothing to clean")


# ---------------------------------------------------------------------------
# URL-mode pipeline (one-off clips via yt-dlp — bypasses RSS + manifest)
# ---------------------------------------------------------------------------

class _UrlEpisode:
    """Episode-like adapter so existing note-gen + write steps work for URL mode.

    Mirrors the relevant fields of rss.Episode without participating in the
    show-based manifest.
    """

    def __init__(self, clip, source_label: str, source_url: str):
        self.id = clip.id
        self.title = _derive_clean_title(clip)
        self.published = clip.published
        self.audio_url = source_url  # original web URL, not the audio CDN URL
        self.duration = clip.duration
        self.description = clip.description
        self.link = source_url
        self.show_name = source_label

    def safe_filename(self) -> str:
        # Same char set as rss.Episode.safe_filename — includes Obsidian
        # wikilink-breaking chars (#, ^, [, ])
        safe_title = re.sub(r'[<>:"/\\|?*\[\]#^]', '', self.title)
        safe_title = safe_title.strip('. ')
        if len(safe_title) > 120:
            safe_title = safe_title[:120].rsplit(' ', 1)[0]
        if not safe_title:
            safe_title = self.id
        return f"{self.published} - {safe_title}"

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "title": self.title,
            "published": self.published,
            "audio_url": self.audio_url,
            "duration": self.duration,
            "description": self.description,
            "link": self.link,
            "show_name": self.show_name,
        }


def _derive_clean_title(clip) -> str:
    """Build a readable title for the note from yt-dlp metadata.

    yt-dlp titles for X tweets look like "uploader - <description>".
    Strip the uploader prefix and keep the first sentence-ish chunk.
    """
    raw = (clip.title or "").strip()
    uploader = (clip.uploader or "").strip()

    # Strip "<uploader> - " prefix that yt-dlp adds for X
    if uploader and raw.lower().startswith(uploader.lower() + " - "):
        raw = raw[len(uploader) + 3:].strip()

    # Drop trailing t.co URLs
    raw = re.sub(r"\s*https?://t\.co/\S+\s*$", "", raw).strip()

    # Take first sentence-ish chunk (split on newlines, then on "。" or ". ")
    first_line = raw.split("\n", 1)[0].strip()
    for sep in ("。", ". ", "！", "？"):
        if sep in first_line:
            first_line = first_line.split(sep, 1)[0].strip() + sep.strip()
            break

    if not first_line:
        first_line = f"{clip.extractor or 'clip'} {clip.id}"

    if len(first_line) > 100:
        first_line = first_line[:100].rsplit(" ", 1)[0] + "…"

    return first_line


def _source_label_for(clip) -> str:
    """Folder/group label for clips, e.g. "X — @servasyy_ai" or "YouTube — channel"."""
    extractor = (clip.extractor or "").lower()
    platform_map = {
        "twitter": "X",
        "x": "X",
        "youtube": "YouTube",
        "vimeo": "Vimeo",
        "tiktok": "TikTok",
        "instagram": "Instagram",
    }
    platform = "Clip"
    for key, label in platform_map.items():
        if key in extractor:
            platform = label
            break

    handle = clip.uploader_id or clip.uploader or "unknown"
    handle = handle.lstrip("@")
    return f"{platform} — @{handle}"


def run_url_pipeline(args: argparse.Namespace) -> None:
    """One-off pipeline: download a single web video via yt-dlp, transcribe, write note.

    Bypasses RSS detection and the manifest. Used when --url is provided.
    """
    config = load_config()

    print("╔══════════════════════════════════════════════════════╗")
    print("║   podcast-to-obsidian — URL Mode (one-off clip)     ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  URL : {args.url}")
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    # Override config with CLI args
    if args.model:
        config["whisper_model"] = args.model
    if args.device:
        config["whisper_device"] = args.device

    work_dir = SKILL_DIR / config.get("work_dir", ".work")
    work_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 1: Download via yt-dlp ---
    print("\n=== Step 1: Download Audio (yt-dlp) ===\n")
    try:
        yt = _get_yt_downloader()
        clip = yt.download_clip(url=args.url, output_dir=work_dir / "audio")
    except Exception as e:
        import traceback
        print(f"  [error] yt-dlp download failed: {e}")
        traceback.print_exc()
        return

    source_label = args.show_name or _source_label_for(clip)
    if args.title:
        # Manual title override — bypass auto-derivation
        clip_title_override = args.title
        episode = _UrlEpisode(clip, source_label, args.url)
        episode.title = clip_title_override
    else:
        episode = _UrlEpisode(clip, source_label, args.url)

    print(f"  Title    : {episode.title}")
    print(f"  Uploader : {clip.uploader} (@{clip.uploader_id})")
    print(f"  Published: {episode.published}")
    print(f"  Duration : {episode.duration or '(unknown)'}")
    print(f"  Folder   : {source_label}")

    if args.check_only:
        print("\n[check-only] Stopping before transcription.")
        return

    # --- Step 2: Transcribe ---
    transcribed = step_transcribe(
        downloaded=[(episode, clip.audio_path)],
        work_dir=work_dir,
        model=config.get("whisper_model", "large-v3"),
        device=config.get("whisper_device", "auto"),
        language=config.get("whisper_language"),
    )
    if not transcribed:
        print("\n[error] Transcription produced no output.")
        return

    if args.transcribe_only:
        print("\n=== Transcript ready ===")
        for ep, audio_path, transcript_path, meta in transcribed:
            print(f"  Transcript: {transcript_path}")
        return

    # --- Step 3: Generate note ---
    notes = step_generate_notes(
        transcribed=transcribed,
        config=config,
        work_dir=work_dir,
        use_ai=not args.no_ai,
    )
    if not notes:
        print("\n[error] Note generation failed.")
        return

    # --- Step 4: Inject source_url into frontmatter + write to vault ---
    clips_folder = args.clips_folder or config.get("clips_folder", "Clips")
    safe_show = re.sub(r'[<>:"/\\|?*]', '', source_label).strip()

    if args.dry_run:
        print("\n=== Step 4: Write to Vault (dry-run) ===\n")
        for ep, content, _vault_path, _transcript_src in notes:
            vault_path = f"{clips_folder}/{safe_show}/{ep.safe_filename()}.md"
            content = _inject_source_url(content, args.url)
            print(f"  [dry-run] Would write: {vault_path}")
            print(f"            ({len(content)} chars)")
        return

    print("\n=== Step 4: Write to Vault ===\n")
    try:
        ob = Obsidian()
    except Exception as e:
        print(f"  [error] Cannot connect to Obsidian: {e}")
        return

    written = 0
    for ep, content, _old_vault_path, _transcript_src in notes:
        vault_path = f"{clips_folder}/{safe_show}/{ep.safe_filename()}.md"
        content = _inject_source_url(content, args.url)
        print(f"  [write] {vault_path}")
        try:
            result = ob.create(path=vault_path, content=content, overwrite=True)
            if result.ok:
                written += 1
                print(f"  [ok] Written")
            else:
                print(f"  [error] Obsidian write failed: {result.stderr}")
        except Exception as e:
            print(f"  [error] Write exception: {e}")

    # --- Cleanup ---
    if written > 0:
        step_cleanup(work_dir=work_dir, written_episodes=[], keep_audio=args.keep_audio)

    print(f"\n{'='*60}")
    print(f"  URL Pipeline Complete — {written}/{len(notes)} note(s) written")
    print(f"{'='*60}\n")


def _inject_source_url(note_content: str, source_url: str) -> str:
    """Inject `source_url` field into note frontmatter (after `source:` line)."""
    if "source_url:" in note_content:
        return note_content
    pattern = re.compile(r"^(source: podcast-to-obsidian)$", re.MULTILINE)
    # Single-quoted YAML: no backslash escaping (the Obsidian CLI writer strips
    # backslash escapes from content). Only ' needs doubling. Function
    # replacement so re.sub does not reinterpret the URL.
    safe = "'" + str(source_url).replace("'", "''") + "'"
    return pattern.sub(lambda m: f"{m.group(1)}\nsource_url: {safe}", note_content, count=1)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(args: argparse.Namespace) -> None:
    """Execute the full podcast-to-obsidian pipeline."""
    config = load_config()
    manifest = Manifest(CONFIG_DIR / "podcast-manifest.json")

    print("╔══════════════════════════════════════════════════════╗")
    print("║       podcast-to-obsidian — Pipeline Runner         ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    stats = manifest.stats()
    print(f"  Manifest: {stats['shows']} shows, {stats['completed']} episodes processed")

    # Override config with CLI args
    if args.model:
        config["whisper_model"] = args.model
    if args.device:
        config["whisper_device"] = args.device
    if args.max_episodes is not None:
        config["max_episodes"] = args.max_episodes

    # Manual backfill overrides.  Default behaviour is new releases only;
    # reaching into a show's archive must always be an explicit request.
    if getattr(args, "ignore_watermark", False):
        config["only_new_releases"] = False
        config["max_age_days"] = 0
        print("\n  [backfill] Watermark ignored — considering all episodes in window")
    elif getattr(args, "backfill_since", None):
        config["only_new_releases"] = False
        config["backfill_since"] = args.backfill_since
        print(f"\n  [backfill] Considering episodes published on or after {args.backfill_since}")

    # Work directory
    work_dir = SKILL_DIR / config.get("work_dir", ".work")
    work_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 1: Detect ---
    new_episodes = step_detect_episodes(
        config=config,
        manifest=manifest,
        show_filter=args.show,
    )

    if not new_episodes:
        print("\n✓ No new episodes to process. All caught up!")
        return

    # --- Episode filter ---
    if args.episode:
        needle = args.episode.lower()
        filtered = {}
        for show_id, episodes in new_episodes.items():
            matched = [ep for ep in episodes if needle in ep.title.lower()]
            if matched:
                filtered[show_id] = matched
        if not filtered:
            print(f"\n✗ No episodes matching '{args.episode}' found in new episodes.")
            return
        total_before = sum(len(eps) for eps in new_episodes.values())
        total_after = sum(len(eps) for eps in filtered.values())
        print(f"\n  --episode filter: {total_after}/{total_before} episodes match '{args.episode}'")
        new_episodes = filtered

    # --- Check-only mode ---
    if args.check_only:
        print("\n=== New Episodes Available ===\n")
        for show_id, episodes in new_episodes.items():
            show_data = manifest.get_show(show_id)
            show_name = show_data["name"] if show_data else show_id
            print(f"  {show_name}:")
            for ep in episodes:
                print(f"    • {ep.published} — {ep.title}")
        return

    # --- Process each show's episodes ---
    total_written = 0
    for show_id, episodes in new_episodes.items():
        show_data = manifest.get_show(show_id)
        show_name = show_data["name"] if show_data else show_id
        print(f"\n{'='*60}")
        print(f"  Processing: {show_name} ({len(episodes)} episodes)")
        print(f"{'='*60}")

        # Step 2: Download
        downloaded = step_download(episodes, work_dir)
        if not downloaded:
            print(f"  [skip] No audio downloaded for {show_name}")
            continue

        # Step 3: Transcribe
        transcribed = step_transcribe(
            downloaded=downloaded,
            work_dir=work_dir,
            model=config.get("whisper_model", "large-v3"),
            device=config.get("whisper_device", "auto"),
            language=config.get("whisper_language"),
        )
        if not transcribed:
            print(f"  [skip] No transcriptions completed for {show_name}")
            continue

        # --- Transcribe-only mode: print paths and stop ---
        if args.transcribe_only:
            summaries_dir = work_dir / "summaries"
            summaries_dir.mkdir(parents=True, exist_ok=True)
            print(f"\n=== Transcripts ready for summarization ===")
            for ep, audio_path, transcript_path, meta in transcribed:
                summary_path = summaries_dir / (transcript_path.stem + ".json")
                print(f"  Episode : {ep.title}")
                print(f"  Transcript: {transcript_path}")
                print(f"  Summary → : {summary_path}")
                print()
            continue

        # Step 4: Generate notes
        notes = step_generate_notes(
            transcribed=transcribed,
            config=config,
            work_dir=work_dir,
            use_ai=not args.no_ai,
        )
        if not notes:
            print(f"  [skip] No notes generated for {show_name}")
            continue

        # Step 5: Write to vault
        written = step_write_to_vault(
            notes=notes,
            config=config,
            manifest=manifest,
            show_id=show_id,
            dry_run=args.dry_run,
        )
        total_written += written

    # --- Cleanup ---
    if total_written > 0 and not args.dry_run:
        step_cleanup(
            work_dir=work_dir,
            written_episodes=[],
            keep_audio=args.keep_audio,
        )

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"  Pipeline Complete")
    print(f"{'='*60}")
    stats = manifest.stats()
    print(f"  Episodes written this run: {total_written}")
    print(f"  Manifest totals: {stats['shows']} shows, {stats['completed']} completed, {stats['failed']} failed")
    print()


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_add_show(args: argparse.Namespace) -> None:
    """Add a new show to config and manifest."""
    config = load_config()
    manifest = Manifest(CONFIG_DIR / "podcast-manifest.json")

    name = args.name
    rss_url = args.rss
    show_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

    print(f"Adding show: {name}")
    print(f"  ID: {show_id}")
    print(f"  RSS: {rss_url}")

    # Add to config.json
    config.setdefault("shows", {})[show_id] = {
        "name": name,
        "rss_url": rss_url,
        "enabled": True,
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

    # Register in manifest
    manifest.add_show(show_id=show_id, name=name, rss_url=rss_url)
    manifest.save()

    # Verify feed
    try:
        episodes = parse_feed(rss_url, max_episodes=3)
        print(f"  Feed verified: {len(episodes)} recent episodes found")
        for ep in episodes[:3]:
            print(f"    • {ep.published} — {ep.title}")
    except Exception as e:
        print(f"  [warn] Could not verify feed: {e}")

    print(f"\n✓ Show '{name}' added. Run the pipeline to process episodes.")


def cmd_seed_watermarks(args: argparse.Namespace) -> None:
    """Seed each show's release watermark from its newest completed episode.

    Lets an existing manifest adopt new-releases-only detection without the
    pipeline suddenly discovering (and reprocessing) a show's back catalogue.
    """
    manifest = Manifest(CONFIG_DIR / "podcast-manifest.json")

    print("\n=== Seed Release Watermarks ===\n")

    existing = {
        show_id: show.get("latest_published")
        for show_id, show in manifest._data.get("shows", {}).items()
        if show.get("latest_published")
    }
    seeded = manifest.seed_watermarks()

    for show_id, watermark in sorted(seeded.items()):
        print(f"  [seed] {show_id}: {watermark}")
    for show_id, watermark in sorted(existing.items()):
        print(f"  [keep] {show_id}: {watermark} (already set)")

    unseeded = [
        show_id
        for show_id, show in manifest._data.get("shows", {}).items()
        if not show.get("latest_published")
    ]
    for show_id in sorted(unseeded):
        print(f"  [none] {show_id}: no completed episodes — will use max_age_days on first run")

    if seeded:
        manifest.save()
        print(f"\n✓ Seeded {len(seeded)} shows. Episodes at or before each watermark "
              f"will no longer be auto-detected.")
    else:
        print("\n✓ Nothing to seed — all shows already have a watermark.")


def cmd_set_watermark(args: argparse.Namespace) -> None:
    """Force the release watermark for every show (or one) to a given date.

    `--set-watermark today` draws a line in the sand: everything currently in
    every feed becomes historical, and only genuinely future releases are
    auto-fetched.  Backfill stays available via --backfill-since.
    """
    raw = (args.set_watermark or "").strip().lower()
    if raw in ("today", "now"):
        target = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        target = args.set_watermark.strip()
        try:
            datetime.strptime(target, "%Y-%m-%d")
        except ValueError:
            print(f"\n✗ Invalid date '{target}'. Use YYYY-MM-DD or 'today'.")
            return

    manifest = Manifest(CONFIG_DIR / "podcast-manifest.json")
    shows = manifest._data.get("shows", {})

    print(f"\n=== Set Release Watermark → {target} ===\n")

    changed = 0
    for show_id, show in sorted(shows.items()):
        if args.show:
            needle = args.show.lower()
            if needle not in show_id.lower() and needle not in show.get("name", "").lower():
                continue

        current = show.get("latest_published", "") or ""
        if current and target < current and not args.force:
            print(f"  [keep] {show_id}: {current} (would lower to {target}; use --force)")
            continue
        if current == target:
            print(f"  [same] {show_id}: {target}")
            continue

        show["latest_published"] = target
        changed += 1
        print(f"  [set]  {show_id}: {current or '(none)'} → {target}")

    if changed:
        manifest.save()
        print(f"\n✓ Watermark set on {changed} shows. Episodes published on or before "
              f"{target} will no longer be auto-detected.")
        print("  Backfill manually with: --backfill-since YYYY-MM-DD [--show \"Name\"]")
    else:
        print("\n✓ No changes made.")


def cmd_list_shows(args: argparse.Namespace) -> None:
    """List all tracked shows."""
    manifest = Manifest(CONFIG_DIR / "podcast-manifest.json")
    shows = manifest.list_shows()

    if not shows:
        print("No shows tracked yet. Add one with --add-show --name 'X' --rss 'URL'")
        return

    print(f"\n{'='*60}")
    print(f"  Tracked Podcasts ({len(shows)} shows)")
    print(f"{'='*60}\n")
    for show in shows:
        status = "✓" if show["completed"] > 0 else "○"
        print(f"  {status} {show['name']}")
        print(f"    Episodes: {show['completed']} completed, {show['failed']} failed")
        if show.get("rss_url"):
            print(f"    RSS: {show['rss_url'][:60]}...")
        print()


def cmd_retry_failed(args: argparse.Namespace) -> None:
    """Retry failed episodes."""
    manifest = Manifest(CONFIG_DIR / "podcast-manifest.json")
    failed = manifest.get_failed_episodes()

    if not failed:
        print("No failed episodes to retry.")
        return

    print(f"\nRetrying {len(failed)} failed episodes...")
    for ep in failed:
        print(f"  • {ep['show_name']}: {ep.get('title', ep['episode_id'])}")
        print(f"    Error: {ep.get('error', 'unknown')}")

    # Reset failed status so pipeline picks them up
    for ep in failed:
        show = manifest.get_show(ep["show_id"])
        if show and "episodes" in show:
            if ep["episode_id"] in show["episodes"]:
                del show["episodes"][ep["episode_id"]]
    manifest.save()

    print("\nFailed episodes reset. Run the pipeline to retry them.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="podcast-to-obsidian — Podcast → Transcript → Obsidian pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Pipeline options
    parser.add_argument("--check-only", action="store_true",
                        help="Only detect new episodes, don't process")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run pipeline but don't write to vault")
    parser.add_argument("--show", type=str, default=None,
                        help="Process only this show (by name)")
    parser.add_argument("--model", type=str, default=None,
                        help="Whisper model override (tiny/base/small/medium/large-v3)")
    parser.add_argument("--device", type=str, default=None,
                        help="Compute device (auto/cpu/cuda)")
    parser.add_argument("--no-ai", action="store_true",
                        help="Skip AI summaries, use template-only mode")
    parser.add_argument("--transcribe-only", action="store_true",
                        help="Stop after transcription; print paths for orchestrator summarization")
    parser.add_argument("--max-episodes", type=int, default=None,
                        help="Max episodes to process per show (overrides config)")
    parser.add_argument("--episode", type=str, default=None,
                        help="Filter to episodes matching this title substring (case-insensitive)")

    # URL mode (one-off clips via yt-dlp — bypasses RSS + manifest)
    parser.add_argument("--url", type=str, default=None,
                        help="One-off mode: download + transcribe a single web video (X, YouTube, etc.) via yt-dlp")
    parser.add_argument("--clips-folder", type=str, default=None,
                        help="Vault subfolder for --url notes (default: Clips)")
    parser.add_argument("--show-name", type=str, default=None,
                        help="Override the auto-derived source label/folder (e.g. \"X — @servasyy_ai\")")
    parser.add_argument("--title", type=str, default=None,
                        help="Override the auto-derived note title (URL mode only)")

    # Subcommands
    parser.add_argument("--add-show", action="store_true",
                        help="Add a new show")
    parser.add_argument("--name", type=str, default=None,
                        help="Show name (for --add-show)")
    parser.add_argument("--rss", type=str, default=None,
                        help="RSS feed URL (for --add-show)")
    parser.add_argument("--list-shows", action="store_true",
                        help="List all tracked shows")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Retry failed episodes")
    parser.add_argument("--keep-audio", action="store_true",
                        help="Don't purge .mp3 files after successful run")
    parser.add_argument("--backfill-since", type=str, default=None, metavar="YYYY-MM-DD",
                        help="Manual backfill: also consider episodes published on or "
                             "after this date, ignoring the release watermark. "
                             "Combine with --show and --episode to target precisely.")
    parser.add_argument("--ignore-watermark", action="store_true",
                        help="Manual backfill: consider every episode in the detection "
                             "window regardless of publish date. Use with care.")
    parser.add_argument("--seed-watermarks", action="store_true",
                        help="Set each show's release watermark from its newest completed "
                             "episode, then exit. Adopts new-releases-only behaviour on an "
                             "existing manifest without reprocessing anything.")
    parser.add_argument("--set-watermark", type=str, default=None, metavar="YYYY-MM-DD|today",
                        help="Force the release watermark for every show (or just --show X) "
                             "to a date, then exit. '--set-watermark today' draws a line in "
                             "the sand: nothing currently in any feed is auto-fetched again, "
                             "only future releases. Never lowers an existing watermark unless "
                             "--force is given.")
    parser.add_argument("--force", action="store_true",
                        help="Allow --set-watermark to lower an existing watermark")

    args = parser.parse_args()

    # Tee all output to .work/logs/<timestamp>.log before doing any work, so
    # unattended and detached runs always leave a debuggable artifact.
    log_path = _start_run_log()

    try:
        # Route to subcommands
        if args.add_show:
            if not args.name or not args.rss:
                parser.error("--add-show requires --name and --rss")
            cmd_add_show(args)
        elif args.seed_watermarks:
            cmd_seed_watermarks(args)
        elif args.set_watermark:
            cmd_set_watermark(args)
        elif args.list_shows:
            cmd_list_shows(args)
        elif args.retry_failed:
            cmd_retry_failed(args)
        elif args.url:
            run_url_pipeline(args)
        else:
            run_pipeline(args)
    except Exception:
        # Make sure the traceback reaches the log file, not just the console.
        import traceback
        traceback.print_exc()
        raise
    finally:
        if log_path:
            print(f"\n  [log] {log_path}")


if __name__ == "__main__":
    main()
