@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (py -3 run_spacemedic.pyw & exit /b)
where python >nul 2>nul && (python run_spacemedic.pyw & exit /b)
echo Python 3 was not found. Install Python from https://python.org then try again.
pause
