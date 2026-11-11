@echo off
rem Twinwise - start the local review screen (Windows)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setting up Twinwise for the first time...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/ and try again.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -e .
)
".venv\Scripts\python.exe" -m twinwise ui
pause
