#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc_typing_server.py —— PC 端「打字上屏」桥

作用：
  1) 在 127.0.0.1:8000 提供网页（typing.html），网页上打字；
  2) 网页把文字 POST 到本服务，本服务通过 TCP 把文字发给机器人 192.168.1.103:9001；
  3) 机器人上运行的 PCTEXT.c 收到后显示在机身屏幕上。

用法（Windows 双击 启动打字演示.cmd 即可）：
  py -3 pc_typing_server.py --robot 192.168.1.103 --open
"""
import argparse
import json
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE_DIR = __import__("os").path.dirname(__import__("os").path.abspath(__file__))

QUEUE = []                 # 待发送的 bytes 行
QUEUE_LOCK = threading.Lock()
QUEUE_MAX = 200

STATE = {
    "connected": False,
    "sent": 0,
    "error": "",
    "last": "",
    "robot": "",
}
STATE_LOCK = threading.Lock()


def log(msg):
    print("[typing] " + msg, flush=True)


def enqueue(line):
    data = line.encode("utf-8", "replace") + b"\n"
    with QUEUE_LOCK:
        QUEUE.append(data)
        if len(QUEUE) > QUEUE_MAX:
            del QUEUE[: len(QUEUE) - QUEUE_MAX]


def clean_text(text):
    text = (text or "").replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return text[:3000]


def sender_loop(robot_ip, robot_port):
    while True:
        sock = None
        try:
            sock = socket.create_connection((robot_ip, robot_port), timeout=3)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with STATE_LOCK:
                STATE["connected"] = True
                STATE["error"] = ""
            log("机器人已连接 %s:%d" % (robot_ip, robot_port))
            while True:
                with QUEUE_LOCK:
                    item = QUEUE.pop(0) if QUEUE else None
                if item is None:
                    time.sleep(0.01)
                    continue
                sock.sendall(item)
                with STATE_LOCK:
                    STATE["sent"] += 1
                    STATE["last"] = item[:160].decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            with STATE_LOCK:
                STATE["connected"] = False
                STATE["error"] = "%s: %s" % (type(exc).__name__, exc)
            time.sleep(1.5)
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass


class Handler(BaseHTTPRequestHandler):
    server_version = "PCTyping/1.0"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/typing.html"):
            try:
                with open(BASE_DIR + "/typing.html", "rb") as fh:
                    self._send(200, fh.read(), "text/html; charset=utf-8")
            except OSError:
                self._send(500, "typing.html 不存在")
            return
        if path == "/status":
            with STATE_LOCK:
                info = dict(STATE)
            with QUEUE_LOCK:
                info["queued"] = len(QUEUE)
            info["ok"] = True
            self._send(200, json.dumps(info, ensure_ascii=False))
            return
        if path == "/favicon.ico":
            self._send(204, b"")
            return
        self._send(404, "not found")

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b"{}"
            body = json.loads(raw.decode("utf-8", "replace") or "{}")
        except (ValueError, json.JSONDecodeError):
            self._send(400, '{"ok": false, "error": "bad json"}')
            return

        if path == "/send":
            text = clean_text(body.get("text", ""))
            mode = (body.get("mode") or "T").upper()[:1]
            if mode not in ("T", "A"):
                mode = "T"
            enqueue("%s %s" % (mode, text))
            self._send(200, '{"ok": true}')
            return
        if path == "/clear":
            enqueue("C")
            self._send(200, '{"ok": true}')
            return
        self._send(404, "not found")

    def log_message(self, fmt, *args):  # 静默默认访问日志
        return


def main():
    parser = argparse.ArgumentParser(description="PC 打字上屏桥")
    parser.add_argument("--robot", default="192.168.1.103", help="机器人 IP")
    parser.add_argument("--robot-port", type=int, default=9001, help="机器人端口")
    parser.add_argument("--http-port", type=int, default=8000, help="本机网页端口")
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    args = parser.parse_args()

    with STATE_LOCK:
        STATE["robot"] = "%s:%d" % (args.robot, args.robot_port)

    threading.Thread(
        target=sender_loop,
        args=(args.robot, args.robot_port),
        daemon=True,
    ).start()

    url = "http://127.0.0.1:%d/typing.html" % args.http_port
    server = ThreadingHTTPServer(("127.0.0.1", args.http_port), Handler)
    log("网页地址: " + url)
    log("目标机器人: %s:%d" % (args.robot, args.robot_port))
    log("如果机器人还没运行 PCTEXT.c，请先在机器人屏幕上运行它。")
    if args.open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
