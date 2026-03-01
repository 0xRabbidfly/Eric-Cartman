"""Manifest manager — persistent tracking of processed podcast episodes.

The manifest is the system's memory. It tracks which episodes have been
downloaded, transcribed, and written to the vault, preventing duplicate
processing across runs.

Location: config/podcast-manifest.json (relative to skill root)
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Manifest schema
# ---------------------------------------------------------------------------
# {
#   "version": 1,
#   "shows": {
#     "<show_id>": {
#       "name": "Show Name",
#       "rss_url": "https://...",
#       "spotify_id": "...",        # optional
#       "episodes": {
#         "<episode_id>": {
#           "title": "Episode Title",
#           "published": "2026-02-20",
#           "audio_url": "https://...",
#           "transcript_path": "Podcasts/Show/2026-02-20 - Ep.txt",
#           "note_path": "Podcasts/Show/2026-02-20 - Ep.md",
#           "processed_at": "2026-02-28T12:30:00Z",
#           "status": "completed"    # completed | failed | skipped
#         }
#       }
#     }
#   }
# }

MANIFEST_VERSION = 1


class Manifest:
    """Persistent JSON manifest for tracking processed podcast episodes."""

    def __init__(self, manifest_path: Optional[Path] = None):
        if manifest_path is None:
            skill_dir = Path(__file__).parent.parent.parent.resolve()
            manifest_path = skill_dir / "config" / "podcast-manifest.json"
        self.path = Path(manifest_path)
        self._data: Dict[str, Any] = self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        """Load manifest from disk, or create empty scaffold."""
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("version", 0) < MANIFEST_VERSION:
                    data = self._migrate(data)
                return data
            except (json.JSONDecodeError, KeyError):
                # Corrupted — back up and start fresh
                backup = self.path.with_suffix(".json.bak")
                if self.path.exists():
                    self.path.rename(backup)
                return self._empty()
        return self._empty()

    def save(self) -> None:
        """Persist manifest to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        tmp.replace(self.path)

    @staticmethod
    def _empty() -> Dict[str, Any]:
        return {"version": MANIFEST_VERSION, "shows": {}}

    @staticmethod
    def _migrate(data: Dict) -> Dict:
        """Migrate older manifest formats to current version."""
        data["version"] = MANIFEST_VERSION
        # Future migrations go here
        return data

    # ------------------------------------------------------------------
    # Shows
    # ------------------------------------------------------------------

    def list_shows(self) -> List[Dict[str, Any]]:
        """Return list of all tracked shows with episode counts."""
        result = []
        for show_id, show in self._data.get("shows", {}).items():
            episodes = show.get("episodes", {})
            completed = sum(1 for e in episodes.values() if e.get("status") == "completed")
            result.append({
                "id": show_id,
                "name": show.get("name", show_id),
                "rss_url": show.get("rss_url", ""),
                "spotify_id": show.get("spotify_id", ""),
                "total_episodes": len(episodes),
                "completed": completed,
                "failed": sum(1 for e in episodes.values() if e.get("status") == "failed"),
            })
        return result

    def add_show(
        self,
        show_id: str,
        name: str,
        rss_url: str,
        spotify_id: str = "",
    ) -> None:
        """Register a new show in the manifest."""
        shows = self._data.setdefault("shows", {})
        if show_id not in shows:
            shows[show_id] = {
                "name": name,
                "rss_url": rss_url,
                "spotify_id": spotify_id,
                "episodes": {},
            }
        else:
            # Update metadata, preserve episodes
            shows[show_id]["name"] = name
            if rss_url:
                shows[show_id]["rss_url"] = rss_url
            if spotify_id:
                shows[show_id]["spotify_id"] = spotify_id

    def get_show(self, show_id: str) -> Optional[Dict[str, Any]]:
        """Get show data by ID."""
        return self._data.get("shows", {}).get(show_id)

    def get_show_by_name(self, name: str) -> Optional[tuple]:
        """Find a show by name (case-insensitive). Returns (show_id, show_data)."""
        for show_id, show in self._data.get("shows", {}).items():
            if show.get("name", "").lower() == name.lower():
                return (show_id, show)
        return None

    # ------------------------------------------------------------------
    # Episodes
    # ------------------------------------------------------------------

    def is_processed(self, show_id: str, episode_id: str) -> bool:
        """Check if an episode has already been processed (completed)."""
        show = self._data.get("shows", {}).get(show_id, {})
        ep = show.get("episodes", {}).get(episode_id, {})
        return ep.get("status") == "completed"

    def is_known(self, show_id: str, episode_id: str) -> bool:
        """Check if an episode exists in the manifest (any status)."""
        show = self._data.get("shows", {}).get(show_id, {})
        return episode_id in show.get("episodes", {})

    def get_failed_episodes(self, show_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all failed episodes, optionally filtered by show."""
        failed = []
        shows = self._data.get("shows", {})
        for sid, show in shows.items():
            if show_id and sid != show_id:
                continue
            for eid, ep in show.get("episodes", {}).items():
                if ep.get("status") == "failed":
                    failed.append({
                        "show_id": sid,
                        "show_name": show.get("name", sid),
                        "episode_id": eid,
                        **ep,
                    })
        return failed

    def mark_episode(
        self,
        show_id: str,
        episode_id: str,
        *,
        title: str = "",
        published: str = "",
        audio_url: str = "",
        transcript_path: str = "",
        note_path: str = "",
        status: str = "completed",
        error: str = "",
    ) -> None:
        """Record an episode in the manifest.

        Call this ONLY after a successful vault write (for completed status).
        """
        shows = self._data.setdefault("shows", {})
        show = shows.setdefault(show_id, {"name": show_id, "rss_url": "", "episodes": {}})
        episodes = show.setdefault("episodes", {})
        episodes[episode_id] = {
            "title": title,
            "published": published,
            "audio_url": audio_url,
            "transcript_path": transcript_path,
            "note_path": note_path,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
        }
        if error:
            episodes[episode_id]["error"] = error

    def get_new_episodes(self, show_id: str, candidate_ids: List[str]) -> List[str]:
        """Filter candidate episode IDs to only those not yet processed."""
        show = self._data.get("shows", {}).get(show_id, {})
        episodes = show.get("episodes", {})
        return [
            eid for eid in candidate_ids
            if eid not in episodes or episodes[eid].get("status") == "failed"
        ]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, int]:
        """Return summary statistics."""
        total_shows = 0
        total_episodes = 0
        completed = 0
        failed = 0
        for show in self._data.get("shows", {}).values():
            total_shows += 1
            for ep in show.get("episodes", {}).values():
                total_episodes += 1
                if ep.get("status") == "completed":
                    completed += 1
                elif ep.get("status") == "failed":
                    failed += 1
        return {
            "shows": total_shows,
            "episodes": total_episodes,
            "completed": completed,
            "failed": failed,
        }
