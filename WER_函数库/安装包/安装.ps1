# =============================================================================
#  WER 原生函数积木 - 离线安装脚本（Windows PowerShell 5.1，安装时不需要 Python）
#
#  用法（一般用户）：
#    双击「安装原生积木(离线).cmd」——会自动请求管理员权限（UAC）。
#
#  用法（高级 / 测试）：
#    powershell -NoProfile -ExecutionPolicy Bypass -File "安装.ps1"
#    powershell -NoProfile -ExecutionPolicy Bypass -File "安装.ps1" -Target "D:\Program Files\AbilixScratch3.0" -Yes
#    powershell -NoProfile -ExecutionPolicy Bypass -File "安装.ps1" -Target "X:\任意盘\AbilixScratch3.0" -Yes
#
#  参数：
#    -Target  安装根目录（含 AbilixScratch3.0.exe 的那一层）、或 *_Data 目录、
#             或 Resources 目录、或 browser_assets 文件本身。
#             省略时自动查找本机 AbilixScratch3.0。
#    -Source  补丁包路径（默认：本脚本同目录 browser_assets.patched）
#    -Info    编译信息文件（默认：本脚本同目录 编译信息.txt）
#    -Yes     跳过交互确认（适合自动化 / 无人值守）
#    -Force   放宽检查（IDE 正在运行、目标 sha 不是原版时也继续；不推荐）
#
#  本文件必须保存为「UTF-8 with BOM」，否则 Windows PowerShell 5.1 会按 ANSI
#  读取，导致中文乱码甚至语法错误。
# =============================================================================

