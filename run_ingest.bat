@echo off
rem Fetches prices and announcements from this laptop and writes data\snapshot\.
rem Needs Python 3.10+. Progress is printed here and saved to data\ingest_log.txt.
cd /d "%~dp0"
python -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ needed, found ' + sys.version.split()[0]" || goto :end
echo Installing packages (first run only takes a minute)...
python -m pip install -q -r requirements.txt || goto :end
python -u -m services.pipeline --days 7
:end
pause
