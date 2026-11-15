@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo   Typing Demo  -  PC to Robot Screen
echo   Make sure PCTEXT is running on robot
echo ==========================================
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 pc_typing_server.py --robot 192.168.1.103 --open
) else (
  python pc_typing_server.py --robot 192.168.1.103 --open
)
echo.
echo Server stopped. Press any key to close...
pause >nul
