#<SKCON9><USB><ProgramC>
# ============================================================
# 实验05 · 运行环境探测（只读、不改任何东西）
# ------------------------------------------------------------
# 目的：搞清楚"下载到主板的 .py 到底跑在什么 Python 里、能 import 什么"。
#       这直接决定：
#         - 能不能用 socket 做两板 WiFi 通讯（最快、最实用的方案）；
#         - 能不能读 /dev、/proc（更底层调试的可能性）；
#         - 能不能用 threading（做收发分离的程序）。
#
# 官方文档的"导入白名单"只写了 time / libstarpy / math，但那可能是"生成器约定"，
# 不一定是运行时会拦截。本程序逐项 try import，把结果：
#   1) 显示在屏幕上（robot.print）；
#   2) 写进 EEPROM 地址 100~119（掉电不丢，方便反复查看/换程序读回）。
#
# 使用：
#   1) 下载为 ProgramC（或任意名字，但文件头第一行要一致）；
#   2) 运行，等屏幕打印 "done"；
#   3) 抄下屏幕结果即可；需要的话再运行下面的"读回"小段。
# ============================================================

import time
import libstarpy

robot = Robot()

# ------------------------- 参数区 -------------------------
EE_BASE = 100      # 探测结果存到 EEPROM 100 开始，避开 11~20（官方环境采集占用）
MODS = ['time', 'math', 'sys', 'os', 'socket', 'threading',
        'struct', 'json', 'random', 'subprocess', 'serial', 'ctypes']

def probe_one(name):
    """尝试导入，成功返回 1，失败返回 0。"""
    try:
        __import__(name)
        return 1
    except Exception:
        return 0

def main():
    robot.clear()
    robot.print('env probe...\n')
    time.sleep(0.5)

    # 1) 逐模块探测
    results = []
    for name in MODS:
        ok = probe_one(name)
        results.append(ok)
        robot.print(name + '=' + str(ok) + '\n')
        time.sleep(0.1)
    time.sleep(0.5)

    # 2) 基础环境信息
    try:
        import sys
        ver = str(sys.version)
    except Exception:
        ver = '?'
    robot.print('py=' + ver + '\n')
    time.sleep(0.8)

    # 3) 文件系统可见性（只读，出错就跳过）
    info = []
    try:
        import os
        cwd = os.getcwd()
        info.append('cwd=' + str(cwd))
        try:
            files = os.listdir('.')
            info.append('ls=' + str(len(files)))
        except Exception:
            info.append('ls=ERR')
    except Exception:
        info.append('os=ERR')

    for s in info:
        robot.print(s + '\n')
        time.sleep(0.4)

    # 4) socket 能力（最关键的探测：能否做 WiFi 两板通讯）
    sock_ok = 0
    sock_msg = 'n/a'
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = '?'
        try:
            s.bind(('0.0.0.0', 0))       # 能不能 bind 一个临时端口
            sock_ok = 2
        except Exception as e:
            sock_ok = 1
            sock_msg = str(e)
        try:
            s.close()
        except Exception:
            pass
        sock_msg = 'ip=' + str(ip) + ' ' + sock_msg
    except Exception as e:
        sock_ok = 0
        sock_msg = str(e)
    robot.print('socket=' + str(sock_ok) + '\n')
    robot.print(sock_msg + '\n')

    # 5) 结果写 EEPROM（100 起）
    robot.set_ee(EE_BASE + 0, sock_ok)
    for i in range(len(MODS)):
        robot.set_ee(EE_BASE + 1 + i, results[i])
    robot.set_ee(EE_BASE + 15, len(MODS))

    robot.print('done\n')

main()  # program entry
