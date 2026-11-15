#<SKCON9><WiFi><PYTEST2>
# 实验18 步骤3：验证「编译产物写到 App 私有目录 → 执行 → 联网」+ fork/pipe 子进程 IPC。
# 兼容 Python 3.4（不用 f-string）。
import sys
import os
import time
import libstarpy

robot = Robot()  # 由控制器运行时注入

TMP = "/sdcard/Abilix/tmp"
APP = "/data/data/com.abilix.controller/files"
PCIP = "192.168.1.105"
PCPORT = 12345
BIN = APP + "/wltest"
SRC = APP + "/wltest.c"

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

static int udp_send(const char *ip, int port, const char *msg) {
    struct sockaddr_in a;
    int s;
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons((unsigned short)port);
    a.sin_addr.s_addr = inet_addr(ip);
    s = socket(AF_INET, SOCK_DGRAM, 0);
    if (s < 0) return -1;
    if (sendto(s, msg, strlen(msg), 0, (struct sockaddr *)&a, sizeof(a)) < 0) { close(s); return -2; }
    close(s);
    return 0;
}

int main(int argc, char **argv) {
    const char *tcpmsg = "PYTEST2-C tcp-ok\n";
    const char *udpmsg = "PYTEST2-U udp-ok\n";
    int s = try_connect("192.168.1.105", 12345, 5000);
    if (s >= 0) {
        (void)!send(s, tcpmsg, strlen(tcpmsg), 0);
        close(s);
    }
    (void)udp_send("192.168.1.105", 12345, udpmsg);
    printf("child-stdout-ok\n");
    fflush(stdout);
    return 0;
}
'''

out = []


def P(msg):
    s = str(msg)
    out.append(s)
    try:
        robot.print("\n" + s)
    except Exception:
        pass


def wr(path, s):
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


P("PYTEST2 start")
P("a0 cwd=%s" % os.getcwd())
P("a1 appdir_exists=%s tmp_exists=%s" % (os.path.exists(APP), os.path.exists(TMP)))
P("a2 srcwrite=%s" % wr(SRC, CCODE))
cmd = ("export PATH=/system/xbin/gcc4.8.2/bin:$PATH; export TMPDIR=%s; cd %s; "
       "arm-linux-androideabi-gcc wltest.c -pie -fPIE -o wltest > gcc2.log 2>&1; "
       "echo gcc_rc=$? >> gcc2.log; chmod 755 wltest 2>/dev/null; echo chmod_rc=$? >> gcc2.log"
       ) % (TMP, APP)
rc = os.system(cmd)
P("a3 chain_rc=%d" % rc)
P("a4 gcc=%r" % rd(APP + "/gcc2.log").strip().replace("\n", " | ")[:180])
binexists = os.path.exists(BIN)
binsize = -1
if binexists:
    try:
        binsize = os.path.getsize(BIN)
    except Exception:
        pass
P("a5 binexists=%s size=%s" % (binexists, binsize))
if binexists:
    rc2 = os.system(BIN)
    P("a6 sysexec_rc=%d" % rc2)
    try:
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(r)
                os.dup2(w, 1)
                os.close(w)
                os.execv(BIN, [BIN])
            except Exception:
                pass
            os._exit(127)
        os.close(w)
        time.sleep(1.2)
        data = os.read(r, 200)
        os.close(r)
        os.waitpid(pid, 0)
        txt = data.decode("utf-8", "replace").strip()
        P("a7 forkpipe=%r" % txt)
    except Exception as e:
        P("a7 forkpipe=ERR:%s" % e)
else:
    P("a6 skipped (no binary)")

wr(TMP + "/pytest2_all.txt", "\n".join(out) + "\n")
P("PYTEST2 done")
time.sleep(1)
