"""Transcription module — local audio transcription using faster-whisper.

Wraps faster-whisper for local GPU/CPU transcription of podcast audio.
Falls back to whisper.cpp CLI if faster-whisper is not available.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Wall-clock ceiling for a single transcription. Long-form podcasts on a
# mid-range GPU run ~25 min for a 2h45m episode, so 30 min was too tight to be
# a safety net and too loose to catch a hang quickly.
TRANSCRIBE_TIMEOUT = 5400  # 90 minutes

# Rough floor for how many words a real transcript should contain per minute of
# audio. Below this the transcript is almost certainly truncated.
MIN_WORDS_PER_MINUTE = 40


def _transcript_meta_path(transcript_path: Path) -> Path:
    """Sidecar path recording that a transcript completed, and its metadata."""
    return transcript_path.with_suffix(".meta.json")


def _write_transcript_meta(transcript_path: Path, meta: Dict[str, Any]) -> None:
    """Record completion metadata beside the transcript.

    The sidecar is what makes the 'already transcribed, skip it' shortcut safe:
    a transcript with no sidecar was never confirmed complete, so it gets
    redone rather than trusted.
    """
    try:
        payload = dict(meta or {})
        payload["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _transcript_meta_path(transcript_path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8",
        )
    except Exception as e:
        print(f"  [warn] Could not write transcript metadata sidecar: {e}")


def _read_transcript_meta(transcript_path: Path) -> Optional[Dict[str, Any]]:
    """Load the completion sidecar, or None if absent/unreadable."""
    p = _transcript_meta_path(transcript_path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _check_transcript_coverage(
    transcript_path: Path, meta: Optional[Dict[str, Any]],
) -> None:
    """Warn when a transcript looks too short for the audio it came from.

    Whisper can terminate early on a corrupt or misdetected stream and still
    write a well-formed file. Comparing word count against the audio duration
    catches that before a confidently wrong note gets generated.
    """
    duration = float((meta or {}).get("duration") or 0)
    if duration <= 0:
        return
    try:
        words = len(transcript_path.read_text(encoding="utf-8").split())
    except Exception:
        return
    minutes = duration / 60
    expected = minutes * MIN_WORDS_PER_MINUTE
    if words < expected:
        print(f"  [warn] Transcript looks short: {words:,} words for "
              f"{minutes:.0f} min of audio "
              f"(expected at least {expected:,.0f}). "
              f"Transcription may have stopped early.")


# ---------------------------------------------------------------------------
# Domain vocabulary
#
# Small Whisper models reliably mangle domain jargon and proper nouns -- an
# observed run turned "open-weight models" into "opioid models" throughout,
# which then propagated into every downstream summary.  Two defences:
#   1. initial_prompt primes the decoder toward correct spellings.
#   2. corrections patch what still slips through.
# Both live in config/vocabulary.json so they can be tuned without code edits.
# ---------------------------------------------------------------------------

def _register_cuda_dll_dirs() -> None:
    """Preload nvidia-cublas-cu12's DLLs so ctranslate2 can find cuBLAS.

    ctranslate2's own __init__.py only registers its own package directory
    and preloads DLLs bundled there (e.g. cudnn64_9.dll) -- it does NOT
    know about the separate nvidia-cublas-cu12 pip package, so
    cublas64_12.dll is never preloaded. Registering the directory alone
    via os.add_dll_directory is *not* sufficient: ctranslate2's own
    internal load of cublas64_12.dll still fails with "Library
    cublas64_12.dll is not found or cannot be loaded" even with the
    directory registered. What works is preloading the DLLs into the
    process via ctypes.CDLL first (mirroring exactly what ctranslate2
    does for its own bundled DLLs) -- once already loaded, ctranslate2's
    internal lookup just gets a handle to the loaded module.

    cublas64_12.dll is loaded lazily on the first CUDA matmul, not at
    WhisperModel construction time, so a construct-only CUDA probe can
    pass even when this whole preload step is missing, and the failure
    only surfaces deep into a real transcription run. Safe to call more
    than once.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import importlib.util
        spec = importlib.util.find_spec("nvidia.cublas")
        if spec and spec.submodule_search_locations:
            for loc in spec.submodule_search_locations:
                bin_dir = os.path.join(loc, "bin")
                if os.path.isdir(bin_dir):
                    os.add_dll_directory(bin_dir)
                    for name in ("cublasLt64_12.dll", "cublas64_12.dll"):
                        dll_path = os.path.join(bin_dir, name)
                        if os.path.isfile(dll_path):
                            ctypes.CDLL(dll_path)
    except Exception:
        pass


