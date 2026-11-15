#<SKCON9><WiFi><EETEST>
# 实验20：读写数据(EEPROM)掉电保持 + 未写槽初始值探测
import time
import libstarpy

robot = Robot()


def P(s):
    try:
        robot.print(str(s) + "\n")
    except Exception:
        pass


P("EETEST start")
for a in (1, 2, 121, 122, 123, 126, 127, 128):
    try:
        P("pre%d=%d" % (a, robot.get_ee(a)))
    except Exception as e:
        P("pre%d ERR %r" % (a, e))
for a, v in ((121, 1101), (122, 1102), (123, 1103)):
    try:
        robot.set_ee(a, v)
    except Exception as e:
        P("set%d ERR %r" % (a, e))
time.sleep(0.3)
for a in (121, 122, 123):
    try:
        P("post%d=%d" % (a, robot.get_ee(a)))
    except Exception as e:
        P("post%d ERR %r" % (a, e))
P("EETEST done")
