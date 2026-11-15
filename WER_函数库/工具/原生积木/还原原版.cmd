@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
whoami /groups 2>nul | findstr /c:"S-1-16-12288" >nul
if not errorlevel 1 goto :run
echo Requesting administrator rights (UAC) ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
if errorlevel 1 (
  echo.
  echo [NOT APPLIED] Administrator rights were not granted.
  pause
)
exit /b
:run
set "PY=python"
where python >nul 2>nul
if errorlevel 1 set "PY=py -3"
%PY% "%~dp0原生积木核心.py" restore %*
set "RC=%errorlevel%"
echo.
if "%RC%"=="0" (
  echo [DONE] The original AbilixScratch3.0 resources are restored.
) else (
  echo [NOT APPLIED] Restore failed. Read the messages above.
)
pause
