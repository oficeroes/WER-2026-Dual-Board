# 双板通讯 prelude v0.1 —— 未来会原样注入到「我的函数」积木工程的 Python 代码里。
# 机器人侧 Python 3.4：不能用 f-string；可用 os/threading/time/atexit。
# 原理：用机器人自带 gcc 把内嵌的 C 网络助手编译到 App 私有目录（/sdcard 是 noexec），
#      fork+execv 拉起它，用两条 pipe 做 IPC；助手负责 UDP 收发（端口 8990）。
import os
import time
import atexit
import threading

_WL_PORT = 8990
_WL_APP = "/data/data/com.abilix.controller/files"
_WL_BIN = _WL_APP + "/wlnet_helper"
_WL_SRC = _WL_APP + "/wlnet_helper.c"
_WL_PID = _WL_APP + "/wlnet_helper.pid"
_WL_TMP = "/sdcard/Abilix/tmp"
_WL_GCC_DIR = "/system/xbin/gcc4.8.2/bin"

_WL_C_SRC = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/select.h>
#include <sys/time.h>

#define MAXLINE 2048

static int g_port = 8990;

static int wl_sendto(const char *ip, int port, const char *msg) {
    struct sockaddr_in a;
    int s, rc;
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons((unsigned short)port);
    a.sin_addr.s_addr = inet_addr(ip);
    if (a.sin_addr.s_addr == INADDR_NONE && strcmp(ip, "255.255.255.255") != 0) return -2;
    s = socket(AF_INET, SOCK_DGRAM, 0);
    if (s < 0) return -1;
    rc = sendto(s, msg, strlen(msg), 0, (struct sockaddr *)&a, sizeof(a));
    close(s);
    if (rc < 0) return -3;
    return 0;
}

