#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pc_viewer.py —— 接收机器人推来的 MJPEG 帧并实时显示

协议（机器人 → 电脑，TCP 9002）：
    [4 字节大端长度 N][N 字节 JPEG]

用法：
    python pc_viewer.py [--port 9002] [--save 抓帧目录]
按键：q / Esc 退出，s 保存当前帧
"""
import argparse
import os
import socket
import struct
import time

import cv2
import numpy as np


def recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(min(65536, n - len(buf)))
        if not chunk:
            return None
        buf += chunk
    return buf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9002)
    ap.add_argument("--save", default="")
    args = ap.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", args.port))
    srv.listen(1)
    print(f"[viewer] listening on 0.0.0.0:{args.port} ...", flush=True)

    while True:
        conn, addr = srv.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f"[viewer] robot connected from {addr}", flush=True)

        n_frame = 0
        t0 = time.time()
        fps = 0.0
        try:
            while True:
                head = recv_exact(conn, 4)
                if head is None:
                    break
                size = struct.unpack(">I", head)[0]
                if size <= 0 or size > 8 * 1024 * 1024:
                    print(f"[viewer] bad frame size {size}", flush=True)
                    break
                data = recv_exact(conn, size)
                if data is None:
                    break
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    continue
                n_frame += 1
                el = time.time() - t0
                if el >= 1.0:
                    fps = n_frame / el
                    n_frame = 0
                    t0 = time.time()
                h, w = frame.shape[:2]
                cv2.putText(frame, f"{w}x{h}  {fps:4.1f} fps  {size/1024:5.1f} KB",
                            (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (0, 255, 0), 2, cv2.LINE_AA)
                cv2.imshow("AI Camera (robot)", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    conn.close()
                    srv.close()
                    cv2.destroyAllWindows()
                    return
                if key == ord("s"):
                    os.makedirs(args.save or ".", exist_ok=True)
                    name = os.path.join(args.save or ".", time.strftime("frame_%H%M%S.jpg"))
                    cv2.imwrite(name, frame)
                    print(f"[viewer] saved {name}", flush=True)
        finally:
            conn.close()
            print("[viewer] robot disconnected, waiting for reconnect...", flush=True)


if __name__ == "__main__":
    main()
