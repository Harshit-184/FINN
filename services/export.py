"""Writes the static fallback the web app ships with: the same payloads the API returns, as files.

    python -m services.export            (run after services.pipeline)
"""
import json
from pathlib import Path
from .api import main, store
from .engine.config import holdings

OUT = Path(__file__).resolve().parents[1] / "apps" / "web" / "public" / "snapshot"


def run(extra: dict | None = None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {f"brief_{w}.json": {**main.brief(w), **(extra or {})} for w in main.WINDOWS}
    files |= {"portfolio.json": main.portfolio(), "alerts.json": main.alerts(), "rules.json": main.rules(),
              "meta.json": {**store.meta(), **(extra or {})}}
    files |= {f"company_{s}.json": main.company_page(s) for s in holdings()}
    for name, payload in files.items():
        (OUT / name).write_text(json.dumps(payload))
    return len(files)


if __name__ == "__main__":
    print(f"wrote {run()} files to {OUT}")
