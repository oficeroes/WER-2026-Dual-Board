@echo off
chcp 65001 >nul 2>nul
setlocal EnableExtensions
title WER Function Library - Update Native Portable Copy
cd /d "%~dp0"

rem ==========================================================================
rem  Rebuild the native function blocks inside the portable copy from the
rem  current "my functions" library (my_lib .srh/.srhs). The original
rem  browser_assets kept in the copy is reused; the copy is replaced atomically.
rem  
rem  Usage : double-click this file (close the portable IDE first).
rem  Extra : normal options are forwarded, e.g. --dry-run / --verify-only.
rem
rem  Usage : double-click this file (close the portable IDE first).
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

%PY% -c "import runpy,os,sys; p=os.path.join(os.getcwd(),'\u66f4\u65b0\u4fbf\u643a\u51fd\u6570\u7248.py'); sys.argv[0]=os.path.basename(p); runpy.run_path(p,run_name='__main__')" %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo ------------------------------------------------------------
  echo   DONE. Restart the portable IDE to see the new "My Functions" blocks.
  echo ------------------------------------------------------------
) else (
  echo ------------------------------------------------------------
  echo   FAILED with code %RC%. Read the messages above.
  echo ------------------------------------------------------------
)
pause
exit /b %RC%
