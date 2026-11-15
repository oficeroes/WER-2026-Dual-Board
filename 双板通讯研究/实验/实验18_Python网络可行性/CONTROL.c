/* 实验18 控制组 CONTROL：完全不调用 Printf（怀疑 Printf 导致崩溃）。
 * 唯一可观察输出 = LED 心跳 + 8888 监听。
 * 行为：启动立刻 LED 闪 3 下（自检）→ 之后每 2 秒闪 1 下（心跳，证明程序在持续运行），
 *       同时监听 0.0.0.0:8888 120 秒，电脑连上来就回一行 "CONTROL alive pid=..."。
 * 判读：LED 每 2 秒闪 = 程序在跑（说明之前是 Printf 或别处崩了）；电脑连上 8888 = 能收 TCP。 */
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

#define SRV_PORT 8888
#define RUN_SECONDS 120

static void blink(int n, int ms) {
    int i;
    for (i = 0; i < n; i++) {
        SetDO(1, 1); usleep(ms * 1000);
        SetDO(1, 0); usleep(ms * 1000);
    }
}

int Main(int argc, char **argv) {
    int lfd, cfd, one = 1, loops;
    struct sockaddr_in sa, ca;
    socklen_t clen = sizeof(ca);
    FILE *fp;
    (void)argc; (void)argv;

    fp = fopen("/sdcard/Abilix/tmp/control.txt", "a");
    if (fp) { fprintf(fp, "CONTROL start\n"); fflush(fp); }

    blink(3, 150);  /* 启动自检：闪 3 下 */

    /* 开监听（先于任何可能出问题的调用） */
    lfd = socket(AF_INET, SOCK_STREAM, 0);
    if (lfd < 0) { blink(5, 100); return 2; }
    setsockopt(lfd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    memset(&sa, 0, sizeof(sa));
    sa.sin_family = AF_INET;
    sa.sin_port = htons(SRV_PORT);
    sa.sin_addr.s_addr = htonl(INADDR_ANY);
    if (bind(lfd, (struct sockaddr *)&sa, sizeof(sa)) < 0) { blink(4, 100); return 3; }
    listen(lfd, 4);

    for (loops = 0; loops < RUN_SECONDS / 2; loops++) {
        fd_set rf;
        struct timeval tv;
        FD_ZERO(&rf); FD_SET(lfd, &rf);
        tv.tv_sec = 2; tv.tv_usec = 0;
        /* 等 2 秒内是否有连接；超时就闪一下心跳 */
        if (select(lfd + 1, &rf, NULL, NULL, &tv) <= 0) {
            SetDO(1, 1); usleep(60 * 1000); SetDO(1, 0);
            if (fp) { fprintf(fp, "hb %d\n", loops); fflush(fp); }
            continue;
        }
        clen = sizeof(ca);
        cfd = accept(lfd, (struct sockaddr *)&ca, &clen);
        if (cfd < 0) { continue; }
        {
            char buf[128];
            sprintf(buf, "CONTROL alive pid=%d src=%s\n", (int)getpid(), inet_ntoa(ca.sin_addr));
            (void)!send(cfd, buf, (int)strlen(buf), 0);
            if (fp) { fprintf(fp, "%s", buf); fflush(fp); }
        }
        close(cfd);
        blink(2, 120);  /* 有人连上就闪 2 下 */
    }
    close(lfd);
    SetDO(1, 0);
    if (fp) { fprintf(fp, "CONTROL done\n"); fclose(fp); }
    return 0;
}
