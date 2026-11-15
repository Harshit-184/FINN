@echo off
rem Research (Pull): screener tables, last 4 concall transcripts, guidance extraction. Cached steps are skipped.
cd /d "%~dp0"
python -m pip install -q -r requirements.txt || goto :end
python -u -m services.research INFY DIXON TATAPOWER PERSISTENT TRENT IRCTC HAL
:end
pause
