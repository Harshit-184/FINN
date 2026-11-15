"""Pull: research one NSE symbol from primary sources and write data/research/<SYMBOL>.json.

    python -m services.research INFY PERSISTENT

Steps: resolve on screener -> actuals (tables) -> last 4 concall transcripts -> guidance extraction (cheap model,
schema-checked, every quote must be found on the page it cites) -> matching in code -> scorecard.
"""
import hashlib, json, re, sys
from pathlib import Path
import httpx
from .engine import match, periods
from .engine.config import company
from .engine.models import GuidanceItem
from .ingest import screener
from .ingest.http import UA, get
from .llm import router
from .pipeline import say

OUT = Path(__file__).resolve().parents[1] / "data" / "research"
PROMPT = (Path(__file__).parent / "llm" / "prompts" / "guidance_v1.txt").read_text()


def pdf_pages(data: bytes) -> list[str]:
    import pymupdf
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [p.get_text() for p in doc]


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def grounded(item: dict, pages: list[str]) -> int | None:
    """The quote must appear on the cited page (or a neighbour: PDF page labels drift). Returns the real page or None."""
    q = _squash(item.get("quote", ""))[:120]
    if len(q) < 25:
        return None
    cited = int(item.get("page") or 0)
    for n in sorted(range(1, len(pages) + 1), key=lambda n: abs(n - cited)):
        if q in _squash(pages[n - 1]):
            return n
    return None


def extract(client, symbol: str, name: str, t: dict) -> tuple[list[GuidanceItem], dict]:
    stated_in = screener.call_period(t["label"])
    info = {"label": t["label"], "period": stated_in, "url": t["url"], "pages": 0, "extracted": 0, "kept": 0, "dropped": []}
    try:
        data = get(client, t["url"], headers={"User-Agent": UA, "Referer": "https://www.bseindia.com/"}, ttl=365 * 86400, as_json=False)
        pages = pdf_pages(data)
    except Exception as e:
        info["error"] = f"could not read transcript: {type(e).__name__}"
        return [], info
    info["pages"] = len(pages)
    text = "\n".join(f"[PAGE {i + 1}]\n{p}" for i, p in enumerate(pages))[:180_000]
    raw = router.ask_json(client, PROMPT.format(company=name, symbol=symbol, call_period=periods.label(stated_in), text=text),
                          doc_hash=hashlib.sha1(data).hexdigest(), prompt_version="guidance_v1")
    if raw is None:
        info["error"] = "model unavailable or returned invalid output"
        say(f"llm error: {router.last_error} | tried: {router._candidates.get('cheap')}")
        return [], info
    items = []
    info["extracted"] = len(raw)
    for r in raw:
        page = grounded(r, pages)
        try:
            if page is None:
                raise ValueError("quote not found in the transcript")
            if r["metric"] == "other":
                raise ValueError("metric has no verified actuals")
            periods.parse(r["period"])
            items.append(GuidanceItem(company=symbol, metric=r["metric"], kind=r["kind"], low=float(r["low"]), high=float(r["high"]),
                                      unit="INR_CRORE" if r["kind"] == "absolute" else "PCT", period=r["period"], stated_in=stated_in,
                                      speaker=str(r.get("speaker", "")), quote=r["quote"], document=t["url"], page=page,
                                      supersedes_explicitly=bool(r.get("revises_earlier")), withdrawn=bool(r.get("withdrawn"))))
        except (KeyError, ValueError, TypeError) as e:
            info["dropped"].append({"label": r.get("metric_label") or r.get("metric"), "why": str(e), "quote": r.get("quote", "")[:200],
                                    "page": page, "period": r.get("period")})
    info["kept"] = len(items)
    return items, info


def research(client, symbol: str) -> dict:
    symbol = symbol.upper()
    try:
        soup, basis, url = screener.page(client, symbol)
    except screener.UnknownSymbol:
        return {"symbol": symbol, "error": f"{symbol} was not found. Check the NSE symbol."}
    name = (company(symbol) or {}).get("name") or (soup.select_one("h1").get_text(strip=True) if soup.select_one("h1") else symbol)
    facts = screener.facts(soup, symbol, basis, url)
    # EBITDA proxy from the compiled table: operating profit (before other income, interest, depreciation)
    for f in [f for f in facts if f.metric == "operating_profit"]:
        facts.append(f.model_copy(update={"metric": "ebitda"}))
    calls = screener.transcripts(soup)
    say(f"{symbol}: {len(facts)} facts ({basis}), {len(calls)} transcripts")
    items, docs = [], []
    for t in calls:
        got, info = extract(client, symbol, name, t)
        if not info.get("error"):
            say(f"model used: {router._candidates.get('cheap', ['?'])[0]}")
        say(f"{symbol}: {t['label']} pages={info['pages']} extracted={info['extracted']} kept={info['kept']} {info.get('error', '')}")
        items += got; docs.append(info)
    latest = max((d["period"] for d in docs if not d.get("error")), key=match.order, default=None)
    verdicts = match.scorecard(items, [f for f in facts if f.basis == basis], latest)
    quarters = sorted({f.period for f in facts if f.period_type == "quarterly"}, key=match.order)
    return {"symbol": symbol, "name": name, "basis": basis, "source_page": url,
            "actuals_note": "Actuals are from screener.in's tables, a compiled copy of the company's filed statements. Not yet cross-checked against XBRL, so confidence is Medium.",
            "latest_quarter": quarters[-1] if quarters else None, "documents": docs,
            "scorecard": [v.model_dump(mode="json") for v in verdicts],
            "facts": [f.model_dump(mode="json") for f in facts if f.metric in ("revenue", "total_income", "ebitda", "pat", "pbt", "cfo", "ppop")]}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True) as client:
        for sym in sys.argv[1:]:
            try:
                res = research(client, sym)
            except Exception as e:                       # one bad ticker must not stop the batch
                res = {"symbol": sym.upper(), "error": f"{type(e).__name__}: {e}"}
            say(f"{sym}: " + (res.get("error") or f"{len(res['scorecard'])} guidance items scored"))
            (OUT / f"{sym.upper()}.json").write_text(json.dumps(res, indent=1))
