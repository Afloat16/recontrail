@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :fail
)
.venv\Scripts\python.exe -m pip install .
if errorlevel 1 goto :fail
.venv\Scripts\python.exe -m recontrail serve %*
if errorlevel 1 goto :fail
exit /b 0
:fail
echo ReconTrail stopped. Check the error above and your Python installation.
pause
exit /b 1
