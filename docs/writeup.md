Subject: IIT Delhi – AI Engineer - 2027

Hello,

Please find my submission for the AI Engineer build challenge.

- Live app (open on a phone): https://finn-theta-nine.vercel.app
- Code: https://github.com/Harshit-184/FINN
- AI build history: [LINKS TO BE ADDED]

**What I built**

FINN is a mobile web app for an investor holding 18 NSE stocks. I chose to do two workflows properly rather than
eight thinly.

Push, the Brief. Every exchange filing for the portfolio is deduplicated, classified into the 17 reference categories
by rules, scored, and placed as Critical, Notable or Routine. For the week of 8-15 November the 18 holdings produced
41 NSE filings; the Brief shows 2 as Critical (IRCTC and Tata Power results, each with Revenue, EBITDA, PBT and PAT
against last quarter and last year), 12 as one-line Notable items, and collapses the other 27. Alerts fire on volume
above 2x the 20-day average, moves beyond 4%, and material filings.

Pull, Promised vs Delivered. For any NSE symbol, FINN reads the company's last four earnings-call transcripts,
extracts the targets management stated, and matches them to filed numbers. For Infosys it shows FY27 revenue-growth
guidance being cut from 1.5-3.5% to 1.5-3% and then to 1-2% across three calls, and the 20-22% operating-margin band
tracking at 21.0% after two quarters. Every line links to the transcript page it came from.

**Decisions and trade-offs**

1. Rules first, model last. Classification, scoring, alerts and guidance matching are plain code and config. The model
   does one job: reading transcripts into a fixed schema. The classifier gets 40 of 41 real filings right with no
   model call. (I assigned the expected labels from the exchange text, not the PDFs.)
2. The model's output is checked before it is shown. Running on real transcripts exposed three errors, and each became
   a rule: a quote must be found in the transcript or the target is dropped; a target for one business segment is
   never judged against company totals (Dixon's telecom revenue target had been marked Delivered against company
   revenue); and constant-currency guidance is never judged against rupee growth (Infosys).
3. Signals, not verdicts. FINN tags which of the investor's thesis pillars a filing touches and shows the price around
   it as timing, not cause. It makes no buy or sell call. A target management stops repeating gets a note, not a
   "dropped" label.
4. Cost. Extraction first used one model call per transcript and exhausted the free tier in an afternoon. It now sends
   only the pages that contain guidance language and makes one call per company, about a quarter of the tokens. On the
   earlier results, 30 of 32 targets sit on pages that are still sent. Everything has run on the Gemini free tier.
5. Stored data over live calls. The app reads a stored snapshot, so it opens instantly and does not depend on an
   exchange site or a model being up. The cost is freshness, and the app shows when each source last ran.

**What is not done**

- BSE: the fetcher is written, but BSE's API returned 403 on every attempt, so the data is NSE-only.
- Actuals come from screener.in's tables, labelled as a compiled copy at Medium confidence. I planned to parse the
  exchange XBRL and did not get to it.
- The backend runs and is tested locally but is not deployed; the app serves the same payloads as static files, and
  data refreshes when the ingestion script is run, not on a schedule.
- Not built: the Ask bar, swipe to pin or mute, the alert-rules editor, executive bios for management changes,
  narrative-vs-numbers and bull-vs-bear. Research in the app covers the symbols I ran; any other NSE symbol works
  from the command line.
- Capex targets are extracted but shown as not verifiable, because capex is not in the structured data.

**What I would do next**

Parse results XBRL so headline numbers are exact and cross-checked; add segment actuals so segment targets can be
judged; put ingestion on a schedule with the API deployed; then the Ask bar on top of the same research cards.

I built this in one day (15 November) with Claude for planning and code, and used ChatGPT to review the plan.

Thank you for the opportunity.

[NAME]
[ROLL NUMBER], IIT Delhi
[PHONE]
