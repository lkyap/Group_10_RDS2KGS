@echo off
setlocal
cd /d "%~dp0"
start "" pythonw run_end_to_end.py
endlocal
