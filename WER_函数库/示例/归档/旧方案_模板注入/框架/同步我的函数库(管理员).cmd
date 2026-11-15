@echo off
chcp 65001 >nul 2>nul
setlocal EnableExtensions
title WER Function Library - Sync (Administrator required)
cd /d "%~dp0"

rem ==========================================================================
rem  Sync "my function library" into the software's new-project default
rem  template (browser_assets / Blockly_Code / maingui_init.js).
rem
rem  IMPORTANT: this needs Administrator rights. A UAC prompt will appear:
rem    - Enter an administrator account/password and click Yes  -> sync runs
rem    - Click No / cancel the prompt                            -> nothing happens
rem      (this window will tell you so after the attempt)
rem  Close AbilixScratch3.0 completely BEFORE running this.
rem
rem  This file is pure ASCII (CRLF); Chinese script names use unicode escapes.
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

rem ---- require administrator: self-elevate and WAIT for the elevated window ----
net session >nul 2>&1
if errorlevel 1 (
  echo.
  echo [INFO] Administrator rights are required to modify the software.
  echo        A UAC prompt will appear now.
  echo        - Enter an administrator account/password and click Yes.
  echo        - If you click No or cancel it, the sync will NOT be applied.
  echo.
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Start-Process -FilePath '%~f0' -Verb RunAs -Wait -ErrorAction Stop; exit 0 } catch { exit 1 }"
  if errorlevel 1 (
    echo.
    echo [NOT APPLIED] The UAC prompt was cancelled or failed.
    echo               The software was NOT modified. Nothing was changed.
  ) else (
    echo.
    echo [DONE] The administrator window has finished.
    echo        Check its messages above; if it reported success, the template
    echo        is updated. Close and restart AbilixScratch3.0, then File - New Project.
  )
  echo.
  pause
  exit /b
)

echo ============================================================
echo   WER Function Library - sync to new-project default template
echo ------------------------------------------------------------
echo   Source : the library file (see README; auto-detect)
echo   Target : browser_assets - Blockly_Code/maingui_init.js
echo   Backup : browser_assets.backup-TIMESTAMP (same folder)
echo   Undo   : run the restore .cmd in this folder as Administrator
echo ============================================================
echo.

%PY% -c "import runpy,os,sys; p=os.path.join(os.getcwd(),'\u6846\u67b6\u6838\u5fc3.py'); sys.argv[0]=os.path.basename(p); runpy.run_path(p,run_name='__main__')" sync --install %*
set "RC=%ERRORLEVEL%"

echo %DATE% %TIME% sync exit=%RC% >> "%~dp0sync_log.txt"
echo.
if "%RC%"=="0" (
  echo ------------------------------------------------------------
  echo   DONE. Fully close and restart AbilixScratch3.0,
  echo   then File - New Project: the Function category is preloaded.
  echo   To undo: run the restore .cmd in this folder as Administrator.
  echo ------------------------------------------------------------
) else (
  echo ------------------------------------------------------------
  echo   FAILED with code %RC%. Read the messages above.
  echo ------------------------------------------------------------
)
pause
exit /b %RC%
