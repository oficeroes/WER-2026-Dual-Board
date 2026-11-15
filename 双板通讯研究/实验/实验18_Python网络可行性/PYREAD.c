#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

/* 实验18 诊断读回器：把 PYNETPROBE 可能产生的所有文件读回来，发到 PC:12345
 * 由 8890 fileType=20 下发并在机器人屏幕运行（fileType=20 会自动 gcc 编译）。 */

#define PC_IP "192.168.1.105"
#define PC_PORT 12345

static int s;

static void snd(const char *b, int n) {
    int off = 0;
    while (off < n) {
        int w = (int)send(s, b + off, n - off, 0);
        if (w <= 0) { return; }
        off += w;
    }
}

static void snds(const char *t) { snd(t, (int)strlen(t)); }

static void send_file(const char *path) {
    FILE *f;
    char buf[2048];
    int n;
    snds("=== FILE ");
    snds(path);
    snds(" ===\n");
    f = fopen(path, "rb");
    if (!f) { snds("[MISSING]\n"); return; }
    while ((n = (int)fread(buf, 1, sizeof(buf), f)) > 0) { snd(buf, n); }
    fclose(f);
    snds("\n=== END ");
    snds(path);
    snds(" ===\n");
}

int Main(int argc, char **argv) {
    struct sockaddr_in a;
    int i;
    char tmp[32];
    const char *files[] = {
        "/sdcard/Abilix/tmp/_dir.txt",
        "/sdcard/Abilix/tmp/_dir2.txt",
        "/sdcard/Abilix/tmp/pynetprobe.txt",
        "/sdcard/Abilix/tmp/gcc_hello.log",
        "/sdcard/Abilix/tmp/hello1.out",
        "/sdcard/Abilix/tmp/gcc_wlnet.log",
        "/sdcard/Abilix/tmp/wlnet_sdcard.out",
        "/sdcard/Abilix/tmp/hello.c",
        "/data/data/com.abilix.controller/files/hello1.out",
        "/data/data/com.abilix.controller/files/wlnet_app.out",
        "/data/data/com.abilix.controller/files/write_test.txt",
        NULL
    };
    (void)argc;
    (void)argv;
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons(PC_PORT);
    a.sin_addr.s_addr = inet_addr(PC_IP);
    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) { return 2; }
    if (connect(s, (struct sockaddr *)&a, sizeof(a)) < 0) { return 3; }
    snds("PYREAD start pid=");
    sprintf(tmp, "%d", getpid());
    snds(tmp);
    snds("\n");
    system("ls -la /sdcard/Abilix/tmp/ > /sdcard/Abilix/tmp/_dir.txt 2>&1");
    system("ls -la /data/data/com.abilix.controller/files/ > /sdcard/Abilix/tmp/_dir2.txt 2>&1");
    for (i = 0; files[i]; i++) { send_file(files[i]); }
    snds("PYREAD done\n");
    shutdown(s, SHUT_WR);
    close(s);
    return 0;
}
