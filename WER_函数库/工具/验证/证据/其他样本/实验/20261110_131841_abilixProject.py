#<SKCON9><USB><experiment>

import threading
import time
import libstarpy

robot = Robot()

from numbers import Number

var_past_9 = None
var_time = None
var_S2_0 = None
var_while = None
var_S2_1 = None
var_S3_0 = None
var_result_9 = None
var_past_7 = None
var_result_7 = None
var_S3_1 = None
var_past_10 = None
var_result_10 = None
var_past_8 = None
var_result_8 = None

def func_Learntofollowtheline():
    global var_past_9, var_time, var_S2_0, var_while, var_S2_1, var_S3_0, var_result_9, var_past_7, var_result_7, var_S3_1, var_past_10, var_result_10, var_past_8, var_result_8
    var_time = 3
    for count in range(int(var_time)):
        robot.clear()
        if True:
            robot.print('光电放在黑线上\n')
            robot.print('時間 ' +str(var_time) +'\n')

        var_time = (var_time if isinstance(var_time, Number) else 0) + -1
        time.sleep(1)
    robot.clear()
    if True:
        robot.print('光电放在黑线上\n')
        robot.print('時間 ' +str(var_time) +'\n')

    var_S2_0 = robot.get_gray(1)
    var_S3_0 = robot.get_gray(2)
    robot.set_ee(2,robot.clamp(var_S2_0, -99999, 99999))
    robot.set_ee(3,robot.clamp(var_S3_0, -99999, 99999))
    robot.play('luyin_p1')
    robot.set_double_motor_time(1,robot.clamp(10, -100, 100),2,robot.clamp(10, -100, 100),robot.clamp(0.5, 0, 3600))
    time.sleep(1)
    var_time = 3
    for count2 in range(int(var_time)):
        robot.clear()
        if True:
            robot.print('光电放在白底上\n')
            robot.print('時間 ' +str(var_time) +'\n')

        var_time = (var_time if isinstance(var_time, Number) else 0) + -1
        time.sleep(1)
    robot.clear()
    if True:
        robot.print('光电放在白底上\n')
        robot.print('時間 ' +str(var_time) +'\n')

    var_S2_1 = robot.get_gray(1)
    var_S3_1 = robot.get_gray(2)
    robot.set_ee(6,robot.clamp(var_S2_1, -99999, 99999))
    robot.set_ee(7,robot.clamp(var_S3_1, -99999, 99999))
    robot.play('luyin_p1')
    robot.clear()
    if True:
        robot.print('白底S2 ' +str(robot.get_ee(2)) +'\n')
        robot.print('白底S3 ' +str(robot.get_ee(3)) +'\n')
        robot.print('黑线S2 ' +str(robot.get_ee(6)) +'\n')
        robot.print('黑线S3 ' +str(robot.get_ee(7)) +'\n')

    while True:
        if robot.get_touch(5):
            break
        if robot.get_touch(6):
            var_time = 3
            for count3 in range(int(var_time)):
                robot.clear()
                if True:
                    robot.print('校准陀螺仪\n')
                    robot.print('時間 ' +str(var_time) +'\n')

                var_time = (var_time if isinstance(var_time, Number) else 0) + -1
                time.sleep(1)
            robot.reset_gyro()
            break
    pass

def func_name():
    global var_past_9, var_time, var_S2_0, var_while, var_S2_1, var_S3_0, var_result_9, var_past_7, var_result_7, var_S3_1, var_past_10, var_result_10, var_past_8, var_result_8
    #黑线数据位置
    if True:
        #黑线S2
        robot.print('数据地址 ' +str(2) +'\n')
        #黑线S3
        robot.print('数据地址 ' +str(3) +'\n')
    #白底数据位置
    if True:
        #白底S2
        robot.print('数据地址 ' +str(6) +'\n')
        #白底S3
        robot.print('数据地址 ' +str(7) +'\n')
    pass

def func_initial():
    global var_past_9, var_time, var_S2_0, var_while, var_S2_1, var_S3_0, var_result_9, var_past_7, var_result_7, var_S3_1, var_past_10, var_result_10, var_past_8, var_result_8
    var_time = 0
    var_S2_0 = 0
    var_S2_1 = 0
    var_S3_0 = 0
    var_S3_1 = 0
    var_past_10 = 0
    var_past_8 = 0
    var_past_9 = 0
    var_past_7 = 0
    robot.set_motor(1,robot.clamp(10, -100, 100))
    robot.set_motor(2,robot.clamp(10, -100, 100))
    time.sleep(0.01)
    func_off()
    robot.reset_encoder(1);
    robot.reset_encoder(2);
    pass

def func_off():
    global var_past_9, var_time, var_S2_0, var_while, var_S2_1, var_S3_0, var_result_9, var_past_7, var_result_7, var_S3_1, var_past_10, var_result_10, var_past_8, var_result_8
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    pass


def main():
    global var_past_9, var_time, var_S2_0, var_while, var_S2_1, var_S3_0, var_result_9, var_past_7, var_result_7, var_S3_1, var_past_10, var_result_10, var_past_8, var_result_8
    func_initial()
    var_while = 70
    while True:
        if robot.get_touch(1):
            robot.reset_timer(1)
            for count4 in range(int(var_while)):
                var_past_9 = (var_past_9 + robot.get_gray(9))
                var_past_10 = (var_past_10 + robot.get_gray(10))
                robot.clear()
                if True:
                    robot.print('正在计算中. . .     倒计时:  ' +str(robot.round((((var_while / 10) + 1) - robot.round((robot.get_timer_ms(1) / 1000))))) +'\n')
                    robot.print('灰度9： ' +str(robot.get_gray(9)) +'\n')
                    robot.print('灰度10： ' +str(robot.get_gray(10)) +'\n')

                time.sleep(0.01)
            var_result_9 = robot.round((robot.round((var_past_9 / var_while)) * 1))
            var_result_10 = robot.round((robot.round((var_past_10 / var_while)) * 1))
            robot.clear()
            if True:
                robot.print('灰度9： ' +str(var_result_9) +'\n')
                robot.print('灰度10： ' +str(var_result_10) +'\n')

            robot.set_ee(9,robot.clamp(var_result_9, -99999, 99999))
            robot.set_ee(10,robot.clamp(var_result_10, -99999, 99999))
            break

main()#program entry