_VOCAB_CACHE: Optional[dict] = None


def _load_vocabulary() -> dict:
    """Load config/vocabulary.json (cached).  Returns {} if absent."""
    global _VOCAB_CACHE
    if _VOCAB_CACHE is not None:
        return _VOCAB_CACHE

    _VOCAB_CACHE = {}
    try:
        skill_dir = Path(__file__).resolve().parents[2]
        vocab_path = skill_dir / "config" / "vocabulary.json"
        if vocab_path.exists():
            with open(vocab_path, "r", encoding="utf-8") as f:
                _VOCAB_CACHE = json.load(f)
    except Exception as e:
        print(f"  [warn] Could not load vocabulary.json: {e}")
    return _VOCAB_CACHE


def get_initial_prompt() -> Optional[str]:
    """Domain priming prompt for the Whisper decoder, if configured."""
    prompt = _load_vocabulary().get("initial_prompt")
    return prompt or None


def apply_corrections(text: str) -> Tuple[str, int]:
    """Apply vocabulary corrections to a transcript.

    Matching is case-insensitive and word-boundary anchored, and the
    original capitalisation of the first letter is preserved so
    sentence-initial matches don't get lower-cased.

    Returns (corrected_text, replacement_count).
    """
    corrections = _load_vocabulary().get("corrections") or {}
    if not corrections:
        return text, 0

    total = 0

    # Longest patterns first, so "opioid models" wins over "opioid model".
    for wrong in sorted(corrections, key=len, reverse=True):
        right = corrections[wrong]
        pattern = re.compile(r"\b" + re.escape(wrong) + r"\b", re.IGNORECASE)

        def _sub(match, replacement=right):
            found = match.group(0)
            if found[:1].isupper() and replacement[:1].islower():
                return replacement[:1].upper() + replacement[1:]
            return replacement

        text, n = pattern.subn(_sub, text)
        total += n

    return text, total


def add_corrections(new_corrections: dict) -> int:
    """Append new corrections to the vocabulary glossary.

    Args:
        new_corrections: dict of {"wrong": "right"} pairs

    Returns:
        Number of new corrections added.
    """
    vocab = _load_vocabulary()
    existing = vocab.get("corrections", {})
    added = 0
    for wrong, right in new_corrections.items():
        if wrong not in existing:
            existing[wrong] = right
            added += 1
    if added:
        vocab["corrections"] = existing
        # Write back
        skill_dir = Path(__file__).resolve().parents[2]
        vocab_path = skill_dir / "config" / "vocabulary.json"
        with open(vocab_path, "w", encoding="utf-8") as f:
            json.dump(vocab, f, indent=2, ensure_ascii=False)
        # Invalidate cache
        global _VOCAB_CACHE
        _VOCAB_CACHE = None
        print(f"  [vocab] Added {added} new corrections to glossary")
    return added


# ---------------------------------------------------------------------------
# CUDA detection (no torch dependency)
# ---------------------------------------------------------------------------

