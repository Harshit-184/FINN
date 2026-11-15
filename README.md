# FINN

A mobile-first agent for an investor who holds 15-20 Indian stocks. It reads every exchange filing and price move
for the portfolio and shows only what deserves attention (Push), and it researches any NSE company from its own
transcripts and filed numbers to answer one question first: did management deliver what it promised (Pull).

Built for the ENAM AI Engineer build challenge.

**Live app:** https://finn-theta-nine.vercel.app (open on a phone)

## What it does

**Push: the Brief.** Every filing goes through dedupe, classification, scoring and placement.

- The same filing on NSE and BSE becomes one item. A revised filing replaces the original and is marked Revised.
- Filings are classified into the 17 reference categories by rules. Only what the rules cannot place would go to a model.
- Priority = 0.30 Materiality + 0.20 Severity + 0.20 Thesis relevance + 0.15 Portfolio exposure + 0.15 Confidence.
  Critical items get a full card, Notable items one line, Routine items collapse into a count.
- A CXO exit, a rating downgrade, a pledge creation or a regulatory order is Critical whatever the holding's weight.
- Alerts fire on volume above 2x the 20-day average, a close-to-close move beyond 4%, and material filings. One alert
  per rule, per stock, per day.
- Each Critical card carries the price before the filing and 1 and 5 sessions after, labelled as timing, not cause.

**Pull: Promised vs Delivered.** For any NSE symbol:

1. Resolve the company on screener.in and read its quarterly and annual tables (a compiled copy of filed statements).
2. Download the last four earnings-call transcripts and read them page by page.
3. A model extracts quantified management targets into a fixed schema. A target is kept only if its quote is found
   in the transcript text; the page cited is the page where the quote actually appears.
4. Code, not a model, matches each target to actuals and assigns one of seven statuses: Delivered, Partially
   delivered, Missed, Pending, Revised, Withdrawn, Not verifiable. A full-year target is never judged on part of a
   year. A target that is not repeated gets a note, not a verdict.

Every statement is labelled Reported, Guidance or Interpretation, and the three look different on screen.

## Live, stored, and not built

| Capability | Status |
|---|---|
| Prices (Yahoo Finance, end of day) | Fetched by a script run from a laptop; stored snapshot served by the app |
| NSE announcements | Same. Live from a laptop; NSE blocks most cloud IPs |
| BSE announcements | Fetcher written; BSE's API returned HTTP 403 on every attempt, so the data is NSE-only |
| Brief, Portfolio, Alerts, Company screens | Working, from the stored snapshot |
| Research for any NSE symbol | Works from the command line for any symbol; the app shows the symbols already run |
| Results card (Revenue, EBITDA, PBT, PAT, QoQ, YoY) | Working from screener's quarterly table at Medium confidence. The XBRL parser in the plan is not built |
| API on a server, Postgres | The FastAPI app runs locally and is tested; it is not deployed. The web app ships with the same payloads as static files |
| Scheduled refresh, Ask bar, swipe to pin/mute, rules editor, executive bios, narrative vs numbers, bull vs bear | Not built |

Nothing shown in the app is simulated. The portfolio weights are illustrative, and the app says so.

## Architecture

```
laptop / scheduled job                      repo                         phone
  prices.py   (Yahoo)      ┐
  nse.py      (NSE)        ├─ pipeline.py ─► data/snapshot/*.json ─┐
  bse.py      (BSE)        ┘   dedupe → classify → score → alerts  ├─ export.py ─► apps/web/public/snapshot ─► Next.js PWA
  screener.py + transcripts ─ research.py ─► data/research/*.json ─┘                 (also served by services/api)
        guidance extraction (model) → grounding check → match.py (code)
```

- `config/` holds everything tunable: the portfolio with thesis pillars, classification rules, scoring weights,
  alert thresholds and the metric dictionary. Changing a rule does not need a code change.
- `services/engine/` is pure Python with no network access, so every test runs offline.
- `services/ingest/` has one fetcher per source, sharing one cached, rate-limited GET with three retries.
- `services/llm/router.py` picks a model from what the API key can call and caches output by document hash and prompt version.

## Run it

```bash
pip install -r requirements.txt
pytest                                         # engine, API and benchmark tests, no network needed
python -m services.pipeline --days 7           # fetch prices and announcements (run from a normal network)
python -m services.pipeline --reprocess        # re-run rules and scoring over stored raw filings, no network
python -m services.research INFY HAL           # research any NSE symbols (needs GEMINI_API_KEY in .env)
python -m services.export                      # write the payloads the web app ships with
uvicorn services.api.main:app --reload         # API on :8000
cd apps/web && npm install && npm run dev      # app on :3000
```

## Tests

RESULTS_TABLE
