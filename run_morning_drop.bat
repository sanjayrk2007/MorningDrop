@echo off
REM ============================================================
REM  The Morning Drop — Scheduled Auto-Runner
REM  Runs the full pipeline and emails the news brief.
REM  Logs output to logs\morning_drop_YYYY-MM-DD.log
REM ============================================================

cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Date stamp for log file (format: YYYY-MM-DD)
REM Date stamp for log file (format: YYYY-MM-DD) - robust PowerShell method
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd'"`) do set LOGDATE=%%i
set LOGFILE=logs\morning_drop_%LOGDATE%.log

echo [%DATE% %TIME%] Starting Morning Drop Auto Pipeline >> "%LOGFILE%"

REM Run the auto pipeline using the virtual environment's python directly (more reliable)
REM Use -u for unbuffered output so logs write in real-time
"%~dp0morning-bot\Scripts\python.exe" -u "%~dp0main.py" --auto >> "%LOGFILE%" 2>&1

if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] Pipeline completed successfully. >> "%LOGFILE%"
) else (
    echo [%DATE% %TIME%] Pipeline FAILED with exit code %ERRORLEVEL%. >> "%LOGFILE%"
)
