/* CAMPROBE.c —— 摄像头/图像通道探测（跑在机器人 App 进程里）
 *
 * 目的：查清 AI 摄像头（USB-A 口，UVC）在当前板子上到底以什么形式存在：
 *   - 有没有 /dev/video*（内核 uvcvideo 驱动）
 *   - /dev/bus/usb/* 能不能 open（libusb/usbfs 路线）
 *   - /proc/self/fd 里有没有已经打开的 usbfs fd（App 自己开的）
 *   - framebuffer（/dev/graphics/fb0）能不能读（屏幕回传兜底）
 *   - 系统里有哪些 usb/uvc 相关 .so
 *
 * 输出：TCP 服务器 0.0.0.0:9001（PC 主动连入，与 PCTEXT 相同方向）
 *       连上后立即发送整份报告，以 "=== END ===" 结尾。
 *       命令：R 重发报告，Q 退出。
 *       同时写 /sdcard/Abilix/tmp/camprobe.log
 *
 * 入口 Main（libRobot.so dlsym("Main")）。
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <dirent.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/select.h>
#include <sys/utsname.h>

extern void Printf(const char *format, ...);
extern void Clear(void);

#define CAM_PORT   9001
#define CAM_LOG    "/sdcard/Abilix/tmp/camprobe.log"
#define REP_MAX    (96 * 1024)

static char g_rep[REP_MAX];
static int  g_replen;
static int  g_log = -1;

static void logmsg(const char *fmt, ...) {
    char buf[512];
    va_list ap;
    int n;
    va_start(ap, fmt);
    n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (n > 0 && g_log >= 0) (void)!write(g_log, buf, (size_t)n);
}

static void rp(const char *fmt, ...) {
    va_list ap;
    int n;
    if (g_replen >= REP_MAX - 1) return;
    va_start(ap, fmt);
    n = vsnprintf(g_rep + g_replen, (size_t)(REP_MAX - g_replen), fmt, ap);
    va_end(ap);
    if (n > 0) {
        if (g_replen + n >= REP_MAX) n = REP_MAX - g_replen - 1;
        g_replen += n;
        g_rep[g_replen] = 0;
    }
}

static int readfile(const char *path, char *buf, int cap) {
    int fd = open(path, O_RDONLY);
    int n;
    if (fd < 0) return -1;
    n = (int)read(fd, buf, (size_t)(cap - 1));
    close(fd);
    if (n < 0) n = 0;
    buf[n] = 0;
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r')) buf[--n] = 0;
    return n;
}

static const char *rd1(const char *path) {
    static char b[4][256];
    static int k = 0;
    char *p = b[k];
    k = (k + 1) & 3;
    if (readfile(path, p, 256) <= 0) return "?";
    return p;
}

/* ---------- v4l2（头文件可能不存在，手写结构体与 ioctl 号） ---------- */
struct v4l2_capability {
    unsigned char  driver[16];
    unsigned char  card[32];
    unsigned char  bus_info[32];
    unsigned int   version;
    unsigned int   capabilities;
    unsigned int   device_caps;
    unsigned int   reserved[3];
};
struct v4l2_fmtdesc {
    unsigned int   index;
    unsigned int   type;
    unsigned int   flags;
    unsigned char  description[32];
    unsigned int   pixelformat;
    unsigned int   reserved[4];
};
#define VIDIOC_QUERYCAP 0x80685600UL
#define VIDIOC_ENUM_FMT 0xC0405602UL

