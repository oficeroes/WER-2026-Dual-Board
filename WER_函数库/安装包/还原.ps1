# =============================================================================
#  WER 原生函数积木 - 离线还原脚本（Windows PowerShell 5.1，不需要 Python）
#
#  作用：把安装了「原生函数积木」补丁的 browser_assets 还原成 AbilixScratch3.0
#        的原始版本。原版文件来自安装时自动生成的备份：
#            browser_assets.备份-yyyyMMdd-HHmmss（在目标 browser_assets 同目录）
#
#  用法（一般用户）：
#    双击「还原原版(离线).cmd」——会自动请求管理员权限（UAC）。
#
#  用法（高级 / 测试）：
#    powershell -NoProfile -ExecutionPolicy Bypass -File "还原.ps1"
#    powershell -NoProfile -ExecutionPolicy Bypass -File "还原.ps1" -Target "D:\Program Files\AbilixScratch3.0" -Yes
#    powershell -NoProfile -ExecutionPolicy Bypass -File "还原.ps1" -Backup "D:\...\browser_assets.备份-20261111-120000" -Yes
#
#  参数：
#    -Target  安装根目录（含 AbilixScratch3.0.exe 的那一层）、或 *_Data 目录、
#             或 Resources 目录、或 browser_assets 文件本身。省略时自动查找。
#    -Backup  指定要恢复的原版备份文件；省略时自动找最新的原版备份。
#    -Info    编译信息文件（默认：本脚本同目录 编译信息.txt；用于交叉校验原版 sha）
#    -Yes     跳过交互确认
#    -Force   放宽检查（IDE 正在运行、当前 sha 未知时也继续）
#
#  本文件必须保存为「UTF-8 with BOM」，否则 Windows PowerShell 5.1 会按 ANSI
#  读取，导致中文乱码甚至语法错误。
# =============================================================================

[CmdletBinding()]
param(
    [string]$Target = '',
    [string]$Backup = '',
    [string]$Info = '',
    [switch]$Yes,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

try { $OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }

$ToolName = 'WER 原生函数积木 - 离线还原'
$ToolVersion = '1.0.0'

$OriginalSha = 'DF6DB241752D42BFF2995FCD24521E070ADF9EB5D96E870148F9DC51690EDC40'
$OriginalSize = [int64]85271033

$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
}

# ---------------------------------------------------------------------------
# 小工具函数
# ---------------------------------------------------------------------------
function Write-Info([string]$m) { Write-Host "[INFO] $m" }
function Write-Ok([string]$m)   { Write-Host "[OK]   $m" -ForegroundColor Green }
function Write-Warn([string]$m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }

function Stop-WithError([string]$msg) {
    Write-Host ''
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    Write-Host ''
    Write-Host '[ERROR] 还原未完成。目标文件如果已被改动，请重试或手动用备份文件恢复。'
    exit 1
}

function Get-Sha256([string]$path) {
    $h = Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop
    return ([string]$h.Hash).ToUpperInvariant()
}

function Format-Size([long]$n) {
    if ($n -ge 1073741824) { return ('{0:N2} GB' -f ($n / 1073741824.0)) }
    if ($n -ge 1048576)    { return ('{0:N1} MB' -f ($n / 1048576.0)) }
    if ($n -ge 1024)       { return ('{0:N1} KB' -f ($n / 1024.0)) }
    return ("$n B")
}

function Resolve-AgainstScriptDir([string]$p) {
    if ([System.IO.Path]::IsPathRooted($p)) {
        return [System.IO.Path]::GetFullPath($p)
    }
    return [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($ScriptDir, $p))
}

function Get-UniquePath([string]$p) {
    if (-not [System.IO.File]::Exists($p)) { return $p }
    for ($i = 1; $i -lt 1000; $i++) {
        $q = "$p-$i"
        if (-not [System.IO.File]::Exists($q)) { return $q }
    }
    throw "无法生成不重复的文件名：$p"
}

function Test-IsAdmin {
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        $pr = New-Object Security.Principal.WindowsPrincipal($id)
        return $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

function Test-TargetWritable([string]$path) {
    try {
        $fs = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::Read)
        $fs.Close()
        return $true
    } catch {
        return $false
    }
}

