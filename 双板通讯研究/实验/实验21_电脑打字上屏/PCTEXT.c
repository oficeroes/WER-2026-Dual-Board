/* PCTEXT.c —— 电脑打字上屏（PC → 机器人屏幕）
 *
 * 机器人端：TCP 服务器 0.0.0.0:9001（PC 主动连入）
 * 行协议（UTF-8，每条消息以 '\n' 结尾）：
 *   T <text>   清屏后整屏显示 <text>（打字模式：网页每次同步全文）
 *   A <text>   追加显示 <text>
 *   C          清屏
 *   Q          退出程序
 *
 * 入口函数必须是 Main（libRobot.so 通过 dlsym("Main") 加载）。
 * 屏幕输出用 Printf / Clear（Robot.h 声明，控制器运行时提供）。
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/select.h>
#include <fcntl.h>
#include <time.h>

extern void Printf(const char *format, ...);
extern void Clear(void);

#define PCT_PORT      9001
#define PCT_MAX_LINE  4000
#define PCT_BACKLOG   4
#define PCT_LOG       "/sdcard/Abilix/tmp/pctext.log"

static int g_log = -1;

static void logmsg(const char *fmt, ...) {
    char buf[512];
    va_list ap;
    int n;
    va_start(ap, fmt);
    n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (n > 0 && g_log >= 0) {
        (void)!write(g_log, buf, (size_t)n);
    }
}

/* 处理一条完整命令（不含 '\n'，已去 '\r'） */
static int handle_line(int fd, char *line) {
    const char *text;
    if (line[0] == '\0') return 0;

    if (line[0] == 'T' && line[1] == ' ') {
        text = line + 2;
        if (strlen(text) > PCT_MAX_LINE) text = "文本太长";
        Clear();
        Printf("%s", text);
        Printf("\n");                 /* 换行收尾，让文字立即显示 */
        logmsg("T len=%u\n", (unsigned)strlen(text));
        (void)!send(fd, "OK\n", 3, 0);
        return 0;
    }
    if (line[0] == 'A' && line[1] == ' ') {
        text = line + 2;
        if (strlen(text) > PCT_MAX_LINE) text = "文本太长";
        Printf("%s\n", text);
        logmsg("A len=%u\n", (unsigned)strlen(text));
        (void)!send(fd, "OK\n", 3, 0);
        return 0;
    }
    if (line[0] == 'C') {
        Clear();
        Printf("PCTEXT ready\nport=9001\n");
        logmsg("clear\n");
        (void)!send(fd, "OK\n", 3, 0);
        return 0;
    }
    if (line[0] == 'Q') {
        logmsg("quit by pc\n");
        return 1;
    }
    /* 未知命令：当作追加行显示，方便调试 */
    Printf("%s\n", line);
    logmsg("raw len=%u\n", (unsigned)strlen(line));
    return 0;
}

/* 处理一个客户端连接，返回 1 表示收到 Q 需要退出 */
static int serve_client(int c) {
    char buf[8192];
    char line[PCT_MAX_LINE + 16];
    int llen = 0;
    int quit = 0;
    time_t last = time(NULL);

    Printf("PC connected\n");
    logmsg("client connected\n");

    for (;;) {
        fd_set rf;
        struct timeval tv;
        int r;
        int n;
        int i;

        FD_ZERO(&rf);
        FD_SET(c, &rf);
        tv.tv_sec = 1;
        tv.tv_usec = 0;
        r = select(c + 1, &rf, NULL, NULL, &tv);
        if (r < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (r == 0) {
            /* 90 秒无数据则断开，避免僵死连接 */
            if (time(NULL) - last > 90) {
                logmsg("idle timeout\n");
                break;
            }
            continue;
        }
        n = (int)recv(c, buf, sizeof(buf), 0);
        if (n <= 0) {
            logmsg("client closed n=%d\n", n);
            break;
        }
        last = time(NULL);
        for (i = 0; i < n; i++) {
            char ch = buf[i];
            if (ch == '\n') {
                line[llen] = '\0';
                if (llen > 0 && line[llen - 1] == '\r') line[llen - 1] = '\0';
                if (handle_line(c, line)) { quit = 1; break; }
                llen = 0;
            } else if (llen < PCT_MAX_LINE + 8) {
                line[llen++] = ch;
            }
        }
        if (quit) break;
    }
    Printf("PC disconnected\n");
    logmsg("client disconnected\n");
    return quit;
}

int Main(int argc, char **argv) {
    int s;
    int on = 1;
    struct sockaddr_in addr;
    time_t last_status = 0;

    (void)argc;
    (void)argv;

    g_log = open(PCT_LOG, O_WRONLY | O_CREAT | O_APPEND, 0644);

    Printf("PCTEXT ready\nport=9001\n");
    logmsg("=== PCTEXT start ===\n");

    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) {
        Printf("socket fail %d\n", errno);
        return -1;
    }
    (void)setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(PCT_PORT);

    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        Printf("bind fail %d\n", errno);
        logmsg("bind fail errno=%d\n", errno);
        return -2;
    }
    if (listen(s, PCT_BACKLOG) < 0) {
        Printf("listen fail %d\n", errno);
        return -3;
    }
    Printf("listening :9001\n");
    logmsg("listening 9001\n");

    for (;;) {
        fd_set rf;
        struct timeval tv;
        int r;

        FD_ZERO(&rf);
        FD_SET(s, &rf);
        tv.tv_sec = 1;
        tv.tv_usec = 0;
        r = select(s + 1, &rf, NULL, NULL, &tv);
        if (r > 0) {
            int c = (int)accept(s, NULL, NULL);
            if (c >= 0) {
                if (serve_client(c)) {
                    close(c);
                    break;
                }
                close(c);
            }
        }
        /* 每 30 秒刷一次存活心跳，避免屏幕完全没动静时无法判断程序状态 */
        if (time(NULL) - last_status >= 30 && r <= 0) {
            last_status = time(NULL);
            logmsg("alive\n");
        }
    }

    close(s);
    if (g_log >= 0) close(g_log);
    Printf("PCTEXT exit\n");
    return 0;
}