[CmdletBinding()]
param(
    [string]$Target = '',
    [string]$Source = '',
    [string]$Info = '',
    [switch]$Yes,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# 尽量让控制台/重定向输出用 UTF-8，中文日志才不乱码
try { $OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }

$ToolName = 'WER 原生函数积木 - 离线安装'
$ToolVersion = '1.0.0'

# 本机记录的 AbilixScratch3.0 原始 browser_assets（安装包的 Source 就是它编译的）
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
function Write-FailMark([string]$m) { Write-Host "[ERROR] $m" -ForegroundColor Red }

function Stop-WithError([string]$msg) {
    Write-Host ''
    Write-FailMark $msg
    Write-Host ''
    Write-Host '[ERROR] 安装未完成。如果已经动过目标文件，请用备份或「还原原版(离线).cmd」恢复。'
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

# 检测 AbilixScratch3.0 是否正在运行（进程名含 abilixscratch 即视为运行中）
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

# 从「编译信息.txt」读取 key = value 形式的记录
function Read-BuildInfo([string]$path) {
    if (-not [System.IO.File]::Exists($path)) {
        Stop-WithError ("缺少编译信息文件：$path`n" + `
            "「安装包」文件夹必须完整拷贝（至少要有 安装.ps1、还原.ps1、browser_assets.patched、编译信息.txt、README_离线安装.txt）。")
    }
    $map = @{}
    $lines = [System.IO.File]::ReadAllLines($path, [System.Text.Encoding]::UTF8)
    foreach ($line in $lines) {
        $t = ([string]$line).Trim()
        if ($t -eq '') { continue }
        if ($t.StartsWith('#')) { continue }
        if ($t.StartsWith('=')) { continue }
        $i = $t.IndexOf('=')
        if ($i -le 0) { continue }
        $k = $t.Substring(0, $i).Trim()
        $v = $t.Substring($i + 1).Trim()
        if (-not $map.ContainsKey($k)) { $map[$k] = $v }
    }
    return $map
}

function Get-BuildInfoValue($map, [string]$key) {
    if (-not $map.ContainsKey($key)) { Stop-WithError "编译信息.txt 缺少字段：$key（安装包可能不完整或被破坏）" }
    $v = [string]$map[$key]
    if ($v.Trim() -eq '') { Stop-WithError "编译信息.txt 的字段为空：$key" }
    return $v.Trim()
}

# 把 -Target 解析成 browser_assets 文件的绝对路径
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
Write-Host '  纯 PowerShell 5.1 实现：安装时不需要 Python，也不需要 Chrome。'
Write-Host ('=' * 78)
Write-Info "时间       : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Info "脚本目录   : $ScriptDir"

$isAdmin = Test-IsAdmin
if ($isAdmin) {
    Write-Info '当前权限   : 管理员'
} else {
    Write-Info '当前权限   : 普通用户（目标目录可写时也能继续，例如复制出来的测试副本）'
}

# --- 1. 读取并校验安装包自身 ------------------------------------------------
if ($Info -eq '') { $infoPath = [System.IO.Path]::Combine($ScriptDir, '编译信息.txt') }
else { $infoPath = Resolve-AgainstScriptDir $Info }
if ($Source -eq '') { $sourcePath = [System.IO.Path]::Combine($ScriptDir, 'browser_assets.patched') }
else { $sourcePath = Resolve-AgainstScriptDir $Source }

$bi = Read-BuildInfo $infoPath
$patchedSha = (Get-BuildInfoValue $bi '补丁包sha256').ToUpperInvariant()
$patchedSizeText = Get-BuildInfoValue $bi '补丁包大小'
$libSha = Get-BuildInfoValue $bi '函数库sha256'
$funcList = ''
if ($bi.ContainsKey('函数列表')) { $funcList = [string]$bi['函数列表'] }
if ($patchedSha -notmatch '^[0-9A-F]{64}$') { Stop-WithError "编译信息.txt 里的「补丁包sha256」格式不对：$patchedSha" }
$patchedSize = [int64]$patchedSizeText
if ($patchedSize -le 0) { Stop-WithError "编译信息.txt 里的「补丁包大小」无效：$patchedSizeText" }

Write-Info "编译信息   : $infoPath"
Write-Info "对应函数库 : sha256=$libSha"
if ($funcList) { Write-Info "函数列表   : $funcList" }

if (-not [System.IO.File]::Exists($sourcePath)) {
    Stop-WithError ("找不到补丁包文件：$sourcePath`n" + `
        "请确认「安装包」文件夹完整（不能只拷 exe/脚本），或用 -Source 指定 browser_assets.patched 的位置。")
}
$srcFileSize = ([System.IO.FileInfo]$sourcePath).Length
if ($srcFileSize -ne $patchedSize) {
    Write-Warn "补丁包大小与编译信息不一致（文件 $srcFileSize 字节 / 记录 $patchedSize 字节），可能拷贝不完整。"
}
Write-Info "补丁包     : $sourcePath（$(Format-Size $srcFileSize)）"
Write-Info '校验补丁包 sha256 …'
$srcSha = Get-Sha256 $sourcePath
if ($srcSha -ne $patchedSha) {
    Stop-WithError ("补丁包 sha256 与编译信息不一致！`n" +
        "  期望：$patchedSha`n  实际：$srcSha`n" +
        "文件可能拷贝不完整或损坏，请重新完整拷贝「安装包」文件夹。")
}
Write-Ok "补丁包校验通过（sha256 $($patchedSha.Substring(0,16))…）"

# --- 2. 定位安装目标 --------------------------------------------------------
if ($Target -ne '') {
    try {
        $assetsPath = Resolve-TargetAssets $Target
    } catch {
        Stop-WithError $_.Exception.Message
    }
    $targetRootForInfo = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $assetsPath))
    Write-Info "安装目标   : $assetsPath（由 -Target 指定）"
} else {
    $found = Find-DefaultTarget
    if (-not $found) {
        Stop-WithError ("没有自动找到 AbilixScratch3.0 的 browser_assets。`n" +
            "  · 如果 IDE 装在别的盘/别的目录，请用 -Target 指定安装根目录，例如：`n" +
            "    powershell -NoProfile -ExecutionPolicy Bypass -File `"$ScriptDir\安装.ps1`" -Target `"E:\Program Files\AbilixScratch3.0`"`n" +
            "  · 或者把 AbilixScratch3.0 的安装目录拖动/输入到窗口（高级用法）。`n" +
            "  · 默认查找位置：D:\Program Files\AbilixScratch3.0、各盘 Program Files\AbilixScratch3.0 等。")
    }
    $assetsPath = $found.Assets
    $targetRootForInfo = $found.Root
    Write-Info "安装目标   : $assetsPath（自动定位，安装根目录 $($found.Root)）"
}

$assetsDir = Split-Path -Parent $assetsPath
if (-not [System.IO.File]::Exists($assetsPath)) {
    Stop-WithError "目标资源包不存在：$assetsPath（IDE 可能未安装，或安装目录结构不同；请用 -Target 指定）"
}

# --- 3. 权限检查（管理员或目标可写） ----------------------------------------
$writable = Test-TargetWritable $assetsPath
if (-not $writable) {
    Stop-WithError ("没有写入权限：$assetsPath`n" +
        "  · 该文件位于 Program Files 等受保护目录，安装需要管理员权限。`n" +
        "  · 正确做法：双击同目录的「安装原生积木(离线).cmd」，它会自动请求管理员权限（UAC）。`n" +
        "  · 也可以：以管理员身份打开 PowerShell，再运行本脚本。`n" +
        "  · 测试/绿色版：如果目标目录本身可写（例如复制到临时目录的副本），用 -Target 指向它即可，无需管理员。")
}
if (-not $isAdmin) {
    Write-Warn '当前不是管理员，但目标目录可写：继续安装（适用于测试副本 / 绿色版目录；真实 Program Files 安装请用管理员权限）。'
}

# --- 4. 检测 IDE 是否运行 ---------------------------------------------------
$running = Get-AbilixProcessNames
if ($running.Count -gt 0) {
    if (-not $Force) {
        Stop-WithError ("检测到 AbilixScratch3.0 正在运行（$($running -join '、')）。`n" +
            "请先在 IDE 里保存作品并完全关闭它（包括托盘/后台进程），再重新运行安装。")
    } else {
        Write-Warn "AbilixScratch3.0 正在运行（$($running -join '、')），因为指定了 -Force，继续。"
    }
} else {
    Write-Ok 'IDE 未在运行'
}

# --- 5. 检查目标当前状态 -----------------------------------------------------
Write-Info '计算目标资源包当前 sha256 …'
$curSha = Get-Sha256 $assetsPath
$curSize = ([System.IO.FileInfo]$assetsPath).Length
Write-Info "目标当前   : $(Format-Size $curSize)，sha256 $curSha"

if ($curSha -eq $patchedSha) {
    Stop-WithError ("目标资源包已经是本安装包的补丁版本（sha256 与补丁包相同），无需重复安装。`n" +
        "  · 如果想重新安装，请先运行「还原原版(离线).cmd」还原，再安装。`n" +
        "  · 如果想换一个函数库补丁，请先还原，再用对应的安装包安装。")
}
if ($curSha -ne $OriginalSha) {
    if (-not $Force) {
        Stop-WithError ("目标资源包不是本安装包对应的原版（sha256 不同）。`n" +
            "  期望原版 sha256：$OriginalSha`n  目标实际 sha256：$curSha`n" +
            "可能原因：IDE 版本不同、已被别的工具/补丁改过、或安装包与本机 IDE 不匹配。`n" +
            "  · 如果确认要继续，请加 -Force（风险自负，建议先备份）。`n" +
            "  · 如果之前装过旧补丁，请先运行「还原原版(离线).cmd」。")
    } else {
        Write-Warn "目标不是已知原版（sha256 不同），因为指定了 -Force，仍然继续（不推荐）。"
    }
} else {
    Write-Ok '目标是原版资源包，可以安装'
}

# --- 6. 确认 ---------------------------------------------------------------
Write-Host ''
Write-Host '即将执行：'
Write-Host "  1) 备份当前资源包到目标同目录 browser_assets.备份-<时间戳>"
Write-Host "  2) 用补丁包覆盖目标资源包（$(Format-Size $patchedSize)）"
Write-Host "  3) 写入后校验 sha256 必须等于 $($patchedSha.Substring(0,16))…"
Write-Host ''
if (-not $Yes) {
    $ans = Read-Host '确认安装？输入 Y 继续，直接回车取消'
    if ($ans -notmatch '^[Yy]') {
        Write-Host '[OK] 已取消，目标文件没有被修改。'
        exit 0
    }
}

# --- 7. 备份当前资源包 ------------------------------------------------------
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupPath = Get-UniquePath ([System.IO.Path]::Combine($assetsDir, 'browser_assets.备份-' + $stamp))
Write-Info "备份当前资源包 -> $backupPath"
try {
    [System.IO.File]::Copy($assetsPath, $backupPath, $false)
} catch {
    Stop-WithError "备份失败：$($_.Exception.Message)`n（目标磁盘可能空间不足或目录不可写）"
}
$bkSha = Get-Sha256 $backupPath
if ($bkSha -ne $curSha) {
    Stop-WithError "备份校验失败：备份文件 sha256（$bkSha）与备份前（$curSha）不一致，已停止。"
}
Write-Ok "备份完成（sha256 与安装前一致）"

# --- 8. 复制补丁包覆盖 ------------------------------------------------------
Write-Info '正在写入补丁包（约 85 MB，请稍候）…'
$writeOk = $false
try {
    [System.IO.File]::Copy($sourcePath, $assetsPath, $true)
    $writeOk = $true
} catch {
    $writeOk = $false
    $writeErr = $_.Exception.Message
}
if (-not $writeOk) {
    # 尝试回滚
    try { [System.IO.File]::Copy($backupPath, $assetsPath, $true) } catch { }
    Stop-WithError "写入目标资源包失败：$writeErr`n已尝试用备份回滚（备份文件：$backupPath）"
}

# --- 9. 写入后校验，失败自动回滚 -------------------------------------------
Write-Info '校验写入结果 …'
$newSha = Get-Sha256 $assetsPath
$newSize = ([System.IO.FileInfo]$assetsPath).Length
if ($newSha -ne $patchedSha) {
    Write-Warn "写入后 sha256 不符（期望 $patchedSha，实际 $newSha），正在用备份自动回滚 …"
    try {
        [System.IO.File]::Copy($backupPath, $assetsPath, $true)
        $rbSha = Get-Sha256 $assetsPath
        Write-Warn "已回滚，目标当前 sha256 = $rbSha"
    } catch {
        Write-Warn "自动回滚失败：$($_.Exception.Message)`n请手动把备份复制回目标：$backupPath"
    }
    Stop-WithError "安装后校验失败，已停止（目标已尽量恢复原状）。请检查磁盘空间/杀毒软件后重试。"
}
Write-Ok "写入校验通过（sha256 = $patchedSha）"

# --- 10. 写一份安装记录到安装包目录 ----------------------------------------
$recordLines = @(
    'WER 原生函数积木 - 离线安装记录',
    '==================================================',
    ('时间            = ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')),
    ('计算机          = ' + $env:COMPUTERNAME),
    ('用户            = ' + $env:USERNAME),
    ('是否管理员      = ' + $isAdmin),
    ('工具版本        = ' + $ToolVersion),
    ('目标资源包      = ' + $assetsPath),
    ('安装前sha256    = ' + $curSha),
    ('安装后sha256    = ' + $newSha),
    ('补丁包文件      = ' + $sourcePath),
    ('补丁包sha256    = ' + $patchedSha),
    ('函数库sha256    = ' + $libSha),
    ('原版备份文件    = ' + $backupPath),
    ('还原方法        = 运行同目录「还原原版(离线).cmd」，或 powershell -NoProfile -ExecutionPolicy Bypass -File "还原.ps1" -Yes'),
    ('备注            = 本记录由 安装.ps1 自动生成；恢复时优先使用上面的原版备份文件。')
)
$recordPath = ''
try {
    $recordPath = Write-RecordFile ('安装记录-' + $stamp + '.txt') $recordLines
} catch {
    Write-Warn "写安装记录失败（不影响安装结果）：$($_.Exception.Message)"
}

# --- 11. 完成 ---------------------------------------------------------------
Write-Host ''
Write-Host ('=' * 78)
Write-Ok '安装完成'
Write-Host "  安装前 sha256 : $curSha"
Write-Host "  安装后 sha256 : $newSha（与补丁包一致）"
Write-Host "  原版备份文件  : $backupPath"
if ($recordPath) { Write-Host "  安装记录      : $recordPath" }
Write-Host ''
Write-Host '[DONE] 原生函数积木已安装到本机 AbilixScratch3.0。'
Write-Host '       打开 AbilixScratch3.0，新建作品后，左侧积木分类里应出现「我的函数」。'
Write-Host ''
Write-Host '       以后要还原原版：双击同目录的「还原原版(离线).cmd」，或运行：'
Write-Host "       powershell -NoProfile -ExecutionPolicy Bypass -File `"$ScriptDir\还原.ps1`" -Yes"
Write-Host ''
exit 0
