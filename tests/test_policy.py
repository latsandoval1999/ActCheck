from pipeline import policy
from agents import costing


def test_ledac_match():
    assert policy.ledac("AN ACT CREATING THE DEPARTMENT OF WATER RESOURCES", "20")[0][0] == 3
    assert policy.ledac("AN ACT CREATING THE DEPARTMENT OF WATER RESOURCES", "19") == []
    assert policy.ledac("AN ACT DECLARING JUNE 5 A HOLIDAY", "20") == []


def test_policy_context_sources_exist():
    from pipeline.compare import load
    _, secs = load()
    ctx = policy.context({"title": "AN ACT CREATING THE DEPARTMENT OF WATER RESOURCES", "congress": "20"})
    ids = {x["source"] for x in ctx["ledac"]} | {x["source"] for x in ctx["bpf_2027_priority_areas"]}
    for i in ids:
        assert any(s["id"] == i for s in secs[i.split(":")[0]]), i


def test_gaa_comparators():
    c = {x["agency"]: x for x in costing.gaa_comparators()}
    assert c["National Water Resources Board"]["positions"] == 124
    assert 0.3 < c["National Water Resources Board"]["overhead_mooe_share"] < 0.4
    assert 900_000 < c["National Water Resources Board"]["per_position"] < 1_100_000
