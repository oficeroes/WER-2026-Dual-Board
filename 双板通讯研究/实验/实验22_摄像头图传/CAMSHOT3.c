/* CAMSHOT3.c —— 用官方 Camera(1) 拍照，找出照片文件并回传电脑
 *
 * 硬件前提：AI 摄像头插回板子的 USB-A 口。
 *
 * 流程（PC 连入 9001 后）：
 *   1) 列出 /sdcard/Abilix/photo 现有文件
 *   2) 用 pthread 起一个线程调用 Camera(1)（万一它一直阻塞，主线程不受影响）
 *   3) 主线程最多等 20 秒，轮询 photo 目录看有没有新文件
 *   4) 有则发 "IMGSTART <len>\n" + 原始 JPEG 字节 + "\n=== END ===\n"
 *      没有则发 "NOIMG\n=== END ===\n"
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <dirent.h>
#include <pthread.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/select.h>
#include <time.h>

extern void Printf(const char *format, ...);
extern void Camera(int pictureId);

#define S3_PORT 9001
#define PHOTO_DIR "/sdcard/Abilix/photo"
#define REP_MAX (32 * 1024)

static char g_rep[REP_MAX];
static int g_replen;
static int g_log = -1;

static void logmsg(const char *fmt, ...) {
    char buf[512]; va_list ap; int n;
    va_start(ap, fmt); n = vsnprintf(buf, sizeof(buf), fmt, ap); va_end(ap);
    if (n > 0 && g_log >= 0) (void)!write(g_log, buf, (size_t)n);
}

static void rp(const char *fmt, ...) {
    va_list ap; int n;
    if (g_replen >= REP_MAX - 1) return;
    va_start(ap, fmt);
    n = vsnprintf(g_rep + g_replen, (size_t)(REP_MAX - g_replen), fmt, ap);
    va_end(ap);
    if (n > 0) {
        if (g_replen + n >= REP_MAX) n = REP_MAX - g_replen - 1;
        g_replen += n; g_rep[g_replen] = 0;
    }
}

static void *camthread(void *arg) {
    (void)arg;
    logmsg("thread: calling Camera(1)\n");
    Camera(1);
    logmsg("thread: Camera(1) returned\n");
    return NULL;
}

/* 找目录里最新的普通文件；返回 mtime，路径写入 out */
static long newest(const char *dir, char *out, int outsz, long *sizeout) {
    DIR *d = opendir(dir);
    struct dirent *de;
    long best = -1;
    if (!d) return -1;
    while ((de = readdir(d)) != NULL) {
        char p[512];
        struct stat st;
        if (de->d_name[0] == '.') continue;
        snprintf(p, sizeof(p), "%s/%s", dir, de->d_name);
        if (stat(p, &st) != 0) continue;
        if (!S_ISREG(st.st_mode)) continue;
        if ((long)st.st_mtime >= best) {
            best = (long)st.st_mtime;
            snprintf(out, outsz, "%s", p);
            if (sizeout) *sizeout = (long)st.st_size;
        }
    }
    closedir(d);
    return best;
}

static void list_dir(const char *dir) {
    DIR *d = opendir(dir);
    struct dirent *de;
    int n = 0;
    if (!d) { rp("dir %s: open fail errno=%d\n", dir, errno); return; }
    rp("--- %s ---\n", dir);
    while ((de = readdir(d)) != NULL) {
        char p[512];
        struct stat st;
        if (de->d_name[0] == '.') continue;
        snprintf(p, sizeof(p), "%s/%s", dir, de->d_name);
        if (stat(p, &st) == 0)
            rp("  %-32s %8ld  mtime=%ld\n", de->d_name, (long)st.st_size, (long)st.st_mtime);
        n++;
    }
    closedir(d);
    rp("(共 %d 项)\n", n);
}

