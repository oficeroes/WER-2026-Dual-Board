/* 实验18 双向判断版 LIS8888（在 2 号机 192.168.1.103 运行，LED 也在 2 号机）
 * 目的：不依赖"板子主动连电脑"就能拿到结果——
 *   1) 程序启动后先试连 PC:12345（5 秒），把成败记下来；
 *   2) 然后在 8888 端口监听（120 秒）；
 *   3) 电脑主动连 192.168.1.103:8888，程序会把 "outbound=1/0" 直接发回给电脑。
 * 另外 LED：启动自检闪 3 下；之后 outbound 成功闪 1 下、失败闪 2 下。
 * 判读：电脑能连上 8888 → 程序确实在跑；回包里 outbound=1 → 板→电脑的 TCP 出站也通。 */
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <arpa/inet.h>

extern void SetDO(int nPort, int nEnable);
extern void Printf(const char *format, ...);

#define PC_IP "192.168.1.105"
#define PC_PORT 12345
#define SRV_PORT 8888
#define LISTEN_SECONDS 120

static FILE *glog = 0;

static void logf_(const char *s) {
    if (glog) { fprintf(glog, "%s", s); fflush(glog); }
}

static void blink(int n, int ms) {
    int i;
    for (i = 0; i < n; i++) {
        SetDO(1, 1);
        usleep(ms * 1000);
        SetDO(1, 0);
        usleep(ms * 1000);
    }
}

/* 非阻塞 connect，带超时；成功返回 fd，失败返回负值 */
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
    if (rc == 0) { return s; }
    if (errno != EINPROGRESS) { close(s); return -2; }
    FD_ZERO(&wfds); FD_SET(s, &wfds);
    tv.tv_sec = timeout_ms / 1000; tv.tv_usec = (timeout_ms % 1000) * 1000;
    rc = select(s + 1, NULL, &wfds, NULL, &tv);
    if (rc <= 0) { close(s); return -3; }
    if (getsockopt(s, SOL_SOCKET, SO_ERROR, &err, &elen) != 0 || err != 0) { close(s); return -4; }
    fcntl(s, F_SETFL, fl);
    return s;
}

int Main(int argc, char **argv) {
    int s, lfd, cfd, one = 1, rc, loops;
    struct sockaddr_in sa, ca;
    socklen_t clen = sizeof(ca);
    char buf[256];
    (void)argc;
    (void)argv;
    glog = fopen("/sdcard/Abilix/tmp/lis8888.txt", "a");
    logf_("LIS8888 start\n");
    Printf("LIS8888 start pid=%d\n", (int)getpid());
    blink(3, 200);  /* 自检闪 3 下 */

    /* 1) 先测出站：连 PC */
    s = try_connect(PC_IP, PC_PORT, 5000);
    if (s >= 0) { rc = 1; (void)!send(s, "LIS outbound-ok\n", 16, 0); close(s); }
    else { rc = (s == -3) ? -3 : s; }
    Printf("outbound=%d (%s)\n", rc, (rc == 1) ? "PC-OK" : "PC-FAIL");
    sprintf(buf, "LIS8888 outbound=%d\n", rc);
    logf_(buf);
    blink(rc == 1 ? 1 : 2, 400);  /* 出站成功闪 1 下，失败闪 2 下 */

    /* 2) 监听 8888，120 秒；每来一个连接就把结果发回去 */
    lfd = socket(AF_INET, SOCK_STREAM, 0);
    if (lfd < 0) { logf_("listen socket fail\n"); return 2; }
    setsockopt(lfd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    memset(&sa, 0, sizeof(sa));
    sa.sin_family = AF_INET;
    sa.sin_port = htons(SRV_PORT);
    sa.sin_addr.s_addr = htonl(INADDR_ANY);
    if (bind(lfd, (struct sockaddr *)&sa, sizeof(sa)) < 0) { logf_("bind fail\n"); close(lfd); return 3; }
    listen(lfd, 4);
    logf_("listening 8888\n");
    Printf("listening 8888 for %ds\n", LISTEN_SECONDS);
    for (loops = 0; loops < LISTEN_SECONDS; loops++) {
        fd_set rf;
        struct timeval tv;
        FD_ZERO(&rf); FD_SET(lfd, &rf);
        tv.tv_sec = 1; tv.tv_usec = 0;
        if (select(lfd + 1, &rf, NULL, NULL, &tv) <= 0) { continue; }
        cfd = accept(lfd, (struct sockaddr *)&ca, &clen);
        if (cfd < 0) { continue; }
        sprintf(buf, "LIS8888 hello pid=%d outbound=%d src=%s\n", (int)getpid(), rc, inet_ntoa(ca.sin_addr));
        (void)!send(cfd, buf, (int)strlen(buf), 0);
        logf_(buf);
        Printf("PC connected from %s\n", inet_ntoa(ca.sin_addr));
        close(cfd);
    }
    close(lfd);
    SetDO(1, 0);
    logf_("LIS8888 done\n");
    fclose(glog);
    return 0;
}
