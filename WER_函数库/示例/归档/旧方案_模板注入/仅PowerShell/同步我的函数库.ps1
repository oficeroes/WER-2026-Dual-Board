# TOOL-ID: SYNC
# =============================================================================
# 同步我的函数库.ps1
# -----------------------------------------------------------------------------
# 作用：把「我的函数库.srh / .srhs」里的全部函数定义（+变量声明+start 主函数）
#       同步进 AbilixScratch3.0 的新建项目默认模板。
#
# 原理（与 Python 版 工具\底层\patch_browser_assets.py 完全一致，已逐字节对拍）：
#   * 软件新建项目时执行 maingui.importDefaultCode()，读取 resource 包里
#     Blockly_Code/maingui_init.js 中的  var defaultcode = '...';  字符串；
#   * browser_assets 是自定义 zfbRes_v1 打包格式：
#         BinaryWriter.Write("zfbRes_v1") + WriteInt32(条目数)
#         每条: Write(名字) + WriteInt64(数据偏移) + WriteInt32(数据长度)
#         数据区按索引顺序紧凑排列（无压缩、无对齐填充）
#   * 本脚本只替换 maingui_init.js 里「简体中文」的 defaultcode 字符串内容
#     （defaultcodeTr / defaultcodeEn 保持不变），其余 6644 个条目逐字节不动。
#
# 安全设计（任何自检失败都不会安装）：
#   自检1 纯 roundtrip：解包→原样重打包，必须与原文件逐字节相同（sha256 相同）；
#   自检2 逐条目 sha256：除 /Blockly_Code/maingui_init.js 外全部与原包一致；
#   自检3 读回 defaultcode 反转义后必须等于函数库片段。
#   -Install 时先备份原文件为 browser_assets.备份-<时间戳> 再写入，并再校验 sha256。
#
# 兼容性：只依赖 Windows 自带 PowerShell 5.1（不会用到 PowerShell 7 语法），
#         不需要 Python / Node / 任何第三方模块。
#
# 用法（一般用同目录的「一键同步(管理员).cmd」双击即可）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File 同步我的函数库.ps1 -Install
#   powershell -NoProfile -ExecutionPolicy Bypass -File 同步我的函数库.ps1 -Assets <副本> -Out <输出>
#
# 参数：
#   -Assets    browser_assets 路径（默认自动探测安装目录）
#   -Library   函数库源文件 .srh/.srhs（默认 <WER_函数库>\我的函数库.srhs）
#   -Out       补丁包输出路径（默认 <本脚本目录>\browser_assets.patched）
#   -WorkDir   临时工作目录（默认系统临时目录，结束自动清理）
#   -Install   写回 browser_assets（需要管理员；副本/便携版目录可写时也可用）
#   -SkipIdenticalCheck  跳过「纯 roundtrip 必须逐字节一致」检查（不建议）
#   -KeepWork  保留临时工作目录（排查用）
# =============================================================================

[CmdletBinding()]
param(
    [string]$Assets = '',
    [string]$Library = '',
    [string]$Out = '',
    [string]$WorkDir = '',
    [switch]$Install,
    [switch]$SkipIdenticalCheck,
    [switch]$KeepWork
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# 常量（与 Python 版保持一致）
# ---------------------------------------------------------------------------
$script:ZFB_MAGIC = 'zfbRes_v1'
$script:INIT_ENTRY_NAME = '/Blockly_Code/maingui_init.js'
$script:INIT_REL_PATH = 'Blockly_Code/maingui_init.js'
$script:BACKUP_PREFIX = 'browser_assets.备份-'
$script:INFO_START = '<Abilix.ScratchProject.Info>'
$script:INFO_END = '</Abilix.ScratchProject.Info>'
$script:PROJ_START = '<Abilix.ScratchProject.ProjectString>'
$script:PROJ_END = '</Abilix.ScratchProject.ProjectString>'
$script:ZFB_MAGIC_ENTRY = 'abilixProject.srh'
$script:DEFAULTCODE_VARS = @('defaultcode', 'defaultcodeTr', 'defaultcodeEn')

# 旧版（Python 参考实现里写死）的安装路径用下划线；真实安装目录是点号。
# 两种都探测，点号优先。
$script:ASSET_SUBPATHS = @(
    'AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets',
    'AbilixScratch3.0\AbilixScratch3_0_Data\Resources\browser_assets'
)

# ===========================================================================
# 一、通用小工具
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
    Write-Host ('[同步] ' + $Message)
}

function Write-Detail {
    param([string]$Message)
    Write-Host ('        ' + $Message)
}

function Get-Sha256HexFromBytes {
    param([byte[]]$Bytes)
    if ($null -eq $Bytes) { $Bytes = [byte[]]@() }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha.ComputeHash($Bytes)
    } finally {
        $sha.Dispose()
    }
    return ([System.BitConverter]::ToString($hash).Replace('-', '').ToLowerInvariant())
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

# .NET UTF-8 严格解码；若带 BOM 则跳过 BOM（与 Python 参考实现的 utf-8-sig 行为一致）
function ConvertFrom-Utf8Strict {
    param([byte[]]$Bytes)
    $offset = 0
    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) {
        $offset = 3
    }
    $enc = [System.Text.UTF8Encoding]::new($false, $true)
    try {
        return $enc.GetString($Bytes, $offset, $Bytes.Length - $offset)
    } catch {
        throw ('文本不是合法 UTF-8：' + $_.Exception.Message)
    }
}

function Get-BomLength {
    param([byte[]]$Bytes)
    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) {
        return 3
    }
    return 0
}

function ConvertTo-Utf8Bytes {
    param(
        [string]$Text,
        [switch]$WithBom
    )
    $enc = [System.Text.UTF8Encoding]::new($false)
    $body = $enc.GetBytes($Text)
    if (-not $WithBom) { return , $body }
    $result = [byte[]]::new(3 + $body.Length)
    $result[0] = 0xEF
    $result[1] = 0xBB
    $result[2] = 0xBF
    [System.Array]::Copy($body, 0, $result, 3, $body.Length)
    return , $result
}

# ===========================================================================
# 二、browser_assets（zfbRes_v1）读取 / 校验 / 重新打包
# ===========================================================================