function Get-AbilixProcessNames {
    $names = New-Object System.Collections.ArrayList
    try {
        $procs = @(Get-Process -ErrorAction SilentlyContinue)
        foreach ($p in $procs) {
            $n = ''
            try { $n = [string]$p.ProcessName } catch { }
            if ($n -and $n.ToLowerInvariant().Contains('abilixscratch')) {
                if (-not $names.Contains($n)) { [void]$names.Add($n) }
            }
        }
    } catch { }
    return @($names)
}

function Resolve-TargetAssets([string]$p) {
    $full = [System.IO.Path]::GetFullPath($p)
    if ([System.IO.File]::Exists($full)) {
        if ([System.IO.Path]::GetFileName($full).ToLowerInvariant() -eq 'browser_assets') {
            return $full
        }
        throw "指定的 -Target 是一个文件，但文件名不是 browser_assets：$full"
    }
    if (-not [System.IO.Directory]::Exists($full)) {
        throw "指定的 -Target 不存在：$full"
    }
    $cands = @(
        [System.IO.Path]::Combine($full, 'browser_assets'),
        [System.IO.Path]::Combine($full, 'Resources\browser_assets'),
        [System.IO.Path]::Combine($full, 'AbilixScratch3.0_Data\Resources\browser_assets'),
        [System.IO.Path]::Combine($full, 'AbilixScratch3_0_Data\Resources\browser_assets'),
        [System.IO.Path]::Combine($full, 'Data\Resources\browser_assets')
    )
    foreach ($c in $cands) {
        if ([System.IO.File]::Exists($c)) { return $c }
    }
    throw ("在指定目录下找不到 browser_assets：$full`n" + `
        "请把 -Target 指到 AbilixScratch3.0 安装根目录（含 exe 的那一层），或直接指到 browser_assets 文件。")
}

function Find-DefaultTarget {
    $roots = New-Object System.Collections.ArrayList
    [void]$roots.Add('D:\Program Files\AbilixScratch3.0')
    if ($env:ProgramFiles) { [void]$roots.Add([System.IO.Path]::Combine($env:ProgramFiles, 'AbilixScratch3.0')) }
    $pf86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    if ($pf86) { [void]$roots.Add([System.IO.Path]::Combine($pf86, 'AbilixScratch3.0')) }
    foreach ($drive in @('C:\', 'D:\', 'E:\', 'F:\')) {
        [void]$roots.Add([System.IO.Path]::Combine($drive, 'Program Files\AbilixScratch3.0'))
        [void]$roots.Add([System.IO.Path]::Combine($drive, 'Program Files (x86)\AbilixScratch3.0'))
        [void]$roots.Add([System.IO.Path]::Combine($drive, 'AbilixScratch3.0'))
    }
    $seen = New-Object System.Collections.ArrayList
    foreach ($r in $roots) {
        $key = ([string]$r).ToLowerInvariant()
        if ($seen.Contains($key)) { continue }
        [void]$seen.Add($key)
        try {
            $a = Resolve-TargetAssets $r
            if ($a) { return @{ Root = $r; Assets = $a } }
        } catch { }
    }
    return $null
}

function Write-RecordFile([string]$fileName, [string[]]$lines) {
    $p = [System.IO.Path]::Combine($ScriptDir, $fileName)
    $text = ($lines -join "`r`n") + "`r`n"
    [System.IO.File]::WriteAllText($p, $text, (New-Object System.Text.UTF8Encoding($true)))
    return $p
}

# ---------------------------------------------------------------------------
# 开始
# ---------------------------------------------------------------------------
Write-Host ('=' * 78)
Write-Host "  $ToolName    v$ToolVersion"
Write-Host '  把 browser_assets 还原成 AbilixScratch3.0 原始版本（不需要 Python）。'
Write-Host ('=' * 78)
Write-Info "时间       : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Info "脚本目录   : $ScriptDir"

$isAdmin = Test-IsAdmin
if ($isAdmin) {
    Write-Info '当前权限   : 管理员'
} else {
    Write-Info '当前权限   : 普通用户（目标目录可写时也能继续，例如复制出来的测试副本）'
}

# 如果安装包里有编译信息，交叉校验一下原版 sha（防止装错版本的还原脚本）
$expectedOriginalSha = $OriginalSha
$expectedOriginalSize = $OriginalSize
if ($Info -eq '') { $infoPath = [System.IO.Path]::Combine($ScriptDir, '编译信息.txt') }
else { $infoPath = Resolve-AgainstScriptDir $Info }
if ([System.IO.File]::Exists($infoPath)) {
    try {
        $lines = [System.IO.File]::ReadAllLines($infoPath, [System.Text.Encoding]::UTF8)
        foreach ($line in $lines) {
            $t = ([string]$line).Trim()
            $i = $t.IndexOf('=')
            if ($i -le 0) { continue }
            $k = $t.Substring(0, $i).Trim()
            $v = $t.Substring($i + 1).Trim()
            if ($k -eq '原版资源包sha256' -and $v -match '^[0-9A-Fa-f]{64}$') { $expectedOriginalSha = $v.ToUpperInvariant() }
            if ($k -eq '原版资源包大小') { try { $expectedOriginalSize = [int64]$v } catch { } }
        }
    } catch { }
}
if ($expectedOriginalSha -ne $OriginalSha) {
    Write-Warn "编译信息.txt 里的原版 sha256 与本脚本内置的不一致（使用编译信息里的值：$expectedOriginalSha）。"
}

# --- 1. 定位安装目标 --------------------------------------------------------
if ($Target -ne '') {
    try {
        $assetsPath = Resolve-TargetAssets $Target
    } catch {
        Stop-WithError $_.Exception.Message
    }
    Write-Info "还原目标   : $assetsPath（由 -Target 指定）"
} else {
    $found = Find-DefaultTarget
    if (-not $found) {
        Stop-WithError ("没有自动找到 AbilixScratch3.0 的 browser_assets。`n" +
            "  · 如果 IDE 装在别的盘/别的目录，请用 -Target 指定安装根目录，例如：`n" +
            "    powershell -NoProfile -ExecutionPolicy Bypass -File `"$ScriptDir\还原.ps1`" -Target `"E:\Program Files\AbilixScratch3.0`" -Yes")
    }
    $assetsPath = $found.Assets
    Write-Info "还原目标   : $assetsPath（自动定位）"
}

