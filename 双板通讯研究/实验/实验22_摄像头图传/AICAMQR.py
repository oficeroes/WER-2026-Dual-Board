#<SKCON9><USB><AICAMQR>
# ============================================================
# AICAMQR.py —— 用官方 AI 接口驱动「人工智能摄像头」扫二维码
#   robot.start_qr_identify(秒)  对应积木「扫描二维码 持续 [N] 秒」
# 现象：屏幕循环显示本次扫描结果。扫到二维码就打印内容。
# 用途：确认摄像头在官方 App 这条链路上到底能不能出图。
# ============================================================

import time
import libstarpy

robot = Robot()

def show(lines):
    try:
        robot.clear()
        for s in lines:
            robot.print(s + '\n')
    except Exception:
        pass

def main():
    show(['AICAM QR', 'starting...'])
    time.sleep(0.5)

    n = 0
    ok = 0
    while True:
        n = n + 1
        show(['AICAM QR test', 'scan #' + str(n), 'scanning 3s...'])
        try:
            r = robot.start_qr_identify(3)
            s = str(r)
            ok = ok + 1
        except Exception as e:
            s = 'ERR ' + str(e)
        show(['AICAM QR test',
              'scan #' + str(n) + ' ok=' + str(ok),
              'QR=' + s[:60]])
        time.sleep(0.3)

main()
