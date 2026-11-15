@echo off
chcp 65001 >nul 2>nul
setlocal EnableExtensions
title WER Function Library - Sync Status Check
cd /d "%~dp0"

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

echo Running sync status check (read-only)...
echo.
%PY% -c "import runpy,os,sys; p=os.path.join(os.getcwd(),'\u540c\u6b65\u72b6\u6001\u68c0\u67e5.py'); sys.argv[0]=os.path.basename(p); runpy.run_path(p,run_name='__main__')" %*
set "RC=%ERRORLEVEL%"
echo.
echo (Exit code: %RC%)
pause
exit /b %RC%