if (-not [System.IO.File]::Exists($assetsPath)) {
    Stop-WithError "目标资源包不存在：$assetsPath（IDE 可能未安装，或安装目录结构不同；请用 -Target 指定）"
}
$assetsDir = Split-Path -Parent $assetsPath

# --- 2. 权限检查 ------------------------------------------------------------
if (-not (Test-TargetWritable $assetsPath)) {
    Stop-WithError ("没有写入权限：$assetsPath`n" +
        "  · 该文件位于 Program Files 等受保护目录，还原需要管理员权限。`n" +
        "  · 正确做法：双击同目录的「还原原版(离线).cmd」，它会自动请求管理员权限（UAC）。`n" +
        "  · 测试/绿色版：目标目录可写时（例如复制到临时目录的副本），用 -Target 指向它即可，无需管理员。")
}
if (-not $isAdmin) {
    Write-Warn '当前不是管理员，但目标目录可写：继续还原（适用于测试副本 / 绿色版目录；真实 Program Files 安装请用管理员权限）。'
}

# --- 3. 检查当前状态 --------------------------------------------------------
Write-Info '计算目标资源包当前 sha256 …'
$curSha = Get-Sha256 $assetsPath
$curSize = ([System.IO.FileInfo]$assetsPath).Length
Write-Info "目标当前   : $(Format-Size $curSize)，sha256 $curSha"

if ($curSha -eq $expectedOriginalSha) {
    Write-Ok '目标资源包已经是原版，无需还原。'
    Write-Host ''
    Write-Host '[DONE] 未做任何修改。'
    exit 0
}

