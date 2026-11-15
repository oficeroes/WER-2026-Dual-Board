/*
 * W5SELFTEST.c -- W5 单板自环一体测试（server + client 同进程）
 *
 * 背景：机器人同一时刻只能运行一个用户程序，所以"先跑 server 再跑 client"会被
 *       后启动的程序顶掉。本程序在一个进程里同时开 TCP server(8888) 和客户端线程，
 *       客户端连自己的 LAN IP 192.168.1.103:8888，完成：
 *         3 轮 PING 回显测 RTT + 1 次 4096 字节回显测吞吐
 *       结果经报告通道发给 PC(192.168.1.102:12345)，并写 /sdcard/Abilix/tmp/w5selftest.log。
 *
 * 用途：在只有一块板的情况下，验证"板子当服务器 + 板子当客户端"的完整链路；
 *       明天第二块板到位后，仍用 W5SERVER.c / W5CLIENT.c 做真正的板↔板实测。
 *
 * 入口：int Main(int argc, char **argv)（libRobot.so dlsym("Main")）
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
#include <pthread.h>
#include <sys/time.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define PC_IP      "192.168.1.102"
#define PC_PORT    12345
#define SELF_IP    "192.168.1.103"
#define SRV_PORT   8888
#define LOGPATH    "/sdcard/Abilix/tmp/w5selftest.log"
#define BIG_BYTES  4096

static FILE *g_log = NULL;
static int g_pc = -1;
static volatile int g_client_done = 0;
static volatile int g_ping_ok = 0;

static void local_log(const char *s)
{
    if (g_log) {
        fprintf(g_log, "[W5SELFTEST] %s\n", s);
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

static double now_ms(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (double)tv.tv_sec * 1000.0 + (double)tv.tv_usec / 1000.0;
}

static int recv_full(int fd, char *buf, int n, int timeout_s)
{
    int got = 0;
    double t0 = now_ms();
    while (got < n) {
        int r = (int)recv(fd, buf + got, (size_t)(n - got), 0);
        if (r <= 0) break;
        got += r;
        if (now_ms() - t0 > (double)timeout_s * 1000.0) break;
    }
    return got;
}

/* 客户端线程：连本机 LAN IP 的 8888（就是本进程的 server） */
static void *client_thread(void *arg)
{
    int fd = -1;
    int i;
    int ok = 0;
    char line[256];
    char big[BIG_BYTES];
    double rtt_min = 1e9, rtt_max = 0, rtt_sum = 0;

    (void)arg;
    sleep(1);

    for (i = 0; i < 20; i++) {
        struct sockaddr_in a;
        fd = (int)socket(AF_INET, SOCK_STREAM, 0);
        if (fd < 0) break;
        memset(&a, 0, sizeof(a));
        a.sin_family = AF_INET;
        a.sin_port = htons(SRV_PORT);
        inet_pton(AF_INET, SELF_IP, &a.sin_addr);
        if (connect(fd, (struct sockaddr *)&a, sizeof(a)) == 0) break;
        close(fd);
        fd = -1;
        report("W5SELFTEST client connect retry %d/20 errno=%d", i + 1, errno);
        sleep(1);
    }
    if (fd < 0) {
        report("W5SELFTEST SELFTEST FAILED: cannot connect self %s:%d errno=%d",
               SELF_IP, SRV_PORT, errno);
        local_log("self connect failed");
        g_client_done = 1;
        return NULL;
    }
    report("W5SELFTEST client connected self %s:%d", SELF_IP, SRV_PORT);

    for (i = 1; i <= 3; i++) {
        int n;
        int got;
        double t;

        n = snprintf(line, sizeof(line), "SELF %d\n", i);
        t = now_ms();
        send_all(fd, line, n);
        got = recv_full(fd, big, n, 5);
        {
            double rtt = now_ms() - t;
            if (got == n) {
                ok++;
                rtt_sum += rtt;
                if (rtt < rtt_min) rtt_min = rtt;
                if (rtt > rtt_max) rtt_max = rtt;
                report("W5SELFTEST PING %d ok rtt=%.2fms", i, rtt);
            } else {
                report("W5SELFTEST PING %d FAILED got=%d/%d", i, got, n);
            }
        }
        usleep(100 * 1000);
    }
    g_ping_ok = ok;
    if (ok > 0) {
        report("W5SELFTEST RTT summary ok=%d/3 min=%.2fms avg=%.2fms max=%.2fms",
               ok, rtt_min, rtt_sum / ok, rtt_max);
    }

    memset(big, 'C', sizeof(big));
    {
        double t = now_ms();
        int got;
        send_all(fd, big, BIG_BYTES);
        got = recv_full(fd, big, BIG_BYTES, 10);
        if (got == BIG_BYTES) {
            double dt = (now_ms() - t) / 1000.0;
            double kbps = ((double)BIG_BYTES * 2.0 * 8.0 / 1000.0) / (dt > 0 ? dt : 0.001);
            report("W5SELFTEST BIG echo %d bytes ok round-trip=%.1fms ~%.1f kbps(双向)",
                   BIG_BYTES, dt * 1000.0, kbps);
        } else {
            report("W5SELFTEST BIG echo FAILED got=%d/%d", got, BIG_BYTES);
        }
    }

    send_all(fd, "BYE\n", 4);
    close(fd);
    local_log("self test client done");
    g_client_done = 1;
    return NULL;
}

