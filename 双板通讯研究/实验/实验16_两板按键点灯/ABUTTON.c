/*
 * ABUTTON.c -- W6 演示：A 板（按键/碰撞传感器）端
 *
 * 功能：A 板 1 号端口接碰撞传感器，轮询 GetTouch(1)，状态变化时通过 WiFi TCP
 *       把 "T 1"/"T 0" 发给 B 板（BLED.c，192.168.47.199:8888）；断线自动重连。
 *
 * 入口：int Main(int argc, char **argv)（libRobot.so 用 dlsym("Main") 调用）
 * 注意：不 include Robot.h（避免 jni.h 依赖），直接声明 libRobot.so 导出的 API。
 *
 * 观测：同时通过报告通道把 TOUCH 原始值/变化发给 PC 192.168.47.192:12345。
 *
 * 作者：DSH AI（2026-11-12，W6 两板演示）
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/time.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define PC_IP     "192.168.47.192"
#define PC_PORT   12345
#define B_IP      "192.168.47.199"
#define B_PORT    8888
#define BTN_PORT  1
#define POLL_US   20000          /* 20ms 轮询 */

/* 机器人 libRobot.so 导出的 API（见 逆向资料/apk_assets/Robot.h） */
extern int GetTouch(int nPort);

static int g_pc = -1;

static double now_ms(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (double)tv.tv_sec * 1000.0 + (double)tv.tv_usec / 1000.0;
}

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

static int connect_to(const char *ip, int port, int tries, int interval_s)
{
    int i;
    for (i = 0; i < tries; i++) {
        int fd = (int)socket(AF_INET, SOCK_STREAM, 0);
        struct sockaddr_in a;
        if (fd < 0) return -1;
        memset(&a, 0, sizeof(a));
        a.sin_family = AF_INET;
        a.sin_port = htons(port);
        inet_pton(AF_INET, ip, &a.sin_addr);
        if (connect(fd, (struct sockaddr *)&a, sizeof(a)) == 0) return fd;
        close(fd);
        sleep(interval_s);
    }
    return -1;
}

/* 连 PC 报告通道（失败不阻塞主流程，最多等 10s） */
static void connect_pc(void)
{
    g_pc = connect_to(PC_IP, PC_PORT, 10, 1);
    if (g_pc >= 0) report("ABUTTON report channel ok");
}

int Main(int argc, char **argv)
{
    int last = -1;
    int bfd = -1;
    int raw_tick = 0;
    char cmd[32];

    connect_pc();
    report("ABUTTON start pid=%d B=%s:%d btn_port=%d", (int)getpid(), B_IP, B_PORT, BTN_PORT);

    for (;;) {
        if (bfd < 0) {
            bfd = connect_to(B_IP, B_PORT, 60, 1);   /* 最多重试 60s，然后继续重试 */
            if (bfd < 0) {
                report("ABUTTON connect B failed, retry round");
                sleep(2);
                continue;
            }
            report("ABUTTON connected B %s:%d", B_IP, B_PORT);
            /* 连上先同步一次当前状态 */
            if (last >= 0) {
                int n = snprintf(cmd, sizeof(cmd), "T %d\n", last);
                send_all(bfd, cmd, n);
            }
        }

        {
            int v = GetTouch(BTN_PORT);
            int on = (v > 0) ? 1 : 0;
            int n;

            if (on != last) {
                last = on;
                n = snprintf(cmd, sizeof(cmd), "T %d\n", on);
                send_all(bfd, cmd, n);
                report("ABUTTON TOUCH raw=%d -> sent %d", v, on);
                raw_tick = 0;
            } else if (++raw_tick >= 25) {          /* 每 0.5s 报一次原始值 */
                raw_tick = 0;
                report("ABUTTON TOUCH raw=%d (no change, sent=%d)", v, on);
            }
        }

        usleep(POLL_US);
    }

    return 0;
}
