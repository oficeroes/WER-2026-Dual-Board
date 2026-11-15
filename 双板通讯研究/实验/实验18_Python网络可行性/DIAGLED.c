/* 实验18 灯光诊断版（在 199/B 板运行，LED 在 1 号口）
 * 结果用 LED 闪灯次数告诉人，不依赖屏幕和电脑：
 *   开始：闪 3 下（自检）
 *   之后循环播放结果码：每组 = 停顿 1.5s + N 次短闪（每次亮 0.25s 灭 0.25s）+ 停顿 2s
 *   N=1 全部 OK（自己8890、对方8890、电脑12345 都通）
 *   N=2 电脑 12345 连不上（其他 OK）  ← 最可能的当前情况
 *   N=3 对方 199/109 的 8890 连不上
 *   N=4 自己 8890 连不上
 *   循环 60 秒后常亮 1 秒再退出。
 * 同时把详细结果写 /sdcard/Abilix/tmp/diagled.txt。 */
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

static FILE *glog = 0;

static void logf_(const char *s) {
    if (glog) { fprintf(glog, "%s", s); fflush(glog); }
}

static int try_connect(const char *ip, int port, int timeout_ms) {
    struct sockaddr_in a;
    int s, rc, err = 0, fl;
    socklen_t elen = sizeof(err);
    fd_set wfds;
    struct timeval tv;
    char line[160];
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons((unsigned short)port);
    a.sin_addr.s_addr = inet_addr(ip);
    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) return -1;
    fl = fcntl(s, F_GETFL, 0);
    fcntl(s, F_SETFL, fl | O_NONBLOCK);
    rc = connect(s, (struct sockaddr *)&a, sizeof(a));
    if (rc == 0) { sprintf(line, "OK   %s:%d\n", ip, port); logf_(line); return s; }
    if (errno != EINPROGRESS) {
        sprintf(line, "ERR  %s:%d errno=%d\n", ip, port, errno); logf_(line); close(s); return -1;
    }
    FD_ZERO(&wfds); FD_SET(s, &wfds);
    tv.tv_sec = timeout_ms / 1000; tv.tv_usec = (timeout_ms % 1000) * 1000;
    rc = select(s + 1, NULL, &wfds, NULL, &tv);
    if (rc == 0) { sprintf(line, "TIMEOUT %s:%d\n", ip, port); logf_(line); close(s); return -2; }
    if (rc < 0) { sprintf(line, "SELECT_ERR %s:%d\n", ip, port); logf_(line); close(s); return -3; }
    if (getsockopt(s, SOL_SOCKET, SO_ERROR, &err, &elen) != 0) err = errno;
    if (err != 0) { sprintf(line, "SOERR %s:%d err=%d\n", ip, port, err); logf_(line); close(s); return -4; }
    fcntl(s, F_SETFL, fl);
    sprintf(line, "OK   %s:%d\n", ip, port); logf_(line);
    return s;
}

static void blink(int n) {
    int i;
    for (i = 0; i < n; i++) {
        SetDO(1, 1);
        usleep(250000);
        SetDO(1, 0);
        usleep(250000);
    }
}

int Main(int argc, char **argv) {
    int self_ok, peer_ok, pc_ok, s, loop;
    char msg[160];
    (void)argc;
    (void)argv;
    glog = fopen("/sdcard/Abilix/tmp/diagled.txt", "a");
    logf_("DIAGLED start\n");
    /* 自检：闪 3 下 */
    blink(3);
    self_ok = (try_connect("192.168.1.103", 8890, 3000) >= 0);
    peer_ok = (try_connect("192.168.1.102", 8890, 3000) >= 0);
    s = try_connect("192.168.1.105", 12345, 5000);
    pc_ok = (s >= 0);
    if (s >= 0) {
        sprintf(msg, "DIAGLED pc-socket-ok pid=%d\n", (int)getpid());
        (void)!send(s, msg, (int)strlen(msg), 0);
        close(s);
    }
    sprintf(msg, "RESULT self=%d peer=%d pc=%d\n", self_ok, peer_ok, pc_ok);
    logf_(msg);
    /* 结果循环播放 60 秒：1=全通 2=电脑不通 3=对方8890不通 4=自己8890不通 */
    for (loop = 0; loop < 15; loop++) {
        usleep(1500000);
        if (!self_ok) blink(4);
        else if (!peer_ok) blink(3);
        else if (!pc_ok) blink(2);
        else blink(1);
    }
    SetDO(1, 1);
    usleep(1000000);
    SetDO(1, 0);
    logf_("DIAGLED done\n");
    fclose(glog);
    return 0;
}
