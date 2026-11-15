@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul
if errorlevel 1 set "PY=py -3"
%PY% "%~dp0原生积木核心.py" status
echo.
echo Tip: run this again after you edit and save your function library.
pause
