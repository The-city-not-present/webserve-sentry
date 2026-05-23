# scripts/test_system.py

import subprocess
import time
import sys
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def test_prog_version(tmp_path):
    result = subprocess.run(
        [sys.executable, "dist/webserve_bundle.py","--program","version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f'Failed: returncode == {repr(result.returncode)}, stderr == {repr(result.stderr)}, stdout == {repr(result.stdout)}'
    assert not result.stderr
    assert re.match(r'.*\d+\.\d+.*',result.stdout)
    print("PASS")
