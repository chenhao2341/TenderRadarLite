@echo off
chcp 65001 >nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "LOG_DIR=%PROJECT_ROOT%\logs"

cd /d "%PROJECT_ROOT%" || goto :cd_failed

if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%" >nul 2>nul
)

if not exist "%LOG_DIR%" (
    echo [ERROR] Cannot access logs directory:
    echo        "%LOG_DIR%"
    call :pause_if_needed
    endlocal & exit /b 1
)

echo [TenderRadarLite] Opening logs directory...
start "" "%LOG_DIR%"
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo [ERROR] Failed to open logs directory. Exit code: %RC%
    call :pause_if_needed
    endlocal & exit /b %RC%
)

echo [DONE] Open request sent for:
echo        "%LOG_DIR%"
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
