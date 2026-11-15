/*
 * W5CLIENT.c -- 两板 C 程序直连实验：B 板 TCP 客户端
 *
 * 用途：W5 实验。B 板运行本程序，主动连接 A 板（默认 192.168.1.103:8888）：
 *       1) 先连 PC 报告通道 192.168.1.102:12345（失败也继续，只是无远程观测）；
 *       2) 每 2 秒重试连 A 板，最多 30 次；
 *       3) 连上后：10 次 "PING i" 往返测延迟，再发 4096 字节块测吞吐；
 *       4) 全部结果通过报告通道发回 PC，并在 /sdcard/Abilix/tmp/w5client.log 留底。
 *
 * 入口：libRobot.so 用 dlsym("Main") 调用本符号（Robot.h 里 #define main Main）。
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
#include <sys/time.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define PC_IP       "192.168.47.192"
#define PC_PORT     12345
#define SRV_IP      "192.168.46.109"
#define SRV_PORT    8888
#define LOGPATH     "/sdcard/Abilix/tmp/w5client.log"
#define BIG_BYTES   4096

static FILE *g_log = NULL;
static int g_pc = -1;

static void local_log(const char *s)
{
    if (g_log) {
        fprintf(g_log, "[W5CLIENT] %s\n", s);
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

static int connect_retry(const char *ip, int port, int tries, int gap_s)
{
    int fd;
    int i;
    struct sockaddr_in a;

    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons(port);
    inet_pton(AF_INET, ip, &a.sin_addr);

    for (i = 0; i < tries; i++) {
        fd = (int)socket(AF_INET, SOCK_STREAM, 0);
        if (fd < 0) return -1;
        if (connect(fd, (struct sockaddr *)&a, sizeof(a)) == 0) return fd;
        close(fd);
        if (i + 1 < tries) {
            report("W5CLIENT connect %s:%d failed(errno=%d), retry %d/%d",
                   ip, port, errno, i + 1, tries);
            sleep(gap_s);
        }
    }
    return -1;
}

/* 读满 n 字节（带总超时秒数）；返回实际读到的字节数 */
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

int Main(int argc, char **argv)
{
    int srv = -1;
    int i;
    char line[256];
    char big[BIG_BYTES];
    double t0;
    double rtt_min = 1e9, rtt_max = 0, rtt_sum = 0;
    int ok_count = 0;

    g_log = fopen(LOGPATH, "a");
    local_log("===== start =====");
    snprintf(line, sizeof(line), "start pid=%d argc=%d", (int)getpid(), argc);
    local_log(line);

    g_pc = connect_retry(PC_IP, PC_PORT, 30, 1);
    if (g_pc >= 0) {
        report("W5CLIENT start pid=%d", (int)getpid());
    } else {
        local_log("pc report channel unavailable, continue");
    }

    report("W5CLIENT connecting to A board %s:%d ...", SRV_IP, SRV_PORT);
    srv = connect_retry(SRV_IP, SRV_PORT, 30, 2);
    if (srv < 0) {
        report("W5CLIENT FAILED: cannot connect A board %s:%d (errno=%d)",
               SRV_IP, SRV_PORT, errno);
        local_log("connect A board failed");
        if (g_log) fclose(g_log);
        return -2;
    }
    report("W5CLIENT connected A board %s:%d", SRV_IP, SRV_PORT);
    local_log("connected A board");

    /* 1) 10 次 ping-pong 测 RTT */
    for (i = 1; i <= 10; i++) {
        int n;
        int got;
        double rtt;

        n = snprintf(line, sizeof(line), "PING %d\n", i);
        t0 = now_ms();
        send_all(srv, line, n);
        got = recv_full(srv, big, n, 5);
        rtt = now_ms() - t0;
        if (got == n) {
            ok_count++;
            rtt_sum += rtt;
            if (rtt < rtt_min) rtt_min = rtt;
            if (rtt > rtt_max) rtt_max = rtt;
            report("W5CLIENT PING %d ok rtt=%.2fms echo=%s",
                   i, rtt, (got > 6 ? "match" : "?"));
        } else {
            report("W5CLIENT PING %d FAILED got=%d/%d", i, got, n);
        }
        usleep(200 * 1000);
    }
    if (ok_count > 0) {
        report("W5CLIENT RTT summary: ok=%d/10 min=%.2fms avg=%.2fms max=%.2fms",
               ok_count, rtt_min, rtt_sum / ok_count, rtt_max);
    }

    /* 2) 4096 字节大块回显测吞吐 */
    memset(big, 'A', sizeof(big));
    t0 = now_ms();
    send_all(srv, big, BIG_BYTES);
    {
        int got = recv_full(srv, big, BIG_BYTES, 10);
        double dt = (now_ms() - t0) / 1000.0;
        if (got == BIG_BYTES) {
            double kbps = ((double)BIG_BYTES * 2.0 * 8.0 / 1000.0) / (dt > 0 ? dt : 0.001);
            report("W5CLIENT BIG echo %d bytes ok, round-trip %.1fms, ~%.1f kbps(双向)",
                   BIG_BYTES, dt * 1000.0, kbps);
        } else {
            report("W5CLIENT BIG echo FAILED got=%d/%d", got, BIG_BYTES);
        }
    }

    send_all(srv, "BYE\n", 4);
    report("W5CLIENT done, closing (ok=%d/10)", ok_count);
    local_log("done");
    close(srv);
    if (g_pc >= 0) close(g_pc);
    if (g_log) fclose(g_log);
    return 0;
}
