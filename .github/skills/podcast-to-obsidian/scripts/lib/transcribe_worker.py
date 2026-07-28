#!/usr/bin/env python3
"""Standalone whisper transcription worker.

Runs in its own process so CUDA memory is reclaimed by the OS on exit.
Called by transcriber.py via subprocess.
"""

import argparse
import io
import json
import re
import sys
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


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
    process via ctypes.CDLL first -- once already loaded, ctranslate2's
    internal lookup just gets a handle to the loaded module.
    """
    import os
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True, help="Path to audio file")
    parser.add_argument("--output", required=True, help="Path to write transcript")
    parser.add_argument("--model", default="large-v3", help="Whisper model name")
    parser.add_argument("--language", default=None, help="Language code")
    parser.add_argument("--initial-prompt", default=None, help="Decoder priming prompt")
    parser.add_argument("--corrections-json", default=None, help="Path to vocabulary corrections JSON")
    args = parser.parse_args()

    _register_cuda_dll_dirs()
    from faster_whisper import WhisperModel
    import numpy as np

    # CUDA detection — run a real inference step, not just construction,
    # because cublas64_12.dll is lazy-loaded on first matmul.
    device, compute_type = "cpu", "int8"
    try:
        _test = WhisperModel("tiny", device="cuda", compute_type="float16")
        silence = np.zeros(16000, dtype=np.float32)
        list(_test.transcribe(silence, vad_filter=False)[0])
        del _test
        device, compute_type = "cuda", "float16"
        print(f"[worker] CUDA detected", flush=True)
    except Exception:
        print(f"[worker] Using CPU", flush=True)

    print(f"[worker] Loading {args.model} on {device} ({compute_type})...", flush=True)
    model = WhisperModel(args.model, device=device, compute_type=compute_type)

    kwargs = {}
    if args.language:
        kwargs["language"] = args.language
    if args.initial_prompt:
        kwargs["initial_prompt"] = args.initial_prompt

    print(f"[worker] Transcribing...", flush=True)
    segments, info = model.transcribe(str(args.audio), **kwargs)

    # Consume all segments and write transcript
    full_text_parts = []
    segment_count = 0
    for segment in segments:
        full_text_parts.append(segment.text.strip())
        segment_count += 1
        if segment_count % 50 == 0:
            print(f"[worker] {segment_count} segments...", flush=True)

    full_text = "\n".join(full_text_parts)

    # Apply vocabulary corrections if provided
    corrections_count = 0
    if args.corrections_json and Path(args.corrections_json).exists():
        try:
            corrections = json.loads(Path(args.corrections_json).read_text(encoding="utf-8"))
            for wrong in sorted(corrections, key=len, reverse=True):
                right = corrections[wrong]
                pattern = re.compile(r"\b" + re.escape(wrong) + r"\b", re.IGNORECASE)
                def _sub(match, replacement=right):
                    found = match.group(0)
                    if found[:1].isupper() and replacement[:1].islower():
                        return replacement[:1].upper() + replacement[1:]
                    return replacement
                full_text, n = pattern.subn(_sub, full_text)
                corrections_count += n
        except Exception as e:
            print(f"[worker] Correction error: {e}", flush=True)

    # WRITE TRANSCRIPT BEFORE ANY CLEANUP
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_text, encoding="utf-8")

    # Write metadata as JSON to stdout for parent to parse
    meta = {
        "language": info.language if hasattr(info, "language") else (args.language or "unknown"),
        "duration": info.duration if hasattr(info, "duration") else 0,
        "segments_count": segment_count,
        "vocabulary_corrections": corrections_count,
        "transcript_size_kb": output_path.stat().st_size / 1024,
    }
    print(f"\n__META__{json.dumps(meta)}__META__", flush=True)
    print(f"[worker] Done: {output_path.name} ({meta['transcript_size_kb']:.1f} KB, {segment_count} segments)", flush=True)

    # No manual CUDA cleanup — OS reclaims everything when this process exits


if __name__ == "__main__":
    main()
