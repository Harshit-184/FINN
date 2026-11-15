"""Contracts shared by ingestion, engine, API and LLM outputs."""
from __future__ import annotations
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

Category = Literal[
    "results", "m_and_a", "management_change", "litigation", "fund_raise", "pledging",
    "credit_rating", "capex", "insider_trading", "bonus_split", "dividend", "press_release",
    "earnings_call", "investor_meetings", "agm_egm", "postal_ballot", "unclassified",
]
Tier = Literal["critical", "notable", "routine"]
Evidence = Literal["reported", "guidance", "interpretation"]
Confidence = Literal["high", "medium", "low"]
Basis = Literal["consolidated", "standalone"]


class Filing(BaseModel):
    id: str                                   # "<exchange>:<exchange id>"
    symbol: str
    exchange: Literal["NSE", "BSE"]
    filed_at: datetime                        # IST, naive
    subject: str
    body: str = ""
    headline: str = ""                        # what the card shows: the body without exchange boilerplate
    raw_category: str = ""                    # exchange's own category / subcategory
    pdf_url: Optional[str] = None
    source_url: Optional[str] = None
    # filled by the engine
    also_on: list[str] = Field(default_factory=list)     # ids of the same filing on the other exchange
    amends: Optional[str] = None                         # id of the filing this one revises
    superseded_by: Optional[str] = None
    category: Category = "unclassified"
    classified_by: Literal["rule", "llm", "none"] = "none"
    rule_why: str = ""
    confidence: Confidence = "high"
    score: float = 0.0
    score_terms: dict[str, float] = Field(default_factory=dict)
    tier: Tier = "routine"
    pillar: Optional[str] = None                         # thesis pillar id it touches
    pillar_evidence: Optional[str] = None
    amount_cr: Optional[float] = None


class Fact(BaseModel):
    """One number. Never stored as free text."""
    company: str
    metric: str
    value: float
    unit: Literal["INR_CRORE", "PCT", "RATIO"] = "INR_CRORE"
    period: str                               # "Q2_FY27" or "FY26"
    period_type: Literal["quarterly", "annual", "ytd"] = "quarterly"
    basis: Basis = "consolidated"
    source_type: Literal["xbrl", "screener", "pdf_llm", "derived"]
    document: Optional[str] = None
    page: Optional[int] = None
    evidence: Evidence = "reported"
    confidence: Confidence = "high"


class Check(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class Bar(BaseModel):
    d: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class Alert(BaseModel):
    symbol: str
    d: date
    rule: Literal["volume_spike", "price_move", "material_filing", "combo"]
    headline: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    filing_ids: list[str] = Field(default_factory=list)
    folded: int = 0                           # repeat triggers folded in by the cooldown


class GuidanceItem(BaseModel):
    """A target management stated on a call or in an annual report."""
    company: str
    metric: str
    kind: Literal["absolute", "growth", "margin"]
    low: float
    high: float
    unit: Literal["INR_CRORE", "PCT"]
    period: str                               # the period the target is FOR, e.g. "FY27"
    stated_in: str                            # period of the document it was said in, e.g. "Q1_FY27"
    speaker: str = ""
    quote: str
    document: str
    page: int
    supersedes_explicitly: bool = False       # management said it is changing an earlier target
    withdrawn: bool = False
    caveat: str = ""                          # why filed numbers cannot judge this target (e.g. constant currency)
