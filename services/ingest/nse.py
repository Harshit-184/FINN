"""NSE corporate announcements. NSE needs cookies from a normal page load first and blocks many
cloud IPs, so this runs from a laptop or GitHub Actions and BSE is the second source."""
from datetime import date, datetime
import httpx
from ..engine.models import Filing
from .http import UA, get

HOME = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
API = "https://www.nseindia.com/api/corporate-announcements"
HEADERS = {"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9", "Referer": HOME}


def warm(client: httpx.Client) -> None:
    client.get(HOME, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=20)


def parse(row: dict) -> Filing:
    stamp = row.get("sort_date") or datetime.strptime(row["an_dt"], "%d-%b-%Y %H:%M:%S").isoformat(sep=" ")
    return Filing(id=f"NSE:{row.get('seq_id') or row.get('attchmntFile', '')[-40:]}", symbol=row["symbol"], exchange="NSE",
                  filed_at=datetime.fromisoformat(stamp[:19]), subject=(row.get("desc") or "").strip(),
                  body=(row.get("attchmntText") or "").strip(), raw_category=(row.get("desc") or "").strip(),
                  pdf_url=row.get("attchmntFile") or None, source_url=HOME)


def announcements(client: httpx.Client, symbol: str, start: date, end: date) -> list[Filing]:
    if not client.cookies:
        warm(client)
    rows = get(client, API, headers=HEADERS, min_gap=2.0, params={
        "index": "equities", "symbol": symbol, "from_date": start.strftime("%d-%m-%Y"), "to_date": end.strftime("%d-%m-%Y")})
    return [parse(r) for r in rows if r.get("symbol") == symbol]
