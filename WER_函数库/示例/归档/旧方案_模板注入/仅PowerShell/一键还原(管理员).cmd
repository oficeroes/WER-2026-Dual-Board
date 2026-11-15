@echo off
REM ===========================================================================
REM  One-click RESTORE tool (Administrator)  -  AbilixScratch3.0 default template
REM  This .cmd stays pure ASCII on purpose (avoids codepage garbling); the actual
REM  PowerShell script prints Chinese progress/result messages.
REM ===========================================================================
chcp 65001 >nul
setlocal
title WER Function Library - Restore new-project template

echo ===========================================================================
echo   WER Function Library  ^>  RESTORE AbilixScratch3.0 default template
echo ---------------------------------------------------------------------------
echo   This will:
echo     1. ask for Administrator permission (UAC popup),
echo     2. find the newest browser_assets.backup-* file,
echo     3. save the current file as a pre-restore backup first,
echo     4. restore the backup and verify sha256.
echo   Close the IDE before running.  After success, restart the IDE.
echo ===========================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$d='%~dp0'; $files=@(Get-ChildItem -LiteralPath $d -Filter '*.ps1' -ErrorAction SilentlyContinue | Where-Object { Select-String -LiteralPath $_.FullName -Pattern '^# TOOL-ID: RESTORE$' -Quiet }); if($files.Count -ne 1){ Write-Host ''; Write-Host '[ERROR] Cannot find the restore .ps1 (marker # TOOL-ID: RESTORE) in:' $d -ForegroundColor Red; Write-Host '        Keep the .cmd and .ps1 files in the same folder.' -ForegroundColor Red; exit 2 }; $ps1=$files[0].FullName; Write-Host ('Script: ' + $ps1); try { Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File',$ps1,'-Yes') -ErrorAction Stop } catch { Write-Host ''; Write-Host '[ERROR] Failed to start elevated PowerShell (UAC was cancelled?).' -ForegroundColor Red; Write-Host '        Right-click this .cmd and choose: Run as administrator.' -ForegroundColor Red }"

echo.
echo Done (see the elevated window for detailed result).
pause
endlocal
