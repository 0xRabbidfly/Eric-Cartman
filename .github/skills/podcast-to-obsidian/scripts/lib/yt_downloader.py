"""yt-dlp downloader — fetch audio from arbitrary web video URLs.

Wraps yt-dlp to support X/Twitter, YouTube, Vimeo, and any other site
yt-dlp can handle. Extracts audio as .mp3 using ffmpeg postprocessing.

Used by the pipeline when --url is provided instead of running through
the RSS-based show detection flow.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class YtClip:
    """Metadata for a yt-dlp-downloaded clip.

    Plain class (not @dataclass) because this module is loaded via
    importlib.util.spec_from_file_location, which doesn't populate
    sys.modules — and @dataclass fails in that setup.
    """

    def __init__(
        self,
        id: str,
        title: str,
        uploader: str,
        uploader_id: str,
        published: str,
        duration: str,
        duration_seconds: int,
        description: str,
        source_url: str,
        audio_path: Path,
        extractor: str,
    ):
        self.id = id
        self.title = title
        self.uploader = uploader
        self.uploader_id = uploader_id
        self.published = published  # YYYY-MM-DD
        self.duration = duration  # HH:MM:SS
        self.duration_seconds = duration_seconds
        self.description = description
        self.source_url = source_url
        self.audio_path = audio_path
        self.extractor = extractor  # e.g. "twitter", "youtube"

    def safe_filename(self) -> str:
        """Filesystem-safe filename from clip metadata."""
        safe_title = re.sub(r'[<>:"/\\|?*]', '', self.title)
        safe_title = safe_title.strip('. ')
        if len(safe_title) > 120:
            safe_title = safe_title[:120].rsplit(' ', 1)[0]
        if not safe_title:
            safe_title = self.id
        return f"{self.published} - {safe_title}"


def _format_duration(seconds: Optional[float]) -> str:
    """Convert seconds to HH:MM:SS."""
    if not seconds:
        return ""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _format_date(upload_date: Optional[str], timestamp: Optional[int]) -> str:
    """Convert yt-dlp date fields to YYYY-MM-DD."""
    if upload_date and len(upload_date) == 8:
        try:
            return datetime.strptime(upload_date, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
    if timestamp:
        try:
            return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass
    return datetime.now().strftime("%Y-%m-%d")


def _safe_outtmpl_base(info: Dict[str, Any]) -> str:
    """Produce a safe filename stem for yt-dlp's outtmpl."""
    raw_id = str(info.get("id") or "clip")
    safe = re.sub(r'[<>:"/\\|?*]', '', raw_id)
    return safe or "clip"


def probe_clip(url: str) -> Dict[str, Any]:
    """Fetch metadata without downloading.

    Useful for confirming title/uploader before pulling audio.
    If the URL resolves to a playlist (X tweets can contain multiple videos),
    returns the first entry. The parent playlist's metadata (uploader, date)
    is merged in if missing on the entry.
    """
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "playlist_items": "1",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        if not entries:
            raise RuntimeError(f"yt-dlp returned an empty playlist for {url}")
        entry = entries[0]
        # Merge parent metadata into entry for missing fields
        for key in ("uploader", "uploader_id", "upload_date", "timestamp",
                    "description", "webpage_url", "extractor", "extractor_key"):
            if not entry.get(key) and info.get(key):
                entry[key] = info[key]
        return entry

    return info


def download_clip(
    url: str,
    output_dir: Path,
) -> YtClip:
    """Download audio from a web video URL using yt-dlp.

    Extracts the best audio stream and converts to .mp3 via ffmpeg.

    Args:
        url: Any URL supported by yt-dlp (X/Twitter, YouTube, etc.)
        output_dir: Where to write the .mp3 file.

    Returns:
        YtClip with metadata and audio_path.

    Raises:
        RuntimeError: If yt-dlp fails or ffmpeg is missing.
    """
    import yt_dlp

    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg not found on PATH — required to extract audio. "
            "Install with: winget install Gyan.FFmpeg"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    # First pass: probe to get a stable id we can use for the filename
    print(f"  [probe] {url}")
    info_probe = probe_clip(url)
    clip_id = _safe_outtmpl_base(info_probe)

    outtmpl = str(output_dir / f"{clip_id}.%(ext)s")
    expected_mp3 = output_dir / f"{clip_id}.mp3"

    # Resume support — skip if already downloaded
    if expected_mp3.exists() and expected_mp3.stat().st_size > 0:
        print(f"  [skip] Already downloaded: {expected_mp3.name}")
        info = info_probe
    else:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "no_progress": True,
            "noplaylist": True,
            "playlist_items": "1",
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "progress_hooks": [_progress_hook],
        }

        print(f"  [download] extracting audio via yt-dlp...")
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # If we got a playlist back, drill down to the first entry (same as probe_clip)
        if info and info.get("_type") == "playlist":
            entries = info.get("entries") or []
            if not entries:
                raise RuntimeError(f"yt-dlp returned an empty playlist for {url}")
            parent = info
            info = entries[0]
            for key in ("uploader", "uploader_id", "upload_date", "timestamp",
                        "description", "webpage_url", "extractor", "extractor_key"):
                if not info.get(key) and parent.get(key):
                    info[key] = parent[key]

        if not expected_mp3.exists():
            # yt-dlp may have written a different extension; find the newest file
            candidates = sorted(
                output_dir.glob(f"{clip_id}.*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not candidates:
                raise RuntimeError(f"yt-dlp did not produce an output file for {url}")
            expected_mp3 = candidates[0]

        size_mb = expected_mp3.stat().st_size / (1024 * 1024)
        print(f"  [done] {expected_mp3.name} ({size_mb:.1f} MB)")

    return YtClip(
        id=str(info.get("id") or clip_id),
        title=info.get("title") or info.get("description", "Untitled")[:80] or "Untitled",
        uploader=info.get("uploader") or info.get("uploader_id") or "",
        uploader_id=info.get("uploader_id") or "",
        published=_format_date(info.get("upload_date"), info.get("timestamp")),
        duration=_format_duration(info.get("duration")),
        duration_seconds=int(info.get("duration") or 0),
        description=(info.get("description") or "").strip(),
        source_url=info.get("webpage_url") or url,
        audio_path=expected_mp3,
        extractor=info.get("extractor_key") or info.get("extractor") or "",
    )


def _progress_hook(d: Dict[str, Any]) -> None:
    """Lightweight progress reporter for yt-dlp."""
    status = d.get("status")
    if status == "downloading":
        pct = d.get("_percent_str", "").strip()
        speed = d.get("_speed_str", "").strip()
        if pct:
            print(f"\r  [{pct}] {speed}", end="", flush=True)
    elif status == "finished":
        print()  # newline after progress
