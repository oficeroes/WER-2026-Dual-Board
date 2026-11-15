#<SKCON9><WiFi><ProgramB>
# ============================================================
# 实验08 · WiFi 两板 TCP · 客户端 B（与 实验08 服务端A 配套）
# ------------------------------------------------------------
# 前提：实验05 探测 socket 可用；A 板先运行服务端程序并停在 "listen 12345"。
#
# 需要填：A_IP = A 板的 IP
#   - A 连路由器时：就是下载工具里填过的 A 板 IP（路由器后台可查）；
#   - A 开热点时：热点网段常见 192.168.43.1，真机确认。
#
# 程序作用：每 2 秒向 A 发一行文本（含序号），打印 A 的回包；屏幕显示最近一条回包。
# ============================================================

import time
import libstarpy

robot = Robot()

# ------------------------- 参数区（必须按实际改） -------------------------
A_IP = '192.168.43.1'   # TODO：改成 A 板真实 IP
PORT = 12345
INTERVAL = 2.0          # 发送间隔（秒）

def main():
    robot.clear()
    robot.print('B: wifi client\n')
    robot.print('A=' + A_IP + '\n')
    time.sleep(0.8)

    try:
        import socket
    except Exception as e:
        robot.print('NO SOCKET\n')
        robot.print(str(e) + '\n')
        return

    n = 0
    while True:
        n = n + 1
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((A_IP, PORT))
            msg = 'hello ' + str(n) + '\n'
            s.sendall(msg.encode('utf-8'))
            data = s.recv(256)
            try:
                reply = data.decode('utf-8')
            except Exception:
                reply = str(data)
            robot.print('TX ' + str(n) + ' ok\n')
            robot.print('RX: ' + reply + '\n')
            s.close()
        except Exception as e:
            robot.print('ERR ' + str(n) + '\n')
            robot.print(str(e) + '\n')
        time.sleep(INTERVAL)

main()  # program entry
