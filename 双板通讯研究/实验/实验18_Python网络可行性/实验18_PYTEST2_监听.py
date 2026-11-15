# 实验18 PYTEST2 监听：同时监听 TCP 12345 与 UDP 12345，验证机器人 Python 拉起的 C 助手能否联网。
# 用法: py -3 实验18_PYTEST2_监听.py [--port 12345] [--out 日志路径] [--seconds 300]
import argparse
import os
import socket
import threading
import time


def log(fp, msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    if fp is not None:
        try:
            fp.write(line + "\n")
            fp.flush()
        except Exception:
            pass


def tcp_server(port, fp, stop):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(8)
    srv.settimeout(1.0)
    log(fp, "TCP listening on 0.0.0.0:%d" % port)
    while not stop.is_set():
        try:
            c, addr = srv.accept()
        except socket.timeout:
            continue
        except Exception as e:
            log(fp, "TCP accept error: %r" % (e,))
            continue
        try:
            c.settimeout(3.0)
            data = c.recv(4096)
            log(fp, "TCP-IN from %s:%d data=%r" % (addr[0], addr[1], data))
            try:
                c.sendall(b"ACK tcp\n")
            except Exception:
                pass
        except Exception as e:
            log(fp, "TCP recv error %r" % (e,))
        finally:
            try:
                c.close()
            except Exception:
                pass
    srv.close()


def udp_server(port, fp, stop):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.settimeout(1.0)
    log(fp, "UDP listening on 0.0.0.0:%d" % port)
    while not stop.is_set():
        try:
            data, addr = s.recvfrom(4096)
        except socket.timeout:
            continue
        except Exception as e:
            log(fp, "UDP recv error %r" % (e,))
            continue
        log(fp, "UDP-IN from %s:%d data=%r" % (addr[0], addr[1], data))
    s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=12345)
    ap.add_argument("--out", default="")
    ap.add_argument("--seconds", type=int, default=300)
    args = ap.parse_args()
    fp = None
    if args.out:
        d = os.path.dirname(args.out)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        fp = open(args.out, "a", encoding="utf-8")
    stop = threading.Event()
    t1 = threading.Thread(target=tcp_server, args=(args.port, fp, stop), daemon=True)
    t2 = threading.Thread(target=udp_server, args=(args.port, fp, stop), daemon=True)
    t1.start()
    t2.start()
    log(fp, "listening TCP+UDP on %d, timeout %ds" % (args.port, args.seconds))
    try:
        time.sleep(args.seconds)
    except KeyboardInterrupt:
        pass
    stop.set()
    log(fp, "listener exit")
    if fp is not None:
        fp.close()


if __name__ == "__main__":
    main()
