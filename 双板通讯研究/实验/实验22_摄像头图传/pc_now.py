#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性连机器人 9001：读 PREV 块，发 P，读本次报告，全部写文件（不依赖控制台编码）。"""
import socket
import sys
import time

HOST = "192.168.1.103"
PORT = 9001

try:
    s = socket.create_connection((HOST, PORT), timeout=5)
    s.settimeout(10)
    buf = b""
    while b"=== PREV-END ===" not in buf:
        chunk = s.recv(8192)
        if not chunk:
            break
        buf += chunk
    with open("now_prev.txt", "wb") as f:
        f.write(buf)

    s.sendall(b"P\n")
    cur = b""
    s.settimeout(90)
    t0 = time.time()
    while b"=== END ===" not in cur and time.time() - t0 < 85:
        chunk = s.recv(8192)
        if not chunk:
            break
        cur += chunk
    with open("now_cur.txt", "wb") as f:
        f.write(cur)
    s.close()
    print("OK prev=%d cur=%d" % (len(buf), len(cur)))
except Exception as e:
    print("FAIL %s %s" % (type(e).__name__, e))