int Main(int argc, char **argv)
{
    int srv = -1;
    int on = 1;
    struct sockaddr_in addr;
    pthread_t th;
    char line[256];

    g_log = fopen(LOGPATH, "a");
    local_log("===== start =====");
    snprintf(line, sizeof(line), "start pid=%d argc=%d", (int)getpid(), argc);
    local_log(line);

    /* 报告通道（连不上也继续） */
    {
        int i;
        struct sockaddr_in a;
        memset(&a, 0, sizeof(a));
        a.sin_family = AF_INET;
        a.sin_port = htons(PC_PORT);
        inet_pton(AF_INET, PC_IP, &a.sin_addr);
        for (i = 0; i < 30; i++) {
            int fd = (int)socket(AF_INET, SOCK_STREAM, 0);
            if (fd < 0) break;
            if (connect(fd, (struct sockaddr *)&a, sizeof(a)) == 0) {
                g_pc = fd;
                break;
            }
            close(fd);
            sleep(1);
        }
    }
    report("W5SELFTEST start pid=%d", (int)getpid());

    /* TCP server */
    srv = (int)socket(AF_INET, SOCK_STREAM, 0);
    if (srv < 0) {
        report("W5SELFTEST socket failed errno=%d", errno);
        return -1;
    }
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(SRV_PORT);
    if (bind(srv, (struct sockaddr *)&addr, sizeof(addr)) < 0 || listen(srv, 4) < 0) {
        report("W5SELFTEST bind/listen failed errno=%d", errno);
        local_log("bind/listen failed");
        if (g_log) fclose(g_log);
        return -2;
    }
    fcntl(srv, F_SETFL, O_NONBLOCK);
    report("W5SELFTEST listening on %d", SRV_PORT);
    local_log("listening on 8888");

    if (pthread_create(&th, NULL, client_thread, NULL) != 0) {
        report("W5SELFTEST pthread_create failed errno=%d", errno);
        local_log("pthread_create failed");
        if (g_log) fclose(g_log);
        return -3;
    }

    /* 非阻塞 accept 循环；客户端线程结束后退出 */
    for (;;) {
        struct sockaddr_in peer;
        socklen_t plen = sizeof(peer);
        int c = (int)accept(srv, (struct sockaddr *)&peer, &plen);

        if (c < 0) {
            if (g_client_done) break;
            usleep(100 * 1000);
            continue;
        }
        snprintf(line, sizeof(line), "peer connected from %s:%d",
                 inet_ntoa(peer.sin_addr), (int)ntohs(peer.sin_port));
        report("W5SELFTEST %s", line);
        local_log(line);

        for (;;) {
            char buf[4096];
            int n = (int)recv(c, buf, sizeof(buf), 0);
            if (n <= 0) break;
            send_all(c, buf, n);
            if (n <= 200) {
                buf[n] = 0;
                report("W5SELFTEST echo %d bytes", n);
            } else {
                report("W5SELFTEST echo %d bytes", n);
            }
        }
        close(c);
        report("W5SELFTEST peer closed");
    }

    report("W5SELFTEST done ping_ok=%d/3", g_ping_ok);
    local_log("done");
    close(srv);
    if (g_pc >= 0) close(g_pc);
    if (g_log) fclose(g_log);
    return 0;
}
