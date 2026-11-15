#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""连 CAMSHOT3：收报告，若带 IMGSTART <len> 则把 JPEG 存成 robot_photo.jpg。"""
import socket
import sys
import time

HOST = "192.168.1.103"
PORT = 9001
WAIT = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0

t0 = time.time()
s = None
while time.time() - t0 < WAIT:
    try:
        s = socket.create_connection((HOST, PORT), timeout=4)
        break
    except Exception:
        time.sleep(2)
if s is None:
    with open("shot3_status.txt", "w", encoding="utf-8") as f:
        f.write("never connected\n")
    sys.exit(1)

s.settimeout(40)
buf = b""
while b"IMGSTART" not in buf and b"=== END ===" not in buf:
    try:
        chunk = s.recv(8192)
    except socket.timeout:
        break
    if not chunk:
        break
    buf += chunk

if b"IMGSTART" in buf:
    idx = buf.index(b"IMGSTART")
    text = buf[:idx]
    rest = buf[idx + len(b"IMGSTART"):]
    nl = rest.index(b"\n")
    length = int(rest[:nl].strip())
    data = rest[nl + 1:]
    while len(data) < length:
        chunk = s.recv(65536)
        if not chunk:
            break
        data += chunk
    img = data[:length]
    with open("robot_photo.jpg", "wb") as f:
        f.write(img)
    with open("shot3_report.txt", "wb") as f:
        f.write(text)
    with open("shot3_status.txt", "w", encoding="utf-8") as f:
        f.write("IMG %d bytes head=%s\n" % (length, img[:4].hex()))
else:
    with open("shot3_report.txt", "wb") as f:
        f.write(buf)
    with open("shot3_status.txt", "w", encoding="utf-8") as f:
        f.write("NOIMG / report %d bytes\n" % len(buf))
s.close()
