@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run SETUP.cmd once before starting the app.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m ic705
if errorlevel 1 (
  echo.
  echo The application could not start. Read the error above or run SETUP.cmd again.
  pause
  exit /b 1
)
