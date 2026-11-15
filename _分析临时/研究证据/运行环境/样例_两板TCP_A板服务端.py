#<SKCON9><WiFi><NetServerA>
# =====================================================================
# 两板通讯 · A 板 TCP 服务端（WiFi 直连方案，前提：机器人 Python 可 import socket）
# 状态：【待真机验证】— 先跑 探测_import与环境.py，确认 socket 可用 + 拿到两板 IP。
# 协议：文本行协议，B 板发 "B,<seq>,<value>\n"，A 板回 "A,<seq>,OK\n"
# 下载方式：官方 AbilixScratch3.0 → 代码模式 → 粘贴 → 程序名 NetServerA → 下载
# 运行：机器人屏幕“我的程序”→ NetServerA
# 说明：官方生成代码只有单入口 main()；需要并发时自己开 threading 线程（官方模板也 import threading）。
# =====================================================================

import time
import threading
import libstarpy

robot = Robot()

PORT = 8866          # 自定义端口，避开官方 10086/8890/7777/9999
EE_PEER_VALUE = 100  # 把 B 板最新值写到 EEPROM 100，便于屏幕查看

SOCK_OK = True
try:
    import socket
except Exception as _e:
    SOCK_OK = False
    _IMPORT_ERR = _e


def log(msg):
    try:
        robot.print(msg)
    except Exception:
        pass


def handle(conn):
    """每条连接一个线程；行协议 + 接收缓冲 + 超时。"""
    conn.settimeout(2.0)
    buf = b""
    try:
        while True:
            try:
                data = conn.recv(256)
            except socket.timeout:
                continue
            except Exception:
                break
            if not data:
                break
            buf += data
            if len(buf) > 4096:            # 防脏数据撑爆
                buf = b""
                continue
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                parts = line.split(b",")
                seq = parts[1].decode("ascii") if len(parts) > 1 else "0"
                value = 0
                if len(parts) > 2:
                    try:
                        value = int(parts[2])
                    except Exception:
                        value = 0
                robot.set_ee(EE_PEER_VALUE, value)
                log("A recv seq=%s value=%d" % (seq, value))
                try:
                    conn.sendall(("A," + seq + ",OK\n").encode("ascii"))
                except Exception:
                    break
    finally:
        try:
            conn.close()
        except Exception:
            pass


def serve():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(2)
    log("A listen on %d" % PORT)
    while True:
        try:
            conn, addr = srv.accept()
            log("A accept %s:%d" % (addr[0], addr[1]))
            t = threading.Thread(target=handle, args=(conn,))
            t.daemon = True
            t.start()
        except Exception as e:
            log("A accept err: %s" % e)
            time.sleep(0.5)


def main():
    if not SOCK_OK:
        log("socket NOT available: %s" % _IMPORT_ERR)
        log("A 板请改用 PC 中转/其他方案（见分报告）")
        return
    t = threading.Thread(target=serve)
    t.daemon = True
    t.start()
    n = 0
    while True:                 # 主线程做自己的机器人任务，不阻塞通讯线程
        n += 1
        try:
            robot.set_ee(1, n % 1000)
        except Exception:
            pass
        time.sleep(0.5)


main()
