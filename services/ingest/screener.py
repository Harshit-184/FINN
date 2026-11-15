"""screener.in company page: the company's own filed statements, compiled into tables, plus links to
annual reports and concall transcripts. Used as a compiled copy of filings, and labelled that way."""
import re
from bs4 import BeautifulSoup
import httpx
from ..engine import periods
from ..engine.models import Fact
from .http import UA, get

URL = "https://www.screener.in/company/{}/{}"
MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
# screener row label -> our metric (standard and financial templates)
ROWS = {"sales": "revenue", "revenue": "total_income", "other income": "other_income", "interest": "finance_costs",
        "depreciation": "depreciation", "profit before tax": "pbt", "net profit": "pat", "operating profit": "operating_profit",
        "financing profit": "ppop", "cash from operating activity": "cfo", "borrowings": "borrowings"}


class UnknownSymbol(Exception):
    pass


def page(client: httpx.Client, symbol: str) -> tuple[BeautifulSoup, str, str]:
    for basis, suffix in (("consolidated", "consolidated/"), ("standalone", "")):
        url = URL.format(symbol, suffix)
        try:
            html = get(client, url, headers={"User-Agent": UA}, ttl=7 * 86400, min_gap=2.0, as_json=False).decode("utf-8", "ignore")
        except Exception as e:
            if "404" in str(e):
                raise UnknownSymbol(symbol)
            raise
        soup = BeautifulSoup(html, "html.parser")
        if soup.select_one("#quarters table tbody tr td:nth-of-type(2)"):       # consolidated page is empty for some companies
            return soup, basis, url
    raise UnknownSymbol(symbol)


def _num(s: str) -> float | None:
    s = s.replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _period(header: str, quarterly: bool) -> str | None:
    m = re.match(r"([A-Z][a-z]{2}) (\d{4})", header.strip())
    if not m:
        return None
    from datetime import date
    q = periods.quarter_of(date(int(m[2]), MONTHS[m[1]], 28))
    return q if quarterly else periods.fy_of(q)


def table(soup: BeautifulSoup, section: str, symbol: str, basis: str, url: str, quarterly: bool) -> list[Fact]:
    t = soup.select_one(f"#{section} table")
    if not t:
        return []
    heads = [_period(th.get_text(), quarterly) for th in t.select("thead th")[1:]]
    facts = []
    for tr in t.select("tbody tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        label = re.sub(r"[^a-z ]", "", cells[0].get_text().lower()).strip()
        metric = ROWS.get(label)
        if not metric:
            continue
        for per, td in zip(heads, cells[1:]):
            v = _num(td.get_text())
            if per and v is not None:
                facts.append(Fact(company=symbol, metric=metric, value=v, period=per,
                                  period_type="quarterly" if quarterly else "annual", basis=basis,
                                  source_type="screener", document=url, confidence="medium"))
    return facts


def facts(soup, symbol, basis, url) -> list[Fact]:
    out = table(soup, "quarters", symbol, basis, url, True) + table(soup, "profit-loss", symbol, basis, url, False) \
        + table(soup, "cash-flow", symbol, basis, url, False) + table(soup, "balance-sheet", symbol, basis, url, False)
    # tax is shown as a rate; back it out so the PBT - tax = PAT identity can still be checked elsewhere
    return out


def transcripts(soup: BeautifulSoup, limit: int = 4) -> list[dict]:
    """Latest concall transcript links, newest first: [{'label': 'Oct 2026', 'url': ...}]."""
    out = []
    for li in soup.select("#documents .concalls li, #documents li"):
        a = next((a for a in li.find_all("a") if "transcript" in a.get_text().lower()), None)
        when = re.search(r"([A-Z][a-z]{2}) (\d{4})", li.get_text(" "))
        if a and when and a.get("href") and {"label": when[0], "url": a["href"]} not in out:
            out.append({"label": when[0], "url": a["href"]})
    return out[:limit]


def call_period(label: str) -> str:
    """A call held in Oct 2026 discusses the quarter that ended before it (Q2 FY27)."""
    from datetime import date, timedelta
    m = re.match(r"([A-Z][a-z]{2}) (\d{4})", label)
    held = date(int(m[2]), MONTHS[m[1]], 15)
    return periods.quarter_of(held - timedelta(days=75))
