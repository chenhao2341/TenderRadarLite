@echo off
setlocal
cd /d "%~dp0"
echo TenderRadarLite Web Console
echo http://127.0.0.1:8765
python scripts\start_web_console.py
endlocal
