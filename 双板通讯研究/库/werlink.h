/*
 * werlink.h -- 能力风暴 SKCON9 双板通讯库（header-only，单文件）
 *
 * 设计目标：让"一块板做服务端、一块板做客户端"的 TCP 通讯写起来像串口一样简单，
 * 并且默认开启低延迟配置（TCP_NODELAY + 大 socket 缓冲）。
 *
 * 适用环境：机器人 C 用户程序（8890 fileType=20 下发 → 机器人自编译 → Controller
 * 进程内运行，普通应用 uid，有 INTERNET 权限）。只用 Android 系统 libc，
 * 不需要 root、不需要额外装库。
 *
 * 帧格式（消息模式）：  'W' 'L' | type(1B) | flags(1B,保留=0) | len(4B 小端) | payload
 *   头部固定 8 字节，payload 最长 60000 字节。RAW 模式不加帧，直接收发裸字节流。
 *
 * 最小用法：
 *   // 服务端（B 板）
 *   WL_Conn c; int lfd = wl_listen(8888);
 *   if (wl_accept(lfd, &c, 60000) == 1) {
 *       int type, len; unsigned char buf[256];
 *       for (;;) {
 *           int rc = wl_recv(c.fd, &type, buf, sizeof(buf), 20000, &len);
 *           if (rc == 0) continue;        // 超时，继续等
 *           if (rc < 0) break;            // 对端断开
 *           if (type == 0x40) SetDO(1, buf[0]);
 *       }
 *   }
 *
 *   // 客户端（A 板）
 *   WL_Conn c;
 *   if (wl_open_client(&c, "192.168.47.199", 8888, 30000) == 0) {
 *       unsigned char msg[1]; msg[0] = 1;
 *       wl_send_msg(c.fd, 0x40, msg, 1);
 *   }
 *
 * 注意：本头文件用 static 函数实现，只能被一个 .c 文件 include（用户程序本来就只有一个 .c，
 * 所以没问题）。不要多个 .c 同时 include（会重复定义，虽然 static 也能编过，但会浪费空间）。
 *
 * 作者：DSH AI（2026-11-12，W7 性能优化与封装）
 */
#ifndef WERLINK_H
#define WERLINK_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>

#ifndef MSG_NOSIGNAL
#define MSG_NOSIGNAL 0
#endif

/* ---- 预置消息类型（用户可自定义 0x40 以上） ---- */
#define WL_TYPE_PING   1   /* 心跳/测 RTT：收到后原样回 PONG */
#define WL_TYPE_PONG   2
#define WL_TYPE_BYE    0x10
#define WL_TYPE_RAW_BULK 0x20  /* 后跟 raw 数据流，见 wl_send_raw_bulk() */
#define WL_TYPE_BULK_DONE 0x21
#define WL_TYPE_RAW_DATA 0x30
#define WL_TYPE_SYNC   0x31
#define WL_TYPE_SYNC_ACK 0x32

#define WL_HDR_LEN       8
#define WL_MAX_PAYLOAD   60000
#define WL_DEFAULT_BUFSZ (256 * 1024)

typedef struct {
    int fd;              /* 已连接的 socket，-1 表示未连接 */
    int listen_fd;       /* 服务端监听 fd（客户端为 -1） */
    int is_server;
    char peer_ip[32];
    int peer_port;
    unsigned int tx_seq;
    unsigned long long rx_bytes;
    unsigned long long tx_bytes;
} WL_Conn;

/* ============================ 基础工具 ============================ */

static long long wl_now_ms(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (long long)tv.tv_sec * 1000 + (long long)tv.tv_usec / 1000;
}

static void wl_sleep(int ms)
{
    if (ms > 0) usleep((unsigned int)ms * 1000);
}

/* 设置低延迟参数：TCP_NODELAY 关掉 Nagle（小包即时发出），加大收发缓冲 */
static int wl_set_low_latency(int fd)
{
    int one = 1;
    int sz = WL_DEFAULT_BUFSZ;
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
    setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &sz, sizeof(sz));
    setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &sz, sizeof(sz));
    return 0;
}

static int wl_set_nodelay(int fd, int on)
{
    int v = on ? 1 : 0;
    return setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &v, sizeof(v));
}

