@echo off
chcp 65001 >nul 2>nul
setlocal
title WER FuncLib - patch new-project default template
cd /d "%~dp0"

rem ==========================================================================
rem  WER FuncLib - patch new-project default template
rem  Double-click this file. It will ask for Administrator privileges (UAC).
rem  Close AbilixScratch3.0 BEFORE running this.
rem
rem  This script calls:  patch_browser_assets.py --install
rem  It changes ONLY Blockly_Code/maingui_init.js inside browser_assets.
rem  Original file is backed up as: browser_assets.备份-<timestamp>
rem  Restore with: 还原默认模板(管理员).cmd
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
echo   WER FuncLib - new project default template patch
echo ------------------------------------------------------------
echo   Target : D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets
echo   Change : Blockly_Code/maingui_init.js  (defaultcode only)
echo   Backup : browser_assets.备份-TIMESTAMP (same directory)
echo ============================================================
echo.

"%PY%" "%~dp0patch_browser_assets.py" --install %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo ------------------------------------------------------------
  echo   DONE. Restart AbilixScratch3.0 and use File-New Project
  echo   to verify that the function library blocks are preloaded.
  echo   To undo: 还原默认模板^(管理员^).cmd
  echo ------------------------------------------------------------
) else (
  echo ------------------------------------------------------------
  echo   FAILED with code %RC%. Nothing was installed if the error
  echo   happened before the install step. Please read messages above.
  echo ------------------------------------------------------------
)
pause
exit /b %RC%
