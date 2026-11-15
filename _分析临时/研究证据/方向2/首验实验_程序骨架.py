# -*- coding: utf-8 -*-
"""
方向2 首验实验程序骨架（SKCON9，纯 Python，可直接粘到 AbilixScratch3.0 代码模式/下载到控制器）
配套: 双板通讯研究/分报告_方向2_传感器与光声链路.md §7/§8
说明:
  - 本文件是"骨架+注释"，不是可直接下载的完整工程；下载前请把每个实验的函数单独放进
    一个 .py，并由主程序调用（文件头写法见 WER机器人代码生成_给AI的说明书.md）。
  - 所有"待实测"处都写了怎么判读记录值。
  - 记录手段: robot.print() 打屏 + robot.set_ee(addr,value) 存 EEPROM(1~128),
    在控制器"读写数据"界面可看（手册 3.6 节）。
"""

# =========================================================================
# 实验0｜单板自环：标定 set_do / get_mic 时延 + 声链路可行性（0 器材）
# =========================================================================
def exp0_timing():
    """把三个决定性数字写进 EEPROM: EE1=单次get_mic(ms) EE2=单次set_do(ms) EE3=发声时长(ms)"""
    robot.clear()
    # --- ① get_mic 连续调用耗时 ---
    robot.reset_timer(1)
    n = 200
    for i in range(n):
        m = robot.get_mic()
    t_mic = robot.get_timer_ms(1) / n
    # --- ② set_do 连续调用耗时（用彩灯或任意空口） ---
    robot.reset_timer(1)
    for i in range(n):
        robot.set_do(1, 1)
        robot.set_do(1, 0)
    t_do = robot.get_timer_ms(1) / (2 * n)
    # --- ③ 声强基线 vs 播放 ---
    base = 0
    for i in range(20):
        base = base + robot.get_mic()
    base = base / 20
    robot.reset_timer(1)
    robot.play('luyin_p1')          # 录音回放（真实程序里用过，见样本程序/experiment.py:46）
    peak = 0
    cnt = 0
    loud_ms = 0
    prev = 0
    while robot.get_timer_ms(1) < 3000:
        v = robot.get_mic()
        if v > peak:
            peak = v
        if v > base + 200:            # 门限可按实测改
            cnt = cnt + 1
            if prev:
                loud_ms = robot.get_timer_ms(1)   # 记录最后一次超门限时刻，近似时长
            prev = 1
        else:
            prev = 0
    robot.print('t_mic= ' + str(t_mic) + ' ms\n')
    robot.print('t_do = ' + str(t_do) + ' ms\n')
    robot.print('base= ' + str(base) + ' peak= ' + str(peak) + '\n')
    robot.print('loud_end_ms= ' + str(loud_ms) + '\n')
    robot.set_ee(1, robot.clamp(t_mic, -99999, 99999))
    robot.set_ee(2, robot.clamp(t_do, -99999, 99999))
    robot.set_ee(3, robot.clamp(base, -99999, 99999))
    robot.set_ee(4, robot.clamp(peak, -99999, 99999))
    robot.set_ee(5, robot.clamp(loud_ms, -99999, 99999))
    # 判定: t_mic<10ms 且 peak-base>200  -> D2(声链路) 可行


# =========================================================================
# 实验1｜A 板发射端：彩灯(set_do) OOK 发固定帧（光链路 D1）
#  器材: 彩灯插 A 板 1 号口；B 板 1 号口插光敏
# =========================================================================
def a_tx_light_frame():
    """发 4 字节 0x7E 0xA5 0x01 CRC8，曼彻斯特编码，先 5 bps 起（T=100ms/半位 50ms）"""
    T_HALF = 0.05                     # 半位 50ms -> 5 bps；实测后可减半
    data = [0x7E, 0xA5, 0x01]

    def crc8(bytes_):
        c = 0
        for b in bytes_:
            c = c ^ b
            for _ in range(8):
                if c & 1:
                    c = (c >> 1) ^ 0x8C
                else:
                    c = c >> 1
        return c

    frame = data + [crc8(data)]

    # --- 前导 16 个半位 "1010..."，便于接收端自适应门限 ---
    for i in range(16):
        bit = i % 2
        robot.set_do(1, bit)
        time.sleep(T_HALF)

    # --- 曼彻斯特: 0 -> 10, 1 -> 01 ---
    for byte in frame:
        for k in range(7, -1, -1):
            bit = (byte >> k) & 1
            if bit == 0:
                robot.set_do(1, 1); time.sleep(T_HALF)
                robot.set_do(1, 0); time.sleep(T_HALF)
            else:
                robot.set_do(1, 0); time.sleep(T_HALF)
                robot.set_do(1, 1); time.sleep(T_HALF)

    robot.set_do(1, 0)
    robot.print('tx done\n')


