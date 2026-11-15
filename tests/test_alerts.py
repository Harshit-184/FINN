from datetime import datetime
from services.engine.alerts import combine, filing_alerts, price_volume_alerts
from services.engine.classify import classify
from services.engine.eventprice import strip
from services.engine.score import score
from helpers import bars, filing


def test_volume_spike_and_price_move():
    b = bars([100] * 21 + [106], [1000] * 21 + [3100])
    rules = {a.rule: a for a in price_volume_alerts("INFY", b, b[-1].d)}
    assert rules["volume_spike"].value == 3.1 and rules["price_move"].value == 6.0


def test_quiet_day_fires_nothing():
    b = bars([100] * 21 + [101], [1000] * 21 + [1500])
    assert price_volume_alerts("INFY", b, b[-1].d) == []


def test_suspended_sessions_are_skipped_in_the_average():
    b = bars([100] * 22, [1000] * 10 + [0] * 3 + [1000] * 8 + [1900])
    assert price_volume_alerts("INFY", b, b[-1].d) == []          # 1.9x of 1000, not 2.2x of a diluted average


def test_per_stock_threshold():
    b = bars([100] * 21 + [105])
    assert price_volume_alerts("INFY", b, b[-1].d)
    assert not price_volume_alerts("INFY", b, b[-1].d, {"per_stock": {"INFY": {"price_move_pct": 6.0}}})


def test_cooldown_folds_repeats_and_combo_fires():
    b = bars([100] * 21 + [106], [1000] * 21 + [3100])
    day = b[-1].d
    at = datetime.combine(day, datetime.min.time()).replace(hour=14).isoformat(sep=" ")
    f1 = score(classify(filing("Financial Results Q2", at=at, id="BSE:1")))
    f2 = score(classify(filing("Resignation of Chief Financial Officer", at=at, id="BSE:2")))
    f3 = score(classify(filing("Resignation of Managing Director", at=at, id="BSE:3")))
    alerts = combine(price_volume_alerts("INFY", b, day) + filing_alerts([f1, f2, f3]), [f1, f2, f3])
    by = {}
    for a in alerts:
        by.setdefault(a.rule, []).append(a)
    assert len(by["material_filing"]) == 1 and by["material_filing"][0].folded == 2
    assert len(by["combo"]) == 1 and len(by["volume_spike"]) == 1


def test_event_to_price_strip():
    b = bars([100, 100, 104, 105, 106, 107, 110])
    during = strip(b, datetime.combine(b[2].d, datetime.min.time()).replace(hour=11))
    assert during["before"]["close"] == 100 and during["t1"]["pct"] == 4.0 and during["t5"]["pct"] == 10.0
    after_close = strip(b, datetime.combine(b[2].d, datetime.min.time()).replace(hour=18))
    assert after_close["before"]["close"] == 104 and after_close["t5"] is None
    assert "not cause" in during["label"]
