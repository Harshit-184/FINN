"""Loads the YAML config once. Everything tunable lives in config/, not in code."""
from functools import lru_cache
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def load(name: str) -> dict:
    return yaml.safe_load((ROOT / "config" / f"{name}.yaml").read_text())


@lru_cache
def holdings() -> dict[str, dict]:
    return {h["symbol"]: h for h in load("portfolio")["holdings"]}


def company(symbol: str) -> dict | None:
    if symbol in holdings():
        return holdings()[symbol]
    for c in load("portfolio").get("research_only", []):
        if c["symbol"] == symbol:
            return c
    return None


def template_for(symbol: str) -> str:
    c = company(symbol) or {}
    return c.get("template", "standard")