static void probe_video_node(const char *path) {
    struct stat st;
    int fd, e;
    struct v4l2_capability cap;
    struct v4l2_fmtdesc fm;
    int i;

    if (stat(path, &st) != 0) {
        rp("  %s: absent\n", path);
        return;
    }
    rp("  %s: mode=%04o uid=%d gid=%d rdev=%u:%u\n", path,
       (unsigned)st.st_mode, (int)st.st_uid, (int)st.st_gid,
       (unsigned)(st.st_rdev >> 8), (unsigned)(st.st_rdev & 0xFF));

    fd = open(path, O_RDWR);
    if (fd < 0) {
        e = errno;
        rp("  %s: open(O_RDWR) FAIL errno=%d (%s)\n", path, e, strerror(e));
        fd = open(path, O_RDONLY);
        if (fd < 0) {
            e = errno;
            rp("  %s: open(O_RDONLY) FAIL errno=%d (%s)\n", path, e, strerror(e));
            return;
        }
        rp("  %s: open(O_RDONLY) OK (只读)\n", path);
    } else {
        rp("  %s: open(O_RDWR) OK\n", path);
    }

    memset(&cap, 0, sizeof(cap));
    if (ioctl(fd, VIDIOC_QUERYCAP, &cap) == 0) {
        rp("  %s: QUERYCAP driver=%s card=%s bus=%s ver=%08x caps=%08x devcaps=%08x\n",
           path, cap.driver, cap.card, cap.bus_info,
           cap.version, cap.capabilities, cap.device_caps);
        for (i = 0; i < 8; i++) {
            memset(&fm, 0, sizeof(fm));
            fm.index = (unsigned)i;
            fm.type = 1; /* V4L2_BUF_TYPE_VIDEO_CAPTURE */
            if (ioctl(fd, VIDIOC_ENUM_FMT, &fm) != 0) break;
            rp("    fmt[%d] %c%c%c%c  %s\n", i,
               (int)(fm.pixelformat & 0xFF), (int)((fm.pixelformat >> 8) & 0xFF),
               (int)((fm.pixelformat >> 16) & 0xFF), (int)((fm.pixelformat >> 24) & 0xFF),
               fm.description);
        }
    } else {
        e = errno;
        rp("  %s: QUERYCAP FAIL errno=%d (%s)\n", path, e, strerror(e));
    }
    close(fd);
}

/* ---------- 目录遍历 ---------- */
static void list_dir(const char *path, const char *tag) {
    DIR *d = opendir(path);
    struct dirent *de;
    int cnt = 0;
    if (!d) {
        rp("  %s: opendir FAIL errno=%d\n", path, errno);
        return;
    }
    rp("  %s:\n", path);
    while ((de = readdir(d)) != NULL) {
        struct stat st;
        char full[512];
        if (de->d_name[0] == '.') continue;
        if (tag && tag[0] && !strstr(de->d_name, tag)) continue;
        snprintf(full, sizeof(full), "%s/%s", path, de->d_name);
        memset(&st, 0, sizeof(st));
        if (stat(full, &st) == 0) rp("    %-28s %s mode=%04o\n", de->d_name,
                                     S_ISDIR(st.st_mode) ? "dir " : "file",
                                     (unsigned)st.st_mode);
        else rp("    %-28s stat-fail\n", de->d_name);
        if (++cnt > 80) { rp("    ... (truncated)\n"); break; }
    }
    closedir(d);
}

static void probe_usb_sysfs(void) {
    DIR *d = opendir("/sys/bus/usb/devices");
    struct dirent *de;
    if (!d) { rp("  /sys/bus/usb/devices: opendir FAIL errno=%d\n", errno); return; }
    while ((de = readdir(d)) != NULL) {
        char p[512];
        struct stat st;
        if (de->d_name[0] == '.') continue;
        snprintf(p, sizeof(p), "/sys/bus/usb/devices/%s", de->d_name);
        if (lstat(p, &st) != 0) continue;

        if (strchr(de->d_name, ':') == NULL) {
            /* 设备节点：1-1 / usb1 / 1-0:1.0 等 */
            char vidp[512], pidp[512], prodp[512], cls[512];
            snprintf(vidp, sizeof(vidp), "%s/idVendor", p);
            snprintf(pidp, sizeof(pidp), "%s/idProduct", p);
            snprintf(prodp, sizeof(prodp), "%s/product", p);
            snprintf(cls, sizeof(cls), "%s/bDeviceClass", p);
            rp("  dev %-12s vid=%s pid=%s class=%s product=%s\n",
               de->d_name, rd1(vidp), rd1(pidp), rd1(cls), rd1(prodp));
            {
                char dp[512];
                snprintf(dp, sizeof(dp), "%s/descriptors", p);
                struct stat ds;
                if (stat(dp, &ds) == 0) rp("      descriptors size=%ld\n", (long)ds.st_size);
            }
        } else {
            /* 接口节点：1-1:1.0 */
            char bc[512], bs[512], bp[512], drv[512];
            snprintf(bc, sizeof(bc), "%s/bInterfaceClass", p);
            snprintf(bs, sizeof(bs), "%s/bInterfaceSubClass", p);
            snprintf(bp, sizeof(bp), "%s/bInterfaceProtocol", p);
            snprintf(drv, sizeof(drv), "%s/driver", p);
            rp("  if %-14s class=%s/%s/%s driver=%s\n",
               de->d_name, rd1(bc), rd1(bs), rd1(bp), rd1(drv));
        }
    }
    closedir(d);
}

