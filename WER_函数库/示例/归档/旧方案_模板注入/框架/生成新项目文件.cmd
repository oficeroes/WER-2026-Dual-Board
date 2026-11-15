@echo off
chcp 65001 >nul 2>nul
setlocal EnableExtensions
title WER Function Library - Generate new project file
cd /d "%~dp0"

rem ==========================================================================
rem  WER Function Library Framework  -  build a ready-to-open .srhs project
rem  that already contains the function library (works WITHOUT patching the
rem  installed software).
rem
rem  Usage : Double-click this file. Optional arguments:
rem            this.cmd --library "C:\path\my.srh" --out "C:\path\new.srhs"
rem            this.cmd --program ProgramA --force
rem
rem  Output default: next to the library file, named "<library>_new_project.srhs"
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

%PY% -c "import runpy,os,sys; p=os.path.join(os.getcwd(),'\u6846\u67b6\u6838\u5fc3.py'); sys.argv[0]=os.path.basename(p); runpy.run_path(p,run_name='__main__')" gen %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo ------------------------------------------------------------
  echo   DONE. Open AbilixScratch3.0 - File - Open - select the .srhs.
  echo ------------------------------------------------------------
) else (
  echo ------------------------------------------------------------
  echo   FAILED with code %RC%. Read the messages above.
  echo ------------------------------------------------------------
)
pause
exit /b %RC%