/* 等待 fd 可读：>0 就绪，0 超时，<0 错误 */
static int wl_wait_read(int fd, int timeout_ms)
{
    fd_set rf;
    struct timeval tv;
    int r;
    if (fd < 0) return -1;
    FD_ZERO(&rf);
    FD_SET(fd, &rf);
    tv.tv_sec = timeout_ms / 1000;
    tv.tv_usec = (timeout_ms % 1000) * 1000;
    r = select(fd + 1, &rf, NULL, NULL, &tv);
    if (r < 0 && errno == EINTR) return 0;
    return r;
}

static int wl_send_all(int fd, const void *buf, int len)
{
    const char *p = (const char *)buf;
    int sent = 0;
    int n;
    while (sent < len) {
        n = (int)send(fd, p + sent, len - sent, MSG_NOSIGNAL);
        if (n < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (n == 0) return -1;
        sent += n;
    }
    return sent;
}

/* 带总超时的精确收满：返回 len 成功，0 超时，-1 错误 */
static int wl_recv_all_t(int fd, void *buf, int len, int timeout_ms)
{
    char *p = (char *)buf;
    int got = 0;
    long long deadline = wl_now_ms() + (timeout_ms > 0 ? timeout_ms : 1);
    while (got < len) {
        int r = wl_wait_read(fd, (int)(deadline - wl_now_ms()));
        int n;
        if (r == 0) return 0;
        if (r < 0) return -1;
        n = (int)recv(fd, p + got, len - got, 0);
        if (n <= 0) {
            if (n < 0 && errno == EINTR) continue;
            return -1;
        }
        got += n;
        if (wl_now_ms() > deadline && got < len) return 0;
    }
    return len;
}

/* ============================ 消息模式 ============================ */

static void wl_fill_hdr(unsigned char *h, int type, int len)
{
    h[0] = 'W';
    h[1] = 'L';
    h[2] = (unsigned char)(type & 0xFF);
    h[3] = 0;
    h[4] = (unsigned char)(len & 0xFF);
    h[5] = (unsigned char)((len >> 8) & 0xFF);
    h[6] = (unsigned char)((len >> 16) & 0xFF);
    h[7] = (unsigned char)((len >> 24) & 0xFF);
}

/* 发一条消息：type + payload。返回 payload 长度，<0 出错。
 * 低延迟关键：头部与 payload 拼成一个缓冲、一次 send 发出（否则每个消息会拆成 2 个 TCP 段）。*/
static int wl_send_msg(int fd, int type, const void *data, int len)
{
    unsigned char stackbuf[512];
    unsigned char *frame;
    int n;
    if (fd < 0) return -1;
    if (len < 0 || len > WL_MAX_PAYLOAD) return -2;
    if (WL_HDR_LEN + len <= (int)sizeof(stackbuf)) {
        frame = stackbuf;
    } else {
        frame = (unsigned char *)malloc(WL_HDR_LEN + len);
        if (!frame) return -2;
    }
    wl_fill_hdr(frame, type, len);
    if (len > 0 && data) memcpy(frame + WL_HDR_LEN, data, len);
    n = wl_send_all(fd, frame, WL_HDR_LEN + len);
    if (frame != stackbuf) free(frame);
    return n < 0 ? -1 : len;
}

/* 收一条消息（推荐 API）。
 * 返回：1=收到一条消息（payload 长度写入 *out_len，注意可能是 0 的空消息）；0=超时；
 *       -1=连接关闭/错误；-2=帧非法或缓冲太小。
 * type 可为 NULL；消息非空时 data 不能为 NULL。*/
static int wl_recv(int fd, int *type, void *data, int maxlen, int timeout_ms, int *out_len)
{
    unsigned char h[WL_HDR_LEN];
    int len;
    int n;
    if (out_len) *out_len = 0;
    if (fd < 0) return -1;
    n = wl_recv_all_t(fd, h, WL_HDR_LEN, timeout_ms);
    if (n == 0) return 0;
    if (n < 0) return -1;
    if (h[0] != 'W' || h[1] != 'L') return -2;
    len = (int)(h[4] | (h[5] << 8) | (h[6] << 16) | ((unsigned int)h[7] << 24));
    if (len < 0 || len > WL_MAX_PAYLOAD) return -2;
    if (len > maxlen) return -2;
    if (len > 0) {
        if (data == NULL) return -2;
        n = wl_recv_all_t(fd, data, len, 20000);
        if (n != len) return -1;
    }
    if (type) *type = h[2];
    if (out_len) *out_len = len;
    return 1;
}

/* 服务端便捷封装：收消息，若为 PING 自动回 PONG。
 * 返回同 wl_recv；*handled=1 表示这条已自动处理（调用者可继续循环）。*/
static int wl_serve(WL_Conn *c, int *type, void *data, int maxlen, int timeout_ms, int *out_len, int *handled)
{
    int rc;
    if (handled) *handled = 0;
    rc = wl_recv(c->fd, type, data, maxlen, timeout_ms, out_len);
    if (rc == 1 && *type == WL_TYPE_PING) {
        wl_send_msg(c->fd, WL_TYPE_PONG, data, *out_len);
        if (handled) *handled = 1;
    }
    return rc;
}

/* 单次 RTT 测量（发 PING 等 PONG）：返回毫秒，-1 失败 */
static int wl_rtt_ms(WL_Conn *c, int timeout_ms)
{
    unsigned char buf[16];
    int type = 0;
    int len = 0;
    long long t0, t1;
    int rc;
    memcpy(buf, "ping", 4);
    t0 = wl_now_ms();
    if (wl_send_msg(c->fd, WL_TYPE_PING, buf, 4) < 0) return -1;
    rc = wl_recv(c->fd, &type, buf, sizeof(buf), timeout_ms, &len);
    if (rc != 1) return -1;
    t1 = wl_now_ms();
    return (int)(t1 - t0);
}

/* ============================ 连接管理 ============================ */

/* 服务端：监听端口，返回 listen fd，失败 -1 */
static int wl_listen(int port)
{
    int fd;
    int one = 1;
    struct sockaddr_in a;
    fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return -1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_addr.s_addr = htonl(INADDR_ANY);
    a.sin_port = htons((unsigned short)port);
    if (bind(fd, (struct sockaddr *)&a, sizeof(a)) < 0) {
        close(fd);
        return -1;
    }
    if (listen(fd, 4) < 0) {
        close(fd);
        return -1;
    }
    return fd;
}

/* 服务端：等待一个客户端接入。返回 1 成功/0 超时/-1 错误 */
static int wl_accept(int lfd, WL_Conn *c, int timeout_ms)
{
    struct sockaddr_in a;
    socklen_t al;
    int fd;
    if (lfd < 0 || c == NULL) return -1;
    if (wl_wait_read(lfd, timeout_ms) <= 0) return 0;
    al = sizeof(a);
    memset(&a, 0, sizeof(a));
    fd = accept(lfd, (struct sockaddr *)&a, &al);
    if (fd < 0) return -1;
    memset(c, 0, sizeof(*c));
    c->fd = fd;
    c->listen_fd = lfd;
    c->is_server = 1;
    strncpy(c->peer_ip, inet_ntoa(a.sin_addr), sizeof(c->peer_ip) - 1);
    c->peer_port = ntohs(a.sin_port);
    wl_set_low_latency(fd);
    return 1;
}

/* 单次连接尝试：非阻塞 connect + select 等就绪，超时立即失败。
 * 关键：不能用阻塞 connect —— 当电脑防火墙丢弃 SYN 时，阻塞 connect 会卡 2 分钟以上，
 * 把"日志上报通道"这种可选功能变成整个程序的启动阻塞源（2026-11-12 真机踩坑）。*/
static int wl_connect_try(const char *ip, int port, int timeout_ms)
{
    struct sockaddr_in a;
    int fd;
    int flags;
    int r;
    int err = 0;
    socklen_t elen = sizeof(err);
    fd_set wf;
    struct timeval tv;

    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons((unsigned short)port);
    if (!inet_aton(ip, &a.sin_addr)) return -1;
    fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return -1;
    flags = fcntl(fd, F_GETFL, 0);
    if (flags < 0) flags = 0;
    fcntl(fd, F_SETFL, flags | O_NONBLOCK);
    r = connect(fd, (struct sockaddr *)&a, sizeof(a));
    if (r < 0 && errno == EINPROGRESS) {
        FD_ZERO(&wf);
        FD_SET(fd, &wf);
        if (timeout_ms < 1) timeout_ms = 1;
        tv.tv_sec = timeout_ms / 1000;
        tv.tv_usec = (timeout_ms % 1000) * 1000;
        r = select(fd + 1, NULL, &wf, NULL, &tv);
        if (r <= 0) { close(fd); return -1; }
        if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &err, &elen) < 0 || err != 0) {
            close(fd);
            return -1;
        }
    } else if (r < 0) {
        close(fd);
        return -1;
    }
    fcntl(fd, F_SETFL, flags); /* 恢复阻塞模式 */
    return fd;
}

