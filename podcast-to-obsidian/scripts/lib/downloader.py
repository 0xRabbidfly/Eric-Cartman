"""Audio downloader — fetch podcast audio from RSS enclosure URLs.

Downloads audio files to the work directory with progress tracking
and resume support.
"""

import hashlib
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


def download_audio(
    audio_url: str,
    output_dir: Path,
    filename: str,
    timeout: int = 300,
) -> Path:
    """Download audio file from URL.

    Args:
        audio_url: Direct URL to the audio file (RSS enclosure).
        output_dir: Directory to save the file.
        filename: Desired filename (without extension).
        timeout: Download timeout in seconds.

    Returns:
        Path to the downloaded audio file.

    Raises:
        urllib.error.URLError: On network errors.
        TimeoutError: If download exceeds timeout.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine extension from URL or default to .mp3
    ext = _guess_extension(audio_url)
    safe_name = _safe_filename(filename)
    output_path = output_dir / f"{safe_name}{ext}"

    # Skip if already downloaded (resume support)
    if output_path.exists() and output_path.stat().st_size > 0:
        print(f"  [skip] Already downloaded: {output_path.name}")
        return output_path

    # Partial download support
    tmp_path = output_path.with_suffix(output_path.suffix + ".part")

    print(f"  [download] {audio_url[:80]}...")
    req = urllib.request.Request(
        audio_url,
        headers={
            "User-Agent": "podcast-to-obsidian/1.0",
            "Accept": "audio/*, */*",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024  # 64 KB chunks

            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    _print_progress(downloaded, total)

        # Move tmp to final
        tmp_path.replace(output_path)
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"\n  [done] {output_path.name} ({size_mb:.1f} MB)")
        return output_path

    except Exception:
        # Clean up partial on error
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _guess_extension(url: str) -> str:
    """Guess audio file extension from URL."""
    # Strip query params
    clean = url.split("?")[0].split("#")[0]
    lower = clean.lower()
    for ext in (".mp3", ".m4a", ".ogg", ".opus", ".wav", ".aac", ".flac"):
        if lower.endswith(ext):
            return ext
    return ".mp3"


def _safe_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    safe = re.sub(r'[<>:"/\\|?*]', '', name)
    safe = safe.strip('. ')
    if len(safe) > 150:
        safe = safe[:150].rsplit(' ', 1)[0]
    if not safe:
        safe = "episode"
    return safe


def _print_progress(downloaded: int, total: int) -> None:
    """Print download progress bar."""
    if total > 0:
        pct = (downloaded / total) * 100
        bar_len = 30
        filled = int(bar_len * downloaded / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        mb_down = downloaded / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        sys.stdout.write(f"\r  [{bar}] {pct:5.1f}% ({mb_down:.1f}/{mb_total:.1f} MB)")
        sys.stdout.flush()
    else:
        mb_down = downloaded / (1024 * 1024)
        sys.stdout.write(f"\r  [downloading] {mb_down:.1f} MB")
        sys.stdout.flush()
