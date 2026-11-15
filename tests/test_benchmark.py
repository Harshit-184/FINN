"""Real filings from the first live pull, with the category each one should get. Pass bar from the plan: >= 90%."""
import json
from pathlib import Path
from services.engine.classify import classify
from services.engine.models import Filing
from services.engine.score import score

BENCH = json.loads((Path(__file__).parent / "benchmark" / "nse_week_2026-11-15.json").read_text())["filings"]


def run():
    return [(row["expected"], score(classify(Filing(**{k: v for k, v in row.items() if k != "expected"})))) for row in BENCH]


def test_classification_accuracy():
    out = run()
    wrong = [(f.id, exp, f.category) for exp, f in out if f.category != exp]
    assert 1 - len(wrong) / len(out) >= 0.90, wrong


def test_no_routine_category_reaches_critical():
    routine = {"unclassified", "investor_meetings", "agm_egm", "postal_ballot", "dividend", "bonus_split"}
    assert not [f.id for exp, f in run() if exp in routine and f.tier == "critical"]


def test_results_filings_are_critical():
    assert all(f.tier == "critical" for exp, f in run() if exp == "results")
