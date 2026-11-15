#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""等某个程序的报告：反复连 9001，直到收到的内容里出现指定标记。"""
import socket
import sys
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.103"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9001
MARK = (sys.argv[3] if len(sys.argv) > 3 else "=== JNITEST ===").encode()
OUT = sys.argv[4] if len(sys.argv) > 4 else "wait_report.txt"
WAIT = float(sys.argv[5]) if len(sys.argv) > 5 else 600.0

t0 = time.time()
last = b""
while time.time() - t0 < WAIT:
    try:
        s = socket.create_connection((HOST, PORT), timeout=4)
        s.settimeout(8)
        buf = b""
        while b"=== END ===" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
        s.close()
        last = buf
        if MARK in buf:
            with open(OUT, "wb") as f:
                f.write(buf)
            print(f"[ok] {len(buf)} bytes -> {OUT}", flush=True)
            sys.exit(0)
        print(f"[skip] got {len(buf)} bytes, not target: {buf[:32]!r}", flush=True)
    except Exception:
        pass
    time.sleep(2)
print(f"[fail] timeout; last={last[:60]!r}", flush=True)
sys.exit(1)
