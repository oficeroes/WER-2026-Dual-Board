#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pc_view2.py —— 连机器人 9001，实时显示摄像头画面

协议：[4 字节大端长度][PNG] 循环
按键 q / Esc 退出，s 存图
"""
import os
import socket
import struct
import sys
import time

import cv2
import numpy as np

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.103"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9001


def recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(min(65536, n - len(buf)))
        if not chunk:
            return None
        buf += chunk
    return buf


def main():
    print(f"[viewer] connecting {HOST}:{PORT} ...", flush=True)
    s = socket.create_connection((HOST, PORT), timeout=6)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    s.settimeout(10)
    print("[viewer] connected", flush=True)

    n = 0
    t0 = time.time()
    fps = 0.0
    while True:
        head = recv_exact(s, 4)
        if head is None:
            print("[viewer] robot closed", flush=True)
            break
        size = struct.unpack(">I", head)[0]
        if size <= 0 or size > 8 * 1024 * 1024:
            print("[viewer] bad size", size, flush=True)
            break
        data = recv_exact(s, size)
        if data is None:
            break
        frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            continue
        n += 1
        el = time.time() - t0
        if el >= 1.0:
            fps = n / el
            n = 0
            t0 = time.time()
        h, w = frame.shape[:2]
        cv2.putText(frame, f"{w}x{h} {fps:4.1f}fps {size/1024:5.1f}KB",
                    (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
        cv2.imshow("AI Camera (robot)", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("s"):
            name = time.strftime("snap_%H%M%S.png")
            cv2.imwrite(name, frame)
            print("[viewer] saved", name, flush=True)
    s.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
