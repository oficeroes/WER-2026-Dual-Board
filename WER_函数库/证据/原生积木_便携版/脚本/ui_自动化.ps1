# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    AbilixScratch3.0 便携版 —— 真实 IDE 端到端 UI 自动化（原生函数积木方案）

.DESCRIPTION
    本脚本用 Win32 user32 P/Invoke 做真实鼠标/键盘与截图，用于验证便携副本启动后：
      * 左侧出现「我的函数」紫色分类；
      * 从 flyout 拖拽原生函数块到工作区；
      * 右侧 Python 代码面板生成 def func_Hello() 与 func_Hello() 调用。

    之所以用外部脚本而不是 IDE 内自动化：IDE 是 Unity + 内嵌 CEF 浏览器，没有测试接口，
    只能走真实输入事件。

    注意：本机屏幕高 DPI（2880x1800 @200%）。脚本启动时先 SetProcessDPIAware()，
    之后所有坐标/截图都是**物理像素**，与 GetWindowRect 一致，不会出现 2 倍偏移。

.PARAMETER Action
    info      打印屏幕/窗口信息（不启动）
    launch    启动便携版 IDE 并等待主窗口，打印窗口 rect，整屏截图
    shot      保存整屏截图（-Out 指定路径）
    crop      按窗口 rect 裁剪截图（-Out）
    click     在物理坐标 (-X -Y) 单击
    dclick    双击
    drag      从 (-X1 -Y1) 拖到 (-X2 -Y2)（分步移动，适合 Blockly 拖块）
    key       发送按键（-Key，如 "ctrl+shift+p"）——保留备用
    act       激活窗口（置前）
    rect      打印窗口 rect
    close     关闭 IDE 窗口并等待退出（超时则 Kill）
    waitwin   只等待主窗口出现并打印 rect
    proc      打印便携版 IDE 进程列表（PID/窗口标题）

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File ui_自动化.ps1 -Action launch
    powershell -NoProfile -ExecutionPolicy Bypass -File ui_自动化.ps1 -Action click -X 300 -Y 400
    powershell -NoProfile -ExecutionPolicy Bypass -File ui_自动化.ps1 -Action drag -X1 300 -Y1 400 -X2 800 -Y2 500
    powershell -NoProfile -ExecutionPolicy Bypass -File ui_自动化.ps1 -Action close
#>

param(
    [ValidateSet('info', 'launch', 'shot', 'crop', 'click', 'dclick', 'drag', 'ritedrag',
                 'key', 'act', 'rect', 'close', 'waitwin', 'proc')]
    [string]$Action = 'info',

    [string]$AppDir = 'C:\Users\s1325\AbilixScratch3.0_FuncLib',
    [string]$ExeName = 'AbilixScratch3.0.exe',
    [string]$ProcessName = 'AbilixScratch3.0',

    [string]$Out = '',
    [int]$X = 0, [int]$Y = 0,
    [int]$X1 = 0, [int]$Y1 = 0,
    [int]$X2 = 0, [int]$Y2 = 0,
    [string]$Key = '',
    [int]$Steps = 30,
    [int]$StepDelayMs = 25,
    [int]$WaitSeconds = 40,
    [int]$WindowWidth = 0,
    [int]$WindowHeight = 0,
    [switch]$FastDrag
)

$ErrorActionPreference = 'Stop'
$script:Exists = $false

# ---------------------------------------------------------------------------
# Win32 / GDI 声明
# ---------------------------------------------------------------------------
if (-not $script:Exists) {
    Add-Type -AssemblyName System.Drawing
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class W32 {
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int cmd);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hWnd, ref POINT pt);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wp, IntPtr lp);
    [DllImport("user32.dll")] public static extern int GetSystemMetrics(int index);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr hWnd, StringBuilder text, int max);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@
    $script:Exists = $true
}

[void][W32]::SetProcessDPIAware()

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
$script:ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:EvDir = $script:ScriptDir

function Get-ScreenRect {
    $w = [W32]::GetSystemMetrics(0)
    $h = [W32]::GetSystemMetrics(1)
    return [pscustomobject]@{ Width = $w; Height = $h }
}

function Get-AppProcess {
    # 按进程可执行文件路径前缀匹配（笔记本上可能开着安装版，必须区分）
    $prefix = $AppDir.TrimEnd('\')
    Get-Process -Name $ProcessName -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase) } |
        Sort-Object StartTime
}

