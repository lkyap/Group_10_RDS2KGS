@echo off
setlocal
cd /d "%~dp0"

set "VENV_PYTHONW=.venv\Scripts\pythonw.exe"
if exist "%VENV_PYTHONW%" (
    start "" "%VENV_PYTHONW%" run_end_to_end.py
) else (
    start "" pythonw run_end_to_end.py
)

endlocal
