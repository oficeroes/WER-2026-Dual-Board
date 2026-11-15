@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set "PY=python"
where python >nul 2>nul
if errorlevel 1 set "PY=py -3"
%PY% "tools\install_all.py"
set "RC=%errorlevel%"
echo.
pause
exit /b %RC%
