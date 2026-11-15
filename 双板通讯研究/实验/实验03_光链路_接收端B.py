#<SKCON9><USB><ProgramB>
# ============================================================
# 实验03 · 光链路 · 接收端 B（传感器当"接收器"）
# ------------------------------------------------------------
# 与 实验03_光链路_发送端A.py 配合。
# B 端把光敏传感器（或颜色传感器光敏模式/通用模拟口）插到 PORT，读取光强变化。
#
# 按你手上的传感器选 SENSOR：
#   'light'  robot.get_light(PORT)     光敏传感器（0~4095，手册 p13 光敏 0~4095）
#   'ai'     robot.get_ai(PORT)        通用模拟口（自定义/未识别传感器时可试）
#   'gray'   robot.get_gray(PORT)      灰度传感器（红外反射，若灯是红外/近距离也可能有反应）
#   'color'  robot.get_color(PORT)     颜色传感器（若已切到"光敏模式"，量程 0-4095）
#
# 先用 MONITOR 模式看数值，再改 DECODE 模式解码。
#
# 注意：光敏/灰度传感器的安装高度、环境光影响很大，先让 A 常亮/常灭各 2 秒，
#       看 B 的读数变化是否明显（>10% 量程）再继续。
# ============================================================

import time
import libstarpy

robot = Robot()

# ------------------------- 参数区 -------------------------
PORT = 1
SENSOR = 'light'      # 'light' / 'ai' / 'gray' / 'color'
MODE = 'monitor'      # 先 'monitor' 观察；再改 'decode'
SAMPLE_DT = 0.01
# 阈值：monitor 模式下看读数后填（亮 >= THR_ON，暗 <= THR_OFF）
THR_ON = 2500         # TODO 实测
THR_OFF = 1500        # TODO 实测

def read_sensor():
    if SENSOR == 'light':
        return robot.get_light(PORT)
    elif SENSOR == 'ai':
        return robot.get_ai(PORT)
    elif SENSOR == 'gray':
        return robot.get_gray(PORT)
    else:
        return robot.get_color(PORT)

def main():
    robot.clear()
    robot.print('B: light RX ' + SENSOR + '\n')
    time.sleep(0.5)

    if MODE == 'monitor':
        while True:
            v = read_sensor()
            robot.clear()
            robot.print('val=' + str(v) + '\n')
            # 简易光强条
            n = int(v / 100)
            if n > 40:
                n = 40
            bar = ''
            for _ in range(n):
                bar = bar + '*'
            robot.print(bar + '\n')
            time.sleep(0.05)

    else:
        bits = ''
        last = -1
        while True:
            v = read_sensor()
            b = 1 if v >= THR_ON else (0 if v <= THR_OFF else last)
            if b != last and b >= 0:
                bits = bits + str(b)
                robot.print(str(b))
                last = b
            if len(bits) >= 64:
                robot.print('\n')
                bits = ''
            time.sleep(SAMPLE_DT)

main()  # program entry
