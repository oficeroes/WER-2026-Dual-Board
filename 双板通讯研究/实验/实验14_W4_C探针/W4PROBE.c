/*
 * W4PROBE.c -- 能力风暴 SKCON9 W4 探针程序
 *
 * 目的：验证经 8890 WiFi 通道以 fileType=20 下发的 C 程序，能否被机器人
 *       自带的 gcc4.8.2 编译，并在 Controller 进程内（无 root）跑起来，
 *       以及该进程能否调用 libc 的 socket()/connect()/system()/open()/read()。
 *
 * 行为：
 *   启动后每 2 秒尝试 TCP 连接 PC 的 12345 端口，最多 30 次（约 60 秒）。
 *   一旦连上，向 PC 回传：
 *     - 自身 pid
 *     - system("getprop ...") 写入 /sdcard/Abilix/tmp/w4prop.txt 后读回的内容
 *     - /proc/net/tcp 头部
 *     - /proc/self/maps 头部
 *   全程把日志追加到 /sdcard/Abilix/tmp/w4log.txt（便于屏幕/文件侧核对）。
 *
 * 构建约束（机器人侧）：
 *   arm-linux-androideabi-gcc *.c -pie -fPIC -L. -lm -lRobot -shared -o librobot_W4PROBE.so
 *   Robot.h 里 #define main Main，libRobot.so 通过 dlsym 查找符号 "Main"。
 *   本文件故意不 include Robot.h（不需要机器人 API，也避免 jni.h 依赖）。
 *
 * 作者：DSH AI（2026-11-11，W4 实验）
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define PC_IP    "192.168.1.102"
#define PC_PORT  12345
#define LOGPATH  "/sdcard/Abilix/tmp/w4log.txt"
#define PROPPATH "/sdcard/Abilix/tmp/w4prop.txt"

static FILE *g_log = NULL;

static void wlog(const char *s)
{
    if (g_log) {
        fprintf(g_log, "[W4PROBE] %s\n", s);
        fflush(g_log);
    }
}

static void wlogi(const char *tag, int v)
{
    if (g_log) {
        fprintf(g_log, "[W4PROBE] %s%d\n", tag, v);
        fflush(g_log);
    }
}

static void send_all(int fd, const char *buf, int len)
{
    int off = 0;
    while (off < len) {
        int n = (int)write(fd, buf + off, (size_t)(len - off));
        if (n <= 0) return;
        off += n;
    }
}

static void send_str(int fd, const char *s)
{
    send_all(fd, s, (int)strlen(s));
}

static void send_file(int fd, const char *path, int maxlen)
{
    char buf[4096];
    int f;
    int total = 0;

    f = open(path, O_RDONLY);
    if (f < 0) {
        send_str(fd, "(open failed) ");
        return;
    }
    for (;;) {
        int n = (int)read(f, buf, sizeof(buf));
        if (n <= 0) break;
        if (total + n > maxlen) n = maxlen - total;
        if (n <= 0) break;
        send_all(fd, buf, n);
        total += n;
        if (total >= maxlen) break;
    }
    close(f);
}

int Main(int argc, char **argv)
{
    int attempt;
    int fd = -1;
    char msg[256];
    struct sockaddr_in addr;

    g_log = fopen(LOGPATH, "a");
    wlog("===== start =====");
    wlogi("pid=", (int)getpid());
    wlogi("argc=", argc);

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(PC_PORT);
    inet_pton(AF_INET, PC_IP, &addr.sin_addr);

    wlog("try connect " PC_IP ":12345 ...");
    for (attempt = 1; attempt <= 30; attempt++) {
        fd = (int)socket(AF_INET, SOCK_STREAM, 0);
        if (fd < 0) {
            wlogi("socket failed errno=", errno);
            break;
        }
        if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) == 0) {
            wlogi("connected, attempt=", attempt);
            break;
        }
        wlogi("connect failed, errno=", errno);
        close(fd);
        fd = -1;
        sleep(2);
    }

    if (fd < 0) {
        wlog("no PC listener, give up");
        if (g_log) fclose(g_log);
        return 0;
    }

    /* 1) banner */
    snprintf(msg, sizeof(msg), "W4PROBE socket ok pid=%d argc=%d\n",
             (int)getpid(), argc);
    send_str(fd, msg);

    /* 2) system() 探针：把 getprop 结果写到 /sdcard 再读回来回传 */
    if (system("getprop ro.build.version.release > " PROPPATH " 2>&1; "
               "getprop ro.product.model >> " PROPPATH " 2>&1; "
               "getprop ro.build.fingerprint >> " PROPPATH " 2>&1") != 0) {
        send_str(fd, "(system getprop returned nonzero)\n");
    } else {
        wlog("system getprop ok");
    }
    send_str(fd, "--- getprop ---\n");
    send_file(fd, PROPPATH, 1024);

    /* 3) /proc/net/tcp 探针（验证能读系统文件） */
    send_str(fd, "--- /proc/net/tcp (head) ---\n");
    send_file(fd, "/proc/net/tcp", 2048);

    /* 4) /proc/self/maps 摘要（验证内存映射信息可读） */
    send_str(fd, "--- /proc/self/maps (head) ---\n");
    send_file(fd, "/proc/self/maps", 2048);

    send_str(fd, "W4PROBE done\n");
    wlog("probe payload sent, done");
    close(fd);
    if (g_log) fclose(g_log);
    return 0;
}
