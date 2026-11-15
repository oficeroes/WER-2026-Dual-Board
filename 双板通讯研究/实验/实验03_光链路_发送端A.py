#<SKCON9><USB><ProgramA>
# ============================================================
# 实验03 · 光链路 · 发送端 A（执行器当"发射器"）
# ------------------------------------------------------------
# 思路：方向2 里"传感器既能收也能发"，最稳妥的落地方式是：
#   发射端用可控的执行器 = 彩灯/LED/smart_led（开=1，关=0）；
#   接收端用光敏传感器（或颜色传感器光敏模式）读光强。
#   等你手上传感器确定后，也可以把发射端换成"灰度/红外/超声传感器自身发射"（需固件支持，见主报告）。
#
# 两种发射方式（改 MODE 选择）：
#   MODE = 'do'     用 robot.set_do(PORT, 0/1) 直接给彩灯/LED 通断电（最简单，推荐先试）
#   MODE = 'smart'  用 robot.smart_led(PORT, 1, 0, r,g,b) 点亮智能灯 / smart_led(PORT,0,0,0,0,0) 熄灭
#
# 接线/摆放：彩灯或智能灯插在 A 板 PORT 口；B 板的光敏插在 B 板对应口；
#           A 的灯正对 B 的光敏，距离 0.5~10cm 先试，避免环境强光直射。
#
# 注意：本实验不涉及两板端口互连，没有电气对插风险。
# ============================================================

import time
import libstarpy

robot = Robot()

# ------------------------- 参数区 -------------------------
MODE = 'do'         # 'do' = 彩灯/LED；'smart' = 智能灯
PORT = 1
BIT_DT = 0.10       # 每位持续时间（秒），先用慢速
SYNC_N = 6          # 同步头：连续亮 6 位
GAP = 0.30
REPEAT = 3
MSG = [1, 0, 1, 1, 0]     # 要发的比特

def light_on():
    if MODE == 'do':
        robot.set_do(PORT, 1)
    else:
        robot.smart_led(PORT, 1, 0, 255, 255, 255)   # 常亮白光
    time.sleep(0.01)

def light_off():
    if MODE == 'do':
        robot.set_do(PORT, 0)
    else:
        robot.smart_led(PORT, 0, 0, 0, 0, 0)
    time.sleep(0.01)

def send_bits(bits):
    for b in bits:
        if b:
            light_on()
        else:
            light_off()
        time.sleep(BIT_DT)
    light_off()

def main():
    robot.clear()
    robot.print('A: light TX ' + MODE + '\n')
    time.sleep(1.0)

    for r in range(REPEAT):
        robot.print('A: send #' + str(r + 1) + '\n')
        send_bits([1] * SYNC_N)
        time.sleep(GAP / 2)
        send_bits(MSG)
        time.sleep(GAP)

    light_off()
    robot.print('A: done\n')

main()  # program entry
