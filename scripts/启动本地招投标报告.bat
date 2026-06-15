@echo off
chcp 65001 >nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "REPORT_PATH=%PROJECT_ROOT%\reports\latest.html"

cd /d "%PROJECT_ROOT%" || goto :cd_failed

echo [TenderRadarLite] Starting local HTML report...
echo [TenderRadarLite] Current directory: "%CD%"
echo.

python run_mvp.py --local-html
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo [ERROR] Local HTML report failed. Exit code: %RC%
    echo [HINT] Please run the environment check script first.
    call :pause_if_needed
    endlocal & exit /b %RC%
)

if exist "%REPORT_PATH%" (
    echo.
    echo [DONE] Report generated:
    echo        "%REPORT_PATH%"
    echo [INFO] Browser open is handled by Python.
    endlocal & exit /b 0
)

echo.
echo [ERROR] Command finished but report file was not found:
echo        "%REPORT_PATH%"
echo [HINT] Please check the logs directory.
call :pause_if_needed
endlocal & exit /b 1

:cd_failed
echo [ERROR] Cannot switch to project root:
echo        "%PROJECT_ROOT%"
call :pause_if_needed
endlocal & exit /b 1

:pause_if_needed
if "%TENDERRADAR_NO_PAUSE%"=="1" goto :eof
pause
goto :eof
