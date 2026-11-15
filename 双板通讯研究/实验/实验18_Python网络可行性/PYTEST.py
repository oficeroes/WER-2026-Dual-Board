#<SKCON9><WiFi><PYTEST>
# 实验18 步骤2：在真机上测 Python 能力边界（屏幕 + 文件双通道输出）。
# 目的：为「双板通讯积木」确定 Python 能否 os.system 起子进程 + 现场 gcc 编译 + 执行自编译 C 助手。
# 兼容 Python 3.4（不用 f-string）。
import sys
import os
import time
import libstarpy

robot = Robot()  # Robot 由控制器运行时注入（说明书中明确：不是 libstarpy 的属性，也不能自己定义）
TMP = "/sdcard/Abilix/tmp"
ALL = TMP + "/pytest_all.txt"
PCIP = "192.168.1.105"
PCPORT = 12345

CCODE = r'''
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/select.h>
#include <sys/time.h>

static int try_connect(const char *ip, int port, int timeout_ms) {
    struct sockaddr_in a;
    int s, rc, err = 0, fl;
    socklen_t elen = sizeof(err);
    fd_set wfds;
    struct timeval tv;
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons((unsigned short)port);
    a.sin_addr.s_addr = inet_addr(ip);
    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) return -1;
    fl = fcntl(s, F_GETFL, 0);
    fcntl(s, F_SETFL, fl | O_NONBLOCK);
    rc = connect(s, (struct sockaddr *)&a, sizeof(a));
    if (rc == 0) return s;
    if (errno != EINPROGRESS) { close(s); return -2; }
    FD_ZERO(&wfds); FD_SET(s, &wfds);
    tv.tv_sec = timeout_ms / 1000; tv.tv_usec = (timeout_ms % 1000) * 1000;
    rc = select(s + 1, NULL, &wfds, NULL, &tv);
    if (rc <= 0) { close(s); return -3; }
    if (getsockopt(s, SOL_SOCKET, SO_ERROR, &err, &elen) != 0 || err != 0) { close(s); return -4; }
    return s;
}

int main(void) {
    int s = try_connect("192.168.1.105", 12345, 5000);
    if (s >= 0) {
        const char *m = "PYTEST-C helo-from-child\n";
        (void)!send(s, m, strlen(m), 0);
        close(s);
        return 0;
    }
    return 3;
}
'''

lines = []


def P(msg):
    s = str(msg)
    lines.append(s)
    try:
        robot.print(s)
    except Exception:
        pass


def w(path, s):
    try:
        f = open(path, "w")
        f.write(s)
        f.close()
        return True
    except Exception as e:
        return "ERR:%s" % e


def rd(path):
    try:
        f = open(path, "r")
        d = f.read()
        f.close()
        return d
    except Exception as e:
        return "ERR:%s" % e


P("PYTEST start")
P("1 ver=%s" % sys.version.replace("\n", " ")[:60])
P("2 print-ok")
P("3 write=%s" % w(TMP + "/pytest_a.txt", "abc"))
rc = os.system("echo sysok > " + TMP + "/pytest_sys.txt")
P("4 ossystem=%d" % rc)
P("5 read=%r" % rd(TMP + "/pytest_sys.txt").strip())
try:
    d2 = os.popen("echo popenok").read().strip()
except Exception as e:
    d2 = "ERR:%s" % e
P("6 popen=%r" % d2)
P("7 fork=%s pipe=%s execv=%s dup2=%s" % (hasattr(os, "fork"), hasattr(os, "pipe"), hasattr(os, "execv"), hasattr(os, "dup2")))
gcc = "/system/xbin/gcc4.8.2/bin/arm-linux-androideabi-gcc"
P("8 gcc=%s" % os.path.exists(gcc))
P("9 writec=%s" % w(TMP + "/pytest_cli.c", CCODE))
cmd = ("export PATH=/system/xbin/gcc4.8.2/bin:$PATH; export TMPDIR=%s; cd %s; "
       "arm-linux-androideabi-gcc pytest_cli.c -pie -fPIE -o pytest_cli > pytest_gcc.log 2>&1; "
       "echo gcc_rc=$? >> pytest_gcc.log; ./pytest_cli >> pytest_cli.log 2>&1; echo run_rc=$? >> pytest_cli.log") % (TMP, TMP)
rc2 = os.system(cmd)
P("10 chainrc=%d" % rc2)
gl = rd(TMP + "/pytest_gcc.log").strip().replace("\n", " | ")[:150]
cl = rd(TMP + "/pytest_cli.log").strip().replace("\n", " | ")[:120]
P("11 gcclog=%r" % gl)
P("12 clilog=%r" % cl)
w(ALL, "\n".join(lines) + "\n")
P("PYTEST done")
time.sleep(1)
