#<SKCON9><WiFi><ProbeEnv>
# =====================================================================
# SKCON9 机器人端 Python 运行环境探测程序（最小探测，待真机验证）
# 目的：
#   1) 逐项探测 import socket / os / threading / subprocess / ctypes ... 是否可用；
#   2) 探测 libstarpy 暴露了哪些名字（是否有 StarCore/网络类绑定）；
#   3) 探测本机 IP、文件系统可写性、threading 是否真的可跑；
#   4) 所有结论写入 EEPROM 地址 1..40（掉电保存），并 robot.print 到屏幕。
# 用法：
#   官方 AbilixScratch3.0 → 代码模式 → 粘贴本文件全部内容 → 下载到机器人
#   （程序名必须 = ProbeEnv，与文件头 #<SKCON9><WiFi><ProbeEnv> 一致；
#     文件名建议 ProbeEnv.py）
#   然后在机器人屏幕“我的程序”里点击 ProbeEnv 运行（约 3~5 秒）。
# 结果读取（任选）：
#   A. 机器人屏幕 → “读写数据”(EEPROM) 页面：地址 1..40 的值即结果；
#   B. 再下载并运行一次下面的“读回程序”，把 1..40 打印到屏幕上拍照；
#   C. 若后面 ADB/串口 可用，也可从外部读取（见分报告 §C3）。
# 结果编码：
#   1  = 成功/可用        0 或负数 = 失败（-1 import 失败，-2 运行异常）
#   版本号：major*100+minor（如 3.4.x -> 304），micro 单独存
# =====================================================================

import time
import libstarpy

robot = Robot()

EE = {}  # 本地记录，最后统一打印

def save(addr, value):
    EE[addr] = value
    try:
        robot.set_ee(addr, int(value))
    except Exception as e:
        robot.print("set_ee(%d) err: %s" % (addr, e))

def probe_import(addr, name):
    try:
        __import__(name)
        save(addr, 1)
        robot.print("import %-12s OK" % name)
    except Exception as e:
        save(addr, -1)
        robot.print("import %-12s FAIL: %s" % (name, e))

def probe_attr(addr, obj, attr):
    try:
        if hasattr(obj, attr):
            save(addr, 1)
        else:
            save(addr, 0)
    except Exception:
        save(addr, -2)

def main():
    robot.print("=== ProbeEnv start ===")

    # ---- 0. Python 版本（地址 1-3）----
    try:
        import sys
        v = sys.version_info
        save(1, v[0] * 100 + v[1])
        save(2, v[2])
        robot.print("sys.version = " + sys.version)
        robot.print("sys.executable = " + str(getattr(sys, "executable", "?")))
        # sys.path 很长，打印前 200 字符便于截图
        robot.print("sys.path = " + str(sys.path)[:200])
    except Exception as e:
        save(1, -1)
        robot.print("sys FAIL: %s" % e)

    # ---- 1. 标准库 import 探测（地址 10..33）----
    names = [
        (10, "socket"), (11, "os"), (12, "threading"), (13, "time"),
        (14, "sys"), (15, "json"), (16, "struct"), (17, "select"),
        (18, "subprocess"), (19, "errno"), (20, "traceback"),
        (21, "ctypes"), (22, "fcntl"), (23, "signal"), (24, "random"),
        (25, "math"), (26, "hashlib"), (27, "binascii"), (28, "queue"),
        (29, "re"), (30, "io"), (31, "tempfile"), (32, "array"),
        (33, "socketserver"),
    ]
    for addr, mod in names:
        probe_import(addr, mod)
        time.sleep(0.02)

    # ---- 2. libstarpy 形态探测（地址 40..49）----
    probe_attr(40, libstarpy, "Robot")
    probe_attr(41, libstarpy, "log")
    probe_attr(42, libstarpy, "StarCoreFactory")
    probe_attr(43, libstarpy, "SrvGroup")
    probe_attr(44, robot, "get_ee")
    probe_attr(45, robot, "print")
    probe_attr(46, robot, "get_ai")
    try:
        robot.print("libstarpy.__file__ = " + str(getattr(libstarpy, "__file__", "?")))
        robot.print("dir(libstarpy)[:20] = " + str(dir(libstarpy)[:20]))
    except Exception as e:
        robot.print("dir(libstarpy) err: %s" % e)

    # ---- 3. socket 能力与 IP（地址 50..56）----
    try:
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            save(50, 1); s.close()
        except Exception:
            save(50, 0)
        try:
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            u.bind(("", 0))
            save(51, 1)
            # 本机 IP 获取技巧：UDP connect 不发包、不建链
            try:
                u.connect(("8.8.8.8", 80))
                robot.print("LOCAL_IP = " + str(u.getsockname())[:60])
                save(52, 1)
            except Exception as e:
                save(52, 0)
                robot.print("getlocalip FAIL: %s" % e)
            u.close()
        except Exception as e:
            save(51, 0)
            robot.print("udp bind FAIL: %s" % e)
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", 0))
            srv.listen(1)
            save(53, 1)
            robot.print("listen port = %d" % srv.getsockname()[1])
            srv.close()
        except Exception as e:
            save(53, 0)
            robot.print("tcp listen FAIL: %s" % e)
        try:
            robot.print("gethostname = " + str(socket.gethostname())[:60])
            try:
                robot.print("gethostbyname = " + str(socket.gethostbyname(socket.gethostname()))[:60])
            except Exception:
                pass
            save(54, 1)
        except Exception:
            save(54, 0)
        try:
            b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            b.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            save(55, 1)
            b.close()
        except Exception:
            save(55, 0)
    except Exception as e:
        save(50, -1)
        robot.print("socket block FAIL: %s" % e)

    # ---- 4. threading 真实性（地址 60..61）----
    def worker():
        try:
            robot.set_ee(61, 1)
        except Exception:
            pass

    try:
        import threading
        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()
        t.join(2.0)
        # Python3.4: Thread.is_alive 已存在（旧名 isAlive 也在 3.4 保留）
        try:
            alive = t.is_alive()
        except Exception:
            alive = True
        save(60, 1 if not alive else 2)
        robot.print("threading run: join_ok=%d ee61=%d" % (1 if not alive else 2, robot.get_ee(61)))
    except Exception as e:
        save(60, -1)
        robot.print("threading FAIL: %s" % e)

    # ---- 5. 文件系统可写性（地址 70..74）----
    def try_write(path, addr):
        try:
            f = open(path, "w")
            f.write("probe")
            f.close()
            try:
                import os
                os.remove(path)
            except Exception:
                pass
            save(addr, 1)
            robot.print("write %-28s OK" % path)
        except Exception as e:
            save(addr, 0)
            robot.print("write %-28s FAIL: %s" % (path, e))

    try:
        import os
        robot.print("os.getcwd() = " + str(os.getcwd()))
        robot.print("os.listdir('/') = " + str(os.listdir("/"))[:160])
    except Exception as e:
        robot.print("os cwd FAIL: %s" % e)
    try_write("probe_tmp.txt", 70)          # 当前工作目录
    try_write("/sdcard/probe_tmp.txt", 71)  # 外置存储
    try_write("/data/local/tmp/probe_tmp.txt", 72)

    # ---- 6. 收尾 ----
    robot.print("=== ProbeEnv done, see EEPROM 1..74 ===")
    # 注意：不要把耗时操作放在收尾之后；程序结束由机器人控制。

main()
