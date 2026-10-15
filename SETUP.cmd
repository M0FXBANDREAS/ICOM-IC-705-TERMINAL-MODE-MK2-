@echo off
setlocal
cd /d "%~dp0"
echo IC-705 Reflector Link - first-time setup
if exist ".venv\Scripts\python.exe" goto install
set "IC705_PYTHON="
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined IC705_PYTHON (
    py -%%V -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
    if not errorlevel 1 set "IC705_PYTHON=py -%%V"
  )
)
if defined IC705_PYTHON goto create
python -c "import sys,struct; assert (3,10) <= sys.version_info[:2] <= (3,13); assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 set "IC705_PYTHON=python"
if defined IC705_PYTHON goto create
echo.
echo Please install Python 3.13.16 for Windows 64-bit first.
echo https://www.python.org/ftp/python/3.13.16/python-3.13.16-amd64.exe
echo Or double-click DOWNLOAD-PYTHON.url in this folder.
echo Tick Add python.exe to PATH and include the Python launcher in the installer.
echo Include the Python launcher during installation, then run SETUP.cmd again.
echo The program supports Python 3.10 through 3.13, not Python 3.14 or 32-bit Python.
pause
exit /b 1
:create
echo Creating a private Python environment in this folder...
%IC705_PYTHON% -m venv .venv
if errorlevel 1 goto failed
:install
echo Installing the pinned Qt interface libraries from PyPI. Internet is required.
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "from PySide6 import QtCore, QtWidgets, QtNetwork, QtSerialPort; import ic705.gateway"
if errorlevel 1 goto failed
echo.
echo Setup complete. Double-click START.cmd to open the app.
pause
exit /b 0
:failed
echo.
echo Setup failed. Keep this window open to read the error above.
echo Check Internet access and that this folder is fully extracted and writable.
pause
exit /b 1
