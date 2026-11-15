#<SKCON9><WiFi><NetClientB>
# =====================================================================
# 两板通讯 · B 板 TCP 客户端（WiFi 直连方案，前提：机器人 Python 可 import socket）
# 状态：【待真机验证】— 先跑 探测_import与环境.py 拿 IP / 确认 socket。
# 需要改：HOST = A 板 IP（A 板跑 NetServerA；同一路由器/同一热点下）
# 下载方式：官方 AbilixScratch3.0 → 代码模式 → 程序名 NetClientB → 下载
# =====================================================================

import time
import libstarpy

robot = Robot()

HOST = "192.168.43.1"   # ← 改成 A 板实际 IP（获取方法见分报告 §C1）
PORT = 8866
SEND_INTERVAL = 0.2     # 发送周期（秒）

SOCK_OK = True
try:
    import socket
except Exception as _e:
    SOCK_OK = False
    _IMPORT_ERR = _e


def log(msg):
    try:
        robot.print(msg)
    except Exception:
        pass


def send_loop(s):
    seq = 0
    while True:
        seq += 1
        try:
            value = robot.get_ai(1)      # 换成你真实要传的数据源（传感器/EEPROM 等）
        except Exception:
            value = 0
        msg = "B,%d,%d\n" % (seq, value)
        try:
            s.sendall(msg.encode("ascii"))
        except Exception as e:
            log("B send err: %s" % e)
            raise
        # 读一条应答（非阻塞式：超时→记一笔继续）
        try:
            s.settimeout(SEND_INTERVAL)
            r = s.recv(128)
            if r:
                log("B reply=%s" % r.strip())
        except Exception:
            pass
        time.sleep(SEND_INTERVAL)


def main():
    if not SOCK_OK:
        log("socket NOT available: %s" % _IMPORT_ERR)
        return
    while True:                          # 断线重连
        try:
            log("B connect %s:%d" % (HOST, PORT))
            s = socket.create_connection((HOST, PORT), 3.0)
            s.settimeout(3.0)
            log("B connected")
            send_loop(s)
        except Exception as e:
            log("B conn err: %s, retry in 2s" % e)
            try:
                s.close()
            except Exception:
                pass
            time.sleep(2.0)


main()