static void probe_fd_table(void) {
    DIR *d = opendir("/proc/self/fd");
    struct dirent *de;
    int found = 0;
    if (!d) { rp("  /proc/self/fd: FAIL\n"); return; }
    while ((de = readdir(d)) != NULL) {
        char p[512], tgt[512];
        ssize_t n;
        if (de->d_name[0] == '.') continue;
        snprintf(p, sizeof(p), "/proc/self/fd/%s", de->d_name);
        n = readlink(p, tgt, sizeof(tgt) - 1);
        if (n <= 0) continue;
        tgt[n] = 0;
        if (strstr(tgt, "usb") || strstr(tgt, "video") || strstr(tgt, "v4l")) {
            rp("  fd %s -> %s\n", de->d_name, tgt);
            found++;
        }
    }
    closedir(d);
    if (!found) rp("  (没有已打开的 usb/video fd)\n");
}

static void build_report(void) {
    struct utsname un;
    char b[256];
    int i;
    const char *libs[] = {
        "/system/lib/libusb100.so", "/system/lib/libusb1.0.so",
        "/system/lib/libuvc.so", "/system/lib/libuvccamera.so",
        "/system/lib/libjpeg.so", "/system/lib/libRobot.so",
        "/system/lib/libstar.so", "/system/lib/libstarpy.so",
        "/system/vendor/lib/libusb100.so", NULL
    };
    const char *nodes[] = {
        "/dev/video0", "/dev/video1", "/dev/video2", "/dev/video3",
        "/dev/video4", "/dev/v4l-subdev0", "/dev/media0",
        "/dev/graphics/fb0", "/dev/fb0", NULL
    };

    g_replen = 0;
    g_rep[0] = 0;

    rp("=== CAMPROBE ===\n");
    rp("uid=%d gid=%d euid=%d pid=%d\n", (int)getuid(), (int)getgid(),
       (int)geteuid(), (int)getpid());
    if (uname(&un) == 0)
        rp("uname=%s %s %s %s\n", un.sysname, un.release, un.machine, un.version);

    rp("\n--- /dev 关键节点 ---\n");
    for (i = 0; nodes[i]; i++) probe_video_node(nodes[i]);

    rp("\n--- /dev/v4l* ---\n");
    list_dir("/dev", "video");
    list_dir("/dev", "v4l");

    rp("\n--- /sys/class/video4linux ---\n");
    {
        DIR *d = opendir("/sys/class/video4linux");
        struct dirent *de;
        if (d) {
            while ((de = readdir(d)) != NULL) {
                char p[512];
                if (de->d_name[0] == '.') continue;
                snprintf(p, sizeof(p), "/sys/class/video4linux/%s/name", de->d_name);
                rp("  %s name=%s\n", de->d_name, rd1(p));
            }
            closedir(d);
        } else {
            rp("  opendir FAIL errno=%d\n", errno);
        }
    }

    rp("\n--- usb sysfs ---\n");
    probe_usb_sysfs();

    rp("\n--- /dev/bus/usb ---\n");
    {
        DIR *d = opendir("/dev/bus/usb");
        struct dirent *bus;
        if (!d) {
            rp("  opendir FAIL errno=%d\n", errno);
        } else {
            while ((bus = readdir(d)) != NULL) {
                DIR *dd;
                struct dirent *dev;
                char busp[256];
                if (bus->d_name[0] == '.') continue;
                snprintf(busp, sizeof(busp), "/dev/bus/usb/%s", bus->d_name);
                dd = opendir(busp);
                if (!dd) { rp("  %s: opendir FAIL errno=%d\n", busp, errno); continue; }
                while ((dev = readdir(dd)) != NULL) {
                    char full[512];
                    struct stat st;
                    int fd, e;
                    if (dev->d_name[0] == '.') continue;
                    snprintf(full, sizeof(full), "%s/%s", busp, dev->d_name);
                    if (stat(full, &st) != 0) continue;
                    fd = open(full, O_RDWR);
                    if (fd >= 0) {
                        rp("  %s mode=%04o uid=%d gid=%d openRw=OK\n", full,
                           (unsigned)st.st_mode, (int)st.st_uid, (int)st.st_gid);
                        close(fd);
                    } else {
                        e = errno;
                        rp("  %s mode=%04o uid=%d gid=%d openRw=FAIL errno=%d(%s)\n",
                           full, (unsigned)st.st_mode, (int)st.st_uid, (int)st.st_gid,
                           e, strerror(e));
                    }
                }
                closedir(dd);
            }
            closedir(d);
        }
    }

    rp("\n--- 本进程已打开的 usb/video fd ---\n");
    probe_fd_table();

    rp("\n--- 相关库文件 ---\n");
    for (i = 0; libs[i]; i++) {
        struct stat st;
        if (stat(libs[i], &st) == 0) rp("  %s (%ld bytes)\n", libs[i], (long)st.st_size);
        else rp("  %s: absent\n", libs[i]);
    }

    rp("\n--- /proc/mounts sdcard ---\n");
    if (readfile("/proc/mounts", b, sizeof(b)) > 0) {
        char *p = strstr(b, "/sdcard");
        if (p) {
            char *nl = strchr(p, '\n');
            if (nl) *nl = 0;
            rp("  %s\n", p);
        }
    }

    rp("\n--- /system/bin & /system/xbin gcc ---\n");
    {
        const char *g[] = {"/system/xbin/gcc", "/system/bin/gcc", "/system/xbin/gcc4.8.2", NULL};
        for (i = 0; g[i]; i++) {
            struct stat st;
            if (stat(g[i], &st) == 0) rp("  %s present mode=%04o\n", g[i], (unsigned)st.st_mode);
            else rp("  %s absent\n", g[i]);
        }
    }

    rp("=== END ===\n");
    logmsg("report built len=%d\n", g_replen);
}

