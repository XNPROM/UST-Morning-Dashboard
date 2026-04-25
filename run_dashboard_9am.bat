@echo off
cd /d D:\9amust

if not exist logs mkdir logs

echo === Run started %date% %time% === >> logs\dashboard.log

call D:\9amust\venv\Scripts\activate.bat 2>nul
if %ERRORLEVEL% neq 0 (
    echo WARNING: venv not found, using system Python >> logs\dashboard.log
)

python run_dashboard.py >> logs\dashboard.log 2>&1
if %ERRORLEVEL% neq 0 (
    echo FAILED at %date% %time% exit=%ERRORLEVEL% >> logs\dashboard.log
    exit /b 1
)

echo === Run finished %date% %time% === >> logs\dashboard.log
