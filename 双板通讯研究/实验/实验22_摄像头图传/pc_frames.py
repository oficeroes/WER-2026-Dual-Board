#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无界面接收 N 帧，存盘并打印帧率（用于验证实时流）。"""
import socket
import struct
import sys
import time

HOST = "192.168.1.103"
PORT = 9001
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12


def recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(min(65536, n - len(buf)))
        if not chunk:
            return None
        buf += chunk
    return buf


s = socket.create_connection((HOST, PORT), timeout=6)
s.settimeout(120)
print("connected", flush=True)
t0 = time.time()
for i in range(N):
    head = recv_exact(s, 4)
    if head is None:
        print("closed", flush=True)
        break
    size = struct.unpack(">I", head)[0]
    data = recv_exact(s, size)
    if data is None:
        break
    with open("frame_%02d.png" % i, "wb") as f:
        f.write(data)
    print("frame %d %d bytes t=%.2f" % (i, size, time.time() - t0), flush=True)
el = time.time() - t0
print("total %d frames in %.2fs -> %.2f fps" % (N, el, N / el if el > 0 else 0), flush=True)
s.close()
