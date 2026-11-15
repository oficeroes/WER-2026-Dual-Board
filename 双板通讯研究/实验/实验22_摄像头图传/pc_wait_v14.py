#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""等 JNI 探测 v14：反复连 9001，发 P，直到本次探测报告里出现 v14。"""
import socket
import sys
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.103"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9001
WAIT = float(sys.argv[3]) if len(sys.argv) > 3 else 900.0


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
while time.time() - t0 < WAIT:
    try:
        s = socket.create_connection((HOST, PORT), timeout=4)
    except Exception:
        time.sleep(2)
        continue
    try:
        prev = recv_until(s, b"=== PREV-END ===", 8)
        s.sendall(b"P\n")
        cur = recv_until(s, b"=== END ===", 25)
        if b"v14" in cur:
            with open("jni_prev14.txt", "wb") as f:
                f.write(prev)
            with open("jni_cur14.txt", "wb") as f:
                f.write(cur)
            print("---- PREV ----")
            print(prev.decode("utf-8", "replace"))
            print("---- CURRENT ----")
            print(cur.decode("utf-8", "replace"))
            sys.exit(0)
        print(f"[skip] got {len(cur)} bytes, banner:", cur.split(b"\n")[0][:40])
    except Exception as e:
        print("[warn]", e)
    finally:
        s.close()
    time.sleep(2)
print("[fail] timeout")
sys.exit(1)
