/*
 * BLED.c -- W6 演示：B 板（黄色 LED）端
 *
 * 功能：B 板 1 号端口接黄色 LED，监听 0.0.0.0:8888，接收 A 板 ABUTTON.c 发来的
 *       "T 1"/"T 0"，用 SetDO(1, 1/0) 控制灯亮/灭。
 *       启动时先做 3 次闪灯自检（亮 0.2s / 灭 0.2s ×3），证明灯和 SetDO 通路正常。
 *
 * 入口：int Main(int argc, char **argv)（libRobot.so 用 dlsym("Main") 调用）
 * 注意：不 include Robot.h（避免 jni.h 依赖），直接声明 libRobot.so 导出的 API。
 *
 * 观测：同时通过报告通道把事件发给 PC 192.168.47.192:12345。
 *
 * 作者：DSH AI（2026-11-12，W6 两板演示）
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define PC_IP     "192.168.47.192"
#define PC_PORT   12345
#define LED_PORT  1
#define SRV_PORT  8888

/* 机器人 libRobot.so 导出的 API（见 逆向资料/apk_assets/Robot.h） */
extern void SetDO(int nPort, int nEnable);

static int g_pc = -1;

static void send_all(int fd, const char *buf, int len)
{
    int off = 0;
    while (off < len) {
        int n = (int)send(fd, buf + off, (size_t)(len - off), MSG_NOSIGNAL);
        if (n <= 0) return;
        off += n;
    }
}

static void report(const char *fmt, ...)
{
    char buf[400];
    va_list ap;
    int n;

    if (g_pc < 0) return;
    va_start(ap, fmt);
    n = vsnprintf(buf, sizeof(buf) - 2, fmt, ap);
    va_end(ap);
    if (n < 0) return;
    if (n > (int)sizeof(buf) - 2) n = (int)sizeof(buf) - 2;
    buf[n++] = '\n';
    send_all(g_pc, buf, n);
}

static int connect_pc(void)
{
    int i;
    for (i = 0; i < 10; i++) {
        int fd = (int)socket(AF_INET, SOCK_STREAM, 0);
        struct sockaddr_in a;
        if (fd < 0) return -1;
        memset(&a, 0, sizeof(a));
        a.sin_family = AF_INET;
        a.sin_port = htons(PC_PORT);
        inet_pton(AF_INET, PC_IP, &a.sin_addr);
        if (connect(fd, (struct sockaddr *)&a, sizeof(a)) == 0) return fd;
        close(fd);
        sleep(1);
    }
    return -1;
}

static void led(int on)
{
    SetDO(LED_PORT, on ? 1 : 0);
}

int Main(int argc, char **argv)
{
    int srv = -1;
    int on = 1;
    struct sockaddr_in addr;
    int i;

    g_pc = connect_pc();
    if (g_pc >= 0) report("BLED report channel ok");
    report("BLED start pid=%d led_port=%d srv_port=%d", (int)getpid(), LED_PORT, SRV_PORT);

    /* 启动闪灯自检：证明 SetDO + 灯模块通路正常 */
    for (i = 0; i < 3; i++) {
        led(1); usleep(200 * 1000);
        led(0); usleep(200 * 1000);
    }
    report("BLED blink selftest done (3 on/off)");

    srv = (int)socket(AF_INET, SOCK_STREAM, 0);
    if (srv < 0) {
        report("BLED socket failed errno=%d", errno);
        return -1;
    }
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(SRV_PORT);
    if (bind(srv, (struct sockaddr *)&addr, sizeof(addr)) < 0 || listen(srv, 4) < 0) {
        report("BLED bind/listen failed errno=%d", errno);
        return -2;
    }
    report("BLED listening on %d", SRV_PORT);

    for (;;) {
        int c;
        struct sockaddr_in peer;
        socklen_t plen = sizeof(peer);
        char buf[256];
        char line[128];
        int linelen = 0;

        c = (int)accept(srv, (struct sockaddr *)&peer, &plen);
        if (c < 0) {
            usleep(100 * 1000);
            continue;
        }
        report("BLED peer connected from %s:%d",
               inet_ntoa(peer.sin_addr), (int)ntohs(peer.sin_port));

        for (;;) {
            int n = (int)recv(c, buf, sizeof(buf), 0);
            int k;
            if (n <= 0) break;
            for (k = 0; k < n; k++) {
                char ch = buf[k];
                if (ch == '\n' || ch == '\r') {
                    if (linelen > 0) {
                        line[linelen] = 0;
                        if (line[0] == 'T' || line[0] == 't') {
                            int v = (strstr(line, "1") != NULL) ? 1 : 0;
                            led(v);
                            report("BLED led -> %d (cmd=%s)", v, line);
                        } else {
                            report("BLED unknown cmd=%s", line);
                        }
                        linelen = 0;
                    }
                } else if (linelen < (int)sizeof(line) - 1) {
                    line[linelen++] = ch;
                }
            }
        }
        close(c);
        report("BLED peer closed, led -> 0");
        led(0);              /* 断线安全：灯灭 */
    }

    return 0;
}
