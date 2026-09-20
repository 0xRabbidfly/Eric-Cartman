"""Tests for desktop-app presence detection and auto-launch.

Why this exists: Obsidian Sync only pushes vault changes while the desktop
app is running. The bundled CLI spawns a short-lived process per call and
exits, so a vault written entirely through the CLI (or straight to disk, as
create/append now do) can sit unsynced for days. On 2026-09-19 that left the
three newest notes unopenable from the phone — Obsidian launched and reported
the file missing, because it genuinely was missing on that device.

Run:
    python -m pytest .github/skills/obsidian/scripts/test_obsidian_app.py -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "obsidian_under_test", Path(__file__).with_name("obsidian.py")
)
obs = importlib.util.module_from_spec(_SPEC)
sys.modules["obsidian_under_test"] = obs
_SPEC.loader.exec_module(obs)


@pytest.fixture(autouse=True)
def _clear_autolaunch_env(monkeypatch):
    monkeypatch.delenv("OBSIDIAN_AUTOLAUNCH", raising=False)


def test_running_app_is_not_relaunched(monkeypatch):
    launches = []
    monkeypatch.setattr(obs, "app_is_running", lambda: True)
    monkeypatch.setattr(obs, "launch_app", lambda: launches.append(1) or "launched")

    assert obs.ensure_app_running() == "running"
    assert launches == [], "a running app must never be relaunched"


def test_missing_app_is_launched(monkeypatch):
    launches = []
    monkeypatch.setattr(obs, "app_is_running", lambda: False)
    monkeypatch.setattr(obs, "launch_app", lambda: launches.append(1) or "launched")

    assert obs.ensure_app_running() == "launched"
    assert launches == [1], "a stopped app must be launched so Sync gets a window"


def test_autolaunch_opt_out_is_honoured(monkeypatch):
    launches = []
    monkeypatch.setattr(obs, "app_is_running", lambda: False)
    monkeypatch.setattr(obs, "launch_app", lambda: launches.append(1) or "launched")
    monkeypatch.setenv("OBSIDIAN_AUTOLAUNCH", "0")

    assert obs.ensure_app_running() == "disabled"
    assert launches == [], "OBSIDIAN_AUTOLAUNCH=0 must suppress the launch"


def test_explicit_launch_argument_overrides_env(monkeypatch):
    monkeypatch.setattr(obs, "app_is_running", lambda: False)
    monkeypatch.setattr(obs, "launch_app", lambda: "launched")
    monkeypatch.setenv("OBSIDIAN_AUTOLAUNCH", "0")

    assert obs.ensure_app_running(launch=True) == "launched"


def test_unlocatable_app_reports_instead_of_raising(monkeypatch):
    monkeypatch.setattr(obs, "app_is_running", lambda: False)
    monkeypatch.setattr(obs, "_find_obsidian_app", lambda: None)

    result = obs.ensure_app_running()
    assert result.startswith("unavailable"), result


def test_launch_failure_reports_instead_of_raising(monkeypatch):
    def boom():
        raise OSError("access denied")

    monkeypatch.setattr(obs, "app_is_running", lambda: False)
    monkeypatch.setattr(obs, "launch_app", boom)

    result = obs.ensure_app_running()
    assert result.startswith("failed"), result


def test_detection_survives_a_missing_process_tool(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("tasklist")

    monkeypatch.setattr(obs.subprocess, "run", boom)
    assert obs.app_is_running() is False


def test_detection_reads_the_process_table(monkeypatch):
    class Result:
        returncode = 0
        stdout = "Obsidian.exe                  1234 Console      1    210,940 K\n"

    monkeypatch.setattr(obs.sys, "platform", "win32")
    monkeypatch.setattr(obs.subprocess, "run", lambda *a, **k: Result())
    assert obs.app_is_running() is True


def test_detection_handles_an_empty_process_table(monkeypatch):
    class Result:
        returncode = 1
        stdout = "INFO: No tasks are running which match the specified criteria.\n"

    monkeypatch.setattr(obs.sys, "platform", "win32")
    monkeypatch.setattr(obs.subprocess, "run", lambda *a, **k: Result())
    assert obs.app_is_running() is False


def test_instance_method_delegates(monkeypatch):
    monkeypatch.setattr(obs, "app_is_running", lambda: True)
    ob = obs.Obsidian.__new__(obs.Obsidian)  # no CLI discovery needed
    assert ob.ensure_app_running() == "running"
