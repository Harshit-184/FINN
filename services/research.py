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
PROMPT = (Path(__file__).parent / "llm" / "prompts" / "guidance_v3.txt").read_text()


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


CUE = re.compile(r"guidance|outlook|expect|target|aspir|aim to|we (?:will|should|plan|intend)|going forward|next (?:year|fiscal|quarter)|"
                 r"current (?:year|fiscal)|full year|by (?:the )?end of|fy ?'?\d\d|fiscal \d\d", re.I)
PAGE_BUDGET = 36_000          # characters per transcript sent to the model (about 9k tokens)


STRONG = re.compile(r"guidance|guiding|guided", re.I)
MEDIUM = re.compile(r"outlook|target|aspir|we expect|expected to|margin band", re.I)
QUANT = re.compile(r"\d(?:\.\d+)?\s?%|\bcrores?\b|\bbps\b|basis points", re.I)


def page_score(text: str) -> int:
    """Pages where management states a target say 'guidance' and carry a percentage or a rupee amount."""
    if not QUANT.search(text) or not (STRONG.search(text) or MEDIUM.search(text) or CUE.search(text)):
        return 0
    return 6 * len(STRONG.findall(text)) + 3 * len(MEDIUM.findall(text)) + len(CUE.findall(text)) + min(len(QUANT.findall(text)), 5)


def relevant_pages(pages: list[str], budget: int = PAGE_BUDGET) -> list[int]:
    """Guidance sits on a handful of pages. Rank pages and keep the best within the budget, so four transcripts
    fit in one model call."""
    scored = sorted(((page_score(p), -i) for i, p in enumerate(pages) if page_score(p) > 0), reverse=True)
    keep, used = [], 0
    for _, neg in scored:
        i = -neg
        if used + len(pages[i]) > budget and keep:
            continue
        keep.append(i); used += len(pages[i])
    return sorted(keep)


def extract_all(client, symbol: str, name: str, calls: list[dict]) -> tuple[list[GuidanceItem], list[dict]]:
    """One model call per company: every transcript, relevant pages only. Request count, not tokens, is the
    binding limit on a free tier, and this turns 4 requests into 1."""
    docs, blocks, hashes, texts = [], [], [], {}
    for n, t in enumerate(calls, 1):
        info = {"n": n, "label": t["label"], "period": screener.call_period(t["label"]), "url": t["url"],
                "pages": 0, "pages_sent": 0, "extracted": 0, "kept": 0, "dropped": []}
        docs.append(info)
        try:
            data = get(client, t["url"], headers={"User-Agent": UA, "Referer": "https://www.bseindia.com/"}, ttl=365 * 86400, as_json=False)
            pages = pdf_pages(data)
        except Exception as e:
            info["error"] = f"could not read transcript: {type(e).__name__}"
            continue
        keep = relevant_pages(pages)
        info["pages"], info["pages_sent"] = len(pages), len(keep)
        texts[n] = pages
        hashes.append(hashlib.sha1(data).hexdigest())
        blocks.append(f"[DOC {n}] call discussing {periods.label(info['period'])}\n" + "\n".join(f"[PAGE {i + 1}]\n{pages[i]}" for i in keep))
    if not blocks:
        return [], docs
    raw = router.ask_json(client, PROMPT.format(company=name, symbol=symbol, text="\n\n".join(blocks)),
                          doc_hash=hashlib.sha1("".join(hashes).encode()).hexdigest(), prompt_version="guidance_v3")
    if raw is None:
        say(f"llm error: {router.last_error}")
        for d in docs:
            d.setdefault("error", "model unavailable or returned invalid output")
        return [], docs
    items = []
    by_n = {d["n"]: d for d in docs}
    for r in raw:
        info = by_n.get(int(r.get("doc") or 0))
        if not info or info["n"] not in texts:
            continue
        info["extracted"] += 1
        page = grounded(r, texts[info["n"]])
        try:
            if page is None:
                raise ValueError("quote not found in the transcript")
            if r["metric"] == "other":
                raise ValueError("metric has no verified actuals")
            periods.parse(r["period"])
            said = f"{r.get('metric_label', '')} {r['quote']}".lower()
            metric, caveat = r["metric"], ""
            # Traps found on the first live runs: a segment target judged against company totals (Dixon), growth guided
            # in constant currency set beside rupee growth, and "operating margin" read as EBITDA margin (Infosys).
            segment = str(r.get("segment") or "this business") if r.get("scope") != "company" else ""
            if segment:
                caveat = f"This target is for {segment}, not the whole company. Segment actuals are not in the structured data yet, so it is not judged against company totals."
            elif r.get("currency_basis") == "constant_currency" or r["kind"] == "growth" and re.search(r"constant.currency|\bcc\b", said):
                caveat = "Guidance is in constant currency; filed statements report rupee revenue, so the two are not comparable."
            if not segment and r["kind"] == "margin" and re.search(r"operating margin|ebit margin|\bebit\b", said) and "ebitda" not in said:
                metric = "ebit"
            items.append(GuidanceItem(company=symbol, metric=metric, caveat=caveat, segment=segment, kind=r["kind"],
                                      low=float(r["low"]), high=float(r["high"]), unit="INR_CRORE" if r["kind"] == "absolute" else "PCT",
                                      period=r["period"], stated_in=info["period"], speaker=str(r.get("speaker", "")), quote=r["quote"],
                                      document=info["url"], page=page, supersedes_explicitly=bool(r.get("revises_earlier")),
                                      withdrawn=bool(r.get("withdrawn"))))
            info["kept"] += 1
        except (KeyError, ValueError, TypeError) as e:
            info["dropped"].append({"label": r.get("metric_label") or r.get("metric"), "why": str(e), "quote": str(r.get("quote", ""))[:200],
                                    "page": page, "period": r.get("period")})
    return items, docs


