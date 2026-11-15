/*
 * PERF_CLIENT.c -- 双板通讯性能压测 · 客户端（A 板 192.168.46.109）
 *
 * 下发：node 实验14_W4_C程序下发.js 192.168.46.109 实验17_性能压测/PERF_CLIENT.c PERFCLIENT --extra ../库/werlink.h
 * 运行：先让 B 板运行 PERFSERVER.c（监听 8888），再运行本程序。
 *
 * 测试项：
 *   A) TCP_NODELAY=0 时 100 次 16B ping-pong RTT（对照，模拟默认配置）
 *   B) TCP_NODELAY=1 时 200 次 16B ping-pong RTT（优化后）
 *   C) 4MB 单向 bulk 吞吐（服务端计时）
 *   D) 2000 条 16B 单向消息速率（服务端计数计时）
 * 结果经报告通道 PC:12345 上报 + 写 /sdcard/Abilix/tmp/perf_client.log。
 */
#include "werlink.h"
#include <stdarg.h>

#define PC_IP "192.168.47.192"
#define PC_PORT 12345
#define SRV_IP "192.168.47.199"
#define SRV_PORT 8888
#define LOG_PATH "/sdcard/Abilix/tmp/perf_client.log"

#define BULK_BYTES (4 * 1024 * 1024)
#define DATA_MSGS 2000

static int g_rep = -1;
static FILE *g_log = NULL;
static int rtt_a[300];
static int rtt_b[300];

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

static void sort_ints(int *a, int n)
{
    int i, j, v;
    for (i = 1; i < n; i++) {
        v = a[i];
        j = i - 1;
        while (j >= 0 && a[j] > v) {
            a[j + 1] = a[j];
            j--;
        }
        a[j + 1] = v;
    }
}

static void report_stats(const char *phase, int nodelay, int *arr, int n)
{
    int i;
    int mn, mx, p50, p90;
    long long sum = 0;
    sort_ints(arr, n);
    mn = arr[0];
    mx = arr[n - 1];
    p50 = arr[n / 2];
    p90 = arr[(n * 9) / 10];
    for (i = 0; i < n; i++) sum += arr[i];
    rep("PERF_CLIENT phase=%s nodelay=%d n=%d min=%d avg=%.2f p50=%d p90=%d max=%d",
        phase, nodelay, n, mn, (double)sum / (double)n, p50, p90, mx);
}

/* 连续做 n 次 PING-PONG，返回实际成功次数，RTT 写入 arr */
static int run_pings(WL_Conn *c, int *arr, int n)
{
    int i;
    int ok = 0;
    for (i = 0; i < n; i++) {
        int rtt = wl_rtt_ms(c, 3000);
        if (rtt < 0) {
            rep("PERF_CLIENT ping %d/%d failed (disconnected?)", i, n);
            break;
        }
        arr[i] = rtt;
        ok++;
    }
    return ok;
}

static void phase_bulk(WL_Conn *c)
{
    unsigned char *buf;
    unsigned int i;
    long long t0, t1;
    int n;
    int alen = 0;
    int type = 0;
    unsigned char ack[8];
    int total = BULK_BYTES;

    buf = (unsigned char *)malloc(BULK_BYTES);
    if (!buf) {
        rep("PERF_CLIENT bulk malloc failed");
        return;
    }
    for (i = 0; i < (unsigned int)BULK_BYTES; i++) buf[i] = (unsigned char)(i & 0xFF);
    rep("PERF_CLIENT phase=c start bytes=%d", total);
    t0 = wl_now_ms();
    n = wl_send_raw_bulk(c->fd, buf, total);
    t1 = wl_now_ms();
    free(buf);
    if (n != total) {
        rep("PERF_CLIENT bulk send failed n=%d errno=%d", n, errno);
        return;
    }
    n = wl_recv(c->fd, &type, ack, sizeof(ack), 30000, &alen);
    if (n != 1 || alen != 8 || type != WL_TYPE_BULK_DONE) {
        rep("PERF_CLIENT bulk ack bad rc=%d len=%d type=%d", n, alen, type);
        return;
    }
    {
        unsigned int srv_ms = le32(ack);
        unsigned int got = le32(ack + 4);
        double mbps = (double)got * 8.0 / ((double)srv_ms / 1000.0) / 1000000.0;
        rep("PERF_CLIENT phase=c bytes=%u client_send_ms=%lld srv_recv_ms=%u mbps=%.2f",
            got, t1 - t0, srv_ms, mbps);
    }
}

static void phase_msgs(WL_Conn *c)
{
    unsigned char payload[16];
    unsigned char ack[8];
    int i;
    int type = 0;
    int n;
    int alen = 0;
    long long t0, t1;

    memset(payload, 0, sizeof(payload));
    rep("PERF_CLIENT phase=d start msgs=%d", DATA_MSGS);
    t0 = wl_now_ms();
    for (i = 0; i < DATA_MSGS; i++) {
        put_le32(payload, (unsigned int)i);
        if (wl_send_msg(c->fd, WL_TYPE_RAW_DATA, payload, 16) < 0) {
            rep("PERF_CLIENT data send %d failed", i);
            return;
        }
    }
    wl_send_msg(c->fd, WL_TYPE_SYNC, payload, 0);
    t1 = wl_now_ms();
    n = wl_recv(c->fd, &type, ack, sizeof(ack), 30000, &alen);
    if (n != 1 || alen != 8 || type != WL_TYPE_SYNC_ACK) {
        rep("PERF_CLIENT data ack bad rc=%d len=%d type=%d", n, alen, type);
        return;
    }
    {
        unsigned int cnt = le32(ack);
        unsigned int srv_ms = le32(ack + 4);
        double rate = srv_ms > 0 ? (double)cnt * 1000.0 / (double)srv_ms : 0.0;
        rep("PERF_CLIENT phase=d msgs=%u client_send_ms=%lld srv_ms=%u rate=%.1f msg/s",
            cnt, t1 - t0, srv_ms, rate);
    }
}

int Main(int argc, char **argv)
{
    WL_Conn c;
    int n;
    (void)argc;
    (void)argv;

    g_log = fopen(LOG_PATH, "a");
    if (wl_open_client(&c, SRV_IP, SRV_PORT, 40000) != 0) {
        rep("PERF_CLIENT connect %s:%d failed errno=%d", SRV_IP, SRV_PORT, errno);
        return 1;
    }
    rep_open(); /* 先连通数据通道，再连报告通道：避免 PC 监听还没起来时报告通道就放弃 */
    rep("PERF_CLIENT start pid=%d peer=%s:%d", (int)getpid(), c.peer_ip, c.peer_port);

    /* 预热，避免首包建链/慢启动影响统计 */
    run_pings(&c, rtt_a, 10);

    /* A) NODELAY 关：对照组 */
    wl_set_nodelay(c.fd, 0);
    rep("PERF_CLIENT phase=a start nodelay=0 n=100");
    n = run_pings(&c, rtt_a, 100);
    if (n > 0) report_stats("a", 0, rtt_a, n);

    /* B) NODELAY 开：优化组 */
    wl_set_nodelay(c.fd, 1);
    rep("PERF_CLIENT phase=b start nodelay=1 n=200");
    n = run_pings(&c, rtt_b, 200);
    if (n > 0) report_stats("b", 1, rtt_b, n);

    /* C) 4MB bulk 吞吐 */
    phase_bulk(&c);

    /* D) 2000 条 16B 单向消息速率 */
    phase_msgs(&c);

    wl_send_msg(c.fd, WL_TYPE_BYE, NULL, 0);
    wl_conn_close(&c);
    rep("PERF_CLIENT done");
    return 0;
}