int main(int argc, char **argv) {
    int us, n, i, llen = 0, idle = 0;
    char lbuf[MAXLINE];
    char buf[1200];
    struct sockaddr_in a;
    fd_set rfds;
    struct timeval tv;

    if (argc > 1) g_port = atoi(argv[1]);
    if (argc > 2) {
        FILE *pf = fopen(argv[2], "w");
        if (pf) { fprintf(pf, "%d\n", (int)getpid()); fclose(pf); }
    }
    us = socket(AF_INET, SOCK_DGRAM, 0);
    if (us < 0) { printf("E socket\n"); fflush(stdout); return 2; }
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons((unsigned short)g_port);
    a.sin_addr.s_addr = htonl(INADDR_ANY);
    if (bind(us, (struct sockaddr *)&a, sizeof(a)) < 0) {
        printf("E bind %d\n", errno); fflush(stdout); return 3;
    }
    printf("READY %d\n", g_port); fflush(stdout);

    while (1) {
        FD_ZERO(&rfds);
        FD_SET(0, &rfds);
        FD_SET(us, &rfds);
        tv.tv_sec = 1; tv.tv_usec = 0;
        n = select(us + 1, &rfds, NULL, NULL, &tv);
        if (n < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (FD_ISSET(0, &rfds)) {
            n = (int)read(0, buf, sizeof(buf) - 1);
            if (n <= 0) break;
            idle = 0;
            for (i = 0; i < n; i++) {
                char c = buf[i];
                if (c == '\n' || c == '\r') {
                    if (llen > 0) {
                        lbuf[llen] = 0;
                        if (lbuf[0] == 'S' && lbuf[1] == ' ') {
                            char ip[64]; int addr; char val[512]; char msg[700];
                            if (sscanf(lbuf + 2, "%63s %d %511[^\n]", ip, &addr, val) == 3) {
                                int rc;
                                snprintf(msg, sizeof(msg), "R %d %s\n", addr, val);
                                rc = wl_sendto(ip, g_port, msg);
                                printf("SOK %d %d %d\n", addr, rc, (int)strlen(val));
                            } else {
                                printf("E parse\n");
                            }
                        } else if (lbuf[0] == 'P') {
                            printf("K\n");
                        } else if (lbuf[0] == 'Q') {
                            goto done;
                        }
                        llen = 0;
                    }
                } else if (llen < MAXLINE - 2) {
                    lbuf[llen++] = c;
                }
            }
            fflush(stdout);
        }
        if (FD_ISSET(us, &rfds)) {
            struct sockaddr_in from;
            socklen_t fl = sizeof(from);
            n = (int)recvfrom(us, buf, sizeof(buf) - 1, 0, (struct sockaddr *)&from, &fl);
            if (n > 0) {
                char *p = buf;
                buf[n] = 0;
                while (*p) {
                    char *e = strchr(p, '\n');
                    int addr = 0;
                    char val[600];
                    val[0] = 0;
                    if (e) *e = 0;
                    if (p[0] == 'R' && p[1] == ' ') {
                        char *q = p + 2;
                        char *sp = strchr(q, ' ');
                        if (sp) {
                            *sp = 0;
                            addr = atoi(q);
                            strncpy(val, sp + 1, sizeof(val) - 1);
                            val[sizeof(val) - 1] = 0;
                            printf("R %d %s\n", addr, val);
                        }
                    }
                    if (!e) break;
                    p = e + 1;
                }
                fflush(stdout);
            }
        }
        idle++;
        if (idle > 60) break;
    }
done:
    close(us);
    if (argc > 2) unlink(argv[2]);
    return 0;
}
'''

_wl = {"ip": "0.0.0.0", "win": -1, "rout": -1, "rx": {},
       "dead": True, "on": False, "lock": threading.Lock(),
       "errors": [], "last_fail": 0.0}


def _wl_kill_stale():
    try:
        f = open(_WL_PID, "r")
        t = f.read().strip()
        f.close()
    except Exception:
        return
    try:
        if t:
            p = int(t)
            if p > 1:
                os.kill(p, 9)
    except Exception:
        pass
    try:
        os.unlink(_WL_PID)
    except Exception:
        pass


def _wl_build():
    need = False
    try:
        cur = None
        try:
            f = open(_WL_SRC, "r")
            cur = f.read()
            f.close()
        except Exception:
            pass
        if cur != _WL_C_SRC:
            f = open(_WL_SRC, "w")
            f.write(_WL_C_SRC)
            f.close()
            need = True
        if not os.path.exists(_WL_BIN):
            need = True
        else:
            try:
                if os.path.getsize(_WL_BIN) < 1000:
                    need = True
            except Exception:
                need = True
        if need:
            try:
                if not os.path.isdir(_WL_TMP):
                    os.makedirs(_WL_TMP)
            except Exception:
                pass
            cmd = ("export PATH=%s:$PATH; export TMPDIR=%s; cd %s; "
                   "arm-linux-androideabi-gcc -O2 wlnet_helper.c -pie -fPIE -o wlnet_helper "
                   "> wl_gcc.log 2>&1; chmod 755 wlnet_helper 2>/dev/null"
                   ) % (_WL_GCC_DIR, _WL_TMP, _WL_APP)
            os.system(cmd)
        return os.path.exists(_WL_BIN)
    except Exception as e:
        _wl["errors"].append("build:%r" % (e,))
        return False


def _wl_reader():
    fd = _wl["rout"]
    buf = b""
    while True:
        try:
            d = os.read(fd, 4096)
        except Exception:
            break
        if not d:
            break
        buf += d
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            txt = line.decode("utf-8", "replace").strip()
            if txt.startswith("R "):
                p = txt.split(" ", 2)
                if len(p) == 3:
                    try:
                        a = int(p[1])
                    except Exception:
                        continue
                    _wl["rx"][a] = p[2]
    _wl["dead"] = True


def _wl_pinger():
    while not _wl["dead"]:
        time.sleep(3)
        with _wl["lock"]:
            if _wl["dead"] or _wl["win"] < 0:
                break
            try:
                os.write(_wl["win"], b"P\n")
            except Exception:
                _wl["dead"] = True
                break


def _wl_ensure():
    if _wl["on"] and not _wl["dead"]:
        return True
    if time.time() - _wl["last_fail"] < 2.0:
        return False
    with _wl["lock"]:
        if _wl["on"] and not _wl["dead"]:
            return True
        _wl["dead"] = True
        _wl["on"] = False
        try:
            _wl_kill_stale()
        except Exception:
            pass
        if not _wl_build():
            _wl["last_fail"] = time.time()
            return False
        try:
            r1, w1 = os.pipe()
            r2, w2 = os.pipe()
            pid = os.fork()
            if pid == 0:
                try:
                    os.close(w1)
                    os.close(r2)
                    os.dup2(r1, 0)
                    os.dup2(w2, 1)
                    os.close(r1)
                    os.close(w2)
                    os.execv(_WL_BIN, [_WL_BIN, str(_WL_PORT), _WL_PID])
                except Exception:
                    pass
                os._exit(127)
            os.close(r1)
            os.close(w2)
            _wl["win"] = w1
            _wl["rout"] = r2
            _wl["dead"] = False
            _wl["on"] = True
            t = threading.Thread(target=_wl_reader)
            t.daemon = True
            t.start()
            t2 = threading.Thread(target=_wl_pinger)
            t2.daemon = True
            t2.start()
            return True
        except Exception as e:
            _wl["errors"].append("start:%r" % (e,))
            _wl["last_fail"] = time.time()
            return False


def _wl_num(s):
    try:
        return int(s)
    except Exception:
        pass
    try:
        return float(s)
    except Exception:
        return s


def _wl_set_ip(ip):
    _wl["ip"] = str(ip).strip()
    _wl_ensure()


def _wl_send(addr, val):
    if not _wl_ensure():
        return
    try:
        a = int(addr)
    except Exception:
        a = 0
    s = str(val).replace("\r", " ").replace("\n", " ")
    if len(s) > 300:
        s = s[:300]
    line = "S %s %d %s\n" % (_wl["ip"], a, s)
    with _wl["lock"]:
        if _wl["win"] < 0:
            return
        try:
            os.write(_wl["win"], line.encode("utf-8"))
        except Exception:
            _wl["dead"] = True


def _wl_recv(addr):
    _wl_ensure()
    try:
        a = int(addr)
    except Exception:
        a = 0
    v = _wl["rx"].get(a)
    if v is None:
        return 0
    return _wl_num(v)


def _wl_stop():
    try:
        if _wl["win"] >= 0:
            try:
                os.write(_wl["win"], b"Q\n")
            except Exception:
                pass
            try:
                os.close(_wl["win"])
            except Exception:
                pass
            _wl["win"] = -1
        if _wl["rout"] >= 0:
            try:
                os.close(_wl["rout"])
            except Exception:
                pass
            _wl["rout"] = -1
    except Exception:
        pass


atexit.register(_wl_stop)
