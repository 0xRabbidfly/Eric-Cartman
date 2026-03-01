"""Transcription module — local audio transcription using faster-whisper.

Wraps faster-whisper for local GPU/CPU transcription of podcast audio.
Falls back to whisper.cpp CLI if faster-whisper is not available.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Engine detection
# ---------------------------------------------------------------------------

_ENGINE: Optional[str] = None


def _detect_engine() -> str:
    """Detect available transcription engine."""
    global _ENGINE
    if _ENGINE:
        return _ENGINE

    # Try faster-whisper first
    try:
        import faster_whisper
        _ENGINE = "faster-whisper"
        return _ENGINE
    except ImportError:
        pass

    # Try whisper.cpp CLI
    if shutil.which("whisper-cpp") or shutil.which("main"):
        _ENGINE = "whisper-cpp"
        return _ENGINE

    # Try OpenAI whisper
    try:
        import whisper
        _ENGINE = "openai-whisper"
        return _ENGINE
    except ImportError:
        pass

    raise RuntimeError(
        "No transcription engine found. Install one of:\n"
        "  pip install faster-whisper    (recommended, GPU support)\n"
        "  pip install openai-whisper    (original, slower)\n"
        "  Install whisper.cpp           (C++ binary, fast CPU)\n"
    )


def get_engine() -> str:
    """Return the name of the detected transcription engine."""
    return _detect_engine()


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def transcribe(
    audio_path: Path,
    output_dir: Path,
    model_name: str = "base",
    device: str = "auto",
    language: Optional[str] = None,
) -> Tuple[Path, dict]:
    """Transcribe an audio file to text.

    Args:
        audio_path: Path to audio file.
        output_dir: Directory to write transcript file.
        model_name: Whisper model size (tiny, base, small, medium, large-v3).
        device: Compute device (auto, cpu, cuda).
        language: Language code (e.g. 'en'). None for auto-detect.

    Returns:
        Tuple of (transcript_path, metadata_dict).
        metadata_dict contains: language, duration, segments_count.
    """
    engine = _detect_engine()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Output filename matches audio filename but .txt
    transcript_path = output_dir / (audio_path.stem + ".txt")

    # Skip if already transcribed
    if transcript_path.exists() and transcript_path.stat().st_size > 0:
        print(f"  [skip] Already transcribed: {transcript_path.name}")
        meta = {"language": language or "unknown", "duration": 0, "segments_count": 0}
        return transcript_path, meta

    print(f"  [transcribe] {audio_path.name} (engine={engine}, model={model_name})")

    if engine == "faster-whisper":
        return _transcribe_faster_whisper(
            audio_path, transcript_path, model_name, device, language
        )
    elif engine == "openai-whisper":
        return _transcribe_openai_whisper(
            audio_path, transcript_path, model_name, device, language
        )
    elif engine == "whisper-cpp":
        return _transcribe_whisper_cpp(
            audio_path, transcript_path, model_name, language
        )
    else:
        raise RuntimeError(f"Unknown engine: {engine}")


# ---------------------------------------------------------------------------
# faster-whisper engine
# ---------------------------------------------------------------------------

def _transcribe_faster_whisper(
    audio_path: Path,
    transcript_path: Path,
    model_name: str,
    device: str,
    language: Optional[str],
) -> Tuple[Path, dict]:
    """Transcribe using faster-whisper."""
    from faster_whisper import WhisperModel

    # Device selection
    if device == "auto":
        try:
            import torch
            compute_type = "float16" if torch.cuda.is_available() else "int8"
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
            compute_type = "int8"
    elif device == "cuda":
        compute_type = "float16"
    else:
        compute_type = "int8"

    print(f"  [model] Loading {model_name} on {device} ({compute_type})...")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)

    print(f"  [transcribing] This may take a while...")
    segments_list = []
    kwargs = {}
    if language:
        kwargs["language"] = language

    segments, info = model.transcribe(str(audio_path), **kwargs)

    full_text_parts = []
    segment_count = 0
    for segment in segments:
        full_text_parts.append(segment.text.strip())
        segment_count += 1
        if segment_count % 50 == 0:
            print(f"  [progress] {segment_count} segments...")

    full_text = "\n".join(full_text_parts)

    # Write transcript
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    meta = {
        "language": info.language if hasattr(info, "language") else (language or "unknown"),
        "duration": info.duration if hasattr(info, "duration") else 0,
        "segments_count": segment_count,
    }

    size_kb = transcript_path.stat().st_size / 1024
    print(f"  [done] {transcript_path.name} ({size_kb:.1f} KB, {segment_count} segments)")
    return transcript_path, meta


# ---------------------------------------------------------------------------
# OpenAI whisper engine
# ---------------------------------------------------------------------------

def _transcribe_openai_whisper(
    audio_path: Path,
    transcript_path: Path,
    model_name: str,
    device: str,
    language: Optional[str],
) -> Tuple[Path, dict]:
    """Transcribe using OpenAI whisper."""
    import whisper

    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    print(f"  [model] Loading {model_name} on {device}...")
    model = whisper.load_model(model_name, device=device)

    kwargs = {}
    if language:
        kwargs["language"] = language

    print(f"  [transcribing] This may take a while...")
    result = model.transcribe(str(audio_path), **kwargs)

    full_text = result.get("text", "")

    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    meta = {
        "language": result.get("language", language or "unknown"),
        "duration": 0,
        "segments_count": len(result.get("segments", [])),
    }

    size_kb = transcript_path.stat().st_size / 1024
    print(f"  [done] {transcript_path.name} ({size_kb:.1f} KB)")
    return transcript_path, meta


# ---------------------------------------------------------------------------
# whisper.cpp engine
# ---------------------------------------------------------------------------

def _transcribe_whisper_cpp(
    audio_path: Path,
    transcript_path: Path,
    model_name: str,
    language: Optional[str],
) -> Tuple[Path, dict]:
    """Transcribe using whisper.cpp CLI."""
    # Find binary
    binary = shutil.which("whisper-cpp") or shutil.which("main")
    if not binary:
        raise FileNotFoundError("whisper-cpp binary not found on PATH")

    # Model path — whisper.cpp stores models in a specific location
    model_path = _find_whisper_cpp_model(model_name)

    cmd = [
        binary,
        "-m", str(model_path),
        "-f", str(audio_path),
        "--output-txt",
        "--output-file", str(transcript_path.with_suffix("")),
    ]
    if language:
        cmd.extend(["-l", language])

    print(f"  [transcribing] Running whisper.cpp...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

    if result.returncode != 0:
        raise RuntimeError(f"whisper.cpp failed: {result.stderr}")

    # whisper.cpp appends .txt automatically
    actual_path = transcript_path.with_suffix("") if transcript_path.exists() else transcript_path
    if not actual_path.exists():
        # Try with .txt suffix added by whisper.cpp
        alt = Path(str(transcript_path.with_suffix("")) + ".txt")
        if alt.exists():
            alt.rename(transcript_path)

    meta = {"language": language or "unknown", "duration": 0, "segments_count": 0}
    return transcript_path, meta


def _find_whisper_cpp_model(model_name: str) -> Path:
    """Find whisper.cpp model file."""
    # Common locations
    search_paths = [
        Path.home() / ".cache" / "whisper" / f"ggml-{model_name}.bin",
        Path.home() / "whisper.cpp" / "models" / f"ggml-{model_name}.bin",
        Path("/usr/local/share/whisper/models") / f"ggml-{model_name}.bin",
    ]
    for p in search_paths:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"Model ggml-{model_name}.bin not found. "
        f"Download it with: whisper-cpp --download-model {model_name}"
    )
