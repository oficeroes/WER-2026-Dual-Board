# -*- coding: utf-8 -*-
"""阶段1收尾：关闭便携版 IDE。"""
import sys, time, os, subprocess
sys.path.insert(0, r'D:\UserData\Documents\WER\2026普级赛\WER_函数库\证据\原生积木_便携版')
import win32_ui as w
w.SetProcessDPIAware()

hwnd, pid = w.find_window()
print('IDE window:', hwnd, 'pid', pid)
if hwnd:
    w.activate(hwnd)
    w.PostMessage(hwnd, w.WM_CLOSE, 0, 0)
    print('WM_CLOSE sent')
# 等待进程退出
t0 = time.time()
while time.time() - t0 < 40:
    hh, pp = w.find_window()
    if not hh:
        break
    time.sleep(0.5)
print('window gone after %.1fs' % (time.time() - t0))
p = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                    "(Get-Process -Name AbilixScratch3.0 -ErrorAction SilentlyContinue | Measure-Object).Count"],
                   capture_output=True)
print('IDE process count:', p.stdout.decode('utf-8', 'replace').strip())
