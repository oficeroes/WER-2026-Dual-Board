# 双板通讯原生积木扩展 —— 安装脚本（自动生成，勿手改）
param([string]$Target = 'D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets')
$ErrorActionPreference = 'Stop'
$PATCH_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PREBUILT = Join-Path $PATCH_DIR 'browser_assets.patched'
$ORIG_SHA = 'df6db241752d42bff2995fcd24521e070adf9eb5d96e870148f9dc51690edc40'
$OLD_SHA = 'b294b5cce4d8f8dde38bd6f6d317e57de9e934b62f9a080d6f7e152ea63b0b3a'
$NEW_SHA = 'a2515601e51174f4649722883849a94e4a47629eaef5a8af34802f22d5cb3b3b'
$BACKUP_DIR = Join-Path (Split-Path -Parent $PATCH_DIR) '工具\原生积木\备份'

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

Write-Host '=========================================='
Write-Host '  双板通讯原生积木 · 安装'
Write-Host '=========================================='

$ide = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'AbilixScratch*' })
if ($ide.Count -gt 0) {
  Stop-WithMessage ('请先完全关闭 AbilixScratch3.0 再安装（正在运行：' + (($ide | ForEach-Object { $_.ProcessName }) -join ', ') + '）')
}

if (-not (Test-Path $Target)) { Stop-WithMessage "找不到资源包：$Target" }
if (-not (Test-Path $PREBUILT)) { Stop-WithMessage "找不到补丁包：$PREBUILT" }

function Get-SHA256([string]$p) {
  $fs = [System.IO.File]::OpenRead($p)
  try {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = $sha.ComputeHash($fs)
    return ([System.BitConverter]::ToString($bytes) -replace '-', '').ToLower()
  } finally { $fs.Close() }
}

$cur = Get-SHA256 $Target
$new = Get-SHA256 $PREBUILT
Write-Host "当前资源包 sha256：$cur"
Write-Host "补丁包   sha256：$new"
if ($new -ne $NEW_SHA) { Stop-WithMessage '补丁包被改动过（sha 不符）。' }
if ($cur -eq $NEW_SHA) { Stop-WithMessage '当前已经装好双板通讯版本，无需重复安装。' }
if ($cur -ne $ORIG_SHA -and $cur -ne $OLD_SHA) {
  Stop-WithMessage ("当前资源包既不是原版也不是已知的旧补丁版，为安全起见已停止。" + [Environment]::NewLine +
                    "当前：$cur" + [Environment]::NewLine + "原版：$ORIG_SHA" + [Environment]::NewLine + "旧补丁：$OLD_SHA")
}

New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $BACKUP_DIR ("browser_assets.双板通讯前-{0}.bin" -f $ts)
Copy-Item $Target $backup -Force
Write-Host "已备份当前资源包 -> $backup"

Write-Host '正在写入新资源包…'
try {
  Copy-Item $PREBUILT $Target -Force
  $after = Get-SHA256 $Target
  if ($after -ne $NEW_SHA) { throw "安装后 sha256 不符：$after" }
} catch {
  Write-Host '安装失败，正在回滚…' -ForegroundColor Red
  Copy-Item $backup $Target -Force
  Stop-WithMessage ('安装失败：' + $_.Exception.Message + '（已回滚）')
}

Write-Host ''
Write-Host '安装成功！' -ForegroundColor Green
Write-Host '  打开 AbilixScratch3.0，左侧函数栏最上方会出现「双板通讯」分类（3 个积木）。'
Write-Host '  「我的函数」分类保留不变。'
Write-Host '  还原方法：双击「restore_dual.cmd」。'
Write-Host ''
Read-Host '按回车键关闭窗口' | Out-Null
