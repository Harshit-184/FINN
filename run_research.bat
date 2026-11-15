@echo off
rem Research (Pull) for the demo tickers: screener tables, last 4 concall transcripts, guidance extraction.
cd /d "%~dp0"
python -m pip install -q -r requirements.txt || goto :end
python -u -m services.research INFY TATAPOWER DIXON PERSISTENT TRENT
:end
pause
