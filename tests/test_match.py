from services.engine.match import scorecard
from helpers import fact, guide


def year(fy, vals, metric="revenue"):
    return [fact(metric, v, f"Q{i + 1}_{fy}") for i, v in enumerate(vals)]


FY26 = year("FY26", [1000, 1000, 1000, 1000])


def one(items, facts, **kw):
    return {(v.item.stated_in, v.status): v for v in scorecard(items, facts, **kw)}


def test_delivered_growth_target():
    v = scorecard([guide("revenue", "growth", 8, 10, "FY27", "Q4_FY26")], FY26 + year("FY27", [1080, 1090, 1100, 1090]))[0]
    assert v.status == "delivered" and v.actual == 9.0


def test_partial_and_missed():
    g = [guide("revenue", "growth", 10, 12, "FY27", "Q4_FY26")]
    assert scorecard(g, FY26 + year("FY27", [1085] * 4))[0].status == "partially_delivered"     # 8.5% vs 10%
    assert scorecard(g, FY26 + year("FY27", [1040] * 4))[0].status == "missed"                  # 4%


def test_full_year_target_is_not_judged_on_two_quarters():
    v = scorecard([guide("revenue", "growth", 10, 12, "FY27", "Q4_FY26")], FY26 + year("FY27", [1020, 1030]))[0]
    assert v.status == "pending" and v.actual is None and "+2.5% YoY over the first 2 quarter(s)" in v.progress


def test_changed_range_is_revised_and_both_are_kept():
    items = [guide("revenue", "growth", 8, 10, "FY27", "Q4_FY26"), guide("revenue", "growth", 5, 6, "FY27", "Q2_FY27")]
    out = one(items, FY26 + year("FY27", [1050, 1055]))
    old = out[("Q4_FY26", "revised")]
    assert old.replaced_by.low == 5 and ("Q2_FY27", "pending") in out


def test_repeating_the_same_target_is_not_a_revision():
    items = [guide("revenue", "growth", 8, 10, "FY27", "Q4_FY26"), guide("revenue", "growth", 8, 10, "FY27", "Q1_FY27")]
    assert [v.status for v in scorecard(items, FY26)] == ["not_verifiable"]


def test_withdrawn():
    items = [guide("revenue", "growth", 8, 10, "FY27", "Q4_FY26"),
             guide("revenue", "growth", 8, 10, "FY27", "Q2_FY27", withdrawn=True)]
    assert [v.status for v in scorecard(items, FY26)] == ["withdrawn"]


def test_silence_is_a_note_not_a_status():
    v = scorecard([guide("revenue", "growth", 10, 12, "FY27", "Q4_FY26")], FY26 + year("FY27", [1100]), latest_transcript="Q2_FY27")[0]
    assert v.status == "pending" and v.note.startswith("Not reiterated")


def test_margin_target():
    facts = year("FY27", [1000] * 4) + year("FY27", [210] * 4, metric="ebitda")
    assert scorecard([guide("ebitda", "margin", 20, 22, "FY27", "Q4_FY26")], facts)[0].actual == 21.0


def test_no_data_is_not_verifiable():
    v = scorecard([guide("order_book", "absolute", 5000, 5000, "FY27", "Q4_FY26")], [])[0]
    assert v.status == "not_verifiable"


def test_same_target_said_twice_on_one_call_is_one_item():
    items = [guide("revenue", "growth", 1.5, 3, "FY27", "Q1_FY27"), guide("revenue", "growth", 1.5, 3, "FY27", "Q1_FY27")]
    assert len(scorecard(items, FY26)) == 1


def test_constant_currency_guidance_is_never_judged_on_rupee_growth():
    g = [guide("revenue", "growth", 1, 2, "FY27", "Q2_FY27", caveat="Guidance is in constant currency; not comparable.")]
    part = scorecard(g, FY26 + year("FY27", [1120, 1125]))[0]
    full = scorecard(g, FY26 + year("FY27", [1120] * 4))[0]
    assert part.status == "pending" and full.status == "not_verifiable"
    assert "for context" in full.note and "+12.0%" in full.note and full.actual is None


def test_segment_target_is_never_judged_against_company_totals():
    g = [guide("revenue", "absolute", 5500, 6000, "FY26", "Q3_FY26", segment="Telecom", caveat="This target is for Telecom, not the whole company.")]
    v = scorecard(g, [fact("revenue", 48873, "FY26", period_type="annual")])[0]
    assert v.status == "not_verifiable" and v.actual is None and "Telecom" in v.note
