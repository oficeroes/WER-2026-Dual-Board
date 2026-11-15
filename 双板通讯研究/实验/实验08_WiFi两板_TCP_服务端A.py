#<SKCON9><WiFi><ProgramA>
# ============================================================
# 实验08 · WiFi 两板 TCP · 服务端 A（先跑 实验05 确认 socket 可用！）
# ------------------------------------------------------------
# 前提：实验05 的探测结果是 socket=2（能创建并 bind）或至少 socket=1。
#       若 socket=0，本程序会在屏幕上打印 "NO SOCKET"，到此为止，改走实验01/02。
#
# 组网（二选一）：
#   A. 两板都连同一个 2.4G 路由器（推荐）：A、B 各在"设置→WLAN"连同一 SSID；
#      PC 也能连同一个路由器，用下载工具时填的 IP 就是各板 IP。
#   B. A 开热点、B 连 A 的热点（Android 热点网段常见 192.168.43.x，A=192.168.43.1，需真机确认）。
#
# 程序作用：A 在 0.0.0.0:12345 监听，收到 B 的一行文本后回显 + 计数，屏幕显示收发内容。
#           B 端程序：实验08_WiFi两板_TCP_客户端B.py。
#
# 注意：
#   - 如果运行时报错（权限/无 socket），把错误打印出来并记下来；
#   - 端口号尽量选 12345 这类不冲突的；若被占用换 23456；
#   - 本程序是"阻塞服务端"，A 在 accept 期间不做别的动作（比赛程序里可改成线程，若 threading 可用）。
# ============================================================

import time
import libstarpy

robot = Robot()

# ------------------------- 参数区 -------------------------
PORT = 12345
MAX_BYTES = 256

def main():
    robot.clear()
    robot.print('A: wifi server\n')
    time.sleep(0.5)

    try:
        import socket
    except Exception as e:
        robot.print('NO SOCKET\n')
        robot.print(str(e) + '\n')
        return

    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', PORT))
        srv.listen(1)
        robot.print('listen ' + str(PORT) + '\n')
    except Exception as e:
        robot.print('BIND FAIL\n')
        robot.print(str(e) + '\n')
        return

    count = 0
    while True:
        try:
            conn, addr = srv.accept()
            robot.print('client ' + str(addr) + '\n')
            data = conn.recv(MAX_BYTES)
            if data:
                try:
                    text = data.decode('utf-8')
                except Exception:
                    text = str(data)
                count = count + 1
                robot.print('RX' + str(count) + ': ' + text + '\n')
                conn.sendall(('ACK' + str(count) + ':' + text + '\n').encode('utf-8'))
            conn.close()
        except Exception as e:
            robot.print('ERR\n')
            robot.print(str(e) + '\n')
            time.sleep(0.5)

main()  # program entry
