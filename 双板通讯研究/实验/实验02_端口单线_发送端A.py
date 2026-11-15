#<SKCON9><USB><ProgramA>
# ============================================================
# 实验02 · 端口单线链路 · 发送端 A（set_do 数字输出 → 对面 get_ai 模拟输入）
# ------------------------------------------------------------
# 目的：验证"两块主板用一根线连 1 号 I/O 端口，A 输出电平、B 读电平"能否成立。
#       这是最接近你"方向1"设想的可行物理层：虽然不能读/改对方的 EEPROM 地址，
#       但可以用端口线做真正的数据通讯。
#
# !! 先看 00_接线与安全测量.md，用万用表确认引脚再接线，不要直接对插 !!（可能 5V 对 5V）
#
# 接线（推荐自制"只连 GND + SIG"的两针线，先不要接 VCC）：
#   A 板 I/O 端口 1 的 GND  ----  B 板 I/O 端口 1 的 GND
#   A 板 I/O 端口 1 的 SIG  ----  B 板 I/O 端口 1 的 SIG   （SIG = 该口信号针，位置靠测量确认）
#
# 本程序：A 用 robot.set_do(PORT, 0/1) 逐比特拉高/拉低，
#        每位 BIT_DT 秒；先发同步头（连续 1），再发消息。
#        B 端配合程序：实验02_端口单线_接收端B.py。
#
# 注意：
#   - set_do 端口范围 1~12，和"电磁铁/彩灯/数字输出"共用；
#   - 该口若被固件识别成传感器/其它设备，行为可能不同 → 先跑 B 端"监测模式"看读数；
#   - 时序精度取决于 Python 与固件往返（待实测），先慢后快：BIT_DT 从 0.05s 起。
# ============================================================

import time
import libstarpy

robot = Robot()

# ------------------------- 参数区 -------------------------
PORT = 1            # 两板都接 1 号 I/O 端口（按实际接线改）
BIT_DT = 0.05       # 每位持续时间（秒）；20 bit/s。跑通后可缩到 0.02/0.01 试
SYNC_BITS = 8       # 同步头：连续 8 个 1
GAP = 0.30          # 报文之间间隔
REPEAT = 3          # 重复发几遍，方便 B 端观察

# 要发送的比特串（1=高电平/有输出，0=低电平）
MSG = [1, 0, 1, 1, 0, 0, 1, 0]

# ------------------------- 发送函数 -------------------------
def send_bits(bits):
    for b in bits:
        robot.set_do(PORT, b)
        time.sleep(BIT_DT)
    robot.set_do(PORT, 0)     # 发完回低

def main():
    robot.clear()
    robot.print('A: DO TX port=' + str(PORT) + '\n')
    robot.print('BIT_DT=' + str(BIT_DT) + '\n')
    time.sleep(1.0)

    for r in range(REPEAT):
        robot.print('A: send #' + str(r + 1) + '\n')
        send_bits([1] * SYNC_BITS)      # 同步头
        time.sleep(GAP / 2)
        send_bits(MSG)                  # 数据
        time.sleep(GAP)

    robot.set_do(PORT, 0)
    robot.print('A: done\n')

main()  # program entry
