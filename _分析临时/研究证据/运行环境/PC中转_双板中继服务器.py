#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
两板通讯 · PC 中转服务器（在电脑上运行，Python 3.8+）

用途（按可行性排序）：
  A. 两块板在同一 WiFi、但广播/直连被 AP 隔离时：两板都主动连 PC，由 PC 双向转发。
  B. 两板分处不同网络、各自 USB 接 PC 时：配合 adb reverse（需 ADB 可用，待真机验证）：
        adb -s <板A序列号> reverse tcp:9001 tcp:9001
        adb -s <板B序列号> reverse tcp:9002 tcp:9002
     然后板内 Python 程序连 127.0.0.1:9001 / 127.0.0.1:9002 即到 PC 的这两个端口。
  C. 一块板 WiFi、一块板 USB 也行（口子一样）。

协议：纯字节转发（透明管道）。两板约定同一行协议即可，例如 B 板发 "B,<seq>,<val>\\n"。
"""
import socket
import threading
import argparse
import time

LOG_LOCK = threading.Lock()


def log(msg):
    with LOG_LOCK:
        print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def pump(src, dst, tag):
    """src -> dst 单向转发。"""
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        log("%s closed" % tag)
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def pair_loop(port_a, port_b, host="0.0.0.0"):
    """监听 port_a / port_b，各接受一个连接后双向桥接；断线后重新配对。"""
    listener = {}
    for name, port in (("A", port_a), ("B", port_b)):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(2)
        listener[name] = srv
        log("listen %s on %s:%d" % (name, host, port))

    while True:
        conns = {}
        for name, srv in listener.items():
            while True:
                try:
                    conn, addr = srv.accept()
                except OSError:
                    time.sleep(0.2)
                    continue
                log("%s connected from %s:%d" % (name, addr[0], addr[1]))
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                conns[name] = conn
                break
        a, b = conns["A"], conns["B"]
        t1 = threading.Thread(target=pump, args=(a, b, "A->B"), daemon=True)
        t2 = threading.Thread(target=pump, args=(b, a, "B->A"), daemon=True)
        t1.start(); t2.start()
        t1.join(); t2.join()
        for c in (a, b):
            try:
                c.close()
            except OSError:
                pass
        log("pair done, waiting for next pair")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--a-port", type=int, default=9001, help="A 板接入端口")
    ap.add_argument("--b-port", type=int, default=9002, help="B 板接入端口")
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    pair_loop(args.a_port, args.b_port, args.host)
