# 双板通讯原生积木扩展 —— 还原脚本（自动生成，勿手改）
param([string]$Target = 'D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets')
$ErrorActionPreference = 'Stop'
$PATCH_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$ORIG_SHA = 'df6db241752d42bff2995fcd24521e070adf9eb5d96e870148f9dc51690edc40'
$OLD_SHA = 'b294b5cce4d8f8dde38bd6f6d317e57de9e934b62f9a080d6f7e152ea63b0b3a'
$NEW_SHA = 'a2515601e51174f4649722883849a94e4a47629eaef5a8af34802f22d5cb3b3b'
$BACKUP_DIR = Join-Path (Split-Path -Parent $PATCH_DIR) '工具\原生积木\备份'
$ORIG_FILE = Join-Path $BACKUP_DIR 'browser_assets.原始.df6db241752d.bin'

function Stop-WithMessage([string]$msg) {
  Write-Host ''
  Write-Host $msg -ForegroundColor Yellow
  Write-Host ''
  Read-Host '按回车键关闭窗口' | Out-Null
  exit 1
}

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host '需要管理员权限，正在请求提升…'
  $argline = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Target "{1}"' -f $MyInvocation.MyCommand.Path, $Target
  Start-Process powershell.exe -Verb RunAs -ArgumentList $argline | Out-Null
  exit 0
}

$ide = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'AbilixScratch*' })
if ($ide.Count -gt 0) { Stop-WithMessage '请先完全关闭 AbilixScratch3.0 再还原。' }
if (-not (Test-Path $Target)) { Stop-WithMessage "找不到资源包：$Target" }

function Get-SHA256([string]$p) {
  $fs = [System.IO.File]::OpenRead($p)
  try {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = $sha.ComputeHash($fs)
    return ([System.BitConverter]::ToString($bytes) -replace '-', '').ToLower()
  } finally { $fs.Close() }
}

$src = $null
if (Test-Path $BACKUP_DIR) {
  $cand = @(Get-ChildItem -Path $BACKUP_DIR -Filter 'browser_assets.双板通讯前-*.bin' -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending)
  if ($cand.Count -gt 0) { $src = $cand[0].FullName }
}
if (-not $src) {
  if (Test-Path $ORIG_FILE) { $src = $ORIG_FILE }
}
if (-not $src) { Stop-WithMessage '找不到可还原的备份（browser_assets.双板通讯前-*.bin 或原版备份）。' }

$srcSha = Get-SHA256 $src
Write-Host "还原来源：$src"
Write-Host "来源 sha256：$srcSha"
if ($srcSha -ne $ORIG_SHA -and $srcSha -ne $OLD_SHA) { Stop-WithMessage '来源文件不是预期版本，已停止。' }

$cur = Get-SHA256 $Target
if ($cur -ne $NEW_SHA) { Write-Host '当前不是双板通讯版本，仍将按备份覆盖。' }

Copy-Item $src $Target -Force
$after = Get-SHA256 $Target
if ($after -ne $srcSha) { Stop-WithMessage ('还原后 sha256 不符：$after') }
Write-Host ''
Write-Host '还原成功。' -ForegroundColor Green
Write-Host '  已回到安装前的资源包。'
Write-Host ''
Read-Host '按回车键关闭窗口' | Out-Null
