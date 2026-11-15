/* CAMSTREAM2.c —— 重复调用 Camera(1)（同一个 id），验证能否连续出图
 *
 * 与 CAMSTREAM 的区别：每次都用 Camera(1) 覆盖 1.png，靠 mtime 变化判断新帧。
 * 协议：[4 字节大端长度][PNG] 循环
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

#define PHOTO_DIR "/sdcard/Abilix/photo"

static volatile int g_run = 1;
static volatile int g_client = 0;
static volatile int g_sent = 0;

static void *capture_thread(void *arg) {
    (void)arg;
    while (g_run) {
        while (!g_client && g_run) usleep(200000);
        if (!g_run) break;
        Camera(1);                   /* 固定用 1，覆盖写 */
        usleep(200000);
    }
    return NULL;
}

static long newest_mtime(char *out, int outsz, long *sizeout) {
    DIR *d = opendir(PHOTO_DIR);
    struct dirent *de;
    long best = -1;
    char bestp[512] = "";
    long bestsz = 0;
    if (!d) return -1;
    while ((de = readdir(d)) != NULL) {
        char p[512];
        struct stat st;
        if (de->d_name[0] == '.') continue;
        if (!strstr(de->d_name, ".png")) continue;
        snprintf(p, sizeof(p), "%s/%s", PHOTO_DIR, de->d_name);
        if (stat(p, &st) != 0 || !S_ISREG(st.st_mode)) continue;
        if ((long)st.st_mtime >= best) {
            best = (long)st.st_mtime;
            snprintf(bestp, sizeof(bestp), "%s", p);
            bestsz = (long)st.st_size;
        }
    }
    closedir(d);
    if (best < 0) return -1;
    snprintf(out, outsz, "%s", bestp);
    if (sizeout) *sizeout = bestsz;
    return best;
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
    long last = -1;
    int frames = 0;
    time_t t0 = time(NULL), last_t = t0;

    Printf("PC connected\n");
    while (g_run) {
        char path[512];
        long size = 0;
        long mt = newest_mtime(path, sizeof(path), &size);
        if (mt > 0 && size > 1000 && mt != last) {
            int fd = open(path, O_RDONLY);
            if (fd >= 0) {
                unsigned char *buf = (unsigned char *)malloc((size_t)size);
                if (buf) {
                    ssize_t got = read(fd, buf, (size_t)size);
                    unsigned char hdr[4];
                    close(fd);
                    if (got > 0) {
                        hdr[0] = (unsigned char)((got >> 24) & 0xFF);
                        hdr[1] = (unsigned char)((got >> 16) & 0xFF);
                        hdr[2] = (unsigned char)((got >> 8) & 0xFF);
                        hdr[3] = (unsigned char)(got & 0xFF);
                        if (send_all(c, hdr, 4) != 0 || send_all(c, buf, (int)got) != 0) {
                            free(buf);
                            break;
                        }
                        frames++;
                        g_sent = frames;
                        last = mt;
                        unlink(path);
                        if ((frames % 5) == 1) {
                            time_t now = time(NULL);
                            Printf("frames=%d dt=%ds size=%ld\n", frames,
                                   (int)(now - last_t), (long)got);
                            last_t = now;
                        }
                    } else {
                        close(fd);
                    }
                    free(buf);
                } else {
                    close(fd);
                }
            }
        }
        usleep(50000);
        if ((time(NULL) - t0) > 1800) break;
    }
    Printf("PC disconnected frames=%d\n", frames);
    return 0;
}

int Main(int argc, char **argv) {
    int s, on = 1; struct sockaddr_in addr;
    pthread_t th;
    (void)argc; (void)argv;

    Printf("CAMSTREAM2 ready\nport=9001\n");
    if (pthread_create(&th, NULL, capture_thread, NULL) != 0)
        Printf("thread fail %d\n", errno);

    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) return -1;
    (void)setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(9001);
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
