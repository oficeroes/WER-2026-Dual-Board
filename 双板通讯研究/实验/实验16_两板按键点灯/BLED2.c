/*
 * BLED2.c -- 低延迟按键点灯 · B 板（灯端，192.168.1.103）
 *
 * 与旧版 BLED.c 的区别：改用封装的 werlink.h（TCP_NODELAY + 大缓冲 + 单包帧 + 自动 PING/PONG），
 * 收到触摸状态后"先点灯、后回 ACK"，让 A 板能测出真实端到端 RTT。
 *
 * 下发：node 实验14_W4_C程序下发.js 192.168.1.103 实验16_两板按键点灯/BLED2.c BLED2 --extra ../库/werlink.h
 * 运行顺序：B 板先运行 BLED2.c（会闪 3 下自检）→ A 板再运行 ABUTTON2.c。
 */
#include "werlink.h"
#include <stdarg.h>

#define PC_IP "192.168.1.105"
#define PC_PORT 12345
#define SRV_PORT 8888
#define LOG_PATH "/sdcard/Abilix/tmp/bled2.log"

extern void SetDO(int nPort, int nEnable);

static int g_rep = -1;
static FILE *g_log = NULL;

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

static void blink_selftest(void)
{
    int i;
    for (i = 0; i < 3; i++) {
        SetDO(1, 1);
        wl_sleep(200);
        SetDO(1, 0);
        wl_sleep(200);
    }
    SetDO(1, 0);
}

int Main(int argc, char **argv)
{
    int lfd;
    WL_Conn c;
    (void)argc;
    (void)argv;

    g_log = fopen(LOG_PATH, "a");
    blink_selftest();
    /* 日志上报通道是可选功能：电脑没开时最多等 1.2s 就继续，不影响两板直连 */
    g_rep = wl_connect(PC_IP, PC_PORT, 1200);
    if (g_rep >= 0) wl_set_nodelay(g_rep, 1);
    rep("BLED2 start pid=%d selftest done", (int)getpid());

    lfd = wl_listen(SRV_PORT);
    if (lfd < 0) {
        rep("BLED2 listen %d failed errno=%d", SRV_PORT, errno);
        return 1;
    }
    rep("BLED2 listening on %d", SRV_PORT);

    for (;;) {
        WL_Conn cc;
        int acc;
        int connected = 0;
        acc = wl_accept(lfd, &cc, 300000);
        if (acc != 1) continue;
        rep("BLED2 peer connected from %s:%d", cc.peer_ip, cc.peer_port);
        while (!connected) {
            int type = 0;
            int len = 0;
            unsigned char buf[64];
            int rc = wl_recv(cc.fd, &type, buf, sizeof(buf), 10000, &len);
            if (rc == 1 && type == 0x42) {
                wl_send_msg(cc.fd, 0x43, "BLED2", 5);
                connected = 1;
                rep("BLED2 HELLO acked");
                break;
            }
            if (rc <= 0) break;
        }
        if (!connected) {
            wl_conn_close(&cc);
            rep("BLED2 handshake failed, wait next peer");
            continue;
        }
        for (;;) {
            int type = 0;
            int len = 0;
            unsigned char buf[64];
            int rc = wl_recv(cc.fd, &type, buf, sizeof(buf), 30000, &len);
            if (rc == 0) continue; /* 空闲：继续等 */
            if (rc < 0) {
                rep("BLED2 peer read end rc=%d", rc);
                break;
            }
            if (type == 0x40 && len >= 1) {
                int on = buf[0] & 1;
                SetDO(1, on);
                wl_send_msg(cc.fd, 0x41, buf, 1); /* 先点灯再回 ACK */
                rep("BLED2 led=%d acked", on);
            } else if (type == WL_TYPE_PING) {
                wl_send_msg(cc.fd, WL_TYPE_PONG, buf, len);
            } else if (type == WL_TYPE_BYE) {
                rep("BLED2 received BYE");
                break;
            }
        }
        SetDO(1, 0); /* 断线安全灭灯 */
        wl_conn_close(&cc);
        rep("BLED2 peer closed, led off, waiting next");
    }
    return 0;
}
