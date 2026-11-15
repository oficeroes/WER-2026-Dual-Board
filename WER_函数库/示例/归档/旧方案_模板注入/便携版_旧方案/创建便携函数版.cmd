@echo off
chcp 65001 >nul 2>nul
setlocal EnableExtensions
title WER Function Library - Create Portable Copy
cd /d "%~dp0"

rem ==========================================================================
rem  Create a portable copy of AbilixScratch3.0 whose "New Project"
rem  template already contains the functions of my library (.srh/.srhs).
rem
rem  Usage : double-click this file.
rem  Extra : you may pass normal options, e.g.
rem            this.cmd --target "D:\AbilixScratch3.0_FuncLib"
rem
rem  This batch file is intentionally pure ASCII; the Chinese-named python
rem  script is resolved through unicode escapes (chcp 65001 for the console).
rem ==========================================================================

set "PY="
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" set "PY=%%D\python.exe"
  )
)
if not defined PY (
  echo [ERROR] Python 3 was not found.
  echo         Install Python 3.8+ from https://www.python.org/ and enable
  echo         "Add Python to PATH", then run this file again.
  pause
  exit /b 2
)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.8 or newer is required.
  pause
  exit /b 2
)

%PY% -c "import runpy,os,sys; p=os.path.join(os.getcwd(),'\u521b\u5efa\u4fbf\u643a\u51fd\u6570\u7248.py'); sys.argv[0]=os.path.basename(p); runpy.run_path(p,run_name='__main__')" %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo ------------------------------------------------------------
  echo   DONE. Use the desktop shortcut "AbilixScratch3.0 FuncLib".
  echo   File - New Project will preload your functions.
  echo ------------------------------------------------------------
) else (
  echo ------------------------------------------------------------
  echo   FAILED with code %RC%. Read the messages above.
  echo ------------------------------------------------------------
)
pause
exit /b %RC%