function Read-ZfbIndex {
    param([string]$Path)
    if (-not [System.IO.File]::Exists($Path)) {
        throw ('browser_assets 不存在：' + $Path)
    }
    $fs = [System.IO.File]::OpenRead($Path)
    $br = New-Object System.IO.BinaryReader($fs, [System.Text.Encoding]::UTF8)
    try {
        $fileSize = $fs.Length
        try {
            $magic = $br.ReadString()
        } catch {
            throw ('读取资源包文件头失败（文件过短或已损坏）：' + $Path)
        }
        if ($magic -cne 'zfbRes_v1') {
            throw ('不是 zfbRes_v1 资源包（文件头为 ''' + $magic + '''）：' + $Path)
        }
        if (($fs.Length - $fs.Position) -lt 4) {
            throw ('文件过短，缺少条目数量：' + $Path)
        }
        $count = $br.ReadInt32()
        if ($count -lt 0 -or $count -gt 10000000) {
            throw ('资源包条目数量异常：' + $count)
        }
        $entries = New-Object 'System.Collections.Generic.List[object]'
        for ($i = 0; $i -lt $count; $i++) {
            $name = $br.ReadString()
            $offset = $br.ReadInt64()
            $length = $br.ReadInt32()
            $entry = New-Object PSObject -Property @{
                Name = $name
                Offset = $offset
                Length = $length
            }
            $entries.Add($entry)
        }
        $indexEnd = $fs.Position
        return New-Object PSObject -Property @{
            Path = $Path
            Magic = $magic
            Count = $count
            Entries = $entries
            IndexEnd = [long]$indexEnd
            FileSize = [long]$fileSize
        }
    } finally {
        $br.Dispose()
    }
}

function Assert-ZfbLayout {
    param($Info)
    $errors = New-Object 'System.Collections.Generic.List[string]'
    $warnings = New-Object 'System.Collections.Generic.List[string]'
    $entries = $Info.Entries
    if ($Info.Count -le 0) {
        $errors.Add('资源包索引里没有任何条目')
    }
    if ($Info.Count -ne $entries.Count) {
        $errors.Add('条目数量与索引声明不一致（' + $Info.Count + ' vs ' + $entries.Count + '）')
    }
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
    $prev = $null
    $useCnt = 0
    foreach ($e in $entries) {
        if ([string]::IsNullOrEmpty($e.Name)) {
            $errors.Add('存在空的条目名')
            continue
        }
        if (-not $e.Name.StartsWith('/')) {
            $warnings.Add('条目 ' + $e.Name + ' 不以 / 开头（软件以 URL 绝对路径查找，可能取不到）')
        }
        if (-not $seen.Add($e.Name)) {
            $errors.Add('条目名重复：' + $e.Name)
        }
        if ($e.Length -lt 0) {
            $errors.Add('条目 ' + $e.Name + ' 长度为负：' + $e.Length)
        }
        if ($e.Offset -lt 0 -or ($e.Offset + $e.Length) -gt $Info.FileSize) {
            $errors.Add('条目 ' + $e.Name + ' 数据越界：offset=' + $e.Offset + ' len=' + $e.Length +
                ' file_size=' + $Info.FileSize)
        }
        if ($null -ne $prev) {
            if (($prev.Offset + $prev.Length) -ne $e.Offset) {
                $warnings.Add('条目 ' + $e.Name + ' 与前一条目不连续（可能有对齐填充）')
            }
        }
        $prev = $e
        $useCnt = $useCnt + 1
    }
    if ($useCnt -gt 0) {
        $first = $entries[0]
        if ($first.Offset -lt $Info.IndexEnd) {
            $errors.Add('第一个条目 offset=' + $first.Offset + ' 落在索引区内（index_end=' + $Info.IndexEnd + '）')
        }
        $last = $entries[$entries.Count - 1]
        if (($last.Offset + $last.Length) -ne $Info.FileSize) {
            $warnings.Add('最后一个条目结束位置(' + ($last.Offset + $last.Length) + ') != 文件大小(' +
                $Info.FileSize + ')（可能有尾部数据）')
        }
    }
    return New-Object PSObject -Property @{
        Ok = ($errors.Count -eq 0)
        Errors = $errors
        Warnings = $warnings
    }
}

# 从已打开的 FileStream 上读取某个条目的完整字节
function Get-ZfbEntryBytes {
    param(
        [System.IO.FileStream]$Stream,
        $Entry
    )
    $len = [int]$Entry.Length
    if ($len -le 0) { return , ([byte[]]@()) }
    $buffer = [byte[]]::new($len)
    $Stream.Position = [long]$Entry.Offset
    $read = 0
    while ($read -lt $len) {
        $n = $Stream.Read($buffer, $read, $len - $read)
        if ($n -le 0) {
            throw ('读取条目数据不完整：' + $Entry.Name)
        }
        $read = $read + $n
    }
    return , $buffer
}

# 重新打包 zfbRes_v1：
#   索引区（写占位）→ 数据区（按索引顺序）→ 回填索引（偏移/长度）
# 布局与 C# StandaloneWebResources.WriteData 完全一致。
# $Replacement: 可选 hashtable（条目名 -> byte[]），用于替换条目内容。
function Write-ZfbPackage {
    param(
        [string]$SourcePath,
        $Entries,
        [string]$OutPath,
        [hashtable]$Replacement = $null,
        [hashtable]$HashOut = $null
    )
    $fsIn = [System.IO.File]::OpenRead($SourcePath)
    $fsOut = [System.IO.File]::Create($OutPath)
    $enc = [System.Text.UTF8Encoding]::new($false)
    $bw = New-Object System.IO.BinaryWriter($fsOut, $enc)
    $hashes = New-Object 'System.Collections.Generic.Dictionary[string,string]' ([System.StringComparer]::Ordinal)
    try {
        # 1) 文件头：magic + 条目数
        $bw.Write([string]$script:ZFB_MAGIC)
        $bw.Write([int]$Entries.Count)

        # 2) 先写索引占位（偏移/长度稍后回填）
        $indexPos = $fsOut.Position
        foreach ($e in $Entries) {
            $bw.Write([string]$e.Name)
            $bw.Write([int64]0)
            $bw.Write([int32]0)
        }
        $bw.Flush()

        # 3) 写数据区，同时记录每个条目的实际偏移
        $offsets = New-Object 'System.Collections.Generic.Dictionary[string,long]' ([System.StringComparer]::Ordinal)
        $lengths = New-Object 'System.Collections.Generic.Dictionary[string,int]' ([System.StringComparer]::Ordinal)
        foreach ($e in $Entries) {
            $blob = $null
            if ($null -ne $Replacement -and $Replacement.ContainsKey($e.Name)) {
                $blob = [byte[]]$Replacement[$e.Name]
            } else {
                $blob = Get-ZfbEntryBytes -Stream $fsIn -Entry $e
            }
            $offsets[$e.Name] = [long]$fsOut.Position
            $lengths[$e.Name] = [int]$blob.Length
            $bw.Write([byte[]]$blob)
            $hashes[$e.Name] = (Get-Sha256HexFromBytes -Bytes $blob)
        }
        $bw.Flush()

        # 4) 回填索引（偏移 + 长度）
        $fsOut.Position = $indexPos
        foreach ($e in $Entries) {
            $bw.Write([string]$e.Name)
            $bw.Write([int64]$offsets[$e.Name])
            $bw.Write([int32]$lengths[$e.Name])
        }
        $bw.Flush()
    } finally {
        $bw.Dispose()
        $fsIn.Dispose()
    }
    if ($null -ne $HashOut) {
        foreach ($key in $hashes.Keys) { $HashOut[$key] = $hashes[$key] }
    }
    $result = New-Object PSObject -Property @{
        Path = $OutPath
        Count = $Entries.Count
        Bytes = [long]([System.IO.FileInfo]::new($OutPath)).Length
        Sha256 = (Get-Sha256HexFromFile -Path $OutPath)
        Hashes = $hashes
    }
    return $result
}

# 从资源包里读一个条目的字节（读完整文件，简单可靠；85MB 内存占用可接受）
function Get-ZfbEntryBytesFromFile {
    param(
        [string]$Path,
        $Entries,
        [string]$EntryName
    )
    $target = $null
    foreach ($e in $Entries) {
        if ($e.Name -ceq $EntryName) { $target = $e; break }
    }
    if ($null -eq $target) {
        throw ('资源包里找不到条目：' + $EntryName)
    }
    $all = [System.IO.File]::ReadAllBytes($Path)
    $len = [int]$target.Length
    $result = [byte[]]::new($len)
    if ($len -gt 0) {
        [System.Array]::Copy($all, [long]$target.Offset, $result, [long]0, [long]$len)
    }
    return , $result
}

# ===========================================================================
# 三、读取函数库（.srh / .srhs）并抽取 defaultcode 片段
# ===========================================================================

function Read-ZipEntryBytes {
    param(
        [string]$ZipPath,
        [string]$PreferredName
    )
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
    $zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $entry = $null
        foreach ($e in $zip.Entries) {
            if ($e.FullName -ieq $PreferredName) { $entry = $e; break }
        }
        if ($null -eq $entry -and $zip.Entries.Count -eq 1) {
            $entry = $zip.Entries[0]
        }
        if ($null -eq $entry) {
            $names = @()
            foreach ($e in $zip.Entries) { $names += $e.FullName }
            throw ('.srhs 内找不到 ' + $PreferredName + ' 条目（实际条目: ' + (($names | Select-Object -First 20) -join ', ') + '）')
        }
        $ms = New-Object System.IO.MemoryStream
        try {
            $s = $entry.Open()
            try {
                $s.CopyTo($ms)
            } finally {
                $s.Dispose()
            }
            return , ([byte[]]$ms.ToArray())
        } finally {
            $ms.Dispose()
        }
    } finally {
        $zip.Dispose()
    }
}

# 读函数库文件，返回 .srh 文本（.srhs 会先取出 abilixProject.srh）
function Read-LibrarySrhText {
    param([string]$Path)
    if (-not [System.IO.File]::Exists($Path)) {
        throw ('函数库文件不存在：' + $Path)
    }
    $ext = [System.IO.Path]::GetExtension($Path).ToLowerInvariant()
    $bytes = $null
    if ($ext -eq '.srhs') {
        $bytes = Read-ZipEntryBytes -ZipPath $Path -PreferredName $script:ZFB_MAGIC_ENTRY
    } elseif ($ext -eq '.srh') {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
    } else {
        # 其它扩展名：先尝试当 zip 打开，失败则当纯文本
        $isZip = $false
        try {
            Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
            $zipProbe = [System.IO.Compression.ZipFile]::OpenRead($Path)
            $isZip = $true
            $zipProbe.Dispose()
        } catch {
            $isZip = $false
        }
        if ($isZip) {
            $bytes = Read-ZipEntryBytes -ZipPath $Path -PreferredName $script:ZFB_MAGIC_ENTRY
        } else {
            $bytes = [System.IO.File]::ReadAllBytes($Path)
        }
    }
    return (ConvertFrom-Utf8Strict -Bytes $bytes)
}

# 从 .srh 文本里截取 ProjectString 段的项目 XML（与 C# / Python 版一致：取第一对标记，中间 Trim）
function Get-ProjectXmlFromSrhText {
    param([string]$Text)
    $text = $Text
    while ($text.Length -gt 0 -and [int]$text[0] -eq 0xFEFF) {
        $text = $text.Substring(1)
    }
    $infoStart = $text.IndexOf($script:INFO_START, [System.StringComparison]::Ordinal)
    $infoEnd = $text.IndexOf($script:INFO_END, [System.StringComparison]::Ordinal)
    if ($infoStart -lt 0 -or $infoEnd -lt 0 -or $infoEnd -le $infoStart) {
        throw ('不是合法的 .srh 内容：找不到 Info 段标记 ' + $script:INFO_START + ' / ' + $script:INFO_END)
    }
    $projStart = $text.IndexOf($script:PROJ_START, [System.StringComparison]::Ordinal)
    $projEnd = $text.IndexOf($script:PROJ_END, [System.StringComparison]::Ordinal)
    if ($projStart -lt 0 -or $projEnd -lt 0 -or $projEnd -le $projStart) {
        throw ('不是合法的 .srh 内容：找不到 ProjectString 段标记 ' + $script:PROJ_START + ' / ' + $script:PROJ_END)
    }
    $innerStart = $projStart + $script:PROJ_START.Length
    $projectXml = $text.Substring($innerStart, $projEnd - $innerStart).Trim()
    if ([string]::IsNullOrEmpty($projectXml)) {
        throw 'ProjectString 段内容为空'
    }
    try {
        $doc = [xml]$projectXml
    } catch {
        throw ('ProjectString 段不是合法 XML：' + $_.Exception.Message)
    }
    if ($doc.DocumentElement.LocalName -ne 'xml') {
        throw ('ProjectString 段的根节点应为 <xml>，实际为 <' + $doc.DocumentElement.LocalName + '>')
    }
    return $projectXml
}

function ConvertFrom-XmlEscaped {
    param([string]$Text)
    $s = $Text
    $s = $s.Replace('&lt;', '<')
    $s = $s.Replace('&gt;', '>')
    $s = $s.Replace('&quot;', '"')
    $s = $s.Replace('&apos;', "'")
    $s = $s.Replace('&amp;', '&')
    return $s
}

# 从 start 位置开始找 <Tag ...> 元素的结束位置（兼容自闭合标签与同名嵌套）
function Find-XmlElementEnd {
    param(
        [string]$Text,
        [int]$Start,
        [string]$Tag
    )
    $regex = New-Object System.Text.RegularExpressions.Regex(
        '<(/)?([A-Za-z_][A-Za-z0-9_.\-]*)([^>]*?)(/?)>')
    $depth = 0
    $searchPos = $Start
    while ($searchPos -lt $Text.Length) {
        $m = $regex.Match($Text, $searchPos)
        if (-not $m.Success) {
            throw ('XML 元素 <' + $Tag + '> 未闭合 @' + $Start + '（片段: ' +
                $Text.Substring($Start, [Math]::Min(120, $Text.Length - $Start)) + '）')
        }
        $searchPos = $m.Index + $m.Length
        if (-not $m.Groups[2].Value.Equals($Tag, [System.StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        $isClose = ($m.Groups[1].Value -eq '/')
        $isSelfClosing = ($m.Groups[4].Value -eq '/')
        if ($isClose) {
            $depth = $depth - 1
            if ($depth -le 0) { return ($m.Index + $m.Length) }
        } elseif ($isSelfClosing) {
            if ($depth -eq 0) { return ($m.Index + $m.Length) }
        } else {
            $depth = $depth + 1
        }
    }
    throw ('XML 元素 <' + $Tag + '> 未闭合 @' + $Start)
}

# 把项目 XML 拆成：根开标签 / 顶层 block 列表（原文）/ <variables> 片段 / 根闭标签
# 说明：只保留 <variables> 与顶层 <block>，其它顶层片段（如 <comment>）与空白不进入片段，
#       这与 Python 版 srhs工具.split_top_level + extract_defaultcode 的行为一致。
function Split-BlocklyProjectXml {
    param([string]$ProjectXml)
    $text = $ProjectXml.Trim()
    if ($text.StartsWith('<?xml', [System.StringComparison]::Ordinal)) {
        $k = $text.IndexOf('?>', [System.StringComparison]::Ordinal)
        if ($k -ge 0) {
            $text = $text.Substring($k + 2).Trim()
        }
    }
    $rootRegex = New-Object System.Text.RegularExpressions.Regex('^<xml\b[^>]*>')
    $rootMatch = $rootRegex.Match($text)
    if (-not $rootMatch.Success) {
        throw ('项目 XML 根节点不是 <xml>：' + $text.Substring(0, [Math]::Min(120, $text.Length)))
    }
    $rootOpen = $rootMatch.Value
    $closeStart = $text.LastIndexOf('</xml>', [System.StringComparison]::Ordinal)
    if ($closeStart -lt $rootMatch.Length) {
        throw '项目 XML 缺少 </xml> 结束标记'
    }
    $rootClose = $text.Substring($closeStart)
    $inner = $text.Substring($rootMatch.Length, $closeStart - $rootMatch.Length)

    $tagRegex = New-Object System.Text.RegularExpressions.Regex('\G<([A-Za-z_][A-Za-z0-9_.\-]*)')
    $blockRegex = New-Object System.Text.RegularExpressions.Regex('<block\b[^>]*?\btype="([^"]*)"')
    $nameRegex = New-Object System.Text.RegularExpressions.Regex('<field\s+name="NAME">([^<]*)</field>')
    $blocks = New-Object 'System.Collections.Generic.List[object]'
    $variablesRaw = $null
    $variablesSeen = $false
    $i = 0
    $n = $inner.Length
    while ($i -lt $n) {
        $lt = $inner.IndexOf('<', $i)
        if ($lt -lt 0) { break }
        $tm = $tagRegex.Match($inner, $lt)
        if (-not $tm.Success) {
            throw ('项目 XML 顶层片段解析失败 @' + $lt + ': ' +
                $inner.Substring($lt, [Math]::Min(80, $inner.Length - $lt)))
        }
        $tag = $tm.Groups[1].Value
        $end = Find-XmlElementEnd -Text $inner -Start $lt -Tag $tag
        $raw = $inner.Substring($lt, $end - $lt)
        if ($tag -eq 'variables') {
            if ($variablesSeen) {
                throw '项目 XML 出现多个 <variables> 根级片段'
            }
            $variablesSeen = $true
            $variablesRaw = $raw
        } elseif ($tag -eq 'block') {
            $type = ''
            $tm2 = $blockRegex.Match($raw)
            if ($tm2.Success) { $type = $tm2.Groups[1].Value }
            $name = ''
            $tm3 = $nameRegex.Match($raw)
            if ($tm3.Success) { $name = ConvertFrom-XmlEscaped -Text $tm3.Groups[1].Value }
            $blocks.Add((New-Object PSObject -Property @{
                Raw = $raw
                Type = $type
                Name = $name
            }))
        }
        $i = $end
    }
    return New-Object PSObject -Property @{
        RootOpen = $rootOpen
        RootClose = $rootClose
        Blocks = $blocks
        VariablesRaw = $variablesRaw
    }
}

# 生成 defaultcode 片段（单行 XML）：根开标签 + variables + 全部顶层 block + 根闭标签
function Build-DefaultcodeFragment {
    param([string]$ProjectXml)
    $split = Split-BlocklyProjectXml -ProjectXml $ProjectXml
    if ($split.Blocks.Count -le 0) {
        throw '函数库项目里没有任何顶层积木块，无法生成 defaultcode 片段'
    }
    $startCount = 0
    $defnoreturn = 0
    $defreturn = 0
    $seenDefNames = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
    foreach ($b in $split.Blocks) {
        if ([string]::IsNullOrEmpty($b.Type)) {
            throw ('存在没有 type 属性的顶层 block（片段: ' +
                $b.Raw.Substring(0, [Math]::Min(120, $b.Raw.Length)) + '）')
        }
        if ($b.Type -ceq 'start') { $startCount = $startCount + 1 }
        if ($b.Type -ceq 'procedures_defnoreturn') { $defnoreturn = $defnoreturn + 1 }
        if ($b.Type -ceq 'procedures_defreturn') { $defreturn = $defreturn + 1 }
        if ($b.Type -ceq 'procedures_defnoreturn' -or $b.Type -ceq 'procedures_defreturn') {
            if ([string]::IsNullOrEmpty($b.Name)) {
                throw '存在没有 NAME 字段的函数定义积木块'
            }
            if (-not $seenDefNames.Add($b.Name)) {
                throw ('同名函数定义出现多次：' + $b.Name + '（函数分类里会出现多个同名调用块）')
            }
        }
    }
    if ($startCount -ne 1) {
        throw ('函数库里必须恰好有 1 个 start 主函数积木块，实际找到 ' + $startCount + ' 个')
    }
    # 变量声明重复 id 检查（Blockly 加载会报错）
    $varIds = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
    if ($null -ne $split.VariablesRaw) {
        $varRegex = New-Object System.Text.RegularExpressions.Regex('<variable\b([^>]*)>([^<]*)</variable>')
        $idRegex = New-Object System.Text.RegularExpressions.Regex('\bid="([^"]*)"')
        foreach ($vm in $varRegex.Matches($split.VariablesRaw)) {
            $im = $idRegex.Match($vm.Groups[1].Value)
            if ($im.Success -and -not $varIds.Add($im.Groups[1].Value)) {
                throw ('变量 id 重复：' + $im.Groups[1].Value)
            }
        }
    }
    $parts = New-Object 'System.Collections.Generic.List[string]'
    $parts.Add($split.RootOpen)
    if ($null -ne $split.VariablesRaw) { $parts.Add($split.VariablesRaw) }
    foreach ($b in $split.Blocks) { $parts.Add($b.Raw) }
    $parts.Add($split.RootClose)
    $fragment = [System.String]::Concat($parts.ToArray())
    try {
        $doc = [xml]$fragment
    } catch {
        throw ('生成的 defaultcode 片段不是合法 XML：' + $_.Exception.Message)
    }
    if ($doc.DocumentElement.LocalName -ne 'xml') {
        throw ('生成的 defaultcode 片段根节点异常：<' + $doc.DocumentElement.LocalName + '>')
    }
    $varCount = 0
    if ($null -ne $split.VariablesRaw) {
        $varRegex = New-Object System.Text.RegularExpressions.Regex('<variable\b[^>]*>([^<]*)</variable>')
        $varCount = $varRegex.Matches($split.VariablesRaw).Count
    }
    return New-Object PSObject -Property @{
        Fragment = $fragment
        TopBlocks = $split.Blocks.Count
        StartBlocks = $startCount
        DefNoReturn = $defnoreturn
        DefReturn = $defreturn
        Variables = $varCount
        Chars = $fragment.Length
    }
}

# ===========================================================================
# 四、maingui_init.js：JS 字符串反转义 / 转义 / 替换 defaultcode
# 说明：规则完全照搬 Python 版 js_escape_js_string / js_unescape_js_string，
#       保证两边生成的 maingui_init.js 逐字节相同。
# ===========================================================================

function ConvertFrom-JsStringContent {
    param([string]$Literal)
    $sb = New-Object System.Text.StringBuilder
    $i = 0
    $n = $Literal.Length
    while ($i -lt $n) {
        $code = [int]$Literal[$i]
        if ($code -ne 92) {
            [void]$sb.Append($Literal[$i])
            $i = $i + 1
            continue
        }
        $i = $i + 1
        if ($i -ge $n) {
            [void]$sb.Append('\')
            break
        }
        $e = $Literal[$i]
        $ec = [int]$e
        if ($ec -eq 110) {
            [void]$sb.Append("`n"); $i = $i + 1
        } elseif ($ec -eq 114) {
            [void]$sb.Append("`r"); $i = $i + 1
        } elseif ($ec -eq 116) {
            [void]$sb.Append("`t"); $i = $i + 1
        } elseif ($ec -eq 39) {
            [void]$sb.Append("'"); $i = $i + 1
        } elseif ($ec -eq 34) {
            [void]$sb.Append('"'); $i = $i + 1
        } elseif ($ec -eq 92) {
            [void]$sb.Append('\'); $i = $i + 1
        } elseif ($ec -eq 47) {
            [void]$sb.Append('/'); $i = $i + 1
        } elseif ($ec -eq 98) {
            [void]$sb.Append([char]8); $i = $i + 1
        } elseif ($ec -eq 102) {
            [void]$sb.Append([char]12); $i = $i + 1
        } elseif ($ec -eq 117) {
            if (($i + 4) -lt $n) {
                $hex = $Literal.Substring($i + 1, 4)
                if ($hex -match '^[0-9a-fA-F]{4}$') {
                    [void]$sb.Append([char][Convert]::ToInt32($hex, 16))
                    $i = $i + 5
                } else {
                    [void]$sb.Append('\')
                    [void]$sb.Append('u')
                    $i = $i + 1
                }
            } else {
                [void]$sb.Append('\')
                [void]$sb.Append('u')
                $i = $i + 1
            }
        } elseif ($ec -eq 120) {
            if (($i + 2) -lt $n) {
                $hex = $Literal.Substring($i + 1, 2)
                if ($hex -match '^[0-9a-fA-F]{2}$') {
                    [void]$sb.Append([char][Convert]::ToInt32($hex, 16))
                    $i = $i + 3
                } else {
                    [void]$sb.Append('\')
                    [void]$sb.Append('x')
                    $i = $i + 1
                }
            } else {
                [void]$sb.Append('\')
                [void]$sb.Append('x')
                $i = $i + 1
            }
        } else {
            [void]$sb.Append('\')
            [void]$sb.Append($e)
            $i = $i + 1
        }
    }
    return $sb.ToString()
}

function ConvertTo-JsStringContent {
    param([string]$Content)
    $s = $Content
    $s = $s.Replace('\', '\\')
    $s = $s.Replace("'", "\'")
    $s = $s.Replace("`r", '\r')
    $s = $s.Replace("`n", '\n')
    $s = $s.Replace("`t", '\t')
    $s = $s.Replace([string][char]0x2028, '\u2028')
    $s = $s.Replace([string][char]0x2029, '\u2029')
    return $s
}

# 定位 `var <varName> = '...'`：返回引号位置、内容起止位置、原始内容、行号
function Find-JsVarString {
    param(
        [string]$Text,
        [string]$VarName
    )
    $pattern = '(?m)^[ \t]*var[ \t]+' + [regex]::Escape($VarName) + '[ \t]*=[ \t]*'
    $m = [regex]::Match($Text, $pattern)
    if (-not $m.Success) {
        throw ('maingui_init.js 里找不到 var ' + $VarName + ' = ''...'' 行')
    }
    $afterEq = $m.Index + $m.Length
    # Python 版按行解析：只在当前行内找引号
    $lineEnd = $Text.IndexOf("`n", $afterEq)
    if ($lineEnd -lt 0) { $lineEnd = $Text.Length }
    $quotePos = -1
    $q1 = $Text.IndexOf("'", $afterEq, [System.StringComparison]::Ordinal)
    if ($q1 -ge 0 -and $q1 -lt $lineEnd) {
        $quotePos = $q1
    } else {
        $q2 = $Text.IndexOf('"', $afterEq, [System.StringComparison]::Ordinal)
        if ($q2 -ge 0 -and $q2 -lt $lineEnd) { $quotePos = $q2 }
    }
    if ($quotePos -lt 0) {
        throw ('找到 var ' + $VarName + ' 但后面没有字符串字面量')
    }
    $quote = $Text[$quotePos]
    $i = $quotePos + 1
    $contentEnd = -1
    $n = $Text.Length
    while ($i -lt $n) {
        $c = $Text[$i]
        if ([int]$c -eq 92) {
            $i = $i + 2
            continue
        }
        if ($c -eq $quote) {
            $contentEnd = $i
            break
        }
        $i = $i + 1
    }
    if ($contentEnd -lt 0) {
        throw ('JS 字符串字面量未闭合（从位置 ' + $quotePos + ' 开始）')
    }
    # 行号（仅用于报告）
    $lineNo = 1
    for ($k = 0; $k -lt $quotePos; $k++) {
        if ([int]$Text[$k] -eq 10) { $lineNo = $lineNo + 1 }
    }
    return New-Object PSObject -Property @{
        VarName = $VarName
        Line = $lineNo
        QuotePos = $quotePos
        ContentStart = $quotePos + 1
        ContentEnd = $contentEnd
        RawContent = $Text.Substring($quotePos + 1, $contentEnd - $quotePos - 1)
    }
}

# 修改 maingui_init.js 字节：把 zh-hans 的 defaultcode 内容换成片段；保留原 BOM 状态。
function Update-MainguiInitBytes {
    param(
        [byte[]]$OldBytes,
        [string]$Fragment
    )
    $bomLen = Get-BomLength -Bytes $OldBytes
    $oldText = ConvertFrom-Utf8Strict -Bytes $OldBytes
    $loc = Find-JsVarString -Text $oldText -VarName 'defaultcode'
    $oldDecoded = ConvertFrom-JsStringContent -Literal $loc.RawContent
    $newLiteral = ConvertTo-JsStringContent -Content $Fragment
    $newText = $oldText.Substring(0, $loc.QuotePos + 1) + $newLiteral + $oldText.Substring($loc.ContentEnd)
    # defaultcodeTr / defaultcodeEn 必须保持原样
    foreach ($otherVar in @('defaultcodeTr', 'defaultcodeEn')) {
        $oldLoc = $null
        $newLoc = $null
        try {
            $oldLoc = Find-JsVarString -Text $oldText -VarName $otherVar
        } catch {
            $oldLoc = $null
        }
        if ($null -ne $oldLoc) {
            $newLoc = Find-JsVarString -Text $newText -VarName $otherVar
            if (-not $newLoc.RawContent.Equals($oldLoc.RawContent, [System.StringComparison]::Ordinal)) {
                throw ('修改 defaultcode 时意外改动了 ' + $otherVar + '（本脚本只应改简体中文 defaultcode）')
            }
        }
    }
    $withBom = ($bomLen -gt 0)
    $newBytes = ConvertTo-Utf8Bytes -Text $newText -WithBom:$withBom
    # 回读校验：新文本里 defaultcode 反转义后必须等于片段
    $checkLoc = Find-JsVarString -Text $newText -VarName 'defaultcode'
    $checkDecoded = ConvertFrom-JsStringContent -Literal $checkLoc.RawContent
    if (-not $checkDecoded.Equals($Fragment, [System.StringComparison]::Ordinal)) {
        throw ('替换后回读 defaultcode 与函数库片段不一致（' + $checkDecoded.Length + ' vs ' +
            $Fragment.Length + ' 字符）')
    }
    return New-Object PSObject -Property @{
        OldBytes = $OldBytes
        NewBytes = $newBytes
        OldBomLen = $bomLen
        OldTextChars = $oldText.Length
        OldContentChars = $oldDecoded.Length
        NewContentChars = $Fragment.Length
        NewLiteralChars = $newLiteral.Length
        HasBom = $withBom
        Line = $loc.Line
        Sha256 = (Get-Sha256HexFromBytes -Bytes $newBytes)
    }
}

# 从字节里读回 defaultcode 并反转义（自检3用）
function Get-DefaultcodeContentFromInitBytes {
    param([byte[]]$Bytes)
    $text = ConvertFrom-Utf8Strict -Bytes $Bytes
    $loc = Find-JsVarString -Text $text -VarName 'defaultcode'
    return (ConvertFrom-JsStringContent -Literal $loc.RawContent)
}

# ===========================================================================
# 五、安装 / 备份
# ===========================================================================

function Backup-AssetsFile {
    param([string]$AssetsPath)
    $targetDir = [System.IO.Path]::GetDirectoryName($AssetsPath)
    $stamp = (Get-Date).ToString('yyyyMMdd-HHmmss')
    $backup = Join-Path $targetDir ($script:BACKUP_PREFIX + $stamp)
    $n = 1
    while ([System.IO.File]::Exists($backup)) {
        $backup = Join-Path $targetDir ($script:BACKUP_PREFIX + $stamp + '_' + $n)
        $n = $n + 1
    }
    $origHash = Get-Sha256HexFromFile -Path $AssetsPath
    [System.IO.File]::Copy($AssetsPath, $backup, $false)
    $backupHash = Get-Sha256HexFromFile -Path $backup
    if ($origHash -cne $backupHash) {
        throw ('备份文件校验不一致（未做任何修改）：' + $backup)
    }
    return New-Object PSObject -Property @{
        BackupPath = $backup
        Sha256 = $origHash
    }
}

function Install-PatchedAssets {
    param(
        [string]$PatchedPath,
        [string]$AssetsPath
    )
    $targetDir = [System.IO.Path]::GetDirectoryName($AssetsPath)
    $isAdmin = Test-IsAdministrator
    if (-not $isAdmin) {
        if (-not (Test-DirectoryWritable -Directory $targetDir)) {
            throw ('没有写入权限：' + $targetDir + "`r`n" +
                '  请用「一键同步(管理员).cmd」运行（会自动请求管理员权限），' +
                '或右键该 .cmd → 以管理员身份运行。')
        }
        Write-Warning ('当前不是管理员，但目标目录可写（便携版/副本），继续写入：' + $targetDir)
    }
    $patchedHash = Get-Sha256HexFromFile -Path $PatchedPath
    $backup = Backup-AssetsFile -AssetsPath $AssetsPath
    try {
        [System.IO.File]::Copy($PatchedPath, $AssetsPath, $true)
    } catch {
        throw ('写入 browser_assets 失败（IDE 是否正在运行？请先关闭软件再同步）。原文件备份：' +
            $backup.BackupPath + "`r`n  错误：" + $_.Exception.Message)
    }
    $finalHash = Get-Sha256HexFromFile -Path $AssetsPath
    if ($finalHash -cne $patchedHash) {
        throw ('写入后的 browser_assets 与补丁包 sha256 不一致！' +
            '请立刻用「还原新建模板.ps1」恢复（原文件备份：' + $backup.BackupPath + '）')
    }
    return New-Object PSObject -Property @{
        Ok = $true
        BackupPath = $backup.BackupPath
        BackupSha256 = $backup.Sha256
        FinalSha256 = $finalHash
        IsAdmin = $isAdmin
    }
}

# ===========================================================================
# 六、资源包 / 函数库路径探测
# ===========================================================================

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
        # 兜底：Program Files 下任何 AbilixScratch3* 目录（容错未来改名）
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

function Find-LibraryFile {
    # 脚本在 <WER_函数库>\工具\仅PowerShell\ → 往回两级是 <WER_函数库>
    $libRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $candidates = @(
        (Join-Path $libRoot '我的函数库.srhs'),
        (Join-Path $libRoot '我的函数库.srh'),
        (Join-Path $libRoot 'WER函数库.srhs'),
        (Join-Path $libRoot 'WER函数库.srh'),
        (Join-Path $libRoot '示例\WER函数库.srhs'),
        (Join-Path $libRoot '示例\WER函数库.srh')
    )
    foreach ($c in $candidates) {
        if ([System.IO.File]::Exists($c)) { return $c }
    }
    return $null
}

# ===========================================================================
# 七、主流程
# ===========================================================================

function Invoke-SyncMain {
    Write-Banner 'AbilixScratch3.0 新建项目默认模板 —— 同步「我的函数库」（仅 PowerShell 版）'
    Write-Detail ('本机 PowerShell 版本：' + $PSVersionTable.PSVersion.ToString())

    # ---------- 1) 定位 + 校验原资源包 ----------
    Write-Step '1/7 定位并校验 browser_assets'
    $assetsPath = $Assets
    if ([string]::IsNullOrEmpty($assetsPath)) {
        $found = Find-BrowserAssets
        if ($null -eq $found) {
            throw ('自动探测不到 AbilixScratch3.0 的 browser_assets。' + "`r`n" +
                '  可以用 -Assets 参数手动指定，例如：' + "`r`n" +
                '  -Assets "D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets"')
        }
        $assetsPath = $found
        Write-Detail ('自动探测到：' + $assetsPath)
    } else {
        if (-not [System.IO.File]::Exists($assetsPath)) {
            throw ('-Assets 指定的文件不存在：' + $assetsPath)
        }
        $assetsPath = (Resolve-Path -LiteralPath $assetsPath).Path
    }
    $index = Read-ZfbIndex -Path $assetsPath
    $layout = Assert-ZfbLayout -Info $index
    if (-not $layout.Ok) {
        throw ('原资源包格式校验失败：' + "`r`n  - " + (($layout.Errors) -join "`r`n  - "))
    }
    $origHash = Get-Sha256HexFromFile -Path $assetsPath
    Write-Detail ('原资源包：' + $assetsPath)
    Write-Detail ('条目数=' + $index.Count + '  文件大小=' + (Format-ByteSize -Bytes $index.FileSize) +
        '  索引结束=' + $index.IndexEnd)
    Write-Detail ('原包 sha256=' + $origHash)
    foreach ($w in $layout.Warnings) { Write-Warning $w }

    # ---------- 2) 纯 roundtrip 自检 ----------
    Write-Step '2/7 纯 roundtrip 自检（解包→原样重打包→逐字节比较）'
    $workRoot = $WorkDir
    $createdTemp = $false
    if ([string]::IsNullOrEmpty($workRoot)) {
        $workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('zfb_patch_ps_' + [System.Guid]::NewGuid().ToString('N').Substring(0, 8))
        $createdTemp = $true
    }
    if (-not [System.IO.Directory]::Exists($workRoot)) {
        [void][System.IO.Directory]::CreateDirectory($workRoot)
    }
    $workRoot = (Resolve-Path -LiteralPath $workRoot).Path
    # 记录自动创建的临时目录，供出错时（顶层 catch）清理
    $script:CleanupWorkRoot = $workRoot
    $script:CleanupTempCreated = $createdTemp
    $rtPath = Join-Path $workRoot 'browser_assets.repack_only'
    $rtHashes = New-Object System.Collections.Hashtable
    $rt = Write-ZfbPackage -SourcePath $assetsPath -Entries $index.Entries -OutPath $rtPath -HashOut $rtHashes
    $identical = ($rt.Sha256 -ceq $origHash)
    if (-not $identical) {
        $msg = '纯 roundtrip 后字节不一致！说明 zfbRes_v1 打包布局与原文件有差异，不能安全改包（' +
            '原包 ' + $origHash + ' / 重打包 ' + $rt.Sha256 + '）。'
        if (-not $SkipIdenticalCheck) {
            throw ($msg + ' 可加 -SkipIdenticalCheck 强制继续（不建议）。')
        }
        Write-Warning ($msg + ' 已按要求强制跳过。')
    } else {
        Write-Detail ('逐字节一致 OK（' + $rt.Sha256 + '）')
    }

    # ---------- 3) 读取函数库 → 片段 ----------
    Write-Step '3/7 读取函数库并生成 defaultcode 片段'
    $libraryPath = $Library
    if ([string]::IsNullOrEmpty($libraryPath)) {
        $libraryPath = Find-LibraryFile
        if ($null -eq $libraryPath) {
            throw ('找不到函数库文件。请先用 IDE 把函数库保存为 <WER_函数库>\我的函数库.srhs，' +
                '或用 -Library 参数指定 .srh/.srhs 路径。')
        }
        Write-Detail ('默认函数库：' + $libraryPath)
    } else {
        if (-not [System.IO.File]::Exists($libraryPath)) {
            throw ('-Library 指定的文件不存在：' + $libraryPath)
        }
        $libraryPath = (Resolve-Path -LiteralPath $libraryPath).Path
    }
    $libText = Read-LibrarySrhText -Path $libraryPath
    $projectXml = Get-ProjectXmlFromSrhText -Text $libText
    $fragInfo = Build-DefaultcodeFragment -ProjectXml $projectXml
    $fragment = $fragInfo.Fragment
    Write-Detail ('来源：' + $libraryPath)
    Write-Detail ('顶层积木块=' + $fragInfo.TopBlocks + '（start=' + $fragInfo.StartBlocks +
        '，无返回函数=' + $fragInfo.DefNoReturn + '，有返回函数=' + $fragInfo.DefReturn +
        '）变量=' + $fragInfo.Variables + '  片段=' + $fragInfo.Chars + ' 字符')

    # ---------- 4) 修改 maingui_init.js ----------
    Write-Step '4/7 修改 Blockly_Code/maingui_init.js（只改简体中文 defaultcode）'
    $initBytes = Get-ZfbEntryBytesFromFile -Path $assetsPath -Entries $index.Entries -EntryName $script:INIT_ENTRY_NAME
    $initOldHash = Get-Sha256HexFromBytes -Bytes $initBytes
    Write-Detail ('原 defaultcode 条目：' + $initBytes.Length + ' 字节  sha256=' + $initOldHash +
        '  BOM=' + ((Get-BomLength -Bytes $initBytes) -gt 0))
    $initPatched = Update-MainguiInitBytes -OldBytes $initBytes -Fragment $fragment
    Write-Detail ('修改后：' + $initPatched.NewBytes.Length + ' 字节  sha256=' + $initPatched.Sha256 +
        '  （' + $initPatched.OldContentChars + ' -> ' + $initPatched.NewContentChars + ' 字符）')

    # ---------- 5) 重新打包 ----------
    Write-Step '5/7 重新打包 browser_assets'
    if ($Install -and [string]::IsNullOrEmpty($Out)) {
        $patchedPath = Join-Path $workRoot 'browser_assets.patched'
        $outPath = ''
    } else {
        if ([string]::IsNullOrEmpty($Out)) {
            $outPath = Join-Path $PSScriptRoot 'browser_assets.patched'
        } else {
            $outPath = $Out
            if (-not [System.IO.Path]::IsPathRooted($outPath)) {
                $outPath = Join-Path (Get-Location).Path $outPath
            }
        }
        $outDir = [System.IO.Path]::GetDirectoryName($outPath)
        if (-not [string]::IsNullOrEmpty($outDir) -and -not [System.IO.Directory]::Exists($outDir)) {
            [void][System.IO.Directory]::CreateDirectory($outDir)
        }
        $patchedPath = $outPath
    }
    $replacement = @{}
    $replacement[$script:INIT_ENTRY_NAME] = $initPatched.NewBytes
    $patchedHashes = New-Object System.Collections.Hashtable
    $patched = Write-ZfbPackage -SourcePath $assetsPath -Entries $index.Entries -OutPath $patchedPath -Replacement $replacement -HashOut $patchedHashes
    Write-Detail ('补丁包：' + $patched.Path)
    Write-Detail ('大小=' + (Format-ByteSize -Bytes $patched.Bytes) + '  sha256=' + $patched.Sha256)

    # ---------- 6) 打包后自检 ----------
    Write-Step '6/7 打包后自检（逐条目 sha256 + 布局 + 读回 defaultcode）'
    $newIndex = Read-ZfbIndex -Path $patchedPath
    $newLayout = Assert-ZfbLayout -Info $newIndex
    if (-not $newLayout.Ok) {
        throw ('补丁包布局自检失败：' + "`r`n  - " + (($newLayout.Errors) -join "`r`n  - "))
    }
    if ($newIndex.Count -ne $index.Count) {
        throw ('补丁包条目数不一致：原 ' + $index.Count + ' / 新 ' + $newIndex.Count)
    }
    $changedCount = 0
    for ($i = 0; $i -lt $index.Entries.Count; $i++) {
        $oldEntry = $index.Entries[$i]
        $newEntry = $newIndex.Entries[$i]
        if (-not $oldEntry.Name.Equals($newEntry.Name, [System.StringComparison]::Ordinal)) {
            throw ('补丁包条目顺序/名称与原包不一致（第 ' + $i + ' 条：' + $oldEntry.Name + ' vs ' +
                $newEntry.Name + '）')
        }
        $oldH = [string]$rtHashes[$oldEntry.Name]
        $newH = [string]$patchedHashes[$newEntry.Name]
        if ($oldEntry.Name -ceq $script:INIT_ENTRY_NAME) {
            if ($oldH -ceq $newH) {
                throw ('期望被修改的条目 ' + $oldEntry.Name + ' 实际没有变化')
            }
            if ($newH -cne $initPatched.Sha256) {
                throw ('maingui_init.js 的 sha256 与修改结果不一致')
            }
            $changedCount = $changedCount + 1
        } else {
            if ($oldH -cne $newH) {
                throw ('不允许被修改的条目发生了变化：' + $oldEntry.Name + '（原 ' + $oldH +
                    ' / 新 ' + $newH + '）')
            }
        }
    }
    Write-Detail ('其它 ' + ($index.Count - $changedCount) + ' 个条目 sha256 全部一致 OK；变化条目 ' +
        $changedCount + ' 个（' + $script:INIT_ENTRY_NAME + ' ' + $initBytes.Length + ' -> ' +
        $initPatched.NewBytes.Length + ' 字节）')
    # 自检3：从补丁包里重新读出 defaultcode，反转义后必须与片段一致
    $patchedInitBytes = Get-ZfbEntryBytesFromFile -Path $patchedPath -Entries $newIndex.Entries -EntryName $script:INIT_ENTRY_NAME
    $readBack = Get-DefaultcodeContentFromInitBytes -Bytes $patchedInitBytes
    if (-not $readBack.Equals($fragment, [System.StringComparison]::Ordinal)) {
        throw ('从补丁包读回的 defaultcode 与函数库片段不一致（' + $readBack.Length + ' vs ' +
            $fragment.Length + ' 字符）')
    }
    Write-Detail ('读回 defaultcode 反转义后与片段一致 OK（' + $readBack.Length + ' 字符）')

    # ---------- 7) 输出 / 安装 ----------
    $installInfo = $null
    if ($Install) {
        Write-Step '7/7 安装到 browser_assets（会先自动备份原文件）'
        $installInfo = Install-PatchedAssets -PatchedPath $patchedPath -AssetsPath $assetsPath
        Write-Detail ('原文件备份：' + $installInfo.BackupPath)
        Write-Detail ('备份 sha256=' + $installInfo.BackupSha256)
        Write-Detail ('写入后 sha256=' + $installInfo.FinalSha256)
    } elseif ([string]::IsNullOrEmpty($outPath)) {
        Write-Step '7/7 生成补丁包（未安装）'
    } else {
        Write-Step '7/7 复制补丁包到输出路径（未安装）'
    }

    # ---------- 汇总 ----------
    Write-Host ''
    Write-Host ('=' * 74)
    Write-Host '  同步结果'
    Write-Host ('-' * 74)
    Write-Host ('  原资源包    : ' + $assetsPath)
    Write-Host ('  原包 sha256 : ' + $origHash)
    Write-Host ('  函数库来源  : ' + $libraryPath)
    Write-Host ('  defaultcode : 顶层块=' + $fragInfo.TopBlocks + '（start=' + $fragInfo.StartBlocks +
        '）函数=' + $fragInfo.DefNoReturn + ' 变量=' + $fragInfo.Variables + ' 字符=' + $fragInfo.Chars)
    Write-Host ('  纯 roundtrip: ' + $(if ($identical) { '逐字节一致 OK' } else { '不一致（已强制跳过）' }))
    Write-Host ('  打包后自检  : 通过 OK（条目 ' + $index.Count + '，变化 ' + $changedCount + ' 个）')
    Write-Host ('  补丁包      : ' + $patchedPath)
    Write-Host ('  补丁包sha256: ' + $patched.Sha256)
    if ($Install) {
        Write-Host ('  原文件备份  : ' + $installInfo.BackupPath)
        Write-Host '  状态        : OK 已写入安装目录（重启 IDE 后「新建项目」即自带函数库）'
        Write-Host '  还原方法    : 双击「一键还原(管理员).cmd」或运行 还原新建模板.ps1'
    } else {
        Write-Host '  状态        : 补丁包已生成，尚未安装（加 -Install 由管理员安装，或双击 一键同步(管理员).cmd）'
    }
    foreach ($w in $layout.Warnings) { Write-Host ('  [警告] ' + $w) }
    foreach ($w in $newLayout.Warnings) { Write-Host ('  [警告] ' + $w) }
    Write-Host ('=' * 74)

    if ($createdTemp) {
        if ($KeepWork) {
            Write-Host ('临时工作目录已保留：' + $workRoot)
        } else {
            try {
                Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
            } catch { }
        }
    }
    return 0
}

# 只有被直接运行（而不是被 dot-source 做单元测试）时才执行主流程
if ($MyInvocation.InvocationName -ne '.') {
    $exitCode = 0
    try {
        $exitCode = Invoke-SyncMain
    } catch {
        Write-Host ''
        Write-Host ('[错误] ' + $_.Exception.Message) -ForegroundColor Red
        if ($Verbose -and -not [string]::IsNullOrEmpty($_.ScriptStackTrace)) {
            Write-Host ('  位置：' + $_.ScriptStackTrace) -ForegroundColor DarkGray
        }
        $exitCode = 1
    } finally {
        # 出错时也要清理自动创建的临时目录（用户显式 -WorkDir / -KeepWork 的保留）
        if ($script:CleanupTempCreated -and -not $KeepWork -and -not [string]::IsNullOrEmpty($script:CleanupWorkRoot)) {
            try {
                Remove-Item -LiteralPath $script:CleanupWorkRoot -Recurse -Force -ErrorAction SilentlyContinue
            } catch { }
        }
    }
    exit $exitCode
}
