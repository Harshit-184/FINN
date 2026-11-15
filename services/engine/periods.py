"""Indian fiscal periods. FY27 = 1 Apr 2026 .. 31 Mar 2027. Q1 = Apr-Jun."""
import re
from datetime import date

_Q = re.compile(r"^Q([1-4])_FY(\d{2})$")
_FY = re.compile(r"^FY(\d{2})$")


def quarter_of(d: date) -> str:
    """Fiscal quarter that contains date d (e.g. a quarter-end date)."""
    fy = d.year + 1 if d.month >= 4 else d.year
    q = (d.month - 4) % 12 // 3 + 1
    return f"Q{q}_FY{fy % 100:02d}"


def parse(period: str) -> tuple[int | None, int]:
    """-> (quarter or None, fiscal year as 2 digits)."""
    if m := _Q.match(period):
        return int(m[1]), int(m[2])
    if m := _FY.match(period):
        return None, int(m[1])
    raise ValueError(f"bad period: {period}")


def prev_quarter(period: str) -> str:
    q, fy = parse(period)
    if q is None:
        raise ValueError("annual period has no previous quarter")
    return f"Q{q - 1}_FY{fy:02d}" if q > 1 else f"Q4_FY{(fy - 1) % 100:02d}"


def year_ago(period: str) -> str:
    q, fy = parse(period)
    return f"FY{(fy - 1) % 100:02d}" if q is None else f"Q{q}_FY{(fy - 1) % 100:02d}"


def fy_of(period: str) -> str:
    return f"FY{parse(period)[1]:02d}"


def quarters_of(fy: str) -> list[str]:
    return [f"Q{q}_{fy}" for q in (1, 2, 3, 4)]


def end_date(period: str) -> date:
    q, fy = parse(period)
    year = 2000 + fy
    if q is None or q == 4:
        return date(year, 3, 31)
    return {1: date(year - 1, 6, 30), 2: date(year - 1, 9, 30), 3: date(year - 1, 12, 31)}[q]


def label(period: str) -> str:
    return period.replace("_", " ")