# =========================================================================
# 实验1｜B 板接收端：光敏采样 + 时间戳 + 解调（光链路 D1）
#  注意: 每轮循环记录 (t, value)，先跑通"看到位"再上曼彻斯特解码
# =========================================================================
def b_rx_light_sample():
    """连续采样 4 秒，把 (相对时间, 读数) 打屏；先人工看波形，再写解码"""
    robot.reset_timer(1)
    mx = 0
    mn = 4095
    while robot.get_timer_ms(1) < 4000:
        v = robot.get_light(1)
        t = robot.get_timer_ms(1)
        if v > mx:
            mx = v
        if v < mn:
            mn = v
        robot.print(str(t) + ',' + str(v) + '\n')
    robot.set_ee(11, robot.clamp(mn, -99999, 99999))   # 暗 = L0
    robot.set_ee(12, robot.clamp(mx, -99999, 99999))   # 亮 = L1
    # 判定: mx-mn > 300 -> D1 成立；把阈值取 (mx+mn)/2
    # 进阶: 用时间戳做边沿检测 -> 曼彻斯特解码 -> CRC 校验 -> 打屏


# =========================================================================
# 实验2｜判定 D3: "灰度 LED 是否与读取同步"（两板各 1 灰度，正对贴合+遮光）
#  单板部分: 先记录"本板连续读灰度"时自己的 LED 行为（需另一块板的光敏/灰度看它）
# =========================================================================
def exp2_gray_emit_off():
    """A 板: 完全静止 2 秒，不调用任何 get_gray（供 B 板记录 P0）"""
    time.sleep(2)


def exp2_gray_emit_busy():
    """A 板: 连续紧密读灰度 2 秒（供 B 板记录 P1）"""
    robot.reset_timer(1)
    s = 0
    n = 0
    while robot.get_timer_ms(1) < 2000:
        s = s + robot.get_gray(1)
        n = n + 1
    robot.print('avg= ' + str(robot.round(s / n)) + ' n= ' + str(n) + '\n')


def exp2_gray_probe():
    """B 板: 采样 200 次灰度，记录均值/最大/最小（分别对应 P0 与 P1 两次运行）"""
    s = 0
    mx = 0
    mn = 4095
    for i in range(200):
        v = robot.get_gray(1)
        s = s + v
        if v > mx:
            mx = v
        if v < mn:
            mn = v
    robot.print('avg= ' + str(robot.round(s / 200)) + ' max= ' + str(mx) + ' min= ' + str(mn) + '\n')
    # P1(有读) 的 max 明显高于 P0(无读) -> 情形A(读取即点亮)成立 -> D3可用
    # P1 整体抬高但平坦 -> 情形B(LED常亮) -> 只能做存在检测(1bit)
    # 无差异 -> D3 不可行，等 stm32-re 固件结论


# =========================================================================
# 实验3｜超声互扰可检测性（两板各 1 超声，正对 20cm）
# =========================================================================
def exp3_ultrasonic_ping():
    """A 板: 连续测距 2 秒（制造 ping）"""
    robot.reset_timer(1)
    while robot.get_timer_ms(1) < 2000:
        robot.get_ultra_sonic(1)


def exp3_ultrasonic_probe():
    """B 板: 连续测距 200 次，统计是否出现"假近距"尖峰（<150mm 计数）"""
    s = 0
    mn = 1500
    hit = 0
    for i in range(200):
        d = robot.get_ultra_sonic(1)
        s = s + d
        if d < mn:
            mn = d
        if d < 150:
            hit = hit + 1
    robot.print('avg= ' + str(robot.round(s / 200)) + ' min= ' + str(mn) + ' hit= ' + str(hit) + '\n')
    robot.set_ee(31, robot.clamp(mn, -99999, 99999))
    robot.set_ee(32, robot.clamp(hit, -99999, 99999))
    # 有 ping 时 hit 显著 > 无 ping 时 -> 互扰可检测 -> D5 有机会（否则不可行）


# =========================================================================
# 实验补充｜记录工具
# =========================================================================
def dump_ee(base, count):
    robot.clear()
    for i in range(count):
        robot.print(str(base + i) + '= ' + str(robot.get_ee(base + i)) + '\n')


# 主程序骨架（按需启用其中一个实验，下载前请自行补文件头 + import time/libstarpy + Robot()）
# import time
# import libstarpy
# robot = Robot()
# exp0_timing()
