# 步骤1：启动便携版 IDE（真实窗口），等待加载，截图并输出窗口信息
$ErrorActionPreference = 'Stop'
$ev = 'D:\UserData\Documents\WER\2026普级赛\WER_函数库\证据\原生积木_便携版'
$shotDir = Join-Path $ev '截图'
New-Item -ItemType Directory -Force -Path $shotDir | Out-Null
$ui = Join-Path $ev 'ui_自动化.ps1'
$appDir = 'C:\Users\s1325\AbilixScratch3.0_FuncLib'

# 记录启动前已有的 AbilixScratch3.0 进程
$before = @(Get-Process -Name 'AbilixScratch3.0' -ErrorAction SilentlyContinue)
Write-Output ("BEFORE_PROCS=" + $before.Count)

$out = Join-Path $shotDir '01_IDE启动.png'
& $ui -Action launch -AppDir $appDir -WaitSeconds 90 -Out $out
Write-Output ("SHOT_EXISTS=" + (Test-Path $out))
