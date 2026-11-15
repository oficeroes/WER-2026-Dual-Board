/* JNITEST.c —— 验证 Main 第一个参数是不是真的 JNIEnv*
 *
 * 做法：所有危险的 JNI 调用都放在 fork 出来的子进程里做，
 *      结果写文件，父进程读文件 -> 通过 9001 报回电脑。
 *      子进程就算 SIGSEGV，父进程和服务器都不受影响。
 *
 * 服务器 0.0.0.0:9001，连上即发报告（"=== END ===" 结尾）
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/select.h>

extern void Printf(const char *format, ...);

#define J_PORT 9001
#define J_LOG  "/sdcard/Abilix/tmp/jnitest.log"
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

/* ---------- JNI 最小调用（不依赖 jni.h） ---------- */
typedef void *JEnv;   /* JNIEnv* : 指向函数表的指针 */

static void **jni_fns(JEnv env) { return *(void ***)env; }

/* 子进程里执行：返回结果用固定结构写出 */
struct probe_result {
    int get_version;
    int findclass_ok;
    int findclass_throw;
    char detail[256];
};

static void probe_child(JEnv env, int outfd) {
    struct probe_result r;
    void **f = jni_fns(env);
    memset(&r, 0, sizeof(r));

    if (!f) { _exit(2); }

    /* index 0 = GetVersion */
    {
        int (*GetVersion)(JEnv) = (int (*)(JEnv))f[0];
        r.get_version = GetVersion(env);
    }

    /* index 6 = FindClass */
    {
        void *(*FindClass)(JEnv, const char *) = (void *(*)(JEnv, const char *))f[6];
        void *cls = FindClass(env, "java/lang/String");
        if (cls) {
            r.findclass_ok = 1;
        } else {
            /* index 15 = ExceptionOccurred, 16 = ExceptionDescribe, 17 = ExceptionClear
               （jni.h 顺序：GetVersion0 DefineClass1 FindClass2 ... ）
               实际顺序见下方注释，这里用保守处理：不清异常 */
            r.findclass_ok = 0;
        }
    }
    (void)!write(outfd, &r, sizeof(r));
    _exit(0);
}

static int run_probe(JEnv env, struct probe_result *out) {
    int fds[2];
    pid_t p;
    int status = 0, i;
    if (pipe(fds) != 0) return -1;
    p = fork();
    if (p < 0) { close(fds[0]); close(fds[1]); return -2; }
    if (p == 0) {
        close(fds[0]);
        probe_child(env, fds[1]);
        _exit(0);
    }
    close(fds[1]);
    memset(out, 0, sizeof(*out));
    {
        ssize_t n = read(fds[0], out, sizeof(*out));
        (void)n;
    }
    close(fds[0]);
    for (i = 0; i < 50; i++) {
        pid_t r = waitpid(p, &status, WNOHANG);
        if (r == p) break;
        usleep(100000);
    }
    if (i == 50) { kill(p, SIGKILL); waitpid(p, &status, 0); return -3; }
    if (WIFSIGNALED(status)) return -WTERMSIG(status);
    return 0;
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

static void build_report(JEnv env) {
    struct probe_result r;
    int rc;
    g_replen = 0; g_rep[0] = 0;

    rp("=== JNITEST ===\n");
    rp("uid=%d pid=%d\n", (int)getuid(), (int)getpid());
    rp("Main 参数 env=%p thiz=%p\n", (void *)env, (void *)0);

    rc = run_probe(env, &r);
    rp("probe rc=%d\n", rc);
    if (rc == 0) {
        rp("  GetVersion = 0x%08x\n", r.get_version);
        rp("  FindClass(java/lang/String) ok=%d\n", r.findclass_ok);
    } else if (rc < 0) {
        rp("  子进程被信号 %d (%s)\n", -rc, strsignal(-rc));
    }
    rp("=== END ===\n");
    logmsg("report len=%d rc=%d\n", g_replen, rc);
}

static int serve_client(int c, JEnv env) {
    char cmd[32]; int clen = 0;
    Printf("PC connected\n");
    build_report(env);
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
                if (cmd[0] == 'R') { build_report(env); send_all(c, g_rep, g_replen); }
                clen = 0; i = -1;
            }
        }
    }
    return 0;
}

int Main(void *env, void *thiz) {
    int s, on = 1; struct sockaddr_in addr;
    (void)thiz;
    g_log = open(J_LOG, O_WRONLY | O_CREAT | O_APPEND, 0644);
    logmsg("=== JNITEST start env=%p thiz=%p ===\n", env, thiz);
    Printf("JNITEST ready\nport=9001\n");

    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) { Printf("socket fail %d\n", errno); return -1; }
    (void)setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(J_PORT);
    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) { Printf("bind fail %d\n", errno); return -2; }
    if (listen(s, 4) < 0) { Printf("listen fail\n"); return -3; }

    for (;;) {
        fd_set rf; struct timeval tv; int r;
        FD_ZERO(&rf); FD_SET(s, &rf); tv.tv_sec = 1; tv.tv_usec = 0;
        r = select(s + 1, &rf, NULL, NULL, &tv);
        if (r > 0) {
            int c = (int)accept(s, NULL, NULL);
            if (c >= 0) { int q = serve_client(c, env); close(c); if (q) break; }
        }
    }
    close(s);
    return 0;
}
