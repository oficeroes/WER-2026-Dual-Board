#<SKCON9><USB><ProbeRead>
# 读回探测结果：把 EEPROM 1..74 打印到屏幕（运行 ProbeEnv 之后用）
# 用途：机器人屏幕小、EEPROM 页面翻页麻烦时，逐条打印便于拍照记录。
# 下载程序名：ProbeRead（与文件头一致）
import time
import libstarpy

robot = Robot()

ADDRS = [
    1, 2, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22,
    23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33,
    40, 41, 42, 43, 44, 45, 46,
    50, 51, 52, 53, 54, 55,
    60, 61, 70, 71, 72,
]


def main():
    robot.print("=== ProbeRead ===")
    i = 0
    while i < len(ADDRS):
        addr = ADDRS[i]
        try:
            robot.print("EE[%d] = %d" % (addr, robot.get_ee(addr)))
        except Exception as e:
            robot.print("EE[%d] read err: %s" % (addr, e))
        i += 1
        time.sleep(0.05)
    robot.print("=== end ===")


main()
