@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto setup
if not exist "frontend\dist\index.html" goto setup
goto run

:setup
echo Preparing RaceChip AI. The first run downloads Python dependencies.
if exist "frontend\dist\index.html" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\setup.ps1" -SkipFrontendBuild
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\setup.ps1"
)
if errorlevel 1 goto failed

:run
echo Open http://127.0.0.1:8000/ in your browser after the server starts.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\run.ps1" %*
if errorlevel 1 goto failed
exit /b 0

:failed
echo Setup or startup failed. Check the error above and the README.
pause
exit /b 1
