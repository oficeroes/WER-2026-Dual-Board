#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""带重连的收帧器：连上就收帧存盘，断开就重连。最多收 N 帧或 T 秒。"""
import socket
import struct
import sys
import time

HOST = "192.168.1.103"
PORT = 9001
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
T = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0


def recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(min(65536, n - len(buf)))
        if not chunk:
            return None
        buf += chunk
    return buf


t_start = time.time()
got = 0
while got < N and time.time() - t_start < T:
    try:
        s = socket.create_connection((HOST, PORT), timeout=4)
    except Exception:
        time.sleep(2)
        continue
    s.settimeout(60)
    print("connected", flush=True)
    try:
        while got < N:
            head = recv_exact(s, 4)
            if head is None:
                break
            size = struct.unpack(">I", head)[0]
            data = recv_exact(s, size)
            if data is None:
                break
            with open("frame_%02d.png" % got, "wb") as f:
                f.write(data)
            got += 1
            print("frame %d %d bytes t=%.1f" % (got - 1, size, time.time() - t_start), flush=True)
    except Exception as e:
        print("recv error", type(e).__name__, flush=True)
    finally:
        s.close()
    time.sleep(1)
print("done got=%d elapsed=%.1f" % (got, time.time() - t_start), flush=True)
