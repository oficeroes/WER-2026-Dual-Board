/* CAMSHOT.c —— 探测 Camera(1)「拍照」到底把图存到哪
 *
 * 流程：
 *   1) 扫描 /sdcard + App 私有目录，记录文件(path,size,mtime)
 *   2) 调用 libRobot 的 Camera(1)
 *   3) 等 2 秒再扫，报告新增/变化的文件
 *   4) 结果通过 9001 回传电脑
 *
 * 服务器 0.0.0.0:9001，连上即发报告（"=== END ===" 结尾）
 * 命令：R 重新拍照并重扫；Q 退出
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
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/select.h>
#include <time.h>

extern void Printf(const char *format, ...);
extern void Clear(void);
extern void Camera(int pictureId);

#define SHOT_PORT 9001
#define SHOT_LOG  "/sdcard/Abilix/tmp/camshot.log"
#define REP_MAX   (128 * 1024)
#define MAX_ENT   6000

static char g_rep[REP_MAX];
static int  g_replen;
static int  g_log = -1;

struct ent { char path[240]; long size; long mtime; };
static struct ent g_ents[MAX_ENT];
static int g_nent;

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

static void walk(const char *dir, int depth) {
    DIR *d;
    struct dirent *de;
    if (depth <= 0 || g_nent >= MAX_ENT - 10) return;
    d = opendir(dir);
    if (!d) return;
    while ((de = readdir(d)) != NULL) {
        char p[512];
        struct stat st;
        if (de->d_name[0] == '.') continue;
        if (strcmp(de->d_name, "Android") == 0) continue;   /* 太大，跳过 */
        snprintf(p, sizeof(p), "%s/%s", dir, de->d_name);
        if (lstat(p, &st) != 0) continue;
        if (S_ISDIR(st.st_mode)) {
            walk(p, depth - 1);
        } else if (S_ISREG(st.st_mode)) {
            if (g_nent < MAX_ENT) {
                strncpy(g_ents[g_nent].path, p, sizeof(g_ents[0].path) - 1);
                g_ents[g_nent].path[sizeof(g_ents[0].path) - 1] = 0;
                g_ents[g_nent].size = (long)st.st_size;
                g_ents[g_nent].mtime = (long)st.st_mtime;
                g_nent++;
            }
        }
    }
    closedir(d);
}

static void scan(void) {
    g_nent = 0;
    walk("/sdcard", 4);
    walk("/data/data/com.abilix.controller/files", 3);
    walk("/data/data/com.abilix.controller/cache", 3);
    logmsg("scan n=%d\n", g_nent);
}

static int cmp_mtime(const void *a, const void *b) {
    const struct ent *x = (const struct ent *)a;
    const struct ent *y = (const struct ent *)b;
    if (x->mtime < y->mtime) return 1;
    if (x->mtime > y->mtime) return -1;
    return 0;
}

static void list_top(const char *title, int limit) {
    int i;
    qsort(g_ents, (size_t)g_nent, sizeof(g_ents[0]), cmp_mtime);
    rp("\n--- %s（最近 %d 个）---\n", title, limit);
    for (i = 0; i < g_nent && i < limit; i++) {
        rp("  %-58s %8ld  %s", g_ents[i].path, g_ents[i].size,
           ctime((const time_t *)&g_ents[i].mtime));
    }
}

static void list_dirs(void) {
    const char *dirs[] = {"/sdcard", "/sdcard/Abilix", "/storage/emulated/0", NULL};
    int i;
    rp("\n--- 目录结构 ---\n");
    for (i = 0; dirs[i]; i++) {
        DIR *d = opendir(dirs[i]);
        struct dirent *de;
        if (!d) { rp("  %s: opendir fail errno=%d\n", dirs[i], errno); continue; }
        rp("  %s/:\n", dirs[i]);
        while ((de = readdir(d)) != NULL) {
            char p[512]; struct stat st;
            if (de->d_name[0] == '.') continue;
            snprintf(p, sizeof(p), "%s/%s", dirs[i], de->d_name);
            if (lstat(p, &st) == 0 && S_ISDIR(st.st_mode)) rp("      [d] %s\n", de->d_name);
            else if (S_ISREG(st.st_mode)) rp("      [f] %-30s %ld\n", de->d_name, (long)st.st_size);
        }
        closedir(d);
    }
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

/* 拍一张，然后报告新文件；返回新增个数 */
static int shoot_and_diff(int pid, int report) {
    time_t t0 = time(NULL);
    int i, nnew = 0;
    Printf("Camera(%d)...\n", pid);
    logmsg("call Camera(%d)\n", pid);
    Camera(pid);
    sleep(2);

    scan();
    for (i = 0; i < g_nent; i++) {
        if (g_ents[i].mtime >= (long)t0 - 1) {
            nnew++;
            if (report) rp("  NEW %-54s %8ld\n", g_ents[i].path, g_ents[i].size);
        }
    }
    Printf("shot %d done, new=%d\n", pid, nnew);
    logmsg("shot %d new=%d\n", pid, nnew);
    return nnew;
}

static void build_report(void) {
    g_replen = 0; g_rep[0] = 0;
    rp("=== CAMSHOT ===\n");
    rp("uid=%d pid=%d\n", (int)getuid(), (int)getpid());
    list_dirs();
    scan();
    list_top("/sdcard 现有文件", 25);
    rp("\n--- 调用 Camera(1) 看新增 ---\n");
    shoot_and_diff(1, 1);
    rp("\n--- 再拍一张 Camera(2) ---\n");
    shoot_and_diff(2, 1);
    rp("=== END ===\n");
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
    g_log = open(SHOT_LOG, O_WRONLY | O_CREAT | O_APPEND, 0644);
    logmsg("=== CAMSHOT start ===\n");
    Printf("CAMSHOT ready\nport=9001\n");

    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) { Printf("socket fail %d\n", errno); return -1; }
    (void)setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(SHOT_PORT);
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
