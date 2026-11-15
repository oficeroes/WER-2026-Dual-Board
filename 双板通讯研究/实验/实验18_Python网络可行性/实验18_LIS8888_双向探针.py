# -*- coding: utf-8 -*-
"""LIS8888 双向探针：一边监听 12345（收板子出站），一边主动连 2 号机 192.168.1.103:8888。
判读：
  - 若连上 8888 并收到 LIS8888 hello ... outbound=1/0 → 程序在跑；outbound=1 表示板→电脑出站也通；
  - 若 12345 收到 LIS outbound-ok → 出站通；
  - 若 8888 连不上 → 程序没跑起来（编译/运行问题）或 PC→板 TCP 被挡。
用法：python 实验18_LIS8888_双向探针.py --out <日志> [--board 192.168.1.103] [--seconds 180]
"""
import argparse
import socket
import threading
import time


def listener(port, out_path, stop_ev):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(8)
    srv.settimeout(1.0)

    def log(line):
        stamp = time.strftime("%H:%M:%S")
        msg = "[%s] %s" % (stamp, line)
        print(msg, flush=True)
        try:
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    log("listening on 0.0.0.0:%d (outbound probe)" % port)
    while not stop_ev.is_set():
        try:
            conn, addr = srv.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        conn.settimeout(3.0)
        try:
            data = conn.recv(4096)
        except Exception:
            data = b""
        log("OUTBOUND-OK from %s:%d data=%r" % (addr[0], addr[1], data[:200]))
        conn.close()
    srv.close()
    log("listener stopped")


def poll_board(ip, port, out_path, stop_ev, seconds):
    stamp = lambda: time.strftime("%H:%M:%S")
    deadline = time.time() + seconds
    attempt = 0
    seen = 0
    while time.time() < deadline and not stop_ev.is_set():
        attempt += 1
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        try:
            s.connect((ip, port))
            s.settimeout(3.0)
            data = s.recv(4096)
            seen += 1
            msg = "[%s] 8888-CONNECT-OK #%d data=%r" % (stamp(), seen, data[:300])
            print(msg, flush=True)
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
            s.close()
        except Exception as e:
            msg = "[%s] 8888 attempt=%d %s" % (stamp(), attempt, type(e).__name__)
            print(msg, flush=True)
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
            s.close()
        time.sleep(2)
    return seen > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default="192.168.1.103")
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--out", default="lis8888_probe.log")
    ap.add_argument("--seconds", type=int, default=180)
    args = ap.parse_args()
    stop_ev = threading.Event()
    t = threading.Thread(target=listener, args=(12345, args.out, stop_ev), daemon=True)
    t.start()
    ok = poll_board(args.board, args.port, args.out, stop_ev, args.seconds)
    if ok:
        print("RESULT: board 8888 reachable -> program is running", flush=True)
        # 再监听 10 秒等可能的出站连接
        time.sleep(10)
    else:
        print("RESULT: board 8888 NOT reachable within %ds" % args.seconds, flush=True)
    stop_ev.set()
    time.sleep(1.5)


if __name__ == "__main__":
    main()
