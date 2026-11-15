from services.engine.dedupe import dedupe, latest
from helpers import filing


def test_same_filing_on_both_exchanges_is_one_item():
    a = filing("Outcome of Board Meeting - Financial Results Q2 FY27", exchange="NSE", at="2026-11-13 18:05", id="NSE:1")
    b = filing("Financial Results for quarter ended 30.09.2026 - Outcome of Board Meeting", exchange="BSE", at="2026-11-13 18:09", id="BSE:9")
    out = dedupe([b, a])
    assert len(out) == 1 and out[0].id == "NSE:1" and out[0].also_on == ["BSE:9"]


def test_different_filings_close_in_time_stay_separate():
    a = filing("Financial Results Q2 FY27", exchange="NSE", at="2026-11-13 18:05")
    b = filing("Resignation of Chief Financial Officer", exchange="BSE", at="2026-11-13 18:07")
    assert len(dedupe([a, b])) == 2


def test_same_subject_an_hour_apart_is_not_merged():
    a = filing("Press Release", exchange="NSE", at="2026-11-13 10:00")
    b = filing("Press Release", exchange="BSE", at="2026-11-13 11:30")
    assert len(dedupe([a, b])) == 2


def test_amendment_becomes_latest():           # acceptance test 2
    orig = filing("Unaudited Financial Results for the quarter ended September 30, 2026", at="2026-11-12 18:00", id="BSE:1")
    rev = filing("Revised - Unaudited Financial Results for the quarter ended September 30, 2026", at="2026-11-13 11:00", id="BSE:2")
    out = dedupe([orig, rev])
    shown = latest(out)
    assert [f.id for f in shown] == ["BSE:2"]
    assert shown[0].amends == "BSE:1" and next(f for f in out if f.id == "BSE:1").superseded_by == "BSE:2"


def test_corrigendum_for_another_company_does_not_supersede():
    orig = filing("Notice of Postal Ballot", symbol="ITC", at="2026-11-12 18:00")
    rev = filing("Corrigendum to Notice of Postal Ballot", symbol="LT", at="2026-11-13 11:00")
    assert len(latest(dedupe([orig, rev]))) == 2