# --- 4. 检测 IDE 是否运行 ---------------------------------------------------
$running = Get-AbilixProcessNames
if ($running.Count -gt 0) {
    if (-not $Force) {
        Stop-WithError ("检测到 AbilixScratch3.0 正在运行（$($running -join '、')）。`n" +
            "请先完全关闭 IDE，再重新运行还原。")
    } else {
        Write-Warn "AbilixScratch3.0 正在运行（$($running -join '、')），因为指定了 -Force，继续。"
    }
} else {
    Write-Ok 'IDE 未在运行'
}

# --- 5. 找原版备份 ----------------------------------------------------------
$backupPath = ''
if ($Backup -ne '') {
    $b = Resolve-AgainstScriptDir $Backup
    if (-not [System.IO.File]::Exists($b)) {
        # 再按当前目录解释一次
        try { $b2 = [System.IO.Path]::GetFullPath($Backup) } catch { $b2 = '' }
        if ($b2 -and [System.IO.File]::Exists($b2)) { $b = $b2 }
    }
    if (-not [System.IO.File]::Exists($b)) {
        Stop-WithError "指定的备份文件不存在：$Backup（解析为 $b）"
    }
    Write-Info "校验指定备份：$b"
    $bSha = Get-Sha256 $b
    if ($bSha -ne $expectedOriginalSha) {
        Stop-WithError ("指定备份的 sha256 不是原版！`n  期望：$expectedOriginalSha`n  实际：$bSha`n" +
            "为避免把错误文件写回安装目录，已停止。请确认 -Backup 指向的是安装时自动生成的 browser_assets.备份-* 文件。")
    }
    $backupPath = $b
} else {
    Write-Info "在原目录查找原版备份（browser_assets.备份-*）…"
    $cands = @()
    try {
        $cands = @(Get-ChildItem -LiteralPath $assetsDir -Filter 'browser_assets.备份-*' -File -ErrorAction SilentlyContinue)
    } catch { }
    $cands = @($cands | Sort-Object -Property @{Expression = { $_.LastWriteTime }; Descending = $true }, @{Expression = { $_.Name }; Descending = $true })
    $foundList = New-Object System.Collections.ArrayList
    foreach ($c in $cands) {
        $cSha = ''
        try { $cSha = Get-Sha256 $c.FullName } catch { continue }
        [void]$foundList.Add("$($c.Name)  ($(Format-Size $c.Length), sha256 $($cSha.Substring(0,16))…)")
        if (-not $backupPath -and $cSha -eq $expectedOriginalSha) {
            $backupPath = $c.FullName
        }
    }
    if (-not $backupPath) {
        $msg = "没有找到可用的原版备份（sha256 应为 $($expectedOriginalSha.Substring(0,16))…）。`n"
        if ($foundList.Count -gt 0) {
            $msg += "在 $assetsDir 找到这些备份文件，但 sha256 都不是原版：`n  " + ($foundList -join "`n  ") + "`n"
        } else {
            $msg += "在 $assetsDir 没有找到 browser_assets.备份-* 文件。`n"
        }
        $msg += "补救方法：`n" +
            "  · 如果这台电脑还有别的备份/原始文件，用 -Backup 指定它；`n" +
            "  · 也可以从别的同版本电脑拷贝原始 browser_assets 到本机（sha256 必须为 $expectedOriginalSha）；`n" +
            "  · 或者重新安装 AbilixScratch3.0（安装程序会恢复原版资源包，作品文件不受影响）。"
        Stop-WithError $msg
    }
    Write-Info "选用备份   : $backupPath"
}
$bkSha = Get-Sha256 $backupPath
$bkSize = ([System.IO.FileInfo]$backupPath).Length
Write-Ok "备份校验通过（sha256 与内置原版一致）"
Write-Info "备份信息   : $(Format-Size $bkSize)，$backupPath"

