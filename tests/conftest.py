"""Shared test helpers.

Lesson folders start with a number (01_agent_loop), so they are not importable packages.
`load_lesson` imports a lesson script by path. Every test runs offline with ScriptedModel.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "lessons"

# Tests never call a real provider, even if a developer's .env says bedrock.
os.environ["MODEL_PROVIDER"] = "fake"


def load_lesson(relative_path: str) -> ModuleType:
    """Import lessons/<relative_path> as a module (its folder is put on sys.path first)."""
    path = LESSONS / relative_path
    folder = str(path.parent)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    name = "lesson_" + relative_path.replace("/", "_").removesuffix(".py")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def lesson():
    return load_lesson


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    """Lessons that write files (sessions, memory) write into a temp folder."""
    monkeypatch.chdir(tmp_path)
