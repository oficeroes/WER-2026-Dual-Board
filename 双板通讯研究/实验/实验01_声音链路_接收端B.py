#<SKCON9><USB><ProgramB>
# ============================================================
# 实验01 · 声音链路 · 接收端 B
# ------------------------------------------------------------
# 与 实验01_声音链路_发送端A.py 配合：A 播"响/静"序列，B 用内置麦克风读声强。
#
# 原理限制（经逆向确认）：get_mic() 只有声强标量 → 只能用 OOK/脉宽解码，不能解音高。
#
# 两步走：
#   第 1 步 MONITOR：屏幕显示实时声强+峰值线，肉眼确认 A 出声时读数明显变化；
#   第 2 步 DECODE：按阈值把声强序列变成 0/1，并打印（需先标定 QUIET/LOUD）。
#
# 标定方法：
#   1) 安静时运行 MONITOR，记下背景声强最大值 → QUIET_MAX；
#   2) A 播放一声时，记下 B 的声强峰值 → LOUD_MIN；
#   3) 填进下面，MODE 改 'decode'。
# ============================================================

import time
import libstarpy

robot = Robot()

# ------------------------- 参数区（必须实测标定） -------------------------
MODE = 'monitor'      # 'monitor' 先观察；'decode' 再解码
QUIET_MAX = 30        # TODO 实测：安静时最大声强
LOUD_MIN = 300        # TODO 实测：A 出声时最小声强
SAMPLE_DT = 0.02      # 采样间隔
WIN_DT = 0.30         # 判决窗口长度：窗口内峰值 >= LOUD_MIN 判为 1
HOLD_DT = 0.25        # 两次"响"之间的最小间隔，防止一声被切成多声

def main():
    robot.clear()
    robot.print('B: sound OOK RX\n')
    time.sleep(0.5)

    if MODE == 'monitor':
        while True:
            v = robot.get_mic()
            n = int(v / 50)
            if n > 30:
                n = 30
            bar = ''
            for _ in range(n):
                bar = bar + '#'
            robot.clear()
            robot.print('mic=' + str(v) + '\n')
            robot.print(bar + '\n')
            time.sleep(0.05)
    else:
        # 窗口判决：每 WIN_DT 秒取一次峰值；>=LOUD_MIN 记 1，<=QUIET_MAX 记 0
        bits = ''
        while True:
            t0 = time.time()
            peak = 0
            while time.time() - t0 < WIN_DT:
                v = robot.get_mic()
                if v > peak:
                    peak = v
                time.sleep(SAMPLE_DT)
            if peak >= LOUD_MIN:
                bits = bits + '1'
            elif peak <= QUIET_MAX:
                bits = bits + '0'
            else:
                bits = bits + '?'
            robot.print(bits[-1])
            if len(bits) >= 24:
                robot.print('\n')
                bits = ''

main()  # program entry
