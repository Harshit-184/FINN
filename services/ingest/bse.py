"""BSE corporate announcements. BSE keys everything on scrip code, and returns its own category and
subcategory, which the rule classifier uses as a strong hint."""
from datetime import date, datetime
import httpx
from ..engine.models import Filing
from .http import UA, get

API = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
PDF = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/{}"
HEADERS = {"User-Agent": UA, "Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com",
           "Accept": "application/json, text/plain, */*"}


def parse(row: dict, symbol: str) -> Filing:
    stamp = row.get("DT_TM") or row.get("NEWS_DT") or row["DissemDT"]
    att = (row.get("ATTACHMENTNAME") or "").strip()
    raw = " | ".join(x for x in (row.get("CATEGORYNAME"), row.get("SUBCATNAME")) if x and x != "-1")
    return Filing(id=f"BSE:{row['NEWSID']}", symbol=symbol, exchange="BSE",
                  filed_at=datetime.fromisoformat(stamp[:19]), subject=(row.get("NEWSSUB") or row.get("HEADLINE") or "").strip(),
                  body=(row.get("HEADLINE") or "").strip(), raw_category=raw,
                  pdf_url=PDF.format(att) if att else None,
                  source_url=f"https://www.bseindia.com/stock-share-price/x/x/{row.get('SCRIP_CD')}/corp-announcements/")


def announcements(client: httpx.Client, symbol: str, scrip: int, start: date, end: date) -> list[Filing]:
    out, page = [], 1
    while True:
        data = get(client, API, headers=HEADERS, params={
            "pageno": page, "strCat": "-1", "strPrevDate": start.strftime("%Y%m%d"), "strScrip": str(scrip),
            "strSearch": "P", "strToDate": end.strftime("%Y%m%d"), "strType": "C", "subcategory": "-1"})
        rows = data.get("Table") or []
        out += [parse(r, symbol) for r in rows]
        total = (data.get("Table1") or [{}])[0].get("ROWCNT", 0)
        if not rows or len(out) >= total or page >= 10:
            return out
        page += 1
