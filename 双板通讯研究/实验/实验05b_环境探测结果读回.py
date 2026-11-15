#<SKCON9><USB><ProgramD>
# ============================================================
# 实验05b · 读回运行环境探测结果（跑过 实验05_运行环境探测.py 之后用）
# ------------------------------------------------------------
# 实验05 把结果写进了 EEPROM 100 起：
#   100        socket 能力：2=能创建+bind，1=能创建但 bind 失败，0=不能 import socket
#   101~112    MODS 列表顺序的结果（1=能 import，0=不能）
#   115        MODS 长度
# 本程序把 EEPROM 读回来显示，换程序/重启后也能看（EEPROM 掉电不丢）。
# ============================================================

import time
import libstarpy

robot = Robot()

EE_BASE = 100
MODS = ['time', 'math', 'sys', 'os', 'socket', 'threading',
        'struct', 'json', 'random', 'subprocess', 'serial', 'ctypes']

def main():
    robot.clear()
    robot.print('env readback\n')
    time.sleep(0.3)

    sock_ok = robot.get_ee(EE_BASE + 0)
    robot.print('socket=' + str(sock_ok) + '\n')
    for i in range(len(MODS)):
        v = robot.get_ee(EE_BASE + 1 + i)
        robot.print(MODS[i] + '=' + str(v) + '\n')
        time.sleep(0.1)
    robot.print('done\n')

main()  # program entry
