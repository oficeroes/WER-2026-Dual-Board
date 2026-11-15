#<SKCON9><USB><NativeTest>

import threading
import time
import libstarpy

robot = Robot()

def func_Hello():
    robot.print('hello world\n')
    pass

def main():
    func_Hello()

main()#program entry