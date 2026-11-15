# ASCII-only: verify IDE still starts and auto-opens WERFuncLib after config edit; then close.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$exe = 'D:\Program Files\AbilixScratch3.0\AbilixScratch3.0.exe'
$p = Start-Process -FilePath $exe -PassThru
Write-Host "started pid=$($p.Id)"
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 500
  $p.Refresh()
  if ($p.HasExited) { Write-Host 'EXITED_EARLY'; exit 3 }
  if ($p.MainWindowHandle -ne 0) { break }
}
Start-Sleep -Seconds 22
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.X, $b.Y, 0, 0, $bmp.Size)
$out = Join-Path $env:TEMP 'wer_ide_second_launch.png'
$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Host "saved=$out"
$p.CloseMainWindow() | Out-Null
$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500; if ($p.HasExited) { break } }
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
Write-Host 'closed'
