@echo off
chcp 65001 >nul 2>nul
setlocal
title WER FuncLib - restore browser_assets from backup
cd /d "%~dp0"

rem ==========================================================================
rem  Restore browser_assets from browser_assets.备份-<timestamp>
rem  Double-click this file. It will ask for Administrator privileges (UAC).
rem  Close AbilixScratch3.0 BEFORE running this.
rem ==========================================================================

set "PY=C:\Users\s1325\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"

rem ---- require administrator (UAC self-elevation) ----
net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator privileges, please click "Yes" on the UAC dialog...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo ============================================================
echo   Restore browser_assets from backup
echo   (undo the new-project default template patch)
echo ============================================================
echo.

"%PY%" "%~dp0还原默认模板.py" --list
echo.
echo Applying restore (a pre-restore backup will be created)...
"%PY%" "%~dp0还原默认模板.py" --apply %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo ------------------------------------------------------------
  echo   Restore finished. Restart AbilixScratch3.0.
  echo ------------------------------------------------------------
) else (
  echo ------------------------------------------------------------
  echo   Restore FAILED with code %RC%. Please read messages above.
  echo ------------------------------------------------------------
)
pause
exit /b %RC%