static int send_all(int fd, const void *buf, int len) {
    const char *p = (const char *)buf;
    int off = 0;
    while (off < len) {
        int n = (int)send(fd, p + off, (size_t)(len - off), 0);
        if (n <= 0) return -1;
        off += n;
    }
    return 0;
}

static int serve(int c) {
    pthread_t th;
    char fname[512] = "";
    long fsize = 0;
    long before;
    long t0;
    int i;

    g_replen = 0; g_rep[0] = 0;
    rp("=== CAMSHOT3 ===\n");
    rp("uid=%d pid=%d\n", (int)getuid(), (int)getpid());
    list_dir(PHOTO_DIR);

    before = newest(PHOTO_DIR, fname, sizeof(fname), &fsize);
    rp("最新文件（调用前）: %s size=%ld mtime=%ld\n", fname[0] ? fname : "(无)", fsize, before);

    t0 = (long)time(NULL);
    if (pthread_create(&th, NULL, camthread, NULL) != 0) {
        rp("pthread_create FAIL errno=%d\n", errno);
    } else {
        rp("已启动 Camera(1) 线程，等待照片出现...\n");
    }

    for (i = 0; i < 40; i++) {          /* 最多 20 秒 */
        struct stat st;
        usleep(500000);
        if (newest(PHOTO_DIR, fname, sizeof(fname), &fsize) < 0) continue;
        if (stat(fname, &st) == 0 && (long)st.st_mtime >= t0 - 1 && fsize > 0) {
            rp("发现新照片: %s size=%ld\n", fname, fsize);
            break;
        }
    }

    list_dir(PHOTO_DIR);

    if (fsize > 0 && fname[0]) {
        int fd = open(fname, O_RDONLY);
        if (fd < 0) {
            rp("打开照片失败 errno=%d\n", errno);
        } else {
            unsigned char hdr[4];
            ssize_t hn = read(fd, hdr, 4);
            char line[96];
            int ln;
            lseek(fd, 0, SEEK_SET);
            rp("照片头: %02x %02x %02x %02x\n",
               hn > 0 ? hdr[0] : 0, hn > 1 ? hdr[1] : 0,
               hn > 2 ? hdr[2] : 0, hn > 3 ? hdr[3] : 0);
            ln = snprintf(line, sizeof(line), "IMGSTART %ld\n", fsize);
            if (send_all(c, g_rep, g_replen) == 0 &&
                send_all(c, line, ln) == 0) {
                char buf[8192];
                int n;
                while ((n = (int)read(fd, buf, sizeof(buf))) > 0) {
                    if (send_all(c, buf, n) != 0) break;
                }
                send_all(c, "\n=== END ===\n", 13);
                close(fd);
                Printf("IMG sent %ld bytes\n", fsize);
                return 0;
            }
            close(fd);
        }
    }

    rp("NOIMG\n=== END ===\n");
    send_all(c, g_rep, g_replen);
    Printf("NOIMG (%ld)\n", fsize);
    return 0;
}

int Main(int argc, char **argv) {
    int s, on = 1; struct sockaddr_in addr;
    (void)argc; (void)argv;
    g_log = open("/sdcard/Abilix/tmp/camshot3.log", O_WRONLY | O_CREAT | O_APPEND, 0644);
    logmsg("=== CAMSHOT3 start ===\n");
    Printf("CAMSHOT3 ready\nport=9001\n");

    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) { Printf("socket fail\n"); return -1; }
    (void)setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(S3_PORT);
    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) { Printf("bind fail %d\n", errno); return -2; }
    if (listen(s, 4) < 0) return -3;

    for (;;) {
        fd_set rf; struct timeval tv; int r;
        FD_ZERO(&rf); FD_SET(s, &rf); tv.tv_sec = 1; tv.tv_usec = 0;
        r = select(s + 1, &rf, NULL, NULL, &tv);
        if (r > 0) {
            int c = (int)accept(s, NULL, NULL);
            if (c >= 0) { serve(c); close(c); }
        }
    }
}
