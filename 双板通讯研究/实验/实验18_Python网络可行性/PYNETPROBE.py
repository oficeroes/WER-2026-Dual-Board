#<SKCON9><WiFi><PYNETPROBE>
# -*- coding: utf-8 -*-
# 实验18：机器人 Python 端「网络/子进程/编译执行」能力探测（Python 3.4 兼容）
#
# 目的（决定「双板通讯」积木的技术路线）：
#   T1 os.system / os.popen / fork+pipe 是否可用（能否起子进程）
#   T2 机器人自带 gcc4.8.2 能否编译出可执行文件
#   T3 编译产物能否执行（/sdcard vs /data/data/com.abilix.controller/files）
#   T4 编译出的 C 程序能否 TCP 连到 PC（证明子进程有网络权限）
#   T5 顺带复核 import 能力（socket/ctypes/math/random/subprocess/select/...）
#
# 结果：写入 /sdcard/Abilix/tmp/pynetprobe.txt，同时逐行 robot.print 到机器人屏幕；
#       若 T3/T4 成功，程序自动把结果文件发到 PC 监听 192.168.47.192:12345。

import os
import sys
import time
import threading

PC_IP = "192.168.47.192"
PC_PORT = 12345
TMP = "/sdcard/Abilix/tmp"
APPDIR = "/data/data/com.abilix.controller/files"
OUT = TMP + "/pynetprobe.txt"

LINES = []
ROBOT = None
try:
    import libstarpy
    ROBOT = Robot()
except Exception:
    ROBOT = None


def say(s):
    try:
        if ROBOT is not None:
            ROBOT.print(str(s))
    except Exception:
        pass


def rec(k, v):
    s = str(k) + " = " + str(v)
    LINES.append(s)
    say("P| " + s)
    # 每记一条就落盘，程序中途被杀也能保留
    try:
        f = open(OUT, "w")
        f.write("\n".join(LINES) + "\n")
        f.close()
    except Exception:
        pass


C_HELLO = """
#include <stdio.h>
int main(void) {
    printf("hello from robot gcc\\n");
    return 0;
}
"""

C_SENDER = """
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

int main(int argc, char **argv) {
    const char *ip = (argc > 1) ? argv[1] : "127.0.0.1";
    int port = (argc > 2) ? atoi(argv[2]) : 12345;
    const char *path = (argc > 3) ? argv[3] : "/sdcard/Abilix/tmp/pynetprobe.txt";
    struct sockaddr_in a;
    int s, n, total = 0;
    char buf[4096];
    FILE *f;
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons((unsigned short)port);
    a.sin_addr.s_addr = inet_addr(ip);
    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) { printf("socket fail\\n"); return 2; }
    if (connect(s, (struct sockaddr *)&a, sizeof(a)) < 0) { printf("connect fail\\n"); close(s); return 3; }
    f = fopen(path, "rb");
    if (!f) { printf("open fail\\n"); close(s); return 4; }
    while ((n = (int)fread(buf, 1, sizeof(buf), f)) > 0) {
        int off = 0;
        while (off < n) {
            int w = (int)send(s, buf + off, n - off, 0);
            if (w <= 0) { break; }
            off += w;
        }
        total += n;
    }
    fclose(f);
    printf("sent %d bytes\\n", total);
    shutdown(s, SHUT_WR);
    close(s);
    return 0;
}
"""


def write_text(path, text, mode="w"):
    f = open(path, mode)
    f.write(text)
    f.close()


def read_text(path, limit=3000):
    try:
        f = open(path, "r")
        d = f.read()
        f.close()
        return d[:limit]
    except Exception as e:
        return "READFAIL " + repr(e)


def sh(cmd):
    try:
        rc = os.system(cmd)
        return rc
    except Exception as e:
        return "EXC " + repr(e)


