import pytest
from services.engine import periods, verify
from services.engine.results import results_card
from helpers import fact, quarter


def test_periods():
    from datetime import date
    assert periods.quarter_of(date(2026, 9, 30)) == "Q2_FY27"
    assert periods.quarter_of(date(2027, 3, 31)) == "Q4_FY27"
    assert periods.prev_quarter("Q1_FY27") == "Q4_FY26"
    assert periods.year_ago("Q2_FY27") == "Q2_FY26" and periods.year_ago("FY27") == "FY26"
    assert periods.end_date("Q3_FY27") == date(2026, 12, 31)


def test_units():
    assert verify.to_crore(250000, "lakhs") == 2500
    assert verify.to_crore(5000, "millions") == 500
    with pytest.raises(ValueError):
        verify.to_crore(1, "dozens")


def card():
    facts = quarter("Q2_FY27", 1100, 220, 55, 165) + quarter("Q1_FY27", 1000, 200, 50, 150) + quarter("Q2_FY26", 880, 176, 44, 132)
    return results_card("TEST", "Q2_FY27", facts)


def test_headline_metrics_and_changes():                     # acceptance test 1 (synthetic input)
    c = card()
    rows = {r["metric"]: r for r in c["rows"]}
    assert [r["metric"] for r in c["rows"]] == ["revenue", "ebitda", "pbt", "pat"]
    assert rows["revenue"]["qoq"] == 10.0 and rows["revenue"]["yoy"] == 25.0
    assert rows["ebitda"]["value"] == 220 + 10 + 40 - 20       # PBT + finance + depreciation - other income
    assert rows["pat"]["yoy"] == 25.0
    assert c["reconciles"] and c["confidence"] == "high"


def test_margin_change_in_bps():
    facts = quarter("Q2_FY27", 1000, 200, 50, 150) + quarter("Q2_FY26", 1000, 180, 45, 135)
    m = results_card("TEST", "Q2_FY27", facts)["ebitda_margin"]
    assert m["pct"] == 23.0 and m["yoy_bps"] == 200


def test_numbers_that_do_not_reconcile_drop_to_low():
    c = results_card("TEST", "Q2_FY27", quarter("Q2_FY27", 1100, 220, 55, 190))
    assert not c["reconciles"] and c["confidence"] == "low"


def test_standalone_is_never_compared_with_consolidated():
    facts = quarter("Q2_FY27", 1100, 220, 55, 165) + quarter("Q1_FY27", 700, 150, 38, 112, basis="standalone")
    rows = {r["metric"]: r for r in results_card("TEST", "Q2_FY27", facts)["rows"]}
    assert rows["revenue"]["qoq"] is None


def test_missing_comparative_is_blank_not_guessed():
    rows = {r["metric"]: r for r in results_card("TEST", "Q2_FY27", quarter("Q2_FY27", 1100, 220, 55, 165))["rows"]}
    assert rows["pat"]["qoq"] is None and rows["pat"]["yoy"] is None


def test_wild_swing_is_held_at_medium():
    facts = quarter("Q2_FY27", 1100, 220, 55, 165) + quarter("Q1_FY27", 1000, 40, 10, 30)
    assert results_card("TEST", "Q2_FY27", facts)["confidence"] == "medium"


def test_bank_template_has_no_ebitda():
    facts = [fact(m, v, "Q2_FY27", company="HDFCBANK") for m, v in
             dict(total_income=900, net_interest_income=300, ppop=250, pbt=200, tax=50, pat=150).items()]
    c = results_card("HDFCBANK", "Q2_FY27", facts)
    assert c["template"] == "financial" and "ebitda" not in [r["metric"] for r in c["rows"]] and c["ebitda_margin"] is None


def test_cross_source_flag():
    a, b = fact("pat", 165, "Q2_FY27"), fact("pat", 171, "Q2_FY27", source="screener")
    assert not verify.cross_source(a, b).ok and verify.cross_source(a, fact("pat", 165.2, "Q2_FY27", source="screener")).ok
