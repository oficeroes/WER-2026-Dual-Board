@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "CORE=%~dp0原生积木核心.py"
set "ARGSFILE=%TEMP%\wer_native_install_args.txt"
set "OKFILE=%TEMP%\wer_native_install_ok.txt"
set "ASSETS=D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets"
if defined WER_ASSETS set "ASSETS=%WER_ASSETS%"

rem ---- locate Python 3 ----
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
  where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  echo [FAILED] Python 3 was not found on this computer.
  echo Install Python 3, then run this file again.
  echo Alternative: use the offline package: 安装包\安装原生积木^(离线^).cmd
  pause
  exit /b 2
)

rem ==================== elevated phase (2nd half) ====================
whoami /groups 2>nul | findstr /c:"S-1-16-12288" >nul
if errorlevel 1 goto :phase1
if not exist "%ARGSFILE%" goto :admin_hint

echo.
echo Installing with administrator rights ...
set /p PREBUILT=<"%ARGSFILE%"
del "%ARGSFILE%" >nul 2>nul
del "%OKFILE%" >nul 2>nul
if not exist "%PREBUILT%" (
  echo [NOT APPLIED] Prepared patch package not found.
  echo Run this file again normally.
  pause
  exit /b 2
)
%PY% "%CORE%" install --prebuilt "%PREBUILT%" --assets "%ASSETS%"
set "RC=%errorlevel%"
if exist "%PREBUILT%" del "%PREBUILT%" >nul 2>nul
echo.
if "%RC%"=="0" (
  > "%OKFILE%" echo OK
  echo [DONE] Native blocks installed. Open AbilixScratch3.0 and look for the "My Functions" category.
) else (
  echo [NOT APPLIED] Installation failed. Read the messages above.
)
pause
exit /b %RC%

:admin_hint
echo.
echo [NOT APPLIED] This file is already running with administrator rights.
echo Please close it and double-click it normally instead.
echo Step 1 compiles with Chrome (needs normal rights), then the script asks for admin itself.
pause
exit /b 2

rem ==================== normal phase: compile, then install ====================
:phase1
del "%ARGSFILE%" >nul 2>nul
del "%OKFILE%" >nul 2>nul
set "PREBUILT=%TEMP%\wer_native_prebuilt_%RANDOM%%RANDOM%.bin"
set "DRY="
if /i "%~1"=="--dry-run" set "DRY=1"
if /i "%~1"=="--test" set "DRY=1"

echo ============================================================
echo   Step 1 of 2: compile your function library
echo   (no admin needed; the real Blockly engine is used here)
echo ============================================================
%PY% "%CORE%" install --compile-only "%PREBUILT%" --assets "%ASSETS%"
if errorlevel 1 (
  echo.
  echo [NOT APPLIED] Compile failed. The IDE folder was NOT touched.
  echo If this computer has no Chrome/Edge or no Python, use the offline package:
  echo   WER_函数库\安装包\安装原生积木^(离线^).cmd
  pause
  exit /b 1
)

if not defined DRY goto :elevate
echo.
echo [DRY-RUN] Testing the install step on a temporary copy - no UAC, real folder untouched.
%PY% "%CORE%" install --prebuilt "%PREBUILT%" --dry-run --assets "%ASSETS%"
set "RC=%errorlevel%"
if exist "%PREBUILT%" del "%PREBUILT%" >nul 2>nul
echo.
if "%RC%"=="0" (echo [DONE] Dry-run passed. The real install should work.) else (echo [FAILED] Dry-run failed, read the messages above.)
pause
exit /b %RC%

:elevate

> "%ARGSFILE%" echo %PREBUILT%
echo.
echo ============================================================
echo   Step 2 of 2: install (a UAC prompt will appear - click Yes)
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
echo.
if exist "%OKFILE%" (
  del "%OKFILE%" >nul 2>nul
  if exist "%PREBUILT%" del "%PREBUILT%" >nul 2>nul
  echo [DONE] Native blocks are installed. Open AbilixScratch3.0 and look for the "My Functions" category.
  pause
  exit /b 0
)
echo [NOT APPLIED] The patch was not installed.
echo If you cancelled the UAC prompt, run this file again and click Yes.
if exist "%PREBUILT%" del "%PREBUILT%" >nul 2>nul
pause
exit /b 1
