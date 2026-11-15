# -*- coding: utf-8 -*-
"""
实验12（W0）：COM3 波特率扫描 + 机器人侧 TransSerial 协议探测
================================================================
目的（交接文档 §4-W0）：
  确认 USB-C(CH340) 这个口到底是什么：
   A. 115200 / 921600 下是否有启动日志、控制台、shell 提示符（MT6580 调试 UART）；
   B. 1,000,000 8N1 手发 `55 55 11`（机器人侧 TransSerial 握手）→ 是否回 0x61/0x65
      （若回 61 = 这条口能直接进"PC 下载"状态机，比 AA55 文件协议更简单）；
   C. 937500 下用 AA55 协议再发一次握手（已知成功，作对照组，证明口没被占用/板子在线）。

安全：只发送 3 字节握手 / 12 字节握手帧，不传文件、不触发升级、不改任何数据。
用法：
  py -3 实验12_W0_串口扫描与TransSerial探测.py           # 默认 COM3
  py -3 实验12_W0_串口扫描与TransSerial探测.py COM4
"""

import sys
import time

try:
    import serial
except ImportError:
    sys.stderr.write("缺少 pyserial：请先运行  py -3 -m pip install pyserial\n")
    sys.exit(2)

DEFAULT_PORT = "COM3"


def hexs(data):
    return " ".join("%02X" % b for b in data) if data else "(无)"


def build_protocol(robot_type, cmd1, cmd2, data, seq):
    """复刻 RobotUtils.buildProtocol（与实验09一致，seq 显式传入）。"""
    if data is None:
        data = b""
    buff = bytearray([robot_type & 0xFF, cmd1 & 0xFF, cmd2 & 0xFF, 0, 0, 0, seq & 0xFF])
    if cmd1 == 0 and cmd2 == 0:
        buff[4] = 1
    buff += data
    total = len(buff) + 5
    frame = bytearray(total)
    frame[0] = 0xAA
    frame[1] = 0x55
    frame[2] = ((total - 4) >> 8) & 0xFF
    frame[3] = (total - 4) & 0xFF
    frame[4:4 + len(buff)] = buff
    frame[total - 1] = sum(frame[:total - 1]) & 0xFF
    return bytes(frame)


def open_port(port, baud):
    return serial.Serial(port, baud, bytesize=8, parity="N", stopbits=1,
                         timeout=0.2, write_timeout=2.0)


def passive_listen(port, baud, seconds):
    """不发送，只监听 seconds 秒，返回收到的字节。"""
    print("\n[W0-A] %s @ %d 8N1 被动监听 %.1fs（看有无启动日志/shell）" % (port, baud, seconds))
    try:
        ser = open_port(port, baud)
    except Exception as exc:
        print("  打开失败：%r" % (exc,))
        return None
    out = bytearray()
    try:
        deadline = time.time() + seconds
        while time.time() < deadline:
            n = ser.in_waiting
            if n:
                out += ser.read(n)
            else:
                time.sleep(0.02)
    finally:
        ser.close()
    print("  收到 %d 字节：%s" % (len(out), hexs(out[:64]) + (" ..." if len(out) > 64 else "")))
    if out:
        printable = "".join(chr(b) if 32 <= b < 127 or b in (10, 13, 9) else "." for b in out[:300])
        print("  可打印形式：%s" % printable)
    return bytes(out)


def trans_serial_probe(port):
    """1,000,000 8N1 发 `55 55 11`，看回 0x61(对)/0x65(错)。"""
    print("\n[W0-B] %s @ 1,000,000 8N1 发 TransSerial 握手 `55 55 11`" % port)
    try:
        ser = open_port(port, 1000000)
    except Exception as exc:
        print("  打开失败：%r" % (exc,))
        return False
    try:
        # 先被动听 0.5s，排除上电日志
        time.sleep(0.3)
        pre = ser.read(ser.in_waiting or 1) if ser.in_waiting else b""
        if pre:
            print("  发送前收到：%s" % hexs(pre[:64]))
        ok = False
        for attempt in range(3):
            ser.reset_input_buffer()
            ser.write(b"\x55\x55\x11")
            ser.flush()
            time.sleep(0.4)
            # 持续读 1.0s
            buf = bytearray()
            deadline = time.time() + 1.0
            while time.time() < deadline:
                n = ser.in_waiting
                if n:
                    buf += ser.read(n)
                else:
                    time.sleep(0.02)
            print("  第%d次 发送 `55 55 11` → 收到 %d 字节：%s"
                  % (attempt + 1, len(buf), hexs(buf[:64])))
            if buf:
                if buf[0] == 0x61:
                    print("  >>> 0x61 = 机器人侧 TransSerial 握手成功！")
                    ok = True
                    break
                elif buf[0] == 0x65:
                    print("  >>> 0x65 = 机器人侧回了“错误”码（0x65）。")
                else:
                    print("  >>> 首字节不是 61/65，可能是乱码或别的协议。")
        return ok
    finally:
        ser.close()


def aa55_control(port):
    """937500 下 AA55 握手，作为对照组（已知成功）。"""
    print("\n[W0-C] %s @ 937,500 8N1 发 AA55 握手（对照组，已知成功）" % port)
    try:
        ser = open_port(port, 937500)
    except Exception as exc:
        print("  打开失败：%r" % (exc,))
        return False
    try:
        frame = build_protocol(111, 0xB0, 0x01, None, 1)
        print("  发送：%s" % hexs(frame))
        ser.reset_input_buffer()
        ser.write(frame)
        ser.flush()
        buf = bytearray()
        deadline = time.time() + 1.5
        while time.time() < deadline:
            n = ser.in_waiting
            if n:
                buf += ser.read(n)
            else:
                time.sleep(0.02)
        print("  收到 %d 字节：%s" % (len(buf), hexs(buf[:64])))
        ok = len(buf) >= 12 and buf[0] == 0xAA and buf[1] == 0x55 and buf[5] == 0xB0 and buf[6] == 0x01
        if ok:
            payload = buf[11:len(buf) - 1]
            print("  >>> 握手成功，payload=%s" % hexs(payload))
        return ok
    finally:
        ser.close()


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    print("=" * 64)
    print("实验12（W0）：COM3 波特率/协议扫描  port=%s" % port)
    print("=" * 64)

    results = {}
    # 1) 115200 / 921600 被动监听
    results["115200"] = passive_listen(port, 115200, 2.0)
    results["921600"] = passive_listen(port, 921600, 2.0)
    # 2) 1,000,000 TransSerial 主动握手
    results["trans"] = trans_serial_probe(port)
    # 3) 937500 AA55 对照组
    results["aa55"] = aa55_control(port)

    print("\n" + "=" * 64)
    print("结论汇总：")
    for baud in ("115200", "921600"):
        data = results.get(baud)
        if data:
            print("  %s 被动监听：收到 %d 字节（有输出→可能是 MTK 调试串口；全 00/FF 可能是波特率不匹配）"
                  % (baud, len(data)))
        else:
            print("  %s 被动监听：无输出 / 打开失败" % baud)
    print("  1,000,000 `55 55 11`：%s" % ("回 0x61，TransSerial 可用" if results.get("trans") else "未回 61/65"))
    print("  937,500 AA55 握手：%s" % ("成功（通道在线）" if results.get("aa55") else "失败（检查占用/供电）"))
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