function Get-AppWindow {
    param([System.Diagnostics.Process]$Proc)
    $targetPid = $Proc.Id
    $best = [IntPtr]::Zero
    $bestArea = 0
    # 枚举该进程所有可见顶层窗口，取面积最大的（Unity 主窗口）
    # 用 .NET 的 MainWindowHandle 获取窗口句柄（无需 EnumWindows）
    # 直接遍历进程 MainWindowHandle + EnumWindows 太麻烦，这里用 .NET 提供的句柄为主
    foreach ($h in @($Proc.MainWindowHandle)) {
        if ($h -ne [IntPtr]::Zero -and [W32]::IsWindowVisible($h)) {
            $r = New-Object W32+RECT
            if ([W32]::GetWindowRect($h, [ref]$r)) {
                $area = ($r.Right - $r.Left) * ($r.Bottom - $r.Top)
                if ($area -gt $bestArea) { $bestArea = $area; $best = $h }
            }
        }
    }
    return $best
}

function Get-WindowRectInfo {
    param([IntPtr]$Hwnd)
    $r = New-Object W32+RECT
    if (-not [W32]::GetWindowRect($Hwnd, [ref]$r)) {
        throw "GetWindowRect 失败：$Hwnd"
    }
    $c = New-Object W32+RECT
    [void][W32]::GetClientRect($Hwnd, [ref]$c)
    $pt = New-Object W32+POINT
    $pt.X = 0; $pt.Y = 0
    [void][W32]::ClientToScreen($Hwnd, [ref]$pt)
    return [pscustomobject]@{
        hwnd         = $Hwnd.ToInt64()
        left         = $r.Left
        top          = $r.Top
        right        = $r.Right
        bottom       = $r.Bottom
        width        = $r.Right - $r.Left
        height       = $r.Bottom - $r.Top
        client_left  = $pt.X
        client_top   = $pt.Y
        client_width = $c.Right - $c.Left
        client_height = $c.Bottom - $c.Top
    }
}

function Move-Mouse {
    param([int]$px, [int]$py)
    [void][W32]::SetCursorPos($px, $py)
}

function Click-Mouse {
    param([int]$px, [int]$py, [int]$delayMs = 120)
    Move-Mouse $px $py
    Start-Sleep -Milliseconds 80
    [W32]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)   # LEFTDOWN
    Start-Sleep -Milliseconds $delayMs
    [W32]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)   # LEFTUP
    Start-Sleep -Milliseconds 120
    $p = New-Object W32+POINT
    [void][W32]::GetCursorPos([ref]$p)
    return $p
}

