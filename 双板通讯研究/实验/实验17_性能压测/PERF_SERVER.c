/*
 * PERF_SERVER.c -- 双板通讯性能压测 · 服务端（B 板 192.168.47.199）
 *
 * 下发：node 实验14_W4_C程序下发.js 192.168.47.199 实验17_性能压测/PERF_SERVER.c PERFSERVER --extra ../库/werlink.h
 * 运行：机器人屏幕运行 PERFSERVER.c；随后在 A 板运行 PERFCLIENT.c。
 *
 * 职责：
 *   1) 监听 8888，等 A 板连入；
 *   2) 收到 PING 原样回 PONG（测 RTT）；
 *   3) 收到 RAW_BULK 后统计裸数据流吞吐（4MB）；
 *   4) 收到 RAW_DATA 帧计数，收到 SYNC 回 SYNC_ACK（测单向消息速率）；
 *   5) 关键事件经报告通道 PC:12345 上报 + 写 /sdcard/Abilix/tmp/perf_server.log。
 */
#include "werlink.h"
#include <stdarg.h>

#define PC_IP "192.168.47.192"
#define PC_PORT 12345
#define SRV_PORT 8888
#define LOG_PATH "/sdcard/Abilix/tmp/perf_server.log"

static int g_rep = -1;
static FILE *g_log = NULL;

static unsigned int le32(const unsigned char *p)
{
    return (unsigned int)p[0] | ((unsigned int)p[1] << 8) | ((unsigned int)p[2] << 16) | ((unsigned int)p[3] << 24);
}
static void put_le32(unsigned char *p, unsigned int v)
{
    p[0] = (unsigned char)(v & 0xFF);
    p[1] = (unsigned char)((v >> 8) & 0xFF);
    p[2] = (unsigned char)((v >> 16) & 0xFF);
    p[3] = (unsigned char)((v >> 24) & 0xFF);
}

static void rep(const char *fmt, ...)
{
    char line[512];
    int n;
    va_list ap;
    va_start(ap, fmt);
    n = vsnprintf(line, sizeof(line) - 2, fmt, ap);
    va_end(ap);
    if (n < 0) return;
    if (n > (int)sizeof(line) - 2) n = sizeof(line) - 2;
    line[n++] = '\n';
    line[n] = '\0';
    if (g_rep >= 0) wl_send_all(g_rep, line, n);
    if (g_log) {
        fputs(line, g_log);
        fflush(g_log);
    }
}

static void rep_open(void)
{
    g_rep = wl_connect(PC_IP, PC_PORT, 15000);
    if (g_rep >= 0) wl_set_nodelay(g_rep, 1);
}

static void serve_loop(WL_Conn *c)
{
    unsigned char buf[65536];
    int type;
    int n;
    int data_count = 0;
    long long data_t0 = 0;

    for (;;) {
        int rc;
        int len = 0;
        type = 0;
        rc = wl_recv(c->fd, &type, buf, sizeof(buf), 30000, &len);
        if (rc == 0) {
            rep("PERF_SERVER idle timeout 30s, closing peer");
            break;
        }
        if (rc < 0) {
            rep("PERF_SERVER peer read end (rc=%d)", rc);
            break;
        }
        if (type == WL_TYPE_PING) {
            wl_send_msg(c->fd, WL_TYPE_PONG, buf, len);
        } else if (type == WL_TYPE_RAW_BULK) {
            unsigned int total;
            unsigned int got = 0;
            long long t0;
            long long elapsed;
            unsigned char ack[8];
            total = (len == 4) ? le32(buf) : 0;
            if (total == 0) {
                rep("PERF_SERVER bad bulk header len=%d", len);
                continue;
            }
            t0 = wl_now_ms();
            rep("PERF_SERVER bulk start bytes=%u", total);
            while (got < total) {
                int want;
                int r;
                r = wl_wait_read(c->fd, 20000);
                if (r <= 0) {
                    rep("PERF_SERVER bulk recv stalled at %u/%u", got, total);
                    got = 0;
                    break;
                }
                want = (int)(total - got);
                if (want > (int)sizeof(buf)) want = (int)sizeof(buf);
                r = (int)recv(c->fd, buf, want, 0);
                if (r <= 0) {
                    rep("PERF_SERVER bulk recv error errno=%d", errno);
                    got = 0;
                    break;
                }
                got += (unsigned int)r;
            }
            elapsed = wl_now_ms() - t0;
            if (got == total) {
                double mbps = (double)got * 8.0 / ((double)elapsed / 1000.0) / 1000000.0;
                put_le32(ack, (unsigned int)elapsed);
                put_le32(ack + 4, got);
                wl_send_msg(c->fd, WL_TYPE_BULK_DONE, ack, 8);
                rep("PERF_SERVER bulk bytes=%u elapsed=%lldms mbps=%.2f", got, elapsed, mbps);
            }
        } else if (type == WL_TYPE_RAW_DATA) {
            if (data_count == 0) data_t0 = wl_now_ms();
            data_count++;
        } else if (type == WL_TYPE_SYNC) {
            unsigned char ack[8];
            long long elapsed = (data_count > 0) ? (wl_now_ms() - data_t0) : 0;
            put_le32(ack, (unsigned int)data_count);
            put_le32(ack + 4, (unsigned int)elapsed);
            wl_send_msg(c->fd, WL_TYPE_SYNC_ACK, ack, 8);
            rep("PERF_SERVER data msgs=%d elapsed=%lldms rate=%.1f msg/s",
                data_count, elapsed, elapsed > 0 ? data_count * 1000.0 / (double)elapsed : 0.0);
            data_count = 0;
        } else if (type == WL_TYPE_BYE) {
            rep("PERF_SERVER received BYE");
            break;
        } else {
            rep("PERF_SERVER unknown type=%d len=%d", type, len);
        }
    }
}

int Main(int argc, char **argv)
{
    int lfd;
    WL_Conn c;
    int acc;
    (void)argc;
    (void)argv;

    g_log = fopen(LOG_PATH, "a");
    rep_open();
    rep("PERF_SERVER start pid=%d", (int)getpid());
    lfd = wl_listen(SRV_PORT);
    if (lfd < 0) {
        rep("PERF_SERVER listen %d failed errno=%d", SRV_PORT, errno);
        return 1;
    }
    rep("PERF_SERVER listening on %d", SRV_PORT);

    memset(&c, 0, sizeof(c));
    c.fd = -1;
    for (;;) {
        acc = wl_accept(lfd, &c, 300000);
        if (acc == 0) {
            rep("PERF_SERVER accept timeout 300s");
            continue;
        }
        if (acc < 0) {
            rep("PERF_SERVER accept error errno=%d", errno);
            continue;
        }
        rep("PERF_SERVER peer connected from %s:%d", c.peer_ip, c.peer_port);
        serve_loop(&c);
        wl_conn_close(&c);
        rep("PERF_SERVER waiting next peer");
    }
    return 0;
}
