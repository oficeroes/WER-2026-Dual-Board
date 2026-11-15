# 生成「双板通讯」直测程序 WL_A.py / WL_B.py（把 wl_prelude.py 原样拼进程序）。
# 用法: py -3 生成测试程序.py
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PRELUDE = os.path.join(HERE, "wl_prelude.py")

SEND_ADDR = 1
RECV_ADDR = 2
TEXT_ADDR = 3

BODY = '''
_wl_set_ip("%(peer)s")
robot.print("\\n%(name)s start peer=%(peer)s")
i = 0
while i < 180:
    i += 1
    _wl_send(%(send_addr)d, i)
    _wl_send(%(text_addr)d, "%(text)s")
    v = _wl_recv(%(recv_addr)d)
    t = _wl_recv(%(text_addr)d)
    robot.print("\\n%(name)s i=%%d rx=%%s rx3=%%s err=%%r" %% (i, v, t, _wl["errors"]))
    time.sleep(1.0)
robot.print("\\n%(name)s done")
'''


def make(name, peer, text):
    with open(PRELUDE, "r", encoding="utf-8") as f:
        prelude = f.read()
    body = BODY % {
        "name": name,
        "peer": peer,
        "send_addr": SEND_ADDR,
        "recv_addr": RECV_ADDR,
        "text_addr": TEXT_ADDR,
        "text": text,
    }
    content = "#<SKCON9><WiFi><%s>\nimport time\nimport libstarpy\nrobot = Robot()\n" % name
    content += prelude + "\n" + body
    path = os.path.join(HERE, name + ".py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("wrote %s (%d bytes)" % (path, len(content)))


make("WLA", "192.168.1.103", "A-text")
make("WLB", "192.168.1.102", "B-text")
