@echo off
chcp 65001 >nul 2>nul
setlocal EnableExtensions
title WER Function Library - Restore default template (Administrator)
cd /d "%~dp0"

rem ==========================================================================
rem  WER Function Library Framework  -  restore the IDE new-project default
rem  template from browser_assets.<backup-prefix>TIMESTAMP.
rem
rem  Usage : Double-click this file. It will ask for Administrator (UAC).
rem          Close AbilixScratch3.0 completely BEFORE running this.
rem  Extra : this.cmd --backup "C:\path\browser_assets...backup" --yes
rem  Note  : the latest backup is the state BEFORE the last sync. To go back
rem          to the factory template, use --backup with the oldest backup.
rem
rem  This file is intentionally pure ASCII; the core script name is passed
rem  as \u escapes (chcp 65001 is set for the console).
rem ==========================================================================

rem ---- find Python 3 (prefer the "py" launcher, then python in PATH) ----
set "PY="
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo [ERROR] Python 3 was not found in PATH.
  echo         Install Python 3.8+ from https://www.python.org/ and try again.
  pause
  exit /b 2
)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.8 or newer is required.
  pause
  exit /b 2
)

rem ---- require administrator (UAC self-elevation) ----
net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator privileges, please click "Yes" on the UAC dialog...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo ============================================================
echo   WER Function Library - restore new-project default template
echo ------------------------------------------------------------
echo   A pre-restore copy of the current file is always created.
echo ============================================================
echo.

echo [1/2] Available backups:
%PY% -c "import runpy,os,sys; p=os.path.join(os.getcwd(),'\u6846\u67b6\u6838\u5fc3.py'); sys.argv[0]=os.path.basename(p); runpy.run_path(p,run_name='__main__')" restore --list
echo.
echo [2/2] Restoring (latest backup by default) ...
%PY% -c "import runpy,os,sys; p=os.path.join(os.getcwd(),'\u6846\u67b6\u6838\u5fc3.py'); sys.argv[0]=os.path.basename(p); runpy.run_path(p,run_name='__main__')" restore --yes %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo ------------------------------------------------------------
  echo   DONE. Fully close and restart AbilixScratch3.0.
  echo ------------------------------------------------------------
) else (
  echo ------------------------------------------------------------
  echo   FAILED with code %RC%. Read the messages above.
  echo ------------------------------------------------------------
)
pause
exit /b %RC%
