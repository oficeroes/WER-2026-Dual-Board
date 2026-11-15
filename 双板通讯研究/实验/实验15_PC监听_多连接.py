# -*- coding: utf-8 -*-
"""
实验15_PC监听_多连接.py -- W5 两板直连实验的 PC 侧观测点（多连接版）

两块板都会主动连本机 12345：A 板 server 报"监听/收到 B 连接/回显"，B 板 client
报"连接结果/PING 延迟/吞吐"。本脚本为每个连接开一个线程并发收，逐行落盘。

用法：
    py -3 实验15_PC监听_多连接.py [--port 12345] [--out 日志路径] [--timeout 1800]

作者：DSH AI（2026-11-11，W5 实验）
"""
import argparse
import datetime
import socket
import sys
import threading
import time


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=12345)
    ap.add_argument('--out', default=None, help='日志落盘路径（默认不落盘）')
    ap.add_argument('--timeout', type=float, default=1800.0, help='总等待秒数')
    args = ap.parse_args()

    lock = threading.Lock()
    out = None
    if args.out:
        out = open(args.out, 'a', encoding='utf-8')

    def emit(label, line):
        text = '[%s] %s%s' % (now(), label, line)
        with lock:
            print(text, flush=True)
            if out:
                out.write(text + '\n')
                out.flush()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', args.port))
    srv.listen(8)
    srv.settimeout(1.0)
    emit('', 'listening on 0.0.0.0:%d (timeout %.0fs)' % (args.port, args.timeout))

    deadline = time.time() + args.timeout
    stop = threading.Event()

    def handle(conn, addr):
        label = '%s:%d ' % (addr[0], addr[1])
        emit(label, 'CONNECTED')
        buf = b''
        try:
            conn.settimeout(5.0)
            while not stop.is_set():
                try:
                    data = conn.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not data:
                    break
                buf += data
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    emit(label, line.decode('utf-8', 'replace'))
        finally:
            if buf:
                emit(label, buf.decode('utf-8', 'replace'))
            emit(label, 'CLOSED')
            conn.close()

    try:
        while time.time() < deadline:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            t = threading.Thread(target=handle, args=(conn, addr), daemon=True)
            t.start()
    finally:
        stop.set()
        srv.close()
        emit('', 'listener stop')
        if out:
            out.close()


if __name__ == '__main__':
    sys.exit(main())
