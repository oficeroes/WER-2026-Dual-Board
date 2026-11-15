/* CAMSTREAM.c —— 连续拍照 + 实时回传电脑
 *
 * 原理：官方 Camera(n) 每调用一次就往 /sdcard/Abilix/photo/n.png 写一张 320x240 PNG。
 *   - 采集线程：n = 1,2,3... 连续调用 Camera(n)
 *   - 发送线程（PC 连接后）：轮询 photo 目录，发现新文件就整帧发给 PC，然后删除
 *
 * 协议：[4 字节大端长度][PNG 字节] 循环
 * 服务器：0.0.0.0:9001
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

#define ST_PORT 9001
#define PHOTO_DIR "/sdcard/Abilix/photo"

static volatile int g_run = 1;
static volatile int g_client = 0;
static volatile int g_shot = 0;
static volatile int g_sent = 0;

static void *capture_thread(void *arg) {
    int n = 0;
    (void)arg;
    while (g_run) {
        while (!g_client && g_run) usleep(200000);   /* 没有电脑连入就不拍，省空间 */
        if (!g_run) break;
        n++;
        Camera(n);
        g_shot = n;
        if ((n % 20) == 0) Printf("shots=%d sent=%d\n", n, g_sent);
        usleep(80000);
    }
    return NULL;
}

static int newest_photo(char *out, int outsz, long *sizeout, long *mtimeout) {
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
        if (stat(p, &st) != 0) continue;
        if (!S_ISREG(st.st_mode)) continue;
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
    if (mtimeout) *mtimeout = best;
    return 0;
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
    long last_mtime = -1;
    char last_name[256] = "";
    int frames = 0;
    time_t t0 = time(NULL);

    Printf("PC connected\n");
    while (g_run) {
        char path[512];
        long size = 0, mtime = 0;
        if (newest_photo(path, sizeof(path), &size, &mtime) == 0 && size > 1000) {
            if (!(mtime == last_mtime && strcmp(path, last_name) == 0)) {
                int fd = open(path, O_RDONLY);
                if (fd >= 0) {
                    unsigned char hdr[4];
                    unsigned char *buf = (unsigned char *)malloc((size_t)size);
                    ssize_t got;
                    if (buf) {
                        lseek(fd, 0, SEEK_SET);
                        got = read(fd, buf, (size_t)size);
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
                            last_mtime = mtime;
                            snprintf(last_name, sizeof(last_name), "%s", path);
                            unlink(path);         /* 发完就删，避免占空间 */
                            if ((frames % 10) == 1)
                                Printf("sent %d frames\n", frames);
                        } else {
                            unlink(path);
                        }
                        free(buf);
                    } else {
                        close(fd);
                    }
                }
            }
        }
        usleep(60000);
        if (frames > 0 && (time(NULL) - t0) > 3600) break;
    }
    Printf("PC disconnected (%d frames)\n", frames);
    return 0;
}

int Main(int argc, char **argv) {
    int s, on = 1; struct sockaddr_in addr;
    pthread_t th;
    (void)argc; (void)argv;

    Printf("CAMSTREAM ready\nport=9001\n");
    if (pthread_create(&th, NULL, capture_thread, NULL) != 0)
        Printf("thread fail %d\n", errno);

    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) { Printf("socket fail\n"); return -1; }
    (void)setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(ST_PORT);
    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) { Printf("bind fail %d\n", errno); return -2; }
    if (listen(s, 4) < 0) { Printf("listen fail\n"); return -3; }

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
