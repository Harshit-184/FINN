@echo off
rem Fetches prices and announcements from this laptop and writes data\snapshot\.
rem Needs Python 3.10+ (python --version).
cd /d "%~dp0"
python -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ needed, found ' + sys.version.split()[0]" || goto :end
python -m pip install -q -r requirements.txt || goto :end
python -m services.pipeline --days 7 > data\ingest_log.txt 2>&1
type data\ingest_log.txt
:end
pause