def _detect_cuda_device() -> Tuple[str, str]:
    """Detect CUDA availability without depending on PyTorch.

    Tries to load a faster-whisper model on CUDA directly. If that works,
    returns ('cuda', 'float16'). Otherwise falls back to ('cpu', 'int8').

    This avoids the 2 GB torch install just for a one-line CUDA check.
    """
    try:
        import numpy as np
        _register_cuda_dll_dirs()
        from faster_whisper import WhisperModel
        # Load the smallest model and run one real inference step on a
        # second of silence -- the WhisperModel constructor alone doesn't
        # touch cublas64_12.dll (that's lazy-loaded on first matmul), so a
        # construct-only probe can pass while a real transcription run
        # still fails later on the same missing DLL.
        _test = WhisperModel("tiny", device="cuda", compute_type="float16")
        silence = np.zeros(16000, dtype=np.float32)
        list(_test.transcribe(silence, vad_filter=False)[0])
        del _test
        print("  [device] CUDA detected via faster-whisper probe")
        return "cuda", "float16"
    except Exception:
        pass

    print("  [device] CUDA not available, falling back to CPU")
    return "cpu", "int8"


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

    # Skip if already transcribed — but only when a completion sidecar proves
    # the transcript finished. A file left behind by a killed run is
    # indistinguishable by size alone, and reusing one silently produces a
    # note for half an episode.
    if transcript_path.exists() and transcript_path.stat().st_size > 0:
        prior = _read_transcript_meta(transcript_path)
        if prior:
            print(f"  [skip] Already transcribed: {transcript_path.name} "
                  f"({prior.get('segments_count', '?')} segments)")
            return transcript_path, prior
        print(f"  [redo] Found {transcript_path.name} with no completion record "
              f"— re-transcribing rather than trusting it")

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
    """Transcribe using faster-whisper in an isolated subprocess.

    Spawns transcribe_worker.py as a separate process.  When the worker
    exits, the OS reclaims all CUDA memory automatically -- no manual
    gc.collect / empty_cache dance required, and a CUDA crash in the
    worker cannot kill the parent pipeline.
    """
    worker_script = Path(__file__).with_name("transcribe_worker.py")
    if not worker_script.exists():
        raise FileNotFoundError(
            f"Worker script not found: {worker_script}\n"
            "Expected transcribe_worker.py alongside transcriber.py."
        )

    # Build subprocess command
    cmd = [sys.executable, str(worker_script)]
    cmd.extend(["--audio", str(audio_path)])
    cmd.extend(["--output", str(transcript_path)])
    cmd.extend(["--model", model_name])

    if language:
        cmd.extend(["--language", language])

    # Prime the decoder with domain vocabulary
    initial_prompt = get_initial_prompt()
    if initial_prompt:
        cmd.extend(["--initial-prompt", initial_prompt])
        print(f"  [vocab] Priming decoder with domain vocabulary")

    # Extract corrections dict and pass as temp JSON file
    corrections_tmp = None
    vocab = _load_vocabulary()
    corrections = vocab.get("corrections") or {}
    if corrections:
        try:
            corrections_tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8",
            )
            json.dump(corrections, corrections_tmp)
            corrections_tmp.close()
            cmd.extend(["--corrections-json", corrections_tmp.name])
        except Exception as e:
            print(f"  [warn] Could not write corrections temp file: {e}")
            corrections_tmp = None

    # Spawn worker subprocess
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    print(f"  [transcribe] Spawning worker subprocess...")
    print(f"  [transcribe] model={model_name}, audio={audio_path.name}")

    # Stream the worker's output line by line instead of capturing it all and
    # dumping it at exit. A 25-minute transcription used to log nothing until
    # it finished, and a killed worker lost its output entirely.
    meta: Optional[dict] = None
    stdout_lines: List[str] = []
    stderr_lines: List[str] = []
    timed_out = False

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,  # line-buffered
            env=env,
        )

        # Drain stderr on a thread so a chatty worker can't deadlock on a full pipe.
        def _drain_stderr() -> None:
            assert proc.stderr is not None
            for line in proc.stderr:
                stderr_lines.append(line.rstrip())

        err_thread = threading.Thread(target=_drain_stderr, daemon=True)
        err_thread.start()

        deadline = time.monotonic() + TRANSCRIBE_TIMEOUT
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            stdout_lines.append(line)
            m = re.search(r"__META__(.+?)__META__", line)
            if m:
                try:
                    meta = json.loads(m.group(1))
                except json.JSONDecodeError:
                    print("  [warn] Could not parse worker metadata")
            elif line:
                print(f"  {line}", flush=True)
            if time.monotonic() > deadline:
                timed_out = True
                proc.kill()
                break

        returncode = proc.wait(timeout=60)
        err_thread.join(timeout=5)

        if timed_out:
            raise RuntimeError(
                f"Transcription worker timed out after "
                f"{TRANSCRIBE_TIMEOUT // 60} minutes"
            )

        # Completeness is decided by the worker's __META__ marker, which it
        # emits only after the transcript file is fully written. Testing
        # "file exists and is non-empty" instead used to accept a stale
        # transcript from an earlier killed run as a successful result.
        if meta is None:
            tail = "\n".join(stderr_lines[-5:]) or "no stderr"
            raise RuntimeError(
                f"Transcription worker did not complete (exit code {returncode}); "
                f"no metadata marker emitted.\n{tail}"
            )

        if returncode != 0:
            # Transcript was written and metadata emitted, so the non-zero exit
            # is a teardown crash (CUDA/ctranslate2 commonly exit 0xC0000409).
            print(f"  [warn] Worker exited with code {returncode} after writing "
                  f"the transcript — treating as a teardown crash")
            for line in stderr_lines[-5:]:
                print(f"  [worker-stderr] {line}")

    finally:
        # Clean up temp corrections file
        if corrections_tmp:
            try:
                os.unlink(corrections_tmp.name)
            except OSError:
                pass

    if not transcript_path.exists() or transcript_path.stat().st_size == 0:
        raise RuntimeError(
            f"Worker reported success but transcript is missing or empty: "
            f"{transcript_path}"
        )

    _check_transcript_coverage(transcript_path, meta)
    _write_transcript_meta(transcript_path, meta)

    size_kb = transcript_path.stat().st_size / 1024
    print(f"  [done] {transcript_path.name} ({size_kb:.1f} KB)")
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
        device, _ = _detect_cuda_device()

    print(f"  [model] Loading {model_name} on {device}...")
    model = whisper.load_model(model_name, device=device)

    kwargs = {}
    if language:
        kwargs["language"] = language

    initial_prompt = get_initial_prompt()
    if initial_prompt:
        kwargs["initial_prompt"] = initial_prompt
        print(f"  [vocab] Priming decoder with domain vocabulary")

    print(f"  [transcribing] This may take a while...")
    result = model.transcribe(str(audio_path), **kwargs)

    full_text = result.get("text", "")

    full_text, fixes = apply_corrections(full_text)
    if fixes:
        print(f"  [vocab] Applied {fixes} vocabulary corrections")

    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    meta = {
        "vocabulary_corrections": fixes,
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

    initial_prompt = get_initial_prompt()
    if initial_prompt:
        # whisper.cpp caps the prompt, so send a trimmed version.
        cmd.extend(["--prompt", initial_prompt[:900]])
        print(f"  [vocab] Priming decoder with domain vocabulary")

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

    fixes = 0
    if transcript_path.exists():
        text = transcript_path.read_text(encoding="utf-8", errors="replace")
        corrected, fixes = apply_corrections(text)
        if fixes:
            transcript_path.write_text(corrected, encoding="utf-8")
            print(f"  [vocab] Applied {fixes} vocabulary corrections")

    meta = {
        "vocabulary_corrections": fixes,
        "language": language or "unknown",
        "duration": 0,
        "segments_count": 0,
    }
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
