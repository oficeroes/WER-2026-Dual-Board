#<SKCON9><USB><ProgramA>
# ============================================================
# 实验01 · 声音链路 · 发送端 A（零接线，最先做）
# ------------------------------------------------------------
# 目的：验证"板A 能通过内置扬声器，把信息传给板B 的内置麦克风"。
# 这是两板通讯里成本最低、最快能跑通的路径（不用任何线、不用任何外接传感器）。
#
# 重要原理（经逆向确认）：
#   - robot.get_mic() 只返回"声强"一个标量，没有频率/频谱信息
#     → 所以不能用"音高"编码 0/1，只能用 OOK（有声音=1 / 安静=0）或脉宽。
#   - robot.play() 非阻塞（后台播放），robot.play_until() 阻塞到播完。
#   - 内置声音库有钢琴音 gangqin_p0.mp3 ~ gangqin_p7.mp3 等（哪个都行，只当"响声源"）。
#
# 用法：
#   1) 用 VSCode 下载工具把本文件以程序名 ProgramA 下载到 A 板；
#   2) A 板运行本程序，同时 B 板运行 实验01_声音链路_接收端B.py；
#   3) 先看 B 端 monitor 模式：A 播一声、停一下，B 的声强条应明显起伏；
#   4) 稳定后把 B 端改 decode 模式，看能否复现 MSG。
#
# 注意：mp3 实际时长未知（待实测），所以本程序用"播放完再停 GAP"保证符号不重叠；
#       跑通后可根据实测时长调整 SYM_GAP 提升速度。
# ============================================================

import time
import libstarpy

robot = Robot()

# ------------------------- 参数区（按实测调整） -------------------------
NOTE = 'gangqin_p3.mp3'   # 只当"响声源"，音高不重要（接收端只有声强）
MSG = '10110'             # 要发送的比特串：1=响一声，0=安静一个符号
GAP_ON = 0.40             # 每声响完后的静音间隔（秒）
GAP_OFF = 1.00            # "0"符号的静音时长（秒）；先比 1 声略长，便于接收端区分
PREAMBLE = 3              # 同步头：先连续响 3 声
END_MARK = 2              # 结束标记：最后连续响 2 声

def sound_once():
    robot.play_until(NOTE)   # 阻塞到播完
    time.sleep(GAP_ON)

def symbol(bit):
    if bit == '1':
        sound_once()
    else:
        time.sleep(GAP_OFF)

def main():
    robot.clear()
    robot.print('A: sound OOK TX\n')
    time.sleep(1.0)

    robot.print('A: preamble\n')
    for _ in range(PREAMBLE):
        sound_once()
    time.sleep(0.3)

    robot.print('A: send ' + MSG + '\n')
    for bit in MSG:
        symbol(bit)
    time.sleep(0.5)

    # 结束标记：连响，方便 B 端知道报文结束
    for _ in range(END_MARK):
        sound_once()
    robot.print('A: done\n')

main()  # program entry
