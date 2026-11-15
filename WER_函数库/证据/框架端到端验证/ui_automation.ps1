# ui_automation.ps1 —— 真实 IDE 的 PowerShell 鼠标/截图自动化小工具
# 用法（在每个 pwsh 命令里先 dot-source）：
#   . "WER_函数库\证据\框架端到端验证\ui_automation.ps1"
#   Save-Screen "out.png"
#   Move-Mouse 252 67            # 移动（触发 Unity 的 hover 菜单）
#   Click-Mouse 252 67           # 点击
#   $w = Get-AppWindow -PathPrefix "D:\...\AbilixScratch3.0_函数版"
# 说明：界面是 Unity 程序，鼠标事件用 user32(SetCursorPos/mouse_event)；窗口按进程可执行文件路径识别。
#       本脚本只做“移动/点击/截图/读窗口”，不修改任何文件。

Add-Type -AssemblyName System.Drawing, System.Windows.Forms | Out-Null

if (-not ('Win32.UI' -as [type])) {
    Add-Type -Namespace Win32 -Name UI -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
[DllImport("user32.dll")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
[DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);
[DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hWnd, ref POINT lpPoint);
[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
[StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
[StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
'@
}

$script:ScreenBounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds

function Save-Screen {
    param([string]$Path)
    $b = $script:ScreenBounds
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Write-Output ("SCREENSHOT " + $Path + " " + (Get-Item $Path).Length + " bytes")
}

function Crop-Screen {
    param([string]$Path, [int]$X, [int]$Y, [int]$W, [int]$H)
    $b = $script:ScreenBounds
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
    $crop = New-Object System.Drawing.Bitmap $W, $H
    $g2 = [System.Drawing.Graphics]::FromImage($crop)
    $g2.DrawImage($bmp, (New-Object System.Drawing.Rectangle 0, 0, $W, $H), (New-Object System.Drawing.Rectangle $X, $Y, $W, $H), [System.Drawing.GraphicsUnit]::Pixel)
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $crop.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $g2.Dispose(); $bmp.Dispose(); $crop.Dispose()
    Write-Output ("CROP " + $Path + " " + (Get-Item $Path).Length + " bytes")
}

function Get-ScreenSize {
    Write-Output ("SCREEN " + $script:ScreenBounds.Width + "x" + $script:ScreenBounds.Height)
}

function Move-Mouse {
    param([int]$X, [int]$Y)
    [Win32.UI]::SetCursorPos($X, $Y) | Out-Null
    Start-Sleep -Milliseconds 120
    $pos = [System.Windows.Forms.Cursor]::Position
    Write-Output ("MOUSE MOVE -> " + $pos.X + "," + $pos.Y)
}

function Click-Mouse {
    param([int]$X, [int]$Y, [int]$DelayMs = 120)
    [Win32.UI]::SetCursorPos($X, $Y) | Out-Null
    Start-Sleep -Milliseconds $DelayMs
    # MOUSEEVENTF_LEFTDOWN=0x0002, LEFTUP=0x0004
    [Win32.UI]::mouse_event(0x0002, 0, 0, 0, 0)
    Start-Sleep -Milliseconds 60
    [Win32.UI]::mouse_event(0x0004, 0, 0, 0, 0)
    Write-Output ("MOUSE CLICK " + $X + "," + $Y)
}

function Get-AppWindow {
    param([string]$PathPrefix, [string]$ProcessName = "AbilixScratch3.0")
    $procs = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -and $_.Path.StartsWith($PathPrefix, [System.StringComparison]::OrdinalIgnoreCase) } catch { $false }
    }
    if (-not $procs) { return $null }
    $p = $procs | Sort-Object StartTime | Select-Object -Last 1
    $w = New-Object PSObject -Property @{
        Id = $p.Id; Path = $p.Path; MainWindowTitle = $p.MainWindowTitle
        MainWindowHandle = $p.MainWindowHandle; StartTime = $p.StartTime; Process = $p
    }
    return $w
}

function Get-WindowRectInfo {
    param($Window)
    if (-not $Window) { Write-Output "WINDOW NULL"; return }
    $r = New-Object Win32.UI+RECT
    [Win32.UI]::GetWindowRect($Window.MainWindowHandle, [ref]$r) | Out-Null
    $c = New-Object Win32.UI+RECT
    [Win32.UI]::GetClientRect($Window.MainWindowHandle, [ref]$c) | Out-Null
    $pt = New-Object Win32.UI+POINT; $pt.X = 0; $pt.Y = 0
    [Win32.UI]::ClientToScreen($Window.MainWindowHandle, [ref]$pt) | Out-Null
    Write-Output ("WINDOW pid=" + $Window.Id + " title='" + $Window.MainWindowTitle + "' hwnd=" + $Window.MainWindowHandle)
    Write-Output ("RECT left=" + $r.Left + " top=" + $r.Top + " right=" + $r.Right + " bottom=" + $r.Bottom + " size=" + ($r.Right - $r.Left) + "x" + ($r.Bottom - $r.Top))
    Write-Output ("CLIENT origin=" + $pt.X + "," + $pt.Y + " size=" + $c.Right + "x" + $c.Bottom)
}

function Activate-Window {
    param($Window)
    if (-not $Window) { Write-Output "WINDOW NULL"; return }
    [Win32.UI]::ShowWindow($Window.MainWindowHandle, 9) | Out-Null   # SW_RESTORE
    [Win32.UI]::SetForegroundWindow($Window.MainWindowHandle) | Out-Null
    Start-Sleep -Milliseconds 250
    $fg = [Win32.UI]::GetForegroundWindow()
    Write-Output ("ACTIVATE hwnd=" + $Window.MainWindowHandle + " foreground=" + $fg + " match=" + ($fg -eq $Window.MainWindowHandle))
}

function Close-AppWindow {
    param($Window, [int]$WaitSeconds = 60)
    if (-not $Window) { Write-Output "WINDOW NULL"; return }
    # WM_CLOSE = 0x0010，等价于点右上角关闭（IDE 会正常退出并回存配置）
    [Win32.UI]::PostMessage($Window.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $deadline) {
        $p = Get-Process -Id $Window.Id -ErrorAction SilentlyContinue
        if (-not $p) { Write-Output ("CLOSED pid=" + $Window.Id); return }
        Start-Sleep -Milliseconds 400
    }
    Write-Output ("CLOSE TIMEOUT pid=" + $Window.Id)
}
