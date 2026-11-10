"""The product name is Eggnest, with a lowercase n.

This test reads every file git tracks and fails on the old camel-case
spelling, so a page title, CLI help string or docstring can't bring it
back. The ``EggNestSync`` class keeps its name because callers import it,
and nobody reads a class name as the brand.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OLD_SPELLING = "Egg" + "Nest"  # split so this file doesn't flag itself
KEPT_IDENTIFIER = "EggNestSync"


def _tracked_files() -> list[Path]:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=False
    )
    if result.returncode != 0:
        pytest.skip("not running inside a git checkout")
    names = result.stdout.decode("utf-8", "surrogateescape").split("\0")
    return [REPO_ROOT / name for name in names if name]


def test_product_name_is_spelled_eggnest():
    offenders = []
    for path in _tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # binary, deleted or unreadable: no brand text to check
        for number, line in enumerate(text.splitlines(), start=1):
            if OLD_SPELLING in line.replace(KEPT_IDENTIFIER, ""):
                where = path.relative_to(REPO_ROOT)
                offenders.append(f"{where}:{number}: {line.strip()}")
    message = f"Write Eggnest, not {OLD_SPELLING}, in text people read:"
    assert not offenders, "\n".join([message, *offenders])
