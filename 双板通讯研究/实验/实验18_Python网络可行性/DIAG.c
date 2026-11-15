/* 实验18 诊断：把 C 侧网络能力打印到机器人屏幕（Printf）并写文件，无需电脑监听
 * 关键点：先连本机自己的 8890（必成功，作对照），再连 PC:12345。
 * 判读：若 8890 OK 而 PC:12345 超时 → 电脑侧防火墙/网络问题；
 *       若连 8890 也失败 → 程序/网络环境问题。 */
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <arpa/inet.h>

extern void Printf(const char *format, ...);

#define LOG_PATH "/sdcard/Abilix/tmp/diag.txt"

static FILE *glog = 0;

static void say(const char *fmt, ...) {
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    Printf("%s", buf);
    if (glog) { fprintf(glog, "%s", buf); fflush(glog); }
}

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
    if (s < 0) { say("DIAG socket(%s:%d) ERR errno=%d\n", ip, port, errno); return -1; }
    fl = fcntl(s, F_GETFL, 0);
    fcntl(s, F_SETFL, fl | O_NONBLOCK);
    rc = connect(s, (struct sockaddr *)&a, sizeof(a));
    if (rc == 0) { say("DIAG %s:%d OK(immediate)\n", ip, port); return s; }
    if (errno != EINPROGRESS) {
        say("DIAG %s:%d connect ERR errno=%d\n", ip, port, errno);
        close(s);
        return -1;
    }
    FD_ZERO(&wfds);
    FD_SET(s, &wfds);
    tv.tv_sec = timeout_ms / 1000;
    tv.tv_usec = (timeout_ms % 1000) * 1000;
    rc = select(s + 1, NULL, &wfds, NULL, &tv);
    if (rc == 0) {
        say("DIAG %s:%d TIMEOUT %dms\n", ip, port, timeout_ms);
        close(s);
        return -2;
    }
    if (rc < 0) {
        say("DIAG %s:%d select ERR errno=%d\n", ip, port, errno);
        close(s);
        return -3;
    }
    if (getsockopt(s, SOL_SOCKET, SO_ERROR, &err, &elen) != 0) { err = errno; }
    if (err != 0) {
        say("DIAG %s:%d SO_ERROR=%d\n", ip, port, err);
        close(s);
        return -4;
    }
    fcntl(s, F_SETFL, fl);
    say("DIAG %s:%d OK\n", ip, port);
    return s;
}

int Main(int argc, char **argv) {
    int s;
    char msg[128];
    (void)argc;
    (void)argv;
    glog = fopen(LOG_PATH, "a");
    say("DIAG start pid=%d\n", (int)getpid());
    say("DIAG logfile=%s\n", glog ? "ok" : "fail");
    /* 1) 本机 8890（机器人自己的文件通道，必成功，作对照） */
    s = try_connect("192.168.1.102", 8890, 3000);
    if (s >= 0) { close(s); }
    /* 2) 另一块板 199 的 8890（跨网段路由对照） */
    s = try_connect("192.168.1.103", 8890, 3000);
    if (s >= 0) { close(s); }
    /* 3) 电脑监听 12345（关键目标） */
    s = try_connect("192.168.1.105", 12345, 5000);
    if (s >= 0) {
        sprintf(msg, "DIAG pc-socket-ok pid=%d\n", (int)getpid());
        (void)!send(s, msg, (int)strlen(msg), 0);
        close(s);
    }
    say("DIAG done\n");
    if (glog) { fclose(glog); }
    return 0;
}