# --- 6. 确认 ---------------------------------------------------------------
Write-Host ''
Write-Host '即将执行：'
Write-Host "  1) 把当前资源包另存为 browser_assets.还原前备份-<时间戳>（安全网）"
Write-Host "  2) 用原版备份覆盖目标资源包（$(Format-Size $bkSize)）"
Write-Host "  3) 写入后校验 sha256 必须等于 $($expectedOriginalSha.Substring(0,16))…"
Write-Host ''
if (-not $Yes) {
    $ans = Read-Host '确认还原？输入 Y 继续，直接回车取消'
    if ($ans -notmatch '^[Yy]') {
        Write-Host '[OK] 已取消，目标文件没有被修改。'
        exit 0
    }
}

# --- 7. 保存当前文件作为安全网 ---------------------------------------------
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$safetyPath = Get-UniquePath ([System.IO.Path]::Combine($assetsDir, 'browser_assets.还原前备份-' + $stamp))
Write-Info "保存当前资源包 -> $safetyPath"
try {
    [System.IO.File]::Copy($assetsPath, $safetyPath, $false)
} catch {
    Stop-WithError "保存当前资源包失败：$($_.Exception.Message)`n（目标磁盘可能空间不足或目录不可写）"
}
$safetySha = Get-Sha256 $safetyPath
if ($safetySha -ne $curSha) {
    Stop-WithError "安全备份校验失败（$safetySha ≠ $curSha），已停止。"
}
Write-Ok '安全备份完成'

# --- 8. 还原 ---------------------------------------------------------------
Write-Info '正在还原原版资源包（约 85 MB，请稍候）…'
try {
    [System.IO.File]::Copy($backupPath, $assetsPath, $true)
} catch {
    Stop-WithError "还原写入失败：$($_.Exception.Message)`n当前文件安全网备份：$safetyPath"
}

Write-Info '校验还原结果 …'
$newSha = Get-Sha256 $assetsPath
$newSize = ([System.IO.FileInfo]$assetsPath).Length
if ($newSha -ne $expectedOriginalSha) {
    Write-Warn "还原后 sha256 不符（期望 $expectedOriginalSha，实际 $newSha）！"
    Write-Warn "请用安全网备份手动恢复：$safetyPath"
    Stop-WithError '还原校验失败。'
}
if ($newSize -ne $expectedOriginalSize) {
    Write-Warn "还原后文件大小与预期原版不一致（实际 $newSize 字节 / 预期 $expectedOriginalSize 字节），但 sha256 已匹配，通常无需担心。"
}
Write-Ok "还原校验通过（sha256 = $expectedOriginalSha）"

# --- 9. 写还原记录 ---------------------------------------------------------
$recordLines = @(
    'WER 原生函数积木 - 离线还原记录',
    '==================================================',
    ('时间            = ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')),
    ('计算机          = ' + $env:COMPUTERNAME),
    ('用户            = ' + $env:USERNAME),
    ('是否管理员      = ' + $isAdmin),
    ('工具版本        = ' + $ToolVersion),
    ('目标资源包      = ' + $assetsPath),
    ('还原前sha256    = ' + $curSha),
    ('还原后sha256    = ' + $newSha),
    ('使用的原版备份  = ' + $backupPath),
    ('还原前安全备份  = ' + $safetyPath),
    ('备注            = 本记录由 还原.ps1 自动生成。')
)
$recordPath = ''
try {
    $recordPath = Write-RecordFile ('还原记录-' + $stamp + '.txt') $recordLines
} catch {
    Write-Warn "写还原记录失败（不影响还原结果）：$($_.Exception.Message)"
}

# --- 10. 完成 --------------------------------------------------------------
Write-Host ''
Write-Host ('=' * 78)
Write-Ok '还原完成'
Write-Host "  还原前 sha256 : $curSha"
Write-Host "  还原后 sha256 : $newSha（原版）"
Write-Host "  使用的备份    : $backupPath"
Write-Host "  还原前安全备份: $safetyPath"
if ($recordPath) { Write-Host "  还原记录      : $recordPath" }
Write-Host ''
Write-Host '[DONE] AbilixScratch3.0 的资源包已还原成原版。'
Write-Host '       打开 IDE 后「我的函数」分类会消失，这是正常的（补丁已卸载）。'
Write-Host ''
exit 0
