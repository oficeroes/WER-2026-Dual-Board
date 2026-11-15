#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

/* 实验18 最小连通性测试：连 PC:12345 发一句就结束（用于确认 C 通道+监听仍正常） */
#define PC_IP "192.168.1.105"
#define PC_PORT 12345

int Main(int argc, char **argv) {
    struct sockaddr_in a;
    int s;
    char buf[64];
    (void)argc;
    (void)argv;
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons(PC_PORT);
    a.sin_addr.s_addr = inet_addr(PC_IP);
    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) { return 2; }
    if (connect(s, (struct sockaddr *)&a, sizeof(a)) < 0) { return 3; }
    sprintf(buf, "HELLO from robot C pid=%d\n", getpid());
    (void)!send(s, buf, (int)strlen(buf), 0);
    shutdown(s, SHUT_WR);
    close(s);
    return 0;
}
