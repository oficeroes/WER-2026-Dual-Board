/*
 * W5SERVER.c -- 两板 C 程序直连实验：A 板 TCP 回显服务器
 *
 * 用途：W5 实验。A 板运行本程序，监听 0.0.0.0:8888 当 TCP server；
 *       B 板运行 W5CLIENT.c 主动连过来，验证两块 SKCON9 之间能否直接 TCP 收发。
 *
 * 观测：本程序会把所有事件通过"报告通道"发给 PC（192.168.1.102:12345），
 *       同时在 /sdcard/Abilix/tmp/w5server.log 留本地日志。
 *       报告通道连不上时程序仍继续当 server（只是没有远程观测）。
 *
 * 入口：libRobot.so 用 dlsym("Main") 调用本符号（Robot.h 里 #define main Main）。
 * 编译：arm-linux-androideabi-gcc *.c -pie -fPIC -L. -lm -lRobot -shared -o librobot_W5SERVER.so
 *       （机器人自动完成；本文件不 include Robot.h，避免 jni.h 依赖）
 *
 * 作者：DSH AI（2026-11-11，W5 实验）
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <time.h>
#include <sys/time.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define PC_IP      "192.168.47.192"
#define PC_PORT    12345
#define SRV_PORT   8888
#define LOGPATH    "/sdcard/Abilix/tmp/w5server.log"

static FILE *g_log = NULL;
static int g_pc = -1;

static void local_log(const char *s)
{
    if (g_log) {
        fprintf(g_log, "[W5SERVER] %s\n", s);
        fflush(g_log);
    }
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

/* 向 PC 报告一行（失败静默，避免影响 server 主流程） */
static void report(const char *fmt, ...)
{
    char buf[512];
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
    int fd;
    int i;
    struct sockaddr_in a;

    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons(PC_PORT);
    inet_pton(AF_INET, PC_IP, &a.sin_addr);

    for (i = 0; i < 30; i++) {
        fd = (int)socket(AF_INET, SOCK_STREAM, 0);
        if (fd < 0) return -1;
        if (connect(fd, (struct sockaddr *)&a, sizeof(a)) == 0) return fd;
        close(fd);
        sleep(1);
    }
    return -1;
}

int Main(int argc, char **argv)
{
    int srv = -1;
    int on = 1;
    struct sockaddr_in addr;
    char buf[4096];
    char line[256];

    g_log = fopen(LOGPATH, "a");
    local_log("===== start =====");
    snprintf(line, sizeof(line), "start pid=%d argc=%d", (int)getpid(), argc);
    local_log(line);

    g_pc = connect_pc();
    if (g_pc >= 0) {
        snprintf(line, sizeof(line), "W5SERVER start pid=%d", (int)getpid());
        report("%s", line);
        local_log("pc report channel connected");
    } else {
        local_log("pc report channel unavailable, continue as server");
    }

    srv = (int)socket(AF_INET, SOCK_STREAM, 0);
    if (srv < 0) {
        report("W5SERVER socket() failed errno=%d", errno);
        local_log("socket() failed");
        if (g_log) fclose(g_log);
        return -1;
    }
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(SRV_PORT);

    if (bind(srv, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        report("W5SERVER bind 8888 failed errno=%d", errno);
        local_log("bind failed");
        close(srv);
        if (g_log) fclose(g_log);
        return -2;
    }
    if (listen(srv, 4) < 0) {
        report("W5SERVER listen failed errno=%d", errno);
        close(srv);
        if (g_log) fclose(g_log);
        return -3;
    }
    report("W5SERVER listening on %d", SRV_PORT);
    local_log("listening on 8888");

    for (;;) {
        int c;
        struct sockaddr_in peer;
        socklen_t plen = sizeof(peer);

        c = (int)accept(srv, (struct sockaddr *)&peer, &plen);
        if (c < 0) {
            report("W5SERVER accept failed errno=%d", errno);
            continue;
        }
        snprintf(line, sizeof(line), "peer connected from %s:%d",
                 inet_ntoa(peer.sin_addr), (int)ntohs(peer.sin_port));
        report("W5SERVER %s", line);
        local_log(line);

        for (;;) {
            int n = (int)recv(c, buf, sizeof(buf), 0);
            if (n <= 0) break;
            /* 回显：原样发回，验证双向数据 */
            send_all(c, buf, n);
            if (n < (int)sizeof(buf)) {
                buf[n] = 0;
                /* 只把可打印短消息写日志/报告，避免大块数据刷屏 */
                if (n <= 200) {
                    report("W5SERVER echo %d bytes: %s", n, buf);
                } else {
                    report("W5SERVER echo %d bytes", n);
                }
            }
        }
        close(c);
        report("W5SERVER peer closed");
        local_log("peer closed");
    }
}
