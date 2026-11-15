import pytest
from services.engine.classify import classify, needs_llm
from helpers import filing

CASES = [
    ("Outcome of Board Meeting - Unaudited Financial Results for the quarter ended September 30, 2026", "results"),
    ("Board Meeting Intimation for considering financial results", None),   # a date notice is not a result
    ("Resignation of Chief Financial Officer", "management_change"),
    ("Appointment of Mr. X as Independent Director", "management_change"),
    ("Appointment of Scrutinizer for Postal Ballot", "postal_ballot"),      # 'appoint' without a management role
    ("Acquisition of 51% stake in ABC Private Limited", "m_and_a"),
    ("Receipt of Show Cause Notice from GST authority", "litigation"),
    ("Creation of pledge on promoter shares", "pledging"),
    ("Credit Rating - ICRA reaffirms AAA", "credit_rating"),
    ("Allotment of Non-Convertible Debentures on private placement", "fund_raise"),
    ("Declaration of Interim Dividend and Record Date", "dividend"),
    ("Sub-division of equity shares", "bonus_split"),
    ("Transcript of Earnings Call for Q2 FY27", "earnings_call"),
    ("Schedule of Analyst / Institutional Investor Meet", "investor_meetings"),
    ("Notice of 45th Annual General Meeting", "agm_egm"),
    ("Press Release - Company bags order worth Rs. 2,500 crore", "press_release"),
    ("Commencement of commercial production at new plant", "capex"),
    ("Compliance Certificate under Regulation 74(5)", "unclassified"),
    ("Newspaper Publication of financial results", "unclassified"),          # compliance wins over 'results'
    ("Grant of ESOP under Employee Stock Option Scheme", "unclassified"),
]


@pytest.mark.parametrize("subject,expected", CASES)
def test_rules(subject, expected):
    f = classify(filing(subject))
    if expected is None:
        assert f.category != "results"
    else:
        assert f.category == expected, f.rule_why


def test_unmatched_goes_to_llm_queue():
    f = classify(filing("Intimation regarding change of registered office address"))
    assert f.category == "unclassified" and needs_llm(f)


def test_rule_hit_is_not_sent_to_llm():
    assert not needs_llm(classify(filing("Compliance Certificate under Regulation 74(5)")))


def test_exchange_category_is_used():
    f = classify(filing("Announcement under Regulation 30 (LODR)", raw="Company Update | Credit Rating"))
    assert f.category == "credit_rating"
