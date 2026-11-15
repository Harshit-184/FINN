"""Read side. Today this is the committed snapshot; the Postgres store will implement the same three
functions, so the API does not change when it is added."""
import json
from functools import lru_cache
from pathlib import Path
from ..engine.models import Alert, Bar, Filing

SNAP = Path(__file__).resolve().parents[2] / "data" / "snapshot"


def _read(name: str, default):
    p = SNAP / name
    return json.loads(p.read_text()) if p.exists() else default


@lru_cache
def filings() -> list[Filing]:
    return [Filing(**f) for f in _read("filings.json", [])]


@lru_cache
def alerts() -> list[Alert]:
    return [Alert(**a) for a in _read("alerts.json", [])]


@lru_cache
def prices() -> dict[str, list[Bar]]:
    return {s: [Bar(**b) for b in v] for s, v in _read("prices.json", {}).items()}


def meta() -> dict:
    return _read("meta.json", {"generated_at": None, "sources": {}})
