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

`pytest` runs 80 tests offline. All pass.

| What is tested | Tests |
|---|---|
| Volume, price and filing alerts, cooldown, event-to-price | 6 |
| 41 real NSE filings: accuracy at least 90%, no routine item Critical | 3 |
| Brief assembly, API without a model key or snapshot, weekend window | 4 |
| Rule classification into the 17 categories | 23 |
| NSE/BSE merge and amended filings | 5 |
| Promised vs Delivered statuses, YTD progress, segment and constant-currency handling | 12 |
| Screener table parsing, transcript links, quote grounding | 3 |
| Periods, units, QoQ/YoY, EBITDA, bank template, verification checks | 10 |
| Priority formula, overrides and tier caps | 14 |

Benchmark: on the 41 NSE filings pulled for the portfolio (8-15 Nov 2026), the rules classify 40 correctly (97.6%).
The expected labels were assigned from the exchange's subject and summary text, not the attached PDFs.
The one miss is a preferential-issue committee outcome filed under the abbreviation "PI".

Plan acceptance tests: results figures and comparisons (synthetic input), amended filing treated as latest, routine
compliance filing never Critical, and Brief/Portfolio/Alerts working with no model key are covered. "Unseen ticker
end to end" and "question the documents cannot answer" are checked by hand on live runs, not automated.


## Decisions and trade-offs

- **Rules before models.** Classification, scoring, alerts and guidance matching are code. The model is used for one
  job: reading a transcript into a fixed schema. That keeps cost near zero and makes every placement explainable.
- **The model's output is checked, not trusted.** A target whose quote is not in the transcript is dropped. Targets for
  one business segment are never judged against company totals, and constant-currency growth is never judged against
  rupee growth. Both rules exist because the first live run got exactly these wrong (Dixon's telecom revenue target
  was marked Delivered against company revenue; Infosys' 1-2% constant-currency guidance was set beside +12.3% rupee growth).
- **Tier caps on top of the formula.** Exposure and confidence alone contribute up to 30 points, so a dividend from the
  largest holding scored as Notable. Routine-by-nature categories are capped in config.
- **Snapshot first.** The app reads stored payloads, so it loads instantly and does not depend on an exchange site or a
  model being up during a demo. The cost is freshness: data is as of the last ingestion run, and the app shows that time.
- **Screener tables instead of XBRL** for actuals, to fit the time available. They are labelled as a compiled copy and
  capped at Medium confidence.

## Cost

Token use per model call is logged to `data/snapshot/llm_usage.json`. Extraction runs once per transcript and prompt
version and is cached by document hash. All calls so far have been on the Gemini free tier.

## Built with AI

This project was built with Claude (planning and code) in one working day, 15 Nov 2026, with ChatGPT used for a
review of the plan. The conversation exports are in `docs/ai-build-history/`.
