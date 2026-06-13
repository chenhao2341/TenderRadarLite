@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"
set "LOG_DIR=%PROJECT_ROOT%\logs"
set "LOG_FILE=%LOG_DIR%\scheduled-run.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

cd /d "%PROJECT_ROOT%"

>> "%LOG_FILE%" echo ============================================================
>> "%LOG_FILE%" echo [START] %date% %time%
>> "%LOG_FILE%" echo [CWD] %CD%
python run_mvp.py >> "%LOG_FILE%" 2>&1
set "RC=%ERRORLEVEL%"
>> "%LOG_FILE%" echo [END] %date% %time%
>> "%LOG_FILE%" echo [RETURN_CODE] %RC%
>> "%LOG_FILE%" echo.

endlocal & exit /b %RC%
