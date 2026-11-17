"""The portal must stay under the Streamlit Community Cloud memory limit (see scripts/memory_check.py)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_memory_budget():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "memory_check.py")], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
