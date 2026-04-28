@echo off
REM UST Morning Dashboard - Daily 9am runner
REM For use with Windows Task Scheduler
REM
REM Register:  schtasks /Create /TN "UST Morning Dashboard" /TR "D:\9amust\run_dashboard_9am.bat" /SC DAILY /ST 09:00 /F
REM Query:     schtasks /Query /TN "UST Morning Dashboard"
REM Delete:    schtasks /Delete /TN "UST Morning Dashboard" /F
cd /d D:\9amust
python run_dashboard.py --no-push >> logs\dashboard.log 2>&1
