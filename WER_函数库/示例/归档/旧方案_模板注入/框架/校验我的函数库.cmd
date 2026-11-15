@echo off
chcp 65001 >nul 2>nul
setlocal EnableExtensions
title WER Function Library - Validate my library
cd /d "%~dp0"

rem ==========================================================================
rem  WER Function Library Framework  -  validate the library source file
rem  (.srh / .srhs). Read-only: no file is written.
rem
rem  Usage : Double-click this file. Optional arguments:
rem            this.cmd --library "C:\path\my.srh"
rem            this.cmd --json --json-out result.json
rem
rem  Exit code 0 = no ERROR, 1 = ERROR found, 2 = library file missing.
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

%PY% -c "import runpy,os,sys; p=os.path.join(os.getcwd(),'\u6846\u67b6\u6838\u5fc3.py'); sys.argv[0]=os.path.basename(p); runpy.run_path(p,run_name='__main__')" validate %*
set "RC=%ERRORLEVEL%"

echo.
pause
exit /b %RC%