def main():
    say("=== PYNETPROBE start ===")
    rec("sys.version", sys.version.replace("\n", " ")[:90])
    rec("sys.executable", getattr(sys, "executable", "?"))
    rec("sys.path", str(getattr(sys, "path", "?"))[:300])
    rec("cwd", os.getcwd())
    rec("uid_gid", str(os.getuid()) + "/" + str(os.getgid()))
    rec("uname", str(os.uname()[:4]) if hasattr(os, "uname") else "?")
    rec("PATH", os.environ.get("PATH", "?")[:160])
    rec("TMP_exists", os.path.exists(TMP))
    rec("APPDIR_exists", os.path.exists(APPDIR))

    # ---- T5: import 能力复核 ----
    mods = [
        "time", "sys", "os", "threading", "struct", "json", "math", "random",
        "socket", "ctypes", "subprocess", "select", "errno", "fcntl", "array",
        "hashlib", "binascii", "re", "io", "queue", "tempfile", "signal",
        "traceback", "marshal", "zlib", "base64", "collections", "itertools",
    ]
    ok = []
    bad = []
    for m in mods:
        try:
            __import__(m)
            ok.append(m)
        except Exception:
            bad.append(m)
    rec("import_ok", ",".join(ok))
    rec("import_fail", ",".join(bad))

    # ---- T1: os 能力 ----
    attrs = ["system", "popen", "fork", "pipe", "dup2", "execv", "execvp",
             "forkpty", "chmod", "open", "read", "write", "close", "waitpid",
             "kill", "getpid", "listdir", "rename", "remove", "mkdir", "stat",
             "utime", "getcwd", "getuid"]
    have = []
    miss = []
    for a in attrs:
        if hasattr(os, a):
            have.append(a)
        else:
            miss.append(a)
    rec("os_has", ",".join(have))
    rec("os_missing", ",".join(miss))
    rec("has_open_builtin", str(hasattr(__builtins__, "open") if hasattr(__builtins__, "__getitem__") else True))

    # ---- T1a: os.system 基础测试 ----
    try:
        rc = sh("echo sysook > " + TMP + "/sh_test.txt 2>&1")
        rec("system_echo_rc", rc)
        rec("system_echo_out", read_text(TMP + "/sh_test.txt", 200).strip())
    except Exception as e:
        rec("system_echo_exc", repr(e))

    # ---- T1b: os.popen ----
    try:
        p = os.popen("echo popenok")
        d = p.read()
        p.close()
        rec("popen_out", str(d).strip())
    except Exception as e:
        rec("popen_exc", repr(e))

    # ---- T1c: fork + pipe ----
    try:
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(r)
                os.write(w, b"child-ok")
                os._exit(0)
            except Exception:
                os._exit(1)
        else:
            os.close(w)
            d = os.read(r, 64)
            os.close(r)
            os.waitpid(pid, 0)
            rec("fork_pipe", "ok:" + repr(d))
    except Exception as e:
        rec("fork_pipe_exc", repr(e))

    # ---- T1d: threading ----
    try:
        box = []

        def worker():
            time.sleep(0.05)
            box.append(1)

        t = threading.Thread(target=worker)
        t.start()
        t.join(2.0)
        rec("thread_ok", len(box))
    except Exception as e:
        rec("thread_exc", repr(e))

    # ---- 写文件能力 ----
    for name, path in [("tmp", TMP + "/write_test.txt"), ("appdir", APPDIR + "/write_test.txt")]:
        try:
            write_text(path, "writetest " + name)
            rec("write_" + name, read_text(path, 100).strip())
        except Exception as e:
            rec("write_" + name + "_exc", repr(e))

    # ---- T2: gcc 编译 ----
    gcc = "/system/xbin/gcc4.8.2/bin/arm-linux-androideabi-gcc"
    try:
        rec("gcc_exists", os.path.exists(gcc))
        rec("gcc_dir", str(os.listdir("/system/xbin/gcc4.8.2/bin"))[:200] if os.path.exists("/system/xbin/gcc4.8.2/bin") else "?")
    except Exception as e:
        rec("gcc_list_exc", repr(e))

    try:
        write_text(TMP + "/hello.c", C_HELLO)
        cmd = ("export PATH=/system/xbin/gcc4.8.2/bin:$PATH; export TMPDIR=" + TMP +
               "; cd " + TMP + "; arm-linux-androideabi-gcc hello.c -pie -fPIE -o hello1"
               " >gcc_hello.log 2>&1; echo rc=$? >>gcc_hello.log")
        rec("gcc_hello_rc", sh(cmd))
        rec("gcc_hello_log", read_text(TMP + "/gcc_hello.log", 800).replace("\n", " | "))
    except Exception as e:
        rec("gcc_hello_exc", repr(e))

    # ---- T3: 执行 hello（/sdcard） ----
    try:
        sh("cd " + TMP + "; ./hello1 > hello1.out 2>&1; echo rc=$? >> hello1.out")
        rec("exec_sdcard", read_text(TMP + "/hello1.out", 300).replace("\n", " | "))
    except Exception as e:
        rec("exec_sdcard_exc", repr(e))

    # ---- T3b: 复制到 app 私有目录再执行 ----
    try:
        rec("cp_to_app_rc", sh("cp " + TMP + "/hello1 " + APPDIR + "/hello1 2>" + TMP + "/cp.err; echo $?"))
        rec("cp_to_app_err", read_text(TMP + "/cp.err", 200).replace("\n", " "))
        sh("cd " + APPDIR + "; ./hello1 > hello1.out 2>&1; echo rc=$? >> hello1.out")
        rec("exec_appdir", read_text(APPDIR + "/hello1.out", 300).replace("\n", " | "))
    except Exception as e:
        rec("exec_appdir_exc", repr(e))

    # ---- T4: 编译网络 sender 并尝试 TCP 连 PC ----
    try:
        write_text(TMP + "/wlnet.c", C_SENDER)
        cmd = ("export PATH=/system/xbin/gcc4.8.2/bin:$PATH; export TMPDIR=" + TMP +
               "; cd " + TMP + "; arm-linux-androideabi-gcc wlnet.c -pie -fPIE -o wlnet"
               " >gcc_wlnet.log 2>&1; echo rc=$? >>gcc_wlnet.log")
        rec("gcc_wlnet_rc", sh(cmd))
        rec("gcc_wlnet_log", read_text(TMP + "/gcc_wlnet.log", 800).replace("\n", " | "))
    except Exception as e:
        rec("gcc_wlnet_exc", repr(e))

    # 先发一次（此时文件里还没有发送结果）
    try:
        sh("cd " + TMP + "; ./wlnet " + PC_IP + " " + str(PC_PORT) + " " + OUT +
           " > wlnet_sdcard.out 2>&1; echo rc=$? >> wlnet_sdcard.out")
        rec("send_sdcard", read_text(TMP + "/wlnet_sdcard.out", 300).replace("\n", " | "))
    except Exception as e:
        rec("send_sdcard_exc", repr(e))

    # 再试 app 私有目录的副本（若上一个成功，这次能发完整版）
    try:
        sh("cp " + TMP + "/wlnet " + APPDIR + "/wlnet 2>/dev/null")
        sh("cd " + APPDIR + "; ./wlnet " + PC_IP + " " + str(PC_PORT) + " " + OUT +
           " > wlnet_app.out 2>&1; echo rc=$? >> wlnet_app.out")
        rec("send_appdir", read_text(APPDIR + "/wlnet_app.out", 300).replace("\n", " | "))
    except Exception as e:
        rec("send_appdir_exc", repr(e))

    rec("PROBE_DONE", 1)
    say("=== PYNETPROBE done, results in " + OUT + " ===")


main()
