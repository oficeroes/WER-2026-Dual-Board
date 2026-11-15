@echo off
chcp 65001 >nul 2>nul
setlocal EnableExtensions
title WER Function Library - Inspect current default template
cd /d "%~dp0"

rem ==========================================================================
rem  WER Function Library Framework  -  inspect the IDE new-project default
rem  template (read-only: no file is written).
rem
rem  Usage : Double-click this file. Optional arguments:
rem            this.cmd --library "C:\path\my.srh"
rem            this.cmd --assets  "D:\...\Resources\browser_assets"
rem            this.cmd --json
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

%PY% -c "import runpy,os,sys; p=os.path.join(os.getcwd(),'\u6846\u67b6\u6838\u5fc3.py'); sys.argv[0]=os.path.basename(p); runpy.run_path(p,run_name='__main__')" inspect %*
set "RC=%ERRORLEVEL%"

echo.
pause
exit /b %RC%
