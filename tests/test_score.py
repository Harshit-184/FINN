from services.engine.classify import classify
from services.engine.score import amount_cr, score
from helpers import filing


def run(subject, symbol="INFY", **kw):
    return score(classify(filing(subject, symbol=symbol, **kw)), market_cap_cr=kw.pop("mcap", None))


def test_results_is_critical():
    f = run("Outcome of Board Meeting - Audited Financial Results")
    assert f.tier == "critical" and f.score_terms["M"] == 90


def test_cfo_exit_outranks_independent_director():
    cfo, ind = run("Resignation of Chief Financial Officer"), run("Appointment of Independent Director")
    assert cfo.score > ind.score and cfo.score_terms["S"] == 100 and ind.score_terms["S"] == 40


def test_compliance_certificate_is_never_critical():        # acceptance test 3
    for sym in ("RELIANCE", "CDSL"):
        f = run("Compliance Certificate under Regulation 74(5)", symbol=sym)
        assert f.tier == "routine"


def test_small_holding_does_not_hide_a_downgrade():
    f = run("Credit Rating - CRISIL downgrades long-term rating", symbol="CDSL")
    assert f.tier == "critical" and f.score_terms.get("override") == 1.0


def test_reaffirmation_is_not_escalated():
    assert run("Credit Rating - ICRA reaffirms AAA", symbol="CDSL").tier != "critical"


def test_thesis_pillar_is_tagged():
    f = run("Press Release - Infosys announces large deal win with a European bank")
    assert f.pillar == "large_deals" and f.score_terms["T"] == 100


def test_exposure_scales_with_weight():
    assert run("Declaration of Dividend", symbol="RELIANCE").score_terms["P"] == 100
    assert run("Declaration of Dividend", symbol="CDSL").score_terms["P"] == 30


def test_amount_parsing():
    assert amount_cr("order worth Rs. 2,500 crore") == 2500
    assert amount_cr("penalty of INR 45 lakhs") == 0.45
    assert amount_cr("no amount here") is None


def test_deal_size_raises_severity():
    small = score(classify(filing("Acquisition of ABC for Rs. 50 crore")), market_cap_cr=600000)
    big = score(classify(filing("Acquisition of ABC for Rs. 40,000 crore")), market_cap_cr=600000)
    assert big.score_terms["S"] == 100 and small.score_terms["S"] == 70


def test_market_reaction_is_not_a_score_term():
    assert set(run("Financial Results").score_terms) <= {"M", "S", "T", "P", "C", "override"}


def test_dividend_from_the_largest_holding_stays_routine():
    f = run("Declaration of Interim Dividend", symbol="RELIANCE")
    assert f.tier == "routine" and f.score < 45


def test_transcript_landing_lifts_an_earnings_call():
    assert run("Transcript of Earnings Call for Q2 FY27").score > run("Intimation of Earnings Conference Call").score
