/* CAMPROBE2.c —— 摄像头设备形态与权限深挖（跑在机器人 App 进程里）
 *
 * 相比 CAMPROBE：
 *   - 列全部 /dev（不只 video）
 *   - /dev/video* 详细能力
 *   - /dev/bus/usb 节点权限 + open 结果
 *   - root 迹象：su 二进制、build.prop 的 ro.debuggable/ro.secure/ro.build.type
 *   - 常用工具：nc / toybox / busybox / screencap / am / sh
 *   - /proc/self/fd（带 errno）、/proc/self/maps 里的 App 私有 .so
 *   - 每次 PC 连入都重新扫描（可以在程序不重启的情况下看插入/拔出变化）
 *
 * 服务器 0.0.0.0:9001，连上即发报告（"=== END ===" 结尾），R 重扫，Q 退出。
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

#define CAM_PORT 9001
#define CAM_LOG  "/sdcard/Abilix/tmp/camprobe2.log"
#define REP_MAX  (96 * 1024)

static char g_rep[REP_MAX];
static int  g_replen;
static int  g_log = -1;

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

static int readfile(const char *path, char *buf, int cap) {
    int fd = open(path, O_RDONLY), n;
    if (fd < 0) return -1;
    n = (int)read(fd, buf, (size_t)(cap - 1));
    close(fd);
    if (n < 0) n = 0;
    buf[n] = 0;
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r')) buf[--n] = 0;
    return n;
}

static void statline(const char *path, int do_open) {
    struct stat st;
    if (stat(path, &st) != 0) { rp("  %-42s absent\n", path); return; }
    rp("  %-42s mode=%04o uid=%d gid=%d", path, (unsigned)st.st_mode,
       (int)st.st_uid, (int)st.st_gid);
    if (do_open) {
        int fd = open(path, O_RDWR), e;
        if (fd >= 0) { rp(" openRw=OK"); close(fd); }
        else { e = errno; rp(" openRw=FAIL errno=%d(%s)", e, strerror(e)); }
    }
    rp("\n");
}

struct v4l2_capability {
    unsigned char driver[16]; unsigned char card[32]; unsigned char bus_info[32];
    unsigned int version, capabilities, device_caps, reserved[3];
};
struct v4l2_fmtdesc {
    unsigned int index, type, flags; unsigned char description[32];
    unsigned int pixelformat, reserved[4];
};
#define VIDIOC_QUERYCAP 0x80685600UL
#define VIDIOC_ENUM_FMT 0xC0405602UL

static void probe_video_node(const char *path) {
    struct stat st;
    int fd, e, i;
    struct v4l2_capability cap;
    struct v4l2_fmtdesc fm;
    if (stat(path, &st) != 0) { rp("  %s absent\n", path); return; }
    rp("  %s mode=%04o uid=%d gid=%d rdev=%u:%u\n", path,
       (unsigned)st.st_mode, (int)st.st_uid, (int)st.st_gid,
       (unsigned)(st.st_rdev >> 8), (unsigned)(st.st_rdev & 0xFF));
    fd = open(path, O_RDWR);
    if (fd < 0) {
        e = errno;
        rp("    openRw FAIL errno=%d(%s)\n", e, strerror(e));
        fd = open(path, O_RDONLY);
        if (fd < 0) { e = errno; rp("    openRo FAIL errno=%d(%s)\n", e, strerror(e)); return; }
        rp("    openRo OK\n");
    } else rp("    openRw OK\n");
    memset(&cap, 0, sizeof(cap));
    if (ioctl(fd, VIDIOC_QUERYCAP, &cap) == 0) {
        rp("    driver=%s card=%s bus=%s caps=%08x devcaps=%08x\n",
           cap.driver, cap.card, cap.bus_info, cap.capabilities, cap.device_caps);
        for (i = 0; i < 8; i++) {
            memset(&fm, 0, sizeof(fm)); fm.index = (unsigned)i; fm.type = 1;
            if (ioctl(fd, VIDIOC_ENUM_FMT, &fm) != 0) break;
            rp("    fmt %c%c%c%c %s\n",
               (int)(fm.pixelformat & 0xFF), (int)((fm.pixelformat >> 8) & 0xFF),
               (int)((fm.pixelformat >> 16) & 0xFF), (int)((fm.pixelformat >> 24) & 0xFF),
               fm.description);
        }
    } else {
        e = errno; rp("    QUERYCAP FAIL errno=%d(%s)\n", e, strerror(e));
    }
    close(fd);
}

static void build_report(void) {
    struct utsname un;
    static char b[16384];
    int i;
    DIR *d;
    struct dirent *de;

    static const char *sus[] = {
        "/system/bin/su", "/system/xbin/su", "/system/sbin/su",
        "/su/bin/su", "/system/bin/failsafe/su", "/sbin/su", NULL
    };
    static const char *tools[] = {
        "/system/bin/nc", "/system/xbin/nc", "/system/bin/toybox",
        "/system/bin/busybox", "/system/bin/screencap", "/system/bin/am",
        "/system/bin/sh", "/system/xbin/gcc4.8.2", "/system/bin/dmesg", NULL
    };

    g_replen = 0; g_rep[0] = 0;

    rp("=== CAMPROBE2 ===\n");
    rp("uid=%d gid=%d pid=%d\n", (int)getuid(), (int)getgid(), (int)getpid());
    if (uname(&un) == 0) rp("uname=%s %s %s\n", un.sysname, un.release, un.machine);

    /* build.prop 关键行 */
    rp("\n--- build.prop ---\n");
    if (readfile("/system/build.prop", b, sizeof(b)) > 0) {
        char *p = b;
        while (*p) {
            char *nl = strchr(p, '\n');
            if (nl) *nl = 0;
            if (strstr(p, "ro.debuggable") || strstr(p, "ro.secure") ||
                strstr(p, "ro.build.type") || strstr(p, "ro.build.tags") ||
                strstr(p, "ro.product.model") || strstr(p, "ro.build.version.release"))
                rp("  %s\n", p);
            if (!nl) break;
            p = nl + 1;
        }
    } else rp("  read fail errno=%d\n", errno);

    /* /dev 全量 */
    rp("\n--- /dev (全部) ---\n");
    d = opendir("/dev");
    if (d) {
        int cnt = 0;
        while ((de = readdir(d)) != NULL) {
            struct stat st; char full[512];
            if (de->d_name[0] == '.') continue;
            snprintf(full, sizeof(full), "/dev/%s", de->d_name);
            if (stat(full, &st) != 0) continue;
            rp("  %-24s %s %04o %d:%d\n", de->d_name,
               S_ISDIR(st.st_mode) ? "dir " : (S_ISCHR(st.st_mode) ? "chr " : "oth "),
               (unsigned)st.st_mode, (int)st.st_uid, (int)st.st_gid);
            if (++cnt > 110) { rp("  ...truncated\n"); break; }
        }
        closedir(d);
    } else rp("  opendir fail errno=%d\n", errno);

    rp("\n--- 摄像头原始节点 ---\n");
    for (i = 0; i < 10; i++) {
        char p[64];
        snprintf(p, sizeof(p), "/dev/video%d", i);
        probe_video_node(p);
    }
    statline("/dev/media0", 1);
    statline("/dev/v4l-subdev0", 1);

    rp("\n--- 串口（若摄像头是 USB 转串口） ---\n");
    for (i = 0; i < 8; i++) {
        char p[64];
        snprintf(p, sizeof(p), "/dev/ttyUSB%d", i);
        statline(p, 1);
        snprintf(p, sizeof(p), "/dev/ttyACM%d", i);
        statline(p, 1);
    }

    rp("\n--- root 迹象 ---\n");
    for (i = 0; sus[i]; i++) statline(sus[i], 0);
    rp("  uid/euid=%d/%d\n", (int)getuid(), (int)geteuid());

    rp("\n--- 常用工具 ---\n");
    for (i = 0; tools[i]; i++) statline(tools[i], 0);

    rp("\n--- usb sysfs ---\n");
    d = opendir("/sys/bus/usb/devices");
    if (d) {
        while ((de = readdir(d)) != NULL) {
            char p[512], f[512], v[64];
            if (de->d_name[0] == '.') continue;
            snprintf(p, sizeof(p), "/sys/bus/usb/devices/%s", de->d_name);
            if (strchr(de->d_name, ':')) {
                snprintf(f, sizeof(f), "%s/bInterfaceClass", p);
                readfile(f, v, sizeof(v));
                rp("  if %-14s class=%s", de->d_name, v);
                snprintf(f, sizeof(f), "%s/bInterfaceSubClass", p);
                readfile(f, v, sizeof(v)); rp("/%s", v);
                snprintf(f, sizeof(f), "%s/driver", p);
                {
                    ssize_t rn = readlink(f, v, sizeof(v) - 1);
                    if (rn > 0) { v[rn] = 0; rp(" drv=%s", strrchr(v, '/') ? strrchr(v, '/') + 1 : v); }
                }
                rp("\n");
            } else {
                snprintf(f, sizeof(f), "%s/idVendor", p);
                readfile(f, v, sizeof(v)); rp("  dev %-12s vid=%s", de->d_name, v);
                snprintf(f, sizeof(f), "%s/idProduct", p);
                readfile(f, v, sizeof(v)); rp(" pid=%s", v);
                snprintf(f, sizeof(f), "%s/product", p);
                readfile(f, v, sizeof(v)); rp(" product=%s\n", v);
            }
        }
        closedir(d);
    } else rp("  opendir fail errno=%d\n", errno);

    rp("\n--- /dev/bus/usb ---\n");
    d = opendir("/dev/bus/usb");
    if (d) {
        struct dirent *bus;
        while ((bus = readdir(d)) != NULL) {
            DIR *dd; struct dirent *dv; char bp[256];
            if (bus->d_name[0] == '.') continue;
            snprintf(bp, sizeof(bp), "/dev/bus/usb/%s", bus->d_name);
            dd = opendir(bp);
            if (!dd) { rp("  %s opendir fail errno=%d\n", bp, errno); continue; }
            while ((dv = readdir(dd)) != NULL) {
                char full[512];
                if (dv->d_name[0] == '.') continue;
                snprintf(full, sizeof(full), "%s/%s", bp, dv->d_name);
                statline(full, 1);
            }
            closedir(dd);
        }
        closedir(d);
    } else rp("  opendir fail errno=%d\n", errno);

    rp("\n--- /proc/self/fd ---\n");
    d = opendir("/proc/self/fd");
    if (d) {
        while ((de = readdir(d)) != NULL) {
            char p[512], t[512]; ssize_t n;
            if (de->d_name[0] == '.') continue;
            snprintf(p, sizeof(p), "/proc/self/fd/%s", de->d_name);
            n = readlink(p, t, sizeof(t) - 1);
            if (n <= 0) continue;
            t[n] = 0;
            rp("  fd %-3s -> %s\n", de->d_name, t);
        }
        closedir(d);
    } else rp("  opendir fail errno=%d(%s)\n", errno, strerror(errno));

    rp("\n--- App 私有 .so（maps） ---\n");
    if (readfile("/proc/self/maps", b, sizeof(b)) > 0) {
        char *p = b;
        while (*p) {
            char *nl = strchr(p, '\n');
            if (nl) *nl = 0;
            if (strstr(p, ".so") && (strstr(p, "/data/") || strstr(p, "libuvc") || strstr(p, "libusb")))
                rp("  %s\n", strstr(p, "/") ? strstr(p, "/") : p);
            if (!nl) break;
            p = nl + 1;
        }
    } else rp("  read fail errno=%d\n", errno);

    rp("=== END ===\n");
    logmsg("report len=%d\n", g_replen);
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
    char cmd[64]; int clen = 0;
    Printf("PC connected\n");
    build_report();
    if (send_all(c, g_rep, g_replen) != 0) return 0;
    for (;;) {
        fd_set rf; struct timeval tv; int r, n, i;
        FD_ZERO(&rf); FD_SET(c, &rf); tv.tv_sec = 1; tv.tv_usec = 0;
        r = select(c + 1, &rf, NULL, NULL, &tv);
        if (r < 0) { if (errno == EINTR) continue; break; }
        if (r == 0) continue;
        n = (int)recv(c, cmd + clen, sizeof(cmd) - clen - 1, 0);
        if (n <= 0) break;
        clen += n;
        for (i = 0; i < clen; i++) {
            if (cmd[i] == '\n') {
                cmd[i] = 0;
                if (cmd[0] == 'Q') return 1;
                if (cmd[0] == 'R') { build_report(); send_all(c, g_rep, g_replen); }
                clen = 0; i = -1;
            }
        }
    }
    return 0;
}

int Main(int argc, char **argv) {
    int s, on = 1; struct sockaddr_in addr;
    (void)argc; (void)argv;
    g_log = open(CAM_LOG, O_WRONLY | O_CREAT | O_APPEND, 0644);
    logmsg("=== CAMPROBE2 start ===\n");
    Printf("CAMPROBE2 ready\nport=9001\n");

    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) { Printf("socket fail %d\n", errno); return -1; }
    (void)setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(CAM_PORT);
    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) { Printf("bind fail %d\n", errno); return -2; }
    if (listen(s, 4) < 0) { Printf("listen fail\n"); return -3; }

    for (;;) {
        fd_set rf; struct timeval tv; int r;
        FD_ZERO(&rf); FD_SET(s, &rf); tv.tv_sec = 1; tv.tv_usec = 0;
        r = select(s + 1, &rf, NULL, NULL, &tv);
        if (r > 0) {
            int c = (int)accept(s, NULL, NULL);
            if (c >= 0) { int q = serve_client(c); close(c); if (q) break; }
        }
    }
    close(s);
    return 0;
}
