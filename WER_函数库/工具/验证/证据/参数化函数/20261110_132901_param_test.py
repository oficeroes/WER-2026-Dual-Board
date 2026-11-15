#<SKCON9><USB><ProgramA>

import threading
import time
import libstarpy

robot = Robot()

cm = None
var_last_cm = None

def func_MoveCm(cm):
    global var_last_cm
    var_last_cm = cm
    time.sleep(cm)
    pass


def main():
    global cm, var_last_cm
    func_MoveCm(10)
    func_MoveCm(20)

main()#program entry