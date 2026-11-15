# -*- coding: utf-8 -*-
"""
实验14_W4_PC监听.py -- 等待机器人上 W4PROBE.c 程序主动 TCP 连接（验证 C 侧 libc socket）

用法：
    py -3 实验14_W4_PC监听.py [--port 12345] [--out 日志路径] [--timeout 300]

行为：
    监听 0.0.0.0:<port>，直到超时；每收到一个连接就把收到的内容落盘并打印。
    （W4PROBE.c 每 2 秒重试一次、共 30 次，所以本监听器要一直开着等用户去机器人
     屏幕点运行。）

作者：DSH AI（2026-11-11，W4 实验）
"""
import argparse
import datetime
import socket
import sys
import time


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=12345)
    ap.add_argument('--out', default=None, help='日志落盘路径（默认不落盘）')
    ap.add_argument('--timeout', type=float, default=300.0, help='总等待秒数')
    args = ap.parse_args()

    out = None
    if args.out:
        out = open(args.out, 'a', encoding='utf-8')
        out.write('\n===== listener start %s port=%d =====\n' % (now(), args.port))
        out.flush()

    def emit(line):
        print(line, flush=True)
        if out:
            out.write(line + '\n')
            out.flush()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', args.port))
    srv.listen(5)
    srv.settimeout(1.0)
    emit('[%s] listening on 0.0.0.0:%d (timeout %.0fs)' % (now(), args.port, args.timeout))

    deadline = time.time() + args.timeout
    try:
        while time.time() < deadline:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            emit('[%s] ACCEPT from %s:%d' % (now(), addr[0], addr[1]))
            conn.settimeout(5.0)
            chunks = []
            while True:
                try:
                    data = conn.recv(4096)
                except socket.timeout:
                    break
                if not data:
                    break
                chunks.append(data)
            payload = b''.join(chunks)
            emit('[%s] received %d bytes:' % (now(), len(payload)))
            try:
                emit(payload.decode('utf-8', 'replace'))
            except Exception:
                emit(repr(payload))
            conn.close()
    finally:
        srv.close()
        emit('[%s] listener stop' % now())
        if out:
            out.close()


if __name__ == '__main__':
    sys.exit(main())
