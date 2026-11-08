"""Agent 3 tests that run without an API key."""
import pytest

from agents.costing import cost_range, annual_cost_per_person, salary_schedule
from agents.appraisal import unsupported_numbers, governance_flags, build_letter_messages, LABEL


def test_salary_schedule_matches_circular_examples():
    s = salary_schedule()
    assert s[11] == 31705 and s[18] == 53818 and s[29] == 187531


def test_cost_range_is_ordered_and_sourced():
    r = cost_range("SB-20-1624")
    assert 0 < r["range"]["low"] < r["range"]["high"]
    assert all(a["source"] for a in r["assumptions"])
    assert any("SG-29" in a["assumption"] for a in r["assumptions"])


def test_stated_amount_reported_not_replaced():
    r = cost_range("SB-20-1624")
    assert any(abs(x["pesos"] - 200_000_000) < 1 for x in r["stated_in_bill"])


def test_benefits_loading_above_basic():
    assert annual_cost_per_person(50000) > 50000 * 12 * 1.2


def test_invented_figure_flagged_and_engine_figure_allowed():
    r = cost_range("SB-20-1624")
    lo = r["range"]["low"]
    ok_text = f"The range starts at P{lo:,}."
    assert unsupported_numbers("SB-20-1624", ok_text) == []
    assert unsupported_numbers("SB-20-1624", "It will cost P987 million.") == ["P987 million"]


def test_governance_flags():
    assert governance_flags("Approved by Secretary Juan Cruz.", "memo")
    clean = f"[POSITION TO BE DETERMINED BY THE REVIEWER: x]\n[SIGNATURE BLOCK - to be completed by DBM]\n{LABEL}"
    assert governance_flags(clean, "memo") == []


def test_letter_blocked_until_position_decided():
    with pytest.raises(ValueError):
        build_letter_messages("SB-20-1624", "Memo ... [POSITION TO BE DETERMINED BY THE REVIEWER: support / oppose]")
