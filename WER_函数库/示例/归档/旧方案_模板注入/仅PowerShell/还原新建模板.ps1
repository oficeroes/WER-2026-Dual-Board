# TOOL-ID: RESTORE
# =============================================================================
# 还原新建模板.ps1
# -----------------------------------------------------------------------------
# 作用：把 AbilixScratch3.0 的 browser_assets（新建项目默认模板资源包）还原成
#       打补丁之前的样子。
#
# 用法：
#   * 一般直接双击同目录的「一键还原(管理员).cmd」；
#   * 或：powershell -NoProfile -ExecutionPolicy Bypass -File 还原新建模板.ps1 -Yes
#   * 指定副本：... -Assets <browser_assets路径>
#   * 指定某个备份：... -Backup <browser_assets.备份-xxxx>
#
# 行为：
#   1. 在 browser_assets 同目录里找 browser_assets.备份-<时间戳>（同步脚本每次安装前
#      自动生成），按时间取最新一个有效资源包；可用 -Backup 手动指定；
#   2. 先把"当前文件"另存为 browser_assets.还原前备份-<时间戳>（防止误还原丢当前版本）；
#   3. 用备份覆盖 browser_assets，并校验 sha256；
#   4. 还原后重启 IDE 即可看到原始的新建项目模板。
#
# 兼容性：只依赖 Windows 自带 PowerShell 5.1，不需要 Python / 第三方模块。
# =============================================================================

