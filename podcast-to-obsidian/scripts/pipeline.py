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
from datetime import datetime, timezone
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
# Load .env (OPENAI_API_KEY, SPOTIFY_CLIENT_SECRET, etc.)
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    """Load key=value pairs from .env into os.environ (no external deps)."""
    env_file = SKILL_DIR / ".env"
    if not env_file.exists():
        return
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
        "whisper_model": "base",
        "whisper_device": "auto",
        "whisper_language": None,
        "max_episodes": 5,
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
            episodes = parse_feed(rss_url, max_episodes=config.get("max_episodes", 5) * 2)
            print(f"  [found] {len(episodes)} episodes in feed")

            # Filter to new episodes only
            new = []
            for ep in episodes:
                if not manifest.is_processed(show_id, ep.id):
                    new.append(ep)
                    ep.show_name = show_name

            if new:
                # Respect max_episodes limit
                max_ep = config.get("max_episodes", 5)
                new = new[:max_ep]
                new_episodes[show_id] = new
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
    model: str = "base",
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
) -> List[Tuple[Episode, str, str]]:
    """Generate Obsidian notes from transcripts.

    Checks .work/summaries/<name>.json for a pre-generated summary first
    (written by the orchestrator/AI).  Falls back to template-only if absent.

    Returns: [(Episode, note_content, vault_path), ...]
    """
    print("\n=== Step 4: Generate Notes ===\n")
    results = []
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

            # 2. If no pre-generated summary and use_ai, try OpenAI API
            if ai_summary is None and use_ai:
                api_key = os.environ.get("OPENAI_API_KEY")
                if api_key:
                    ai_summary = generate_ai_summary(
                        transcript_text=transcript_text,
                        episode_title=ep.title,
                        show_name=ep.show_name,
                        api_key=api_key,
                    )
                else:
                    print(f"  [info] No summary JSON found — run orchestrator or set OPENAI_API_KEY")

            # Generate note
            note_content = generate_note(
                episode=ep.to_dict(),
                transcript_text=transcript_text,
                ai_summary=ai_summary,
            )

            # Vault path
            safe_show = re.sub(r'[<>:"/\\|?*]', '', ep.show_name).strip()
            vault_path = f"{podcasts_folder}/{safe_show}/{ep.safe_filename()}.md"

            results.append((ep, note_content, vault_path))
            print(f"  [ok] → {vault_path}")

        except Exception as e:
            print(f"  [error] Failed to generate note for '{ep.title}': {e}")

    print(f"\n  Generated: {len(results)}/{len(transcribed)}")
    return results


def step_write_to_vault(
    notes: List[Tuple[Episode, str, str]],
    config: Dict[str, Any],
    manifest: Manifest,
    show_id: str,
    dry_run: bool = False,
) -> int:
    """Write generated notes to Obsidian vault.

    Returns: Number of successfully written notes.
    """
    print("\n=== Step 5: Write to Vault ===\n")
    success = 0

    if dry_run:
        for ep, content, vault_path in notes:
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

    for ep, content, vault_path in notes:
        try:
            print(f"  [write] {vault_path}")
            result = ob.create(path=vault_path, content=content, overwrite=True)

            if result.ok:
                # Update manifest ONLY after successful write
                transcript_path = f"{podcasts_folder}/{ep.show_name}/transcripts/{ep.safe_filename()}.txt"
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
            model=config.get("whisper_model", "base"),
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

    args = parser.parse_args()

    # Route to subcommands
    if args.add_show:
        if not args.name or not args.rss:
            parser.error("--add-show requires --name and --rss")
        cmd_add_show(args)
    elif args.list_shows:
        cmd_list_shows(args)
    elif args.retry_failed:
        cmd_retry_failed(args)
    else:
        run_pipeline(args)


if __name__ == "__main__":
    main()
