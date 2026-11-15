# -*- coding: utf-8 -*-
"""
实验09：电脑经 USB-C（CH340）与主板的有线握手测试
=====================================================

目的（2026-11-11 新增）：
  你的主板 USB-C 口在 Windows 里枚举为 "USB-SERIAL CH340 (COM3)"，
  不是 ADB 设备；但官方 PC 软件正是用这个串口下载程序的。
  本程序只做一件事：按官方协议发"连接握手帧"，看主板是否回应。
  → 能回应 = 这条 USB 线是一条可用的"电脑↔主板"数据通道，
     后续可用它做下载/控制/中继实验（程序下载的完整协议已另外逆向）。

安全说明：
  - 本程序只发送握手帧（cmd1=0xB0, cmd2=0x01），不发送任何文件、不触发升级；
  - 不改主板里的任何程序/数据；随时可拔线退出。

协议逆向依据（PC 端 Assembly-CSharp.decompiled.cs）：
  - RobotUtils.buildProtocol(type, cmd1, cmd2, data)，行 99580-99624：
        帧 = AA 55 | len_hi len_lo | type cmd1 cmd2 00 00 00 idx | data... | sum8
        len = 8 + len(data)；sum8 = 前面所有字节的 8 位累加和
  - 握手：BaseSK.GetConnectProtocolDatasHandler()（行 94925-94928）
        buildProtocol(ROBOT_SELECT, 176, 1, null)   # 176 = 0xB0
  - 校验：BaseSK.RecvConnectDatasValidityHandler()（行 94914-94923）
        收包长度>11 且 recv[5]==176 且 recv[6]==1 且 (recv[11]==1 或 40) → 连接成功
  - 波特率：LibUart.m_nBaudRate = 937500（行 95293）；8N1，读超时 1000ms

用法：
  py -3 实验09_有线握手_CH340.py            # 默认 COM3, 937500, 依次试 type=111/1
  py -3 实验09_有线握手_CH340.py COM4      # 指定串口
  py -3 实验09_有线握手_CH340.py COM3 2000000
"""

import sys
import time

try:
    import serial
except ImportError:
    sys.stderr.write("缺少 pyserial：请先运行  py -3 -m pip install pyserial\n")
    sys.exit(2)

DEFAULT_PORT = "COM3"
DEFAULT_BAUD = 937500
# SKCON9 的 machineType = 111（6F 目录 = 111）；UsbManager 旧路径用 1
CANDIDATE_TYPES = [111, 1]


def build_protocol(robot_type, cmd1, cmd2, data):
    """复刻 RobotUtils.buildProtocol：AA55 + len + 7 字节头 + data + sum8。"""
    if data is None:
        data = b""
    buff = bytearray([robot_type & 0xFF, cmd1 & 0xFF, cmd2 & 0xFF, 0, 0, 0, 0])
    if cmd1 == 0 and cmd2 == 0:
        buff[4] = 1
    # DATA_PACKAGE_INDEX 全局滚动；测试时用递增序号即可
    build_protocol.package_index = (getattr(build_protocol, "package_index", 0) + 1) % 255
    buff[6] = build_protocol.package_index
    buff += data
    total = len(buff) + 5  # AA55(2) + len(2) + buff + sum(1)
    frame = bytearray(total)
    frame[0] = 0xAA
    frame[1] = 0x55
    frame[2] = ((total - 4) >> 8) & 0xFF
    frame[3] = (total - 4) & 0xFF
    frame[4:4 + len(buff)] = buff
    checksum = 0
    for b in frame[:total - 1]:
        checksum = (checksum + b) & 0xFF
    frame[total - 1] = checksum
    return bytes(frame)


def hexs(data):
    return " ".join("%02X" % b for b in data) if data else "(无)"


def read_for(ser, seconds):
    """在 seconds 内持续读取，返回累计字节。"""
    out = bytearray()
    deadline = time.time() + seconds
    while time.time() < deadline:
        n = ser.in_waiting
        if n:
            out += ser.read(n)
        else:
            time.sleep(0.02)
    return bytes(out)