[CmdletBinding()]
param(
    [string]$Assets = '',
    [string]$Backup = '',
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'

$script:ZFB_MAGIC = 'zfbRes_v1'
$script:BACKUP_GLOB = 'browser_assets.备份-*'
$script:PRE_RESTORE_PREFIX = 'browser_assets.还原前备份-'
$script:ASSET_SUBPATHS = @(
    'AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets',
    'AbilixScratch3.0\AbilixScratch3_0_Data\Resources\browser_assets'
)

# ===========================================================================
# 通用小工具（与 同步我的函数库.ps1 中的同名函数逻辑一致）
# ===========================================================================

function Write-Banner {
    param([string]$Title)
    Write-Host ''
    Write-Host ('=' * 74)
    Write-Host ('  ' + $Title)
    Write-Host ('=' * 74)
}

function Write-Step {
    param([string]$Message)
    Write-Host ('[还原] ' + $Message)
}

function Write-Detail {
    param([string]$Message)
    Write-Host ('        ' + $Message)
}

function Get-Sha256HexFromFile {
    param([string]$Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $fs = [System.IO.File]::OpenRead($Path)
    try {
        $hash = $sha.ComputeHash($fs)
    } finally {
        $fs.Dispose()
        $sha.Dispose()
    }
    return ([System.BitConverter]::ToString($hash).Replace('-', '').ToLowerInvariant())
}

function Format-ByteSize {
    param([long]$Bytes)
    if ($Bytes -ge 1048576) { return ('{0:F2} MB' -f ($Bytes / 1048576.0)) }
    if ($Bytes -ge 1024) { return ('{0:F1} KB' -f ($Bytes / 1024.0)) }
    return ([string]$Bytes + ' B')
}

function Test-IsAdministrator {
    try {
        $principal = New-Object Security.Principal.WindowsPrincipal(
            [Security.Principal.WindowsIdentity]::GetCurrent())
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

function Test-DirectoryWritable {
    param([string]$Directory)
    $probe = Join-Path $Directory ('.dsh_write_test_' + [System.Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $stream = [System.IO.File]::Create($probe)
        try { $stream.WriteByte(120) } finally { $stream.Dispose() }
        [System.IO.File]::Delete($probe)
        return $true
    } catch {
        try { if ([System.IO.File]::Exists($probe)) { [System.IO.File]::Delete($probe) } } catch { }
        return $false
    }
}

function Find-BrowserAssets {
    if (-not [string]::IsNullOrEmpty($env:ABILIX_ASSETS)) {
        if ([System.IO.File]::Exists($env:ABILIX_ASSETS)) {
            return (Resolve-Path -LiteralPath $env:ABILIX_ASSETS).Path
        }
    }
    $roots = New-Object 'System.Collections.Generic.List[string]'
    if (-not [string]::IsNullOrEmpty($env:ProgramFiles)) { $roots.Add($env:ProgramFiles) }
    $pf86 = [System.Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    if (-not [string]::IsNullOrEmpty($pf86)) { $roots.Add($pf86) }
    try {
        foreach ($drive in [System.IO.DriveInfo]::GetDrives()) {
            if (-not $drive.IsReady) { continue }
            foreach ($cand in @('Program Files', 'Program Files (x86)')) {
                $p = Join-Path $drive.RootDirectory.FullName $cand
                if ([System.IO.Directory]::Exists($p) -and -not $roots.Contains($p)) {
                    $roots.Add($p)
                }
            }
        }
    } catch { }
    foreach ($root in $roots) {
        foreach ($sub in $script:ASSET_SUBPATHS) {
            $p = Join-Path $root $sub
            if ([System.IO.File]::Exists($p)) {
                return (Resolve-Path -LiteralPath $p).Path
            }
        }
        try {
            $abilixDirs = Get-ChildItem -LiteralPath $root -Directory -Filter 'AbilixScratch3*' -ErrorAction SilentlyContinue
            foreach ($dir in $abilixDirs) {
                $dataDirs = Get-ChildItem -LiteralPath $dir.FullName -Directory -Filter 'AbilixScratch3*_Data' -ErrorAction SilentlyContinue
                foreach ($dd in $dataDirs) {
                    $p = Join-Path $dd.FullName 'Resources\browser_assets'
                    if ([System.IO.File]::Exists($p)) {
                        return (Resolve-Path -LiteralPath $p).Path
                    }
                }
            }
        } catch { }
    }
    return $null
}

# ===========================================================================
# 还原专用函数
# ===========================================================================

function Test-ZfbMagicFile {
    param([string]$Path)
    try {
        $fs = [System.IO.File]::OpenRead($Path)
        $br = New-Object System.IO.BinaryReader($fs, [System.Text.Encoding]::UTF8)
        try {
            $magic = $br.ReadString()
        } finally {
            $br.Dispose()
        }
        return ($magic -ceq 'zfbRes_v1')
    } catch {
        return $false
    }
}

function Find-AssetsBackups {
    param([string]$Directory)
    $result = New-Object 'System.Collections.Generic.List[object]'
    if (-not [System.IO.Directory]::Exists($Directory)) { return , $result }
    $files = @(Get-ChildItem -LiteralPath $Directory -File -Filter $script:BACKUP_GLOB -ErrorAction SilentlyContinue)
    $tmp = New-Object 'System.Collections.Generic.List[object]'
    foreach ($f in $files) {
        $tmp.Add((New-Object PSObject -Property @{
            Path = $f.FullName
            Size = [long]$f.Length
            LastWriteTime = $f.LastWriteTime
            Sha256 = (Get-Sha256HexFromFile -Path $f.FullName)
            IsValidZfb = (Test-ZfbMagicFile -Path $f.FullName)
        }))
    }
    $sorted = @($tmp | Sort-Object -Property @{ Expression = 'LastWriteTime'; Descending = $true },
        @{ Expression = 'Path'; Descending = $true })
    foreach ($item in $sorted) { $result.Add($item) }
    return , $result
}

function Save-PreRestoreBackup {
    param([string]$AssetsPath)
    $targetDir = [System.IO.Path]::GetDirectoryName($AssetsPath)
    $stamp = (Get-Date).ToString('yyyyMMdd-HHmmss')
    $dest = Join-Path $targetDir ($script:PRE_RESTORE_PREFIX + $stamp)
    $n = 1
    while ([System.IO.File]::Exists($dest)) {
        $dest = Join-Path $targetDir ($script:PRE_RESTORE_PREFIX + $stamp + '_' + $n)
        $n = $n + 1
    }
    $currentHash = Get-Sha256HexFromFile -Path $AssetsPath
    [System.IO.File]::Copy($AssetsPath, $dest, $false)
    $destHash = Get-Sha256HexFromFile -Path $dest
    if ($currentHash -cne $destHash) {
        throw ('还原前备份校验失败（未做任何修改）：' + $dest)
    }
    return New-Object PSObject -Property @{
        Path = $dest
        Sha256 = $destHash
    }
}

# ===========================================================================
# 主流程
# ===========================================================================

function Invoke-RestoreMain {
    Write-Banner 'AbilixScratch3.0 新建项目默认模板 —— 还原（仅 PowerShell 版）'
    Write-Detail ('本机 PowerShell 版本：' + $PSVersionTable.PSVersion.ToString())

    # ---------- 1) 定位 browser_assets ----------
    Write-Step '1/6 定位 browser_assets'
    $assetsPath = $Assets
    if ([string]::IsNullOrEmpty($assetsPath)) {
        $found = Find-BrowserAssets
        if ($null -eq $found) {
            throw ('自动探测不到 AbilixScratch3.0 的 browser_assets。' + "`r`n" +
                '  可以用 -Assets 参数手动指定。')
        }
        $assetsPath = $found
        Write-Detail ('自动探测到：' + $assetsPath)
    } else {
        if (-not [System.IO.File]::Exists($assetsPath)) {
            throw ('-Assets 指定的文件不存在：' + $assetsPath)
        }
        $assetsPath = (Resolve-Path -LiteralPath $assetsPath).Path
    }
    $targetDir = [System.IO.Path]::GetDirectoryName($assetsPath)
    $currentHash = Get-Sha256HexFromFile -Path $assetsPath
    $currentSize = ([System.IO.FileInfo]::new($assetsPath)).Length
    Write-Detail ('当前文件：' + (Format-ByteSize -Bytes $currentSize) + '  sha256=' + $currentHash)
    Write-Detail ('是否有效 zfbRes_v1 资源包：' + (Test-ZfbMagicFile -Path $assetsPath))

    # ---------- 2) 找备份 ----------
    Write-Step ('2/6 查找备份文件（' + $script:BACKUP_GLOB + '）')
    $chosen = $null
    if (-not [string]::IsNullOrEmpty($Backup)) {
        if (-not [System.IO.File]::Exists($Backup)) {
            throw ('-Backup 指定的备份文件不存在：' + $Backup)
        }
        $backupPath = (Resolve-Path -LiteralPath $Backup).Path
        $backupFile = [System.IO.FileInfo]::new($backupPath)
        $chosen = New-Object PSObject -Property @{
            Path = $backupPath
            Size = [long]$backupFile.Length
            LastWriteTime = $backupFile.LastWriteTime
            Sha256 = (Get-Sha256HexFromFile -Path $backupPath)
            IsValidZfb = (Test-ZfbMagicFile -Path $backupPath)
        }
        Write-Detail ('手动指定备份：' + $chosen.Path)
    } else {
        $backups = Find-AssetsBackups -Directory $targetDir
        if ($backups.Count -le 0) {
            throw ('没有找到任何备份文件（' + (Join-Path $targetDir $script:BACKUP_GLOB) + '）。' + "`r`n" +
                '  如果从没运行过同步，当前就是原始模板，不需要还原；' + "`r`n" +
                '  如果是便携版/换了目录，请用 -Assets 指定对应 browser_assets，或用 -Backup 指定备份文件。')
        }
        Write-Detail ('找到 ' + $backups.Count + ' 个备份（按时间从新到旧）：')
        $idx = 0
        foreach ($b in $backups) {
            $idx = $idx + 1
            $mark = ''
            if (-not $b.IsValidZfb) { $mark = '  [无效资源包，忽略]' }
            Write-Detail ('  [' + $idx + '] ' + ([System.IO.Path]::GetFileName($b.Path)) + '  ' +
                (Format-ByteSize -Bytes $b.Size) + '  ' + $b.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') +
                '  sha256=' + $b.Sha256.Substring(0, 16) + '...' + $mark)
            if ($null -eq $chosen -and $b.IsValidZfb) {
                $chosen = $b
            }
        }
        if ($null -eq $chosen) {
            throw '找到的备份文件都不是有效的 zfbRes_v1 资源包，无法还原。'
        }
        Write-Detail ('将使用最新有效备份：' + $chosen.Path)
    }
    if (-not $chosen.IsValidZfb) {
        throw ('选中的备份不是有效的 zfbRes_v1 资源包：' + $chosen.Path)
    }

    # ---------- 3) 权限 + 确认 ----------
    Write-Step '3/6 检查写入权限'
    $isAdmin = Test-IsAdministrator
    if (-not $isAdmin -and -not (Test-DirectoryWritable -Directory $targetDir)) {
        throw ('没有写入权限：' + $targetDir + "`r`n" +
            '  请用「一键还原(管理员).cmd」运行（会自动请求管理员权限）。')
    }
    Write-Detail ('管理员=' + $isAdmin + '；目标目录可写=True')
    if (-not $Yes) {
        Write-Host ''
        Write-Host ('即将把：' + $assetsPath)
        Write-Host ('还原为：' + $chosen.Path)
        Write-Host '当前文件会先另存为「browser_assets.还原前备份-<时间戳>」。'
        $answer = Read-Host '确认还原？输入 y 回车继续，其它任意键取消'
        if ($answer -notmatch '^[yY]') {
            Write-Host '已取消（未做任何修改）。'
            return 0
        }
    }

    # ---------- 4) 备份当前文件 ----------
    Write-Step '4/6 先把当前文件另存为还原前备份'
    $pre = Save-PreRestoreBackup -AssetsPath $assetsPath
    Write-Detail ('当前文件已备份：' + $pre.Path)
    Write-Detail ('sha256=' + $pre.Sha256)

    # ---------- 5) 用备份覆盖 ----------
    Write-Step '5/6 用备份覆盖 browser_assets'
    try {
        [System.IO.File]::Copy($chosen.Path, $assetsPath, $true)
    } catch {
        throw ('写入失败（IDE 是否正在运行？请先关闭软件）：' + $_.Exception.Message +
            "`r`n  还原前备份：" + $pre.Path)
    }
    $finalHash = Get-Sha256HexFromFile -Path $assetsPath
    if ($finalHash -cne $chosen.Sha256) {
        throw ('还原后文件 sha256 与备份不一致！请人工处理。' + "`r`n" +
            '  当前文件：' + $assetsPath + "`r`n" +
            '  应还原的备份：' + $chosen.Path + "`r`n" +
            '  还原前备份：' + $pre.Path)
    }

    # ---------- 6) 汇总 ----------
    Write-Step '6/6 完成'
    Write-Host ''
    Write-Host ('=' * 74)
    Write-Host '  还原结果'
    Write-Host ('-' * 74)
    Write-Host ('  browser_assets: ' + $assetsPath)
    Write-Host ('  还原前 sha256 : ' + $currentHash)
    Write-Host ('  还原后 sha256 : ' + $finalHash)
    Write-Host ('  使用的备份    : ' + $chosen.Path)
    Write-Host ('  还原前备份    : ' + $pre.Path)
    Write-Host '  状态          : OK 已还原（重启 IDE 后新建项目恢复原始模板）'
    Write-Host ('=' * 74)
    return 0
}

# 只有被直接运行（而不是被 dot-source 做单元测试）时才执行主流程
if ($MyInvocation.InvocationName -ne '.') {
    $exitCode = 0
    try {
        $exitCode = Invoke-RestoreMain
    } catch {
        Write-Host ''
        Write-Host ('[错误] ' + $_.Exception.Message) -ForegroundColor Red
        if ($Verbose -and -not [string]::IsNullOrEmpty($_.ScriptStackTrace)) {
            Write-Host ('  位置：' + $_.ScriptStackTrace) -ForegroundColor DarkGray
        }
        $exitCode = 1
    }
    exit $exitCode
}
