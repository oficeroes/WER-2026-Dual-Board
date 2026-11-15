@echo off
rem ==========================================================================
rem  WER native function blocks - OFFLINE RESTORE launcher
rem  ----------------------------------------------------------------------
rem  NOTE: this .cmd file is intentionally PURE ASCII + CRLF (for old cmd.exe
rem  and any code page). "chcp 65001" is set for the console only.
rem  The Chinese script name (HUAN-YUAN = restore, .ps1) cannot be spelled
rem  in an ASCII batch file, so its name is built from Unicode code points:
rem     U+8FD8 U+539F = HUAN YUAN -> the restore script name
rem  Do not rewrite this file in a non-ASCII encoding.
rem
rem  rem # TOOL-ID: native-offline-restore
rem ==========================================================================

chcp 65001 >nul
setlocal
set "WER_LAUNCHER=%~f0"

rem ---- request administrator rights (UAC) if not already elevated ----------
whoami /groups 2>nul | findstr /c:"S-1-16-12288" >nul
if not errorlevel 1 goto :run
echo.
echo [WER] Administrator rights are required to restore the AbilixScratch3.0
echo [WER] resource package (usually under Program Files).
echo [WER] Requesting administrator rights (UAC) ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath $env:WER_LAUNCHER -Verb RunAs -Wait"
echo.
echo [WER] If you clicked "No" on the UAC prompt, nothing was changed.
echo [WER] Run this file again and click "Yes" to restore.
exit /b

:run
echo [WER] Starting offline restore script (PowerShell 5.1, no Python needed) ...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; try { $d = Split-Path -Parent $env:WER_LAUNCHER; $f = Join-Path $d (([string][char]0x8FD8) + [char]0x539F + '.ps1'); if (-not (Test-Path -LiteralPath $f)) { Write-Host ('[ERROR] Script not found: ' + $f); exit 3 }; & $f -Yes; if ($null -eq $LASTEXITCODE) { exit 0 } else { exit $LASTEXITCODE } } catch { Write-Host ('[ERROR] ' + $_.Exception.Message); exit 1 }"
set "RC=%errorlevel%"
echo.
if "%RC%"=="0" (
  echo [DONE] Offline restore finished. Read the messages above.
) else (
  echo [NOT DONE] Restore failed or was refused. Read the messages above.
)
echo.
pause
exit /b %RC%