def parse_frames(buf):
    """把接收缓存拆成帧列表（允许帧前有垃圾字节）。"""
    frames = []
    i = 0
    while i + 4 <= len(buf):
        if buf[i] == 0xAA and buf[i + 1] == 0x55:
            length = (buf[i + 2] << 8) | buf[i + 3]
            end = i + 4 + length
            if end > len(buf):
                break  # 半帧，等下一次
            packet = buf[i:end]
            frames.append(packet)
            i = end
        else:
            i += 1
    return frames


def describe_frame(packet):
    """打印一帧的关键字段。"""
    if len(packet) < 12:
        return "  帧太短：%s" % hexs(packet)
    body = packet[4:]
    robot_type, cmd1, cmd2, idx = body[0], body[1], body[2], body[6]
    payload = body[7:-1]
    good_sum = (sum(packet[:-1]) & 0xFF) == packet[-1]
    line = ("  type=%d cmd1=0x%02X cmd2=0x%02X idx=%d payload=%s 校验和%s"
            % (robot_type, cmd1, cmd2, idx, hexs(payload), "OK" if good_sum else "错"))
    if cmd1 == 0xB0 and cmd2 == 0x01 and len(payload) >= 1:
        value = payload[0]
        if value in (1, 40):
            line += "\n  >>> 握手成功（payload[0]=%d，官方判据：1 或 40）" % value
        else:
            line += "\n  >>> 有回应但 payload[0]=%d，不是官方判据值" % value
    return line


def try_handshake(ser, robot_type, baud):
    frame = build_protocol(robot_type, 0xB0, 0x01, None)
    ser.reset_input_buffer()
    print("\n[发送] 握手帧 type=%d baud=%d：%s" % (robot_type, baud, hexs(frame)))
    ser.write(frame)
    ser.flush()
    reply = read_for(ser, 1.2)
    print("[接收] %d 字节：%s" % (len(reply), hexs(reply)))
    frames = parse_frames(reply)
    ok = False
    for packet in frames:
        print(describe_frame(packet))
        body = packet[4:]
        if len(body) >= 8 and body[1] == 0xB0 and body[2] == 0x01 and body[7] in (1, 40):
            ok = True
    if not frames and reply:
        print("  未解析出 AA55 帧，原始字节见上。")
    return ok, reply


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BAUD

    print("=" * 60)
    print("实验09：USB-C(CH340) 有线握手测试")
    print("串口=%s  波特率=%d  8N1  只发握手帧，不下载文件" % (port, baud))
    print("=" * 60)

    try:
        ser = serial.Serial(port, baud, bytesize=8, parity="N", stopbits=1, timeout=0.5)
    except Exception as exc:
        print("打开串口失败：%r" % (exc,))
        print("检查：1) 线是否插好；2) 设备管理器里端口号是否真是 %s；" % port)
        print("      3) 是否有别的程序（官方软件/串口助手）占用了该串口。")
        return 3

    try:
        print("串口已打开：%s @ %d" % (ser.port, ser.baudrate))
        any_ok = False
        for robot_type in CANDIDATE_TYPES:
            ok, reply = try_handshake(ser, robot_type, baud)
            any_ok = any_ok or ok
            if ok:
                print("\n结论：主板在线，USB-C 是一条可用数据通道（type=%d 握手成功）。" % robot_type)
                print("下一步（交接文档里写）：可用同一协议做程序下载/控制；")
                print("若要两板通讯，还需看运行端能否跑 socket（实验05 已判 socket=0）。")
                break
        if not any_ok:
            print("\n结论：没有收到符合官方判据的握手回应。可能原因：")
            print("  A. 串口/波特率不对（官方 937500；个别版本可能不同）；")
            print("  B. 主板端未运行负责串口协议的进程（正常开机桌面即可响应，待确认）；")
            print("  C. 现在的 USB-C 口只做充电/固件口，下载走 WiFi（看 PC 软件里下载方式设置）；")
            print("  D. 需要用官方软件先打开一次（会配置串口）。")
            print("记录：原始回应已打印在上面，可据此判断是乱码（波特率错）还是完全无回应（无协议）。")
        return 0 if any_ok else 1
    finally:
        ser.close()
        print("\n串口已关闭。")


if __name__ == "__main__":
    sys.exit(main())
