/* CAMSHOT2.c —— 安全版：Camera() 放到子进程里调用
 *
 * 连接后先发文件系统报告，再等 PC 发命令：
 *   C        → fork 子进程调用 Camera(1)，父进程等 8 秒收尸，报告退出码/信号，
 *              然后重扫 /sdcard 列出新增文件
 *   C2       → 同上但 Camera(2)
 *   S        → 只重扫并列最近文件
 *   Q        → 退出
 *
 * 这样即使 Camera() 让子进程 SIGSEGV，主进程和连接都还在，能拿到诊断。
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <dirent.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/select.h>
#include <time.h>

extern void Printf(const char *format, ...);
extern void Clear(void);
extern void Camera(int pictureId);

#define SHOT_PORT 9001
#define SHOT_LOG  "/sdcard/Abilix/tmp/camshot2.log"
#define REP_MAX   (160 * 1024)
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
        if (strcmp(de->d_name, "Android") == 0) continue;
        snprintf(p, sizeof(p), "%s/%s", dir, de->d_name);
        if (lstat(p, &st) != 0) continue;
        if (S_ISDIR(st.st_mode)) walk(p, depth - 1);
        else if (S_ISREG(st.st_mode) && g_nent < MAX_ENT) {
            strncpy(g_ents[g_nent].path, p, sizeof(g_ents[0].path) - 1);
            g_ents[g_nent].path[sizeof(g_ents[0].path) - 1] = 0;
            g_ents[g_nent].size = (long)st.st_size;
            g_ents[g_nent].mtime = (long)st.st_mtime;
            g_nent++;
        }
    }
    closedir(d);
}

static void scan(void) {
    g_nent = 0;
    walk("/sdcard", 4);
    walk("/data/data/com.abilix.controller/files", 3);
    walk("/data/data/com.abilix.controller/cache", 3);
}

static int cmp_mtime(const void *a, const void *b) {
    const struct ent *x = (const struct ent *)a;
    const struct ent *y = (const struct ent *)b;
    if (x->mtime < y->mtime) return 1;
    if (x->mtime > y->mtime) return -1;
    return 0;
}

static void list_top(int limit) {
    int i;
    qsort(g_ents, (size_t)g_nent, sizeof(g_ents[0]), cmp_mtime);
    rp("--- 最近文件的 %d 个 ---\n", limit);
    for (i = 0; i < g_nent && i < limit; i++) {
        char tb[32];
        struct tm tmv;
        time_t tt = (time_t)g_ents[i].mtime;
        struct tm *lt = localtime(&tt);
        if (lt) { tmv = *lt; strftime(tb, sizeof(tb), "%m-%d %H:%M:%S", &tmv); }
        else strcpy(tb, "?");
        rp("  %s %9ld  %s\n", tb, g_ents[i].size, g_ents[i].path);
    }
}

static void list_dirs(void) {
    const char *dirs[] = {"/sdcard", "/sdcard/Abilix", "/storage/emulated/0",
                          "/data/data/com.abilix.controller/files", NULL};
    int i;
    rp("--- 目录结构 ---\n");
    for (i = 0; dirs[i]; i++) {
        DIR *d = opendir(dirs[i]);
        struct dirent *de;
        int cnt = 0;
        if (!d) { rp("  %s: opendir fail errno=%d\n", dirs[i], errno); continue; }
        rp("  %s/:\n", dirs[i]);
        while ((de = readdir(d)) != NULL && cnt < 40) {
            char p[512]; struct stat st;
            if (de->d_name[0] == '.') continue;
            snprintf(p, sizeof(p), "%s/%s", dirs[i], de->d_name);
            if (lstat(p, &st) == 0) {
                if (S_ISDIR(st.st_mode)) rp("      [d] %s\n", de->d_name);
                else rp("      [f] %-28s %ld\n", de->d_name, (long)st.st_size);
                cnt++;
            }
        }
        closedir(d);
    }
}

/* 在子进程里拍照，父进程收尸；返回 0=正常退出，>0=退出码，<0=信号 */
static int fork_camera(int pid) {
    pid_t p;
    int status = 0;
    int i;

    logmsg("fork Camera(%d)\n", pid);
    p = fork();
    if (p < 0) { rp("  fork 失败 errno=%d\n", errno); return -1; }
    if (p == 0) {
        Camera(pid);
        _exit(0);
    }
    for (i = 0; i < 80; i++) {           /* 最多等 8 秒 */
        pid_t r = waitpid(p, &status, WNOHANG);
        if (r == p) {
            if (WIFSIGNALED(status)) {
                int sg = WTERMSIG(status);
                rp("  Camera(%d) 子进程被信号终止: %d (%s)\n", pid, sg, strsignal(sg));
                logmsg("Camera signal %d\n", sg);
                return -sg;
            }
            rp("  Camera(%d) 子进程退出码 %d\n", pid, WEXITSTATUS(status));
            logmsg("Camera exit %d\n", WEXITSTATUS(status));
            return WEXITSTATUS(status);
        }
        usleep(100000);
    }
    kill(p, SIGKILL);
    waitpid(p, &status, 0);
    rp("  Camera(%d) 超时 8 秒，已杀掉\n", pid);
    return -999;
}

static void build_base(void) {
    g_replen = 0; g_rep[0] = 0;
    rp("=== CAMSHOT2 ===\n");
    rp("uid=%d pid=%d\n", (int)getuid(), (int)getpid());
    list_dirs();
    scan();
    rp("扫描到文件 %d 个\n", g_nent);
    list_top(20);
    rp("--- 命令：C=拍1张 / C2=拍2张 / S=重扫 / Q=退出 ---\n");
    rp("=== READY ===\n");
}

static void do_shot(int pid) {
    int r;
    time_t t0 = time(NULL);
    int i, nnew = 0;
    g_replen = 0; g_rep[0] = 0;
    rp("=== SHOT %d ===\n", pid);
    r = fork_camera(pid);
    sleep(1);
    scan();
    rp("--- 拍照后新增/变化（mtime>=%ld）---\n", (long)t0);
    for (i = 0; i < g_nent; i++) {
        if (g_ents[i].mtime >= (long)t0 - 1) {
            nnew++;
            rp("  NEW %-56s %8ld\n", g_ents[i].path, g_ents[i].size);
        }
    }
    rp("新增 %d 个；扫描总数 %d\n", nnew, g_nent);
    list_top(10);
    rp("=== END ===\n");
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
    build_base();
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
                if (cmd[0] == 'C') {
                    int pid = (cmd[1] == '2') ? 2 : 1;
                    do_shot(pid);
                    send_all(c, g_rep, g_replen);
                } else if (cmd[0] == 'S') {
                    g_replen = 0; g_rep[0] = 0;
                    scan(); rp("=== SCAN ===\n扫描到 %d 个\n", g_nent);
                    list_top(20); rp("=== END ===\n");
                    send_all(c, g_rep, g_replen);
                }
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
    logmsg("=== CAMSHOT2 start ===\n");
    Printf("CAMSHOT2 ready\nport=9001\n");

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
