# -*- coding: utf-8 -*-
"""原生积木便携版 E2E：Windows 窗口/鼠标控制辅助（ctypes user32，DPI 感知）。

与 ui_自动化.ps1 等价能力，但在前台锁定（SetForegroundWindow 被系统拒绝）时
可用 ALT 键解锁、WScript AppActivate 等多级回退。坐标均为物理像素（2880x1800）。

用法（在证据/自动化目录下执行）：
  python win32_ui.py state               # 打印前台窗口/IDE 窗口状态
  python win32_ui.py activate            # 激活便携版 IDE 窗口（多级回退）
  python win32_ui.py click X Y           # 点击物理坐标
  python win32_ui.py drag X1 Y1 X2 Y2 [steps] [delay_ms]
  python win32_ui.py key "ctrl+s"        # 发送按键（SendKeys 语法）
  python win32_ui.py proc                # 列出 IDE 进程
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import time

user32 = ctypes.WinDLL('user32', use_last_error=True)

SetProcessDPIAware = user32.SetProcessDPIAware
SetCursorPos = user32.SetCursorPos
mouse_event = user32.mouse_event
SetForegroundWindow = user32.SetForegroundWindow
GetForegroundWindow = user32.GetForegroundWindow
ShowWindow = user32.ShowWindow
GetWindowRect = user32.GetWindowRect
GetClientRect = user32.GetClientRect
ClientToScreen = user32.ClientToScreen
IsWindowVisible = user32.IsWindowVisible
IsIconic = user32.IsIconic
GetWindowTextW = user32.GetWindowTextW
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowLongW = user32.GetWindowLongW
SetWindowPos = user32.SetWindowPos
AttachThreadInput = user32.AttachThreadInput
keybd_event = user32.keybd_event
GetWindow = user32.GetWindow
GetTopWindow = user32.GetTopWindow
GetSystemMetrics = user32.GetSystemMetrics
PostMessage = user32.PostMessageW
SendMessageW = user32.SendMessageW

SW_RESTORE = 9
SW_SHOW = 5
HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
VK_MENU = 0x12
WM_CLOSE = 0x0010

AppDir = r'C:\Users\s1325\AbilixScratch3.0_FuncLib'
ProcessName = 'AbilixScratch3.0'


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def _p(msg, **kw):
    d = {'ok': True, 'msg': msg}
    d.update(kw)
    print(json.dumps(d, ensure_ascii=False), flush=True)


def processes():
    """列出 exe 路径以 AppDir 开头的 IDE 进程（PowerShell Get-Process 便于取 Path）。"""
    ps = (
        "Get-Process -Name '%s' -ErrorAction SilentlyContinue | "
        "Select-Object Id,Path,MainWindowTitle,MainWindowHandle | ConvertTo-Json -Compress"
        % ProcessName
    )
    out = subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps],
                         capture_output=True, timeout=60)
    text = out.stdout.decode('utf-8', 'replace').strip()
    if not text:
        return []
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    res = []
    for d in data:
        path = d.get('Path') or ''
        if path.lower().startswith(AppDir.lower()):
            res.append(d)
    return res


def find_window(pid=None):
    procs = processes()
    if not procs:
        return None, None
    if pid is None:
        pid = procs[-1]['Id']
    for pr in procs:
        if pr['Id'] == pid:
            hwnd = int(pr.get('MainWindowHandle') or 0)
            if hwnd:
                return hwnd, pid
    return None, pid


def rect_info(hwnd):
    r = RECT()
    if not GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    c = RECT()
    GetClientRect(hwnd, ctypes.byref(c))
    pt = POINT(0, 0)
    ClientToScreen(hwnd, ctypes.byref(pt))
    return {'hwnd': hwnd, 'left': r.left, 'top': r.top, 'right': r.right,
            'bottom': r.bottom, 'width': r.right - r.left, 'height': r.bottom - r.top,
            'client_left': pt.x, 'client_top': pt.y,
            'client_width': c.right - c.left, 'client_height': c.bottom - c.top,
            'visible': bool(IsWindowVisible(hwnd)), 'iconic': bool(IsIconic(hwnd))}


def window_title(hwnd):
    buf = ctypes.create_unicode_buffer(512)
    GetWindowTextW(hwnd, buf, 512)
    return buf.value


def _alt_unlock():
    """发送一次 ALT 键，解除前台锁定，让 SetForegroundWindow 生效。"""
    keybd_event(VK_MENU, 0, 0, 0)
    time.sleep(0.05)
    keybd_event(VK_MENU, 0, 2, 0)
    time.sleep(0.05)


def activate(hwnd):
    """多级回退激活窗口，返回是否成为前台。"""
    for _ in range(3):
        if IsIconic(hwnd):
            ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.3)
        ShowWindow(hwnd, SW_SHOW)
        SetForegroundWindow(hwnd)
        time.sleep(0.4)
        if GetForegroundWindow() == hwnd:
            return True
        # 回退1：ALT 解锁后再 SetForegroundWindow
        _alt_unlock()
        SetForegroundWindow(hwnd)
        SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW)
        time.sleep(0.4)
        if GetForegroundWindow() == hwnd:
            return True
        # 回退2：WScript.Shell AppActivate（按 PID）
        try:
            pid = wt.DWORD()
            GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            ps = ("(New-Object -ComObject WScript.Shell).AppActivate(%d) | Out-Null" % pid.value)
            subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps],
                           capture_output=True, timeout=30)
        except Exception:
            pass
        time.sleep(0.5)
        if GetForegroundWindow() == hwnd:
            return True
    return GetForegroundWindow() == hwnd


def move_mouse(x, y):
    SetCursorPos(int(x), int(y))
    time.sleep(0.03)


def click(x, y, delay=0.15, double=False):
    move_mouse(x, y)
    mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    if double:
        time.sleep(0.1)
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(delay)


def drag(x1, y1, x2, y2, steps=30, delay_ms=25):
    move_mouse(x1, y1)
    time.sleep(0.15)
    mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.15)
    for i in range(1, steps + 1):
        x = x1 + (x2 - x1) * i / steps
        y = y1 + (y2 - y1) * i / steps
        SetCursorPos(int(x), int(y))
        time.sleep(delay_ms / 1000.0)
    time.sleep(0.2)
    mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.2)


def send_keys(keys):
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.SendKeys]::SendWait('%s')" % keys.replace("'", "''")
    )
    subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps],
                   capture_output=True, timeout=60)


def screenshot(path, dpi_aware=True):
    ui = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui_自动化.ps1')
    args = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ui,
            '-Action', 'shot', '-Out', path]
    out = subprocess.run(args, capture_output=True, timeout=120)
    return out.returncode == 0 and os.path.exists(path)


def main():
    SetProcessDPIAware()
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'state'
    hwnd, pid = find_window()
    if cmd == 'state':
        fg = GetForegroundWindow()
        _p('state', screen={'w': GetSystemMetrics(0), 'h': GetSystemMetrics(1)},
           foreground_hwnd=fg, foreground_title=window_title(fg),
           ide_pid=pid, ide_hwnd=hwnd,
           ide=rect_info(hwnd) if hwnd else None)
    elif cmd == 'proc':
        _p('proc', processes=processes())
    elif cmd == 'activate':
        if not hwnd:
            _p('activate', ok=False, error='IDE 进程不存在')
            sys.exit(1)
        ok = activate(hwnd)
        _p('activate', ok=ok, hwnd=hwnd, foreground=GetForegroundWindow(),
           title=window_title(GetForegroundWindow()), rect=rect_info(hwnd))
    elif cmd == 'click':
        x, y = int(sys.argv[2]), int(sys.argv[3])
        click(x, y)
        _p('click', x=x, y=y)
    elif cmd == 'dclick':
        x, y = int(sys.argv[2]), int(sys.argv[3])
        click(x, y, double=True)
        _p('dclick', x=x, y=y)
    elif cmd == 'drag':
        x1, y1, x2, y2 = map(int, sys.argv[2:6])
        steps = int(sys.argv[6]) if len(sys.argv) > 6 else 30
        delay = int(sys.argv[7]) if len(sys.argv) > 7 else 25
        drag(x1, y1, x2, y2, steps, delay)
        _p('drag', from_=[x1, y1], to=[x2, y2], steps=steps)
    elif cmd == 'key':
        send_keys(sys.argv[2])
        _p('key', keys=sys.argv[2])
    elif cmd == 'shot':
        path = sys.argv[2]
        ok = screenshot(path)
        _p('shot', ok=ok, path=path)
    elif cmd == 'rect':
        _p('rect', ide=rect_info(hwnd) if hwnd else None, title=window_title(hwnd))
    else:
        _p('unknown', cmd=cmd)
        sys.exit(2)


if __name__ == '__main__':
    main()
