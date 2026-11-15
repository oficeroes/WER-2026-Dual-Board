#<SKCON9><USB><ProgramB>
# ============================================================
# 实验02 · 端口单线链路 · 接收端 B（get_ai 模拟输入 / get_touch 数字输入）
# ------------------------------------------------------------
# 与 实验02_端口单线_发送端A.py 配合，接法见发送端注释与 00_接线与安全测量.md。
#
# !!! 先跑本程序的 MONITOR 模式，回答一个关键问题 !!!
#   SKCON9 的端口有"传感器自动识别"（手册 p11）。空置端口（不接传感器）时，
#   固件可能把该口当成"未知/0"，此时 get_ai 可能读不到外部电平。
#   → MONITOR 模式会同时显示 get_ai 和 get_touch 的原始值：
#     - 如果 A 的 set_do 通断能让这里数值/0-1 明显变化 → 端口线方案成立，改 MODE='decode'；
#     - 如果数值一直不变（比如 get_ai=0） → 端口被识别机制"按住"了，需要兜底方案：
#       在信号线上加"碰撞传感器仿真"（用 NPN 三极管/光耦把信号线对地拉低，模拟按键），
#       或改用光/声链路（实验01/03）。
#
# 模式：
#   MODE = 'monitor'  显示原始值（第一步）
#   MODE = 'decode'   按阈值转 0/1 并打印比特流
# ============================================================

import time
import libstarpy

robot = Robot()

# ------------------------- 参数区 -------------------------
PORT = 1
MODE = 'monitor'    # 先 'monitor'
USE_AI = True       # True: robot.get_ai；False: robot.get_touch
SAMPLE_DT = 0.01
THR = 2000          # TODO decode 模式用：A 输出 1/0 时 get_ai 的中间值
SHOW_TOUCH = True   # monitor 模式同时显示 get_touch，帮助判断是否被识别机制干扰

# ------------------------- 工具函数 -------------------------
def read_ai():
    return robot.get_ai(PORT)

def read_touch():
    return robot.get_touch(PORT)

def main():
    robot.clear()
    robot.print('B: RX port=' + str(PORT) + '\n')
    time.sleep(0.5)

    if MODE == 'monitor':
        while True:
            ai = read_ai()
            td = read_touch() if SHOW_TOUCH else -1
            robot.clear()
            robot.print('ai=' + str(ai) + '\n')
            robot.print('touch=' + str(td) + '\n')
            time.sleep(0.05)

    else:
        bits = ''
        last = -1
        while True:
            v = read_ai() if USE_AI else read_touch()
            if USE_AI:
                b = 1 if v >= THR else 0
            else:
                b = 1 if v == 1 else 0
            if b != last:
                bits = bits + str(b)
                robot.print(str(b))
                last = b
            if len(bits) >= 64:
                robot.print('\n')
                bits = ''
            time.sleep(SAMPLE_DT)

main()  # program entry
