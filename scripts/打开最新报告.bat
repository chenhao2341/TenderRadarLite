@echo off
chcp 65001 >nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "REPORT_PATH=%PROJECT_ROOT%\reports\latest.html"

cd /d "%PROJECT_ROOT%" || goto :cd_failed

if not exist "%REPORT_PATH%" (
    echo [INFO] Local report file was not found:
    echo        "%REPORT_PATH%"
    echo [HINT] Please run "??????????????bat" first.
    call :pause_if_needed
    endlocal & exit /b 1
)

echo [TenderRadarLite] Opening latest local report...
start "" "%REPORT_PATH%"
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo [ERROR] Failed to open report. Exit code: %RC%
    call :pause_if_needed
    endlocal & exit /b %RC%
)

echo [DONE] Open request sent for:
echo        "%REPORT_PATH%"
endlocal & exit /b 0

:cd_failed
echo [ERROR] Cannot switch to project root:
echo        "%PROJECT_ROOT%"
call :pause_if_needed
endlocal & exit /b 1

:pause_if_needed
if "%TENDERRADAR_NO_PAUSE%"=="1" goto :eof
pause
goto :eof