/* 客户端：在 retry_ms 内反复尝试连 ip:port。返回 fd，失败 -1。
 * 每次尝试最多阻塞 min(500ms, 剩余时间)，因此总耗时不超 retry_ms + 500ms。*/
static int wl_connect(const char *ip, int port, int retry_ms)
{
    long long deadline = wl_now_ms() + (retry_ms > 0 ? retry_ms : 1);
    for (;;) {
        int left = (int)(deadline - wl_now_ms());
        int step = left < 500 ? left : 500;
        int fd;
        if (step <= 0) return -1;
        fd = wl_connect_try(ip, port, step);
        if (fd >= 0) {
            wl_set_low_latency(fd);
            return fd;
        }
        if (wl_now_ms() >= deadline) return -1;
        wl_sleep(100);
    }
}

/* 客户端：连接并填好 WL_Conn。返回 0 成功，-1 失败 */
static int wl_open_client(WL_Conn *c, const char *ip, int port, int retry_ms)
{
    int fd;
    if (c == NULL) return -1;
    fd = wl_connect(ip, port, retry_ms);
    if (fd < 0) return -1;
    memset(c, 0, sizeof(*c));
    c->fd = fd;
    c->listen_fd = -1;
    c->is_server = 0;
    strncpy(c->peer_ip, ip, sizeof(c->peer_ip) - 1);
    c->peer_port = port;
    return 0;
}

