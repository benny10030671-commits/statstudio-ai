@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call setup.cmd
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m statstudio install-mcp
pause
endlocal
