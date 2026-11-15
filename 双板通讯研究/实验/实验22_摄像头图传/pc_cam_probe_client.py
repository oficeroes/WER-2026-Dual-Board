#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""连到机器人 9001，收 CAMPROBE 报告并存盘。"""
import socket, sys, time, os

ROBOT = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.103"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9001
OUT = sys.argv[3] if len(sys.argv) > 3 else "camprobe_report.txt"
WAIT = float(sys.argv[4]) if len(sys.argv) > 4 else 600.0

t0 = time.time()
while time.time() - t0 < WAIT:
    try:
        s = socket.create_connection((ROBOT, PORT), timeout=5)
        s.settimeout(10)
        buf = b""
        while b"=== END ===" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
        s.close()
        text = buf.decode("utf-8", "replace")
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[ok] got {len(buf)} bytes -> {OUT}", flush=True)
        sys.exit(0)
    except Exception:
        time.sleep(2)
print("[fail] timeout, robot 9001 never answered", flush=True)
sys.exit(1)