def research(client, symbol: str) -> dict:
    symbol = symbol.upper()
    try:
        soup, basis, url = screener.page(client, symbol)
    except screener.UnknownSymbol:
        return {"symbol": symbol, "error": f"{symbol} was not found. Check the NSE symbol."}
    name = (company(symbol) or {}).get("name") or (soup.select_one("h1").get_text(strip=True) if soup.select_one("h1") else symbol)
    facts = screener.facts(soup, symbol, basis, url)
    # EBITDA proxy from the compiled table: operating profit (before other income, interest, depreciation)
    dep = {(f.period, f.basis): f.value for f in facts if f.metric == "depreciation"}
    for f in [f for f in facts if f.metric == "operating_profit"]:
        facts.append(f.model_copy(update={"metric": "ebitda"}))
        if (f.period, f.basis) in dep:                 # EBIT = operating profit - depreciation
            facts.append(f.model_copy(update={"metric": "ebit", "value": f.value - dep[(f.period, f.basis)], "source_type": "derived"}))
    calls = screener.transcripts(soup)
    say(f"{symbol}: {len(facts)} facts ({basis}), {len(calls)} transcripts")
    items, docs = extract_all(client, symbol, name, calls)
    for d in docs:
        say(f"{symbol}: {d['label']} pages={d['pages']} sent={d['pages_sent']} extracted={d['extracted']} kept={d['kept']} {d.get('error', '')}")
    latest = max((d["period"] for d in docs if not d.get("error")), key=match.order, default=None)
    verdicts = match.scorecard(items, [f for f in facts if f.basis == basis], latest)
    quarters = sorted({f.period for f in facts if f.period_type == "quarterly"}, key=match.order)
    return {"symbol": symbol, "name": name, "basis": basis, "source_page": url,
            "actuals_note": "Actuals are from screener.in's tables, a compiled copy of the company's filed statements. Not yet cross-checked against XBRL, so confidence is Medium.",
            "latest_quarter": quarters[-1] if quarters else None, "documents": docs,
            "scorecard": [v.model_dump(mode="json") for v in verdicts],
            "facts": [f.model_dump(mode="json") for f in facts if f.metric in ("revenue", "total_income", "ebitda", "ebit", "pat", "pbt", "cfo", "ppop", "other_income", "finance_costs", "depreciation")]}


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
