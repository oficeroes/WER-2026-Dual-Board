/*
 * ABUTTON2.c -- 低延迟按键点灯 · A 板（按钮端，192.168.1.102）
 *
 * 与旧版 ABUTTON.c 的区别：改用封装的 werlink.h（TCP_NODELAY + 大缓冲 + 单包帧），
 * 1) 按键状态变化 → 立即发 0x40 → 等灯端 0x41 ACK，程序内测出真实端到端 RTT（含点灯）；
 * 2) 每 100ms 发 PING 保活，让 WiFi 射频保持唤醒，压低事件延迟尖峰；
 * 3) 每 5 个事件上报一次统计（n/min/avg/max），同时写 /sdcard/Abilix/tmp/abutton2.log。
 *
 * 下发：node 实验14_W4_C程序下发.js 192.168.1.102 实验16_两板按键点灯/ABUTTON2.c ABUTTON2 --extra ../库/werlink.h
 * 运行顺序：B 板先运行 BLED2.c（闪 3 下自检）→ A 板再运行 ABUTTON2.c。
 */
#include "werlink.h"
#include <stdarg.h>

#define PC_IP "192.168.1.105"
#define PC_PORT 12345
#define SRV_IP "192.168.1.103"
#define SRV_PORT 8888
#define LOG_PATH "/sdcard/Abilix/tmp/abutton2.log"
#define KEEPALIVE_MS 100
#define ACK_TIMEOUT_MS 1000

extern int GetTouch(int nPort);

static int g_rep = -1;
static FILE *g_log = NULL;
static int evt_n = 0, evt_min = 0, evt_max = 0;
static long evt_sum = 0;

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
    if (g_log) { fputs(line, g_log); fflush(g_log); }
}

static void evt_record(int rtt, int state)
{
    evt_n++;
    if (evt_n == 1) { evt_min = rtt; evt_max = rtt; }
    if (rtt < evt_min) evt_min = rtt;
    if (rtt > evt_max) evt_max = rtt;
    evt_sum += rtt;
    rep("ABUTTON2 EVT #%d state=%d rtt=%dms", evt_n, state, rtt);
    if (evt_n % 5 == 0) {
        rep("ABUTTON2 EVTSTAT n=%d min=%d avg=%d max=%dms",
            evt_n, evt_min, (int)(evt_sum / evt_n), evt_max);
    }
}

int Main(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    g_log = fopen(LOG_PATH, "a");
    /* 日志上报通道是可选功能：电脑没开时最多等 1.2s 就继续，不影响两板直连 */
    g_rep = wl_connect(PC_IP, PC_PORT, 1200);
    if (g_rep >= 0) wl_set_nodelay(g_rep, 1);
    rep("ABUTTON2 start pid=%d", (int)getpid());

    for (;;) {
        WL_Conn c;
        int handshake = 0;
        int last = 0;
        int i;
        long long t_ka, t_hb;

        memset(&c, 0, sizeof(c));
        c.fd = -1;
        c.listen_fd = -1;
        if (wl_open_client(&c, SRV_IP, SRV_PORT, 60000) != 0) {
            rep("ABUTTON2 connect %s:%d failed errno=%d", SRV_IP, SRV_PORT, errno);
            wl_sleep(2000);
            continue;
        }
        rep("ABUTTON2 connected %s:%d", c.peer_ip, c.peer_port);

        /* 握手：HELLO(0x42) → BLED2 回 0x43 */
        for (i = 0; i < 100; i++) {
            int type = 0, len = 0, rc;
            unsigned char buf[64];
            wl_send_msg(c.fd, 0x42, "HELLO", 5);
            rc = wl_recv(c.fd, &type, buf, sizeof(buf), 500, &len);
            if (rc == 1 && type == 0x43) { handshake = 1; break; }
            if (rc < 0 && rc != 0) break;
            wl_sleep(100);
        }
        if (!handshake) {
            rep("ABUTTON2 handshake failed, retry");
            wl_conn_close(&c);
            wl_sleep(2000);
            continue;
        }
        rep("ABUTTON2 handshake ok (BLED2 ready)");

        last = GetTouch(1) & 1;
        rep("ABUTTON2 initial touch=%d", last);
        t_ka = wl_now_ms();
        t_hb = t_ka;

        for (;;) {
            int raw;
            int type = 0, len = 0, rc;
            unsigned char buf[256];

            raw = GetTouch(1) & 1;
            if (raw != last) {
                unsigned char m[1];
                long long t0, deadline;
                int acked = 0;
                last = raw;
                m[0] = (unsigned char)raw;
                t0 = wl_now_ms();
                if (wl_send_msg(c.fd, 0x40, m, 1) < 0) {
                    rep("ABUTTON2 send event failed");
                    break;
                }
                deadline = t0 + ACK_TIMEOUT_MS;
                while (wl_now_ms() < deadline) {
                    rc = wl_recv(c.fd, &type, buf, sizeof(buf),
                                 (int)(deadline - wl_now_ms()), &len);
                    if (rc == 0) break;
                    if (rc < 0) { acked = -1; break; }
                    if (type == 0x41) { acked = 1; break; }
                }
                if (acked == 1) {
                    evt_record((int)(wl_now_ms() - t0), raw);
                } else if (acked == 0) {
                    rep("ABUTTON2 EVT state=%d ack timeout", raw);
                } else {
                    rep("ABUTTON2 connection lost while waiting ack");
                    break;
                }
                t_ka = wl_now_ms();
            }

            /* 保活：每 100ms 一个 PING，让射频不进入深度省电 */
            if (wl_now_ms() - t_ka >= KEEPALIVE_MS) {
                if (wl_send_msg(c.fd, WL_TYPE_PING, "k", 1) < 0) break;
                t_ka = wl_now_ms();
            }

            /* 短超时补收，兼顾轮询节拍与断线检测 */
            rc = wl_recv(c.fd, &type, buf, sizeof(buf), 2, &len);
            if (rc < 0) {
                rep("ABUTTON2 disconnected rc=%d", rc);
                break;
            }
            if (rc == 1 && type == WL_TYPE_BYE) {
                rep("ABUTTON2 received BYE");
                break;
            }
            if (wl_now_ms() - t_hb >= 2000) {
                rep("ABUTTON2 alive evt_n=%d ka_pings=%d", evt_n,
                    (int)((wl_now_ms() - t_hb) / KEEPALIVE_MS));
                t_hb = wl_now_ms();
            }
        }
        wl_conn_close(&c);
        rep("ABUTTON2 reconnecting...");
        wl_sleep(1000);
    }
    return 0;
}