static int send_all(int fd, const char *buf, int len) {
    int off = 0;
    while (off < len) {
        int n = (int)send(fd, buf + off, (size_t)(len - off), 0);
        if (n <= 0) return -1;
        off += n;
    }
    return 0;
}

static int serve_client(int c) {
    char cmd[64];
    int clen = 0;
    Printf("PC connected\n");
    logmsg("client connected\n");
    if (send_all(c, g_rep, g_replen) != 0) { Printf("send fail\n"); return 0; }

    for (;;) {
        fd_set rf;
        struct timeval tv;
        int r, n, i;
        FD_ZERO(&rf);
        FD_SET(c, &rf);
        tv.tv_sec = 1;
        tv.tv_usec = 0;
        r = select(c + 1, &rf, NULL, NULL, &tv);
        if (r < 0) { if (errno == EINTR) continue; break; }
        if (r == 0) continue;
        n = (int)recv(c, cmd + clen, sizeof(cmd) - clen - 1, 0);
        if (n <= 0) break;
        clen += n;
        for (i = 0; i < clen; i++) {
            if (cmd[i] == '\n') {
                cmd[i] = 0;
                if (cmd[0] == 'Q') { Printf("quit\n"); return 1; }
                if (cmd[0] == 'R') { build_report(); send_all(c, g_rep, g_replen); }
                clen = 0;
                i = -1;
            }
        }
    }
    Printf("PC disconnected\n");
    return 0;
}

int Main(int argc, char **argv) {
    int s, on = 1;
    struct sockaddr_in addr;
    (void)argc; (void)argv;

    g_log = open(CAM_LOG, O_WRONLY | O_CREAT | O_APPEND, 0644);
    logmsg("=== CAMPROBE start ===\n");
    Printf("CAMPROBE building...\n");
    build_report();

    Printf("CAMPROBE ready\nport=9001\n");
    logmsg("listening 9001\n");

    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) { Printf("socket fail %d\n", errno); return -1; }
    (void)setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(CAM_PORT);
    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        Printf("bind fail %d\n", errno);
        logmsg("bind fail %d\n", errno);
        return -2;
    }
    if (listen(s, 4) < 0) { Printf("listen fail\n"); return -3; }

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
                int q = serve_client(c);
                close(c);
                if (q) break;
            }
        }
    }
    close(s);
    return 0;
}