static void wl_conn_close(WL_Conn *c)
{
    if (c == NULL) return;
    if (c->fd >= 0) close(c->fd);
    c->fd = -1;
}

static void wl_close_all(WL_Conn *c)
{
    if (c == NULL) return;
    if (c->fd >= 0) close(c->fd);
    if (c->listen_fd >= 0) close(c->listen_fd);
    c->fd = -1;
    c->listen_fd = -1;
}

/* ============================ 裸流（大吞吐） ============================ */

/* 发送大块裸数据：先发 BULK 控制帧（payload=4B 总字节数小端），再发 len 字节 payload。
 * 返回发送字节数，<0 出错。对方用 wl_recv_raw() 接收。 */
static int wl_send_raw_bulk(int fd, const void *buf, int len)
{
    unsigned char h[4];
    h[0] = (unsigned char)(len & 0xFF);
    h[1] = (unsigned char)((len >> 8) & 0xFF);
    h[2] = (unsigned char)((len >> 16) & 0xFF);
    h[3] = (unsigned char)((len >> 24) & 0xFF);
    if (wl_send_msg(fd, WL_TYPE_RAW_BULK, h, 4) < 0) return -1;
    return wl_send_all(fd, buf, len);
}

/* 接收裸数据：先解析 BULK 控制帧拿到总长，再收满。返回字节数，<0 失败 */
static int wl_recv_raw(int fd, void *buf, int maxlen, int timeout_ms)
{
    unsigned char h[4];
    int type = 0;
    int n;
    int total;
    int len = 0;
    n = wl_recv(fd, &type, h, sizeof(h), timeout_ms, &len);
    if (n != 1 || len != 4 || type != WL_TYPE_RAW_BULK) return -1;
    total = (int)(h[0] | (h[1] << 8) | (h[2] << 16) | ((unsigned int)h[3] << 24));
    if (total < 0 || total > maxlen) return -2;
    n = wl_recv_all_t(fd, buf, total, 30000);
    if (n != total) return -1;
    return total;
}

#endif /* WERLINK_H */
