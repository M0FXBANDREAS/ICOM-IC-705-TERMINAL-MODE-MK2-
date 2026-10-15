@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run SETUP.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install pyinstaller==6.12.0
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name IC705-Reflector-Link launch.py
if errorlevel 1 goto failed
copy /y LICENSE "dist\IC705-Reflector-Link\LICENSE" >nul
copy /y THIRD_PARTY.md "dist\IC705-Reflector-Link\THIRD_PARTY.md" >nul
copy /y README.html "dist\IC705-Reflector-Link\README.html" >nul
echo The Windows executable is in dist\IC705-Reflector-Link.
echo Keep that entire folder together. If redistributing it, include this source package.
pause
exit /b 0
:failed
echo Build failed. Read the error above.
pause
exit /b 1
