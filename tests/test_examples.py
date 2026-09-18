"""End-to-end checks against the reference CLI in ``examples/`` (real process, real exit codes)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "file.py"


def run_example(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.parametrize(
    "args",
    [
        ("doThing", "-abc", "cInput", "--long-flag", "longFlagInput"),
        ("doThing", "-abccInput", "--long-flag=longFlagInput"),
        ("doThing", "-c", "cInput", "-a", "-b", "--long-flag", "longFlagInput"),
    ],
)
def test_flagship_example(args):
    result = run_example(*args)
    assert result.returncode == 0
    assert result.stdout.strip() == "all=True c='cInput' long='longFlagInput'"


def test_example_help():
    result = run_example("--help")
    assert result.returncode == 0
    assert "Usage: file.py <command> [options]" in result.stdout


def test_example_usage_error():
    result = run_example("doThing", "--bogus")
    assert result.returncode == 2
    assert "error: unknown flag '--bogus'" in result.stderr
    assert "Try 'file.py doThing --help'" in result.stderr


def test_example_missing_value():
    result = run_example("doThing", "-abc")
    assert result.returncode == 2
    assert "flag '-c' requires a value" in result.stderr
