@echo off
chcp 65001 >nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "HAS_ERROR=0"

cd /d "%PROJECT_ROOT%" || goto :cd_failed

echo [TenderRadarLite] Environment check
echo [TenderRadarLite] Project root: "%CD%"
echo.

if exist "run_mvp.py" (
    echo [OK] run_mvp.py found
) else (
    echo [ERROR] run_mvp.py not found. Please start this script from the project folder.
    set "HAS_ERROR=1"
)

if exist "requirements.txt" (
    echo [OK] requirements.txt found
) else (
    echo [ERROR] requirements.txt not found
    set "HAS_ERROR=1"
)

if exist "data" (
    echo [OK] data directory found
) else (
    echo [WARN] data directory not found
    set "HAS_ERROR=1"
)

if exist "logs" (
    echo [OK] logs directory found
) else (
    echo [WARN] logs directory not found
    set "HAS_ERROR=1"
)

if exist "reports" (
    echo [OK] reports directory found
) else (
    echo [WARN] reports directory not found
    set "HAS_ERROR=1"
)

echo.
python --version
if errorlevel 1 (
    echo [ERROR] Python is not available.
    echo [HINT] Please install Python 3.11+ and ensure the python command works.
    set "HAS_ERROR=1"
    goto :summary
)

echo.
python -c "import sys; print('[INFO] Python executable:', sys.executable)"
if errorlevel 1 (
    echo [ERROR] Failed to read Python executable information.
    set "HAS_ERROR=1"
)

python -c "import requests; import dotenv; print('[OK] Dependency import check passed')"
if errorlevel 1 (
    echo [ERROR] Required dependencies are missing.
    echo [HINT] Run: python -m pip install -r requirements.txt
    set "HAS_ERROR=1"
)

:summary
echo.
if "%HAS_ERROR%"=="0" (
    echo [DONE] Environment check passed. You can now run the local HTML report script.
    call :pause_if_needed
    endlocal & exit /b 0
)

echo [DONE] Environment check found issues. Please fix them and try again.
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
