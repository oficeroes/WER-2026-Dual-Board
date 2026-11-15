#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""连到 CAMSHOT2：先收文件系统报告，再发 C 触发拍照，收拍照结果。"""
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

base = recv_until(s, b"=== READY ===", 25)
with open("camshot2_base.txt", "wb") as f:
    f.write(base)
print(f"[ok] base {len(base)} bytes")
if b"=== READY ===" not in base:
    print(base.decode("utf-8", "replace"))
    sys.exit(2)

s.sendall(b"C\n")
shot = recv_until(s, b"=== END ===", 45)
with open("camshot2_shot.txt", "wb") as f:
    f.write(shot)
print(f"[ok] shot {len(shot)} bytes")
s.close()
