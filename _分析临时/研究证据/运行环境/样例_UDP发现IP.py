#<SKCON9><WiFi><NetFindUdp>
# =====================================================================
# 两板通讯 · UDP 自动发现 IP（两板跑同一程序即可；前提：可 import socket）
# 原理：每块板周期性向 255.255.255.255:UDP_PORT 广播 "WHO:<自己的IP>"，
#       同时监听该端口，收到对方广播即打印对方 IP（机器人屏幕拍照即可）。
# 注意：路由器“AP 隔离/客户端隔离”会拦截广播；热点模式一般不隔离。
# 状态：【待真机验证】
# =====================================================================

import time
import libstarpy

robot = Robot()

UDP_PORT = 8867
BROADCAST = "255.255.255.255"
PERIOD = 1.0

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


def get_local_ip():
    """UDP connect 技巧拿本机 IP（不产生实际流量）。"""
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        u.connect(("8.8.8.8", 80))
        return u.getsockname()[0]
    finally:
        u.close()


def main():
    if not SOCK_OK:
        log("socket NOT available: %s" % _IMPORT_ERR)
        return
    try:
        ip = get_local_ip()
    except Exception as e:
        log("get ip FAIL: %s" % e)
        ip = "0.0.0.0"
    log("my ip = %s" % ip)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        s.bind(("", UDP_PORT))
    except Exception as e:
        log("bind %d FAIL: %s" % (UDP_PORT, e))
        return
    s.settimeout(0.2)
    log("udp listen %d" % UDP_PORT)

    last_send = 0.0
    while True:
        now = time.time()
        if now - last_send >= PERIOD:
            last_send = now
            try:
                s.sendto(("WHO:" + ip).encode("ascii"), (BROADCAST, UDP_PORT))
            except Exception as e:
                log("broadcast FAIL: %s" % e)
        try:
            data, addr = s.recvfrom(256)
        except Exception:
            continue                      # 超时/无包
        log("peer %s:%d -> %r" % (addr[0], addr[1], data))
        time.sleep(0.3)


main()
