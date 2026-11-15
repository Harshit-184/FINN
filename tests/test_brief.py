"""End to end over the pure pipeline function and the API, with made-up inputs and no network."""
from datetime import datetime
from fastapi.testclient import TestClient
from services.engine import brief
from services.pipeline import process
from helpers import bars, filing


def sample():
    b = bars([100] * 21 + [106], [1000] * 21 + [3100])
    day = b[-1].d.isoformat()
    raw = [filing("Outcome of Board Meeting - Unaudited Financial Results", at=f"{day} 14:00", exchange="NSE", id="NSE:1"),
           filing("Unaudited Financial Results - Outcome of Board Meeting", at=f"{day} 14:04", exchange="BSE", id="BSE:1"),
           filing("Compliance Certificate under Regulation 74(5)", at=f"{day} 10:00", id="BSE:2"),
           filing("Credit Rating - ICRA reaffirms AAA", symbol="TATAPOWER", at=f"{day} 11:00", id="BSE:3"),
           filing("Declaration of Interim Dividend", symbol="ITC", at=f"{day} 12:00", id="BSE:4")]
    return raw, {"INFY": b}, datetime.fromisoformat(f"{day} 20:00")


def test_brief_tiers_and_headline():
    raw, prices, now = sample()
    filings, alerts = process(raw, prices)
    out = brief.build(filings, alerts, now)
    assert [c["id"] for c in out["critical"]] == ["NSE:1"]            # merged with its BSE twin
    assert all(c["category"] != "unclassified" for c in out["critical"] + out["notable"])
    assert {c["id"] for c in out["routine"]} >= {"BSE:2", "BSE:4"}
    assert out["headline"].startswith("1 thing matters: INFY results")
    assert out["needs_attention"][0]["symbol"] == "INFY" and out["needs_attention"][0]["direction"] == "positive"
    assert any(a["rule"] == "combo" for a in out["alerts"])


def test_quiet_day():
    out = brief.build([], [], datetime(2026, 11, 13, 20))
    assert out["headline"] == "Quiet day. 0 critical filings in your 18 holdings."


def test_api_runs_without_llm_key_or_snapshot(monkeypatch, tmp_path):     # acceptance test 6
    from services.api import main, store
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(store, "SNAP", tmp_path)
    for fn in (store.filings, store.alerts, store.prices):
        fn.cache_clear()
    c = TestClient(main.app)
    assert c.get("/health").json()["llm"] is False
    assert c.get("/brief").status_code == 200 and len(c.get("/portfolio").json()["holdings"]) == 18
    assert c.get("/alerts").json() == [] and c.get("/company/NOPE").status_code == 404
    assert c.get("/brief?window=2y").status_code == 400


def test_weekend_window_reaches_back_to_the_last_session():
    from datetime import date
    f = [__import__("services.engine.score", fromlist=["score"]).score(
        __import__("services.engine.classify", fromlist=["classify"]).classify(
            filing("Outcome of Board Meeting - Financial Results", at="2026-11-13 17:00")))]
    sunday = datetime(2026, 11, 15, 17, 0)
    assert brief.build(f, [], sunday)["critical"] == []
    out = brief.build(f, [], sunday, last_session=date(2026, 11, 13))
    assert len(out["critical"]) == 1 and "closed since Fri 13 Nov" in out["note"]
