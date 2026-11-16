"""The PIDS comment on the DWR bills is a held-out benchmark: no agent prompt or context may contain it."""
from pathlib import Path

from eval import pids_eval

ROOT = Path(__file__).resolve().parents[1]


def test_pids_benchmark_is_held_out():
    for p in list((ROOT / "agents").rglob("*.py")) + list((ROOT / "agents" / "prompts").glob("*.md")) + list((ROOT / "data" / "reference").rglob("*")):
        if p.is_file():
            t = p.read_text(errors="ignore")
            assert "pids_hb6789" not in t and "Navarro" not in t, p


def test_pids_scoring():
    full = " ".join(p["point"] for p in pids_eval.points())
    s = pids_eval.score(full)
    assert s["covered"] == s["of"] == 9
    assert pids_eval.score("The bill creates a department.")["covered"] == 0
