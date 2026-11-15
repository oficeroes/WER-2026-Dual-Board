#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""连 JNIPROBE13：先收上次运行残留的报告，再发 P 触发本次探测并收结果。"""
import socket
import sys
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.103"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9001
WAIT = float(sys.argv[3]) if len(sys.argv) > 3 else 600.0


def recv_until(s, marker, timeout):
    s.settimeout(timeout)
    buf = b""
    while marker not in buf:
        try:
            chunk = s.recv(8192)
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
    return buf


t0 = time.time()
s = None
while time.time() - t0 < WAIT:
    try:
        s = socket.create_connection((HOST, PORT), timeout=4)
        break
    except Exception:
        time.sleep(2)

if s is None:
    print("[fail] never connected")
    sys.exit(1)

prev = recv_until(s, b"=== PREV-END ===", 20)
with open("jni_prev.txt", "wb") as f:
    f.write(prev)
print("---- 上次运行残留 ----")
print(prev.decode("utf-8", "replace"))
print("----------------------")

try:
    s.sendall(b"P\n")
    cur = recv_until(s, b"=== END ===", 40)
    with open("jni_cur.txt", "wb") as f:
        f.write(cur)
    print("---- 本次探测 ----")
    print(cur.decode("utf-8", "replace"))
except Exception as e:
    print("[warn] 本次探测没有返回（进程可能崩溃）:", e)
finally:
    s.close()
