# -*- coding: utf-8 -*-
"""
实验15_电脑直连板子8888_回显探针.py -- W5 单板自环的"PC→板"入站方向验证

板子上运行 W5SERVER.c（监听 0.0.0.0:8888，原样回显）后，本脚本从电脑主动连
192.168.1.103:8888，做 3 轮 PING 回显 + 1 次 4096 字节回显，测 RTT 与吞吐。
这一步验证"板作为 TCP 服务器被局域网主机连接"的方向（明天 B 板连 A 板同机制）。

用法：
    py -3 实验15_电脑直连板子8888_回显探针.py [--host 192.168.1.103] [--port 8888] [--out 日志路径]

作者：DSH AI（2026-11-11，W5 实验）
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
    ap.add_argument('--host', default='192.168.1.103')
    ap.add_argument('--port', type=int, default=8888)
    ap.add_argument('--out', default=None)
    ap.add_argument('--timeout', type=float, default=120.0, help='等待服务器就绪的总秒数')
    args = ap.parse_args()

    out = open(args.out, 'a', encoding='utf-8') if args.out else None

    def log(msg):
        text = '[%s] %s' % (now(), msg)
        print(text, flush=True)
        if out:
            out.write(text + '\n')
            out.flush()

    log('probe start: target %s:%d, wait up to %.0fs' % (args.host, args.port, args.timeout))

    # 1) 等板子服务器就绪（用户运行 W5SERVER.c 需要一点时间）
    sock = None
    t0 = time.time()
    while time.time() - t0 < args.timeout:
        try:
            s = socket.create_connection((args.host, args.port), timeout=3.0)
            sock = s
            log('CONNECTED to %s:%d after %.1fs' % (args.host, args.port, time.time() - t0))
            break
        except OSError as e:
            log('connect not ready (%s), retry in 2s' % e)
            time.sleep(2)
    if sock is None:
        log('FAILED: server not reachable within %.0fs' % args.timeout)
        if out:
            out.close()
        return 2

    sock.settimeout(10.0)
    try:
        # 2) 3 轮 PING 回显
        ok = 0
        for i in range(1, 4):
            msg = ('PCPROBE %d\n' % i).encode()
            t = time.time()
            sock.sendall(msg)
            data = sock.recv(len(msg))
            rtt = (time.time() - t) * 1000.0
            if data == msg:
                ok += 1
                log('PING %d ok rtt=%.2fms echo=%r' % (i, rtt, data))
            else:
                log('PING %d MISMATCH rtt=%.2fms echo=%r expect=%r' % (i, rtt, data, msg))
            time.sleep(0.2)

        # 3) 4096 字节整块回显
        big = b'B' * 4096
        t = time.time()
        sock.sendall(big)
        got = b''
        while len(got) < len(big):
            chunk = sock.recv(4096)
            if not chunk:
                break
            got += chunk
        dt = time.time() - t
        if got == big:
            kbps = (len(big) * 2 * 8 / 1000.0) / (dt if dt > 0 else 0.001)
            log('BIG echo 4096 bytes ok, round-trip %.1fms, ~%.1f kbps(双向)' % (dt * 1000.0, kbps))
        else:
            log('BIG echo FAILED got=%d/4096' % len(got))

        log('probe done: ping_ok=%d/3' % ok)
    finally:
        sock.close()
        if out:
            out.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
