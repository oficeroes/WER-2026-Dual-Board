@echo off
rem ==========================================================================
rem  WER native function blocks - OFFLINE INSTALL launcher
rem  ----------------------------------------------------------------------
rem  NOTE: this .cmd file is intentionally PURE ASCII + CRLF (for old cmd.exe
rem  and any code page). "chcp 65001" is set for the console only.
rem  The Chinese script name (AN-ZHUANG = install, .ps1) cannot be spelled
rem  in an ASCII batch file, so its name is built from Unicode code points:
rem     U+5B89 U+88C5 = AN ZHUANG -> the install script name
rem  Do not rewrite this file in a non-ASCII encoding.
rem
rem  rem # TOOL-ID: native-offline-install
rem ==========================================================================

chcp 65001 >nul
setlocal
set "WER_LAUNCHER=%~f0"

rem ---- request administrator rights (UAC) if not already elevated ----------
whoami /groups 2>nul | findstr /c:"S-1-16-12288" >nul
if not errorlevel 1 goto :run
echo.
echo [WER] Administrator rights are required to modify the AbilixScratch3.0
echo [WER] installation folder (usually Program Files).
echo [WER] Requesting administrator rights (UAC) ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath $env:WER_LAUNCHER -Verb RunAs -Wait"
echo.
echo [WER] If you clicked "No" on the UAC prompt, nothing was changed.
echo [WER] Run this file again and click "Yes" to install.
exit /b

:run
echo [WER] Starting offline installer (PowerShell 5.1, no Python needed) ...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; try { $d = Split-Path -Parent $env:WER_LAUNCHER; $f = Join-Path $d (([string][char]0x5B89) + [char]0x88C5 + '.ps1'); if (-not (Test-Path -LiteralPath $f)) { Write-Host ('[ERROR] Script not found: ' + $f); exit 3 }; & $f -Yes; if ($null -eq $LASTEXITCODE) { exit 0 } else { exit $LASTEXITCODE } } catch { Write-Host ('[ERROR] ' + $_.Exception.Message); exit 1 }"
set "RC=%errorlevel%"
echo.
if "%RC%"=="0" (
  echo [DONE] Offline install finished. Read the messages above.
) else (
  echo [NOT DONE] Install failed or was refused. Read the messages above.
)
echo.
pause
exit /b %RC%
