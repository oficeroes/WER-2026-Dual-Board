# -*- coding: utf-8 -*-
import sys, time
sys.path.insert(0, r'D:\UserData\Documents\WER\2026普级赛\WER_函数库\证据\原生积木_便携版')
import win32_ui as w
w.SetProcessDPIAware()
SH = r'D:\UserData\Documents\WER\2026普级赛\WER_函数库\证据\原生积木_便携版\截图'
hwnd, _ = w.find_window()
print('activate', w.activate(hwnd), 'fg', w.GetForegroundWindow() == hwnd)
w.click(60, 630); time.sleep(2.0)
print('activate2', w.activate(hwnd), 'fg', w.GetForegroundWindow() == hwnd)
w.screenshot(SH + r'\14_示例库20函数_flyout.png')
print('saved 14')