function Drag-Mouse {
    param([int]$fromX, [int]$fromY, [int]$toX, [int]$toY,
          [int]$steps = 30, [int]$delayMs = 25, [switch]$rightButton)
    Move-Mouse $fromX $fromY
    Start-Sleep -Milliseconds 250
    $down = 0x0002; $up = 0x0004
    if ($rightButton) { $down = 0x0008; $up = 0x0010 }
    [W32]::mouse_event($down, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 200
    for ($i = 1; $i -le $steps; $i++) {
        $t = $i / [double]$steps
        $px = [int]($fromX + ($toX - $fromX) * $t)
        $py = [int]($fromY + ($toY - $fromY) * $t)
        Move-Mouse $px $py
        Start-Sleep -Milliseconds $delayMs
    }
    Start-Sleep -Milliseconds 300
    [W32]::mouse_event($up, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 300
}

function Save-Screen {
    param([string]$path)
    $dir = Split-Path -Parent $path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $scr = Get-ScreenRect
    $bmp = New-Object System.Drawing.Bitmap($scr.Width, $scr.Height)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen(0, 0, 0, 0, $bmp.Size)
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    return $path
}

function Crop-Screen {
    param([string]$path, [int]$left, [int]$top, [int]$width, [int]$height)
    $dir = Split-Path -Parent $path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $bmp = New-Object System.Drawing.Bitmap($width, $height)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($left, $top, 0, 0, (New-Object System.Drawing.Size($width, $height)))
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    return $path
}

function Activate-AppWindow {
    param([IntPtr]$Hwnd)
    if ([W32]::IsIconic($Hwnd)) { [void][W32]::ShowWindow($Hwnd, 9) }  # SW_RESTORE
    [void][W32]::SetForegroundWindow($Hwnd)
    Start-Sleep -Milliseconds 400
}

function Wait-AppWindow {
    param([System.Diagnostics.Process]$Proc, [int]$timeoutSec = 40)
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if ($Proc.HasExited) { return $null }
        $Proc.Refresh()
        $h = Get-AppWindow -Proc $Proc
        if ($h -ne [IntPtr]::Zero) { return $h }
        Start-Sleep -Milliseconds 500
    }
    return $null
}

function Write-JsonLine {
    param($obj)
    $obj | ConvertTo-Json -Compress -Depth 5 | Write-Output
}

# ---------------------------------------------------------------------------
# 动作分发
# ---------------------------------------------------------------------------
$exe = Join-Path $AppDir $ExeName

switch ($Action) {

    'info' {
        $scr = Get-ScreenRect
        $dpi = (Get-ItemProperty 'HKCU:\Control Panel\Desktop\WindowMetrics' -ErrorAction SilentlyContinue)
        Write-JsonLine ([pscustomobject]@{
            screenWidth = $scr.Width; screenHeight = $scr.Height
            dpiAwareProcess = $true
            appDir = $AppDir; exe = $exe; exeExists = (Test-Path $exe)
            scriptDir = $script:ScriptDir
        })
    }

    'proc' {
        $ps = @(Get-AppProcess)
        $list = @()
        foreach ($p in $ps) {
            $p.Refresh()
            $h = Get-AppWindow -Proc $p
            $list += [pscustomobject]@{
                pid = $p.Id; path = $p.Path; title = $p.MainWindowTitle
                hwnd = $h.ToInt64(); exited = $p.HasExited
            }
        }
        Write-JsonLine ([pscustomobject]@{ count = $list.Count; processes = $list })
    }

    'waitwin' {
        $ps = @(Get-AppProcess)
        if ($ps.Count -eq 0) { Write-JsonLine ([pscustomobject]@{ ok = $false; reason = '进程不存在' }); exit 3 }
        $proc = $ps[$ps.Count - 1]
        $h = Wait-AppWindow -Proc $proc -timeoutSec $WaitSeconds
        if ($null -eq $h) { Write-JsonLine ([pscustomobject]@{ ok = $false; reason = '等待窗口超时' }); exit 3 }
        $info = Get-WindowRectInfo -Hwnd $h
        Write-JsonLine ([pscustomobject]@{ ok = $true; pid = $proc.Id; window = $info })
    }

    'launch' {
        if (-not (Test-Path $exe)) { throw "找不到便携版 exe：$exe" }
        $ps = @(Get-AppProcess)
        if ($ps.Count -gt 0) {
            throw "便携版已在运行（PID $($ps[0].Id)），请先关闭再启动"
        }
        $proc = Start-Process -FilePath $exe -WorkingDirectory $AppDir -PassThru
        $h = Wait-AppWindow -Proc $proc -timeoutSec $WaitSeconds
        if ($null -eq $h) {
            # 窗口可能还没建好但进程活着：再等，并输出进程信息
            Start-Sleep -Seconds 5
            $proc.Refresh()
            $h = Get-AppWindow -Proc $proc
        }
        $info = $null
        if ($h -ne [IntPtr]::Zero) {
            Activate-AppWindow -Hwnd $h
            if ($WindowWidth -gt 0 -and $WindowHeight -gt 0) { Resize-AppWindow }
            $info = Get-WindowRectInfo -Hwnd $h
        }
        $shot = ''
        if ($Out) { $shot = Save-Screen -path $Out }
        Write-JsonLine ([pscustomobject]@{
            ok = ($h -ne [IntPtr]::Zero); pid = $proc.Id; window = $info
            screenshot = $shot; screen = (Get-ScreenRect)
            exited = $proc.HasExited
        })
    }

    'rect' {
        $ps = @(Get-AppProcess)
        if ($ps.Count -eq 0) { throw '便携版未运行' }
        $proc = $ps[$ps.Count - 1]
        $h = Get-AppWindow -Proc $proc
        if ($h -eq [IntPtr]::Zero) { throw '找不到主窗口' }
        Write-JsonLine (Get-WindowRectInfo -Hwnd $h)
    }

    'act' {
        $ps = @(Get-AppProcess)
        if ($ps.Count -eq 0) { throw '便携版未运行' }
        $proc = $ps[$ps.Count - 1]
        $h = Get-AppWindow -Proc $proc
        Activate-AppWindow -Hwnd $h
        Write-JsonLine ([pscustomobject]@{ ok = $true; hwnd = $h.ToInt64() })
    }

    'shot' {
        $path = if ($Out) { $Out } else { Join-Path $script:EvDir ('截图-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.png') }
        [void](Save-Screen -path $path)
        Write-JsonLine ([pscustomobject]@{ ok = $true; screenshot = $path; screen = (Get-ScreenRect) })
    }

    'crop' {
        $ps = @(Get-AppProcess)
        if ($ps.Count -eq 0) { throw '便携版未运行' }
        $proc = $ps[$ps.Count - 1]
        $h = Get-AppWindow -Proc $proc
        $info = Get-WindowRectInfo -Hwnd $h
        $path = if ($Out) { $Out } else { Join-Path $script:EvDir ('窗口-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.png') }
        [void](Crop-Screen -path $path -left $info.left -top $info.top -width $info.width -height $info.height)
        Write-JsonLine ([pscustomobject]@{ ok = $true; screenshot = $path; window = $info })
    }

    'click' {
        $ret = Click-Mouse $X $Y
        Write-JsonLine ([pscustomobject]@{ ok = $true; clicked = @($X, $Y); cursor = @($ret.X, $ret.Y); foreground = ([W32]::GetForegroundWindow().ToInt64()) })
    }

    'dclick' {
        [void](Click-Mouse $X $Y -delayMs 60)
        Start-Sleep -Milliseconds 120
        [void](Click-Mouse $X $Y -delayMs 60)
        Write-JsonLine ([pscustomobject]@{ ok = $true; dclicked = @($X, $Y) })
    }

    'drag' {
        Drag-Mouse -fromX $X1 -fromY $Y1 -toX $X2 -toY $Y2 -steps $Steps -delayMs $StepDelayMs
        Write-JsonLine ([pscustomobject]@{ ok = $true; from = @($X1, $Y1); to = @($X2, $Y2); steps = $Steps })
    }

    'ritedrag' {
        Drag-Mouse -fromX $X1 -fromY $Y1 -toX $X2 -toY $Y2 -steps $Steps -delayMs $StepDelayMs -rightButton
        Write-JsonLine ([pscustomobject]@{ ok = $true; rightDrag = @($X1, $Y1); to = @($X2, $Y2) })
    }

    'key' {
        if (-not $Key) { throw '缺少 -Key' }
        [System.Windows.Forms.SendKeys]::SendWait($Key)
        Start-Sleep -Milliseconds 300
        Write-JsonLine ([pscustomobject]@{ ok = $true; key = $Key })
    }

    'close' {
        $ps = @(Get-AppProcess)
        if ($ps.Count -eq 0) { Write-JsonLine ([pscustomobject]@{ ok = $true; note = '进程不存在（已退出）' }); exit 0 }
        $proc = $ps[$ps.Count - 1]
        $h = Get-AppWindow -Proc $proc
        $closed = $false
        if ($h -ne [IntPtr]::Zero) {
            [void][W32]::PostMessage($h, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)  # WM_CLOSE
            $deadline = (Get-Date).AddSeconds(20)
            while ((Get-Date) -lt $deadline) {
                Start-Sleep -Milliseconds 500
                if ($proc.HasExited) { $closed = $true; break }
            }
        }
        if (-not $closed) {
            # 弹窗可能拦住退出：强制结束
            try {
                $proc.Refresh()
                if (-not $proc.HasExited) { $proc.CloseMainWindow() | Out-Null; Start-Sleep -Seconds 2 }
                $proc.Refresh()
                if (-not $proc.HasExited) { $proc.Kill(); Start-Sleep -Seconds 2 }
                $proc.Refresh()
                $closed = $proc.HasExited
            } catch { }
        }
        Write-JsonLine ([pscustomobject]@{ ok = $closed; pid = $proc.Id; exited = $proc.HasExited })
        if (-not $closed) { exit 4 }
    }
}

# 供 launch 调整窗口大小（若未来需要）
