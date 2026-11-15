#<SKCON9><USB><PI>

import threading
import time
import libstarpy

robot = Robot()

from numbers import Number

var_ray_left_PID = None
var_ray_right_PID = None
var_ray_left_Error = None
var_ray_white = None
var_ray_left_last_Error = None
var_ray_time = None
var_angle = None
var_ray_choose = None
var_Kp = None
var_cm = None
var_Error_Ki = None
var_turn_Error_Ki = None
var_ray_right_Error = None
var_1cm = None
var_ray_right_last_Error = None
var_angle_up = None
var_ray_speed = None
var_speed = None
var_cm_up = None
var_ray_light_9 = None
var_ray_Kp = None
var_1angle = None
var_angle_down = None
var_cm_down = None
var_Error = None
var_ray_light_10 = None
var_ray_Kd = None
var_turn_speed_max = None
var_speed_max = None
var_turn_RL = None
var_turn_Error = None
var_ray_return_time = None
var_turn_speed_min = None
var_speed_min = None
var_turn_Ki = None
var_Ki = None
var_turn_Kp = None
var_PI = None
var_turn_PI = None
var_turn_speed = None

def func_end():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    #自转
    if True:
        var_angle = robot.ceil((23 * var_1angle))
        var_angle_up = robot.ceil((10 * var_1angle))
        var_angle_down = robot.ceil((10 * var_1angle))
        var_turn_speed_max = 25
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.012
        var_turn_RL = '右'
        func_Turn()
    #前进
    if True:
        var_cm = (78.4 * var_1cm)
        var_cm_up = (10 * var_1cm)
        var_cm_down = (10 * var_1cm)
        var_speed_max = 50
        var_speed_min = 4
        var_Ki = 0.001
        var_Kp = 0.01
        func_forward()
    #自转
    if True:
        var_angle = robot.ceil((66.5 * var_1angle))
        var_angle_up = robot.ceil((10 * var_1angle))
        var_angle_down = robot.ceil((10 * var_1angle))
        var_turn_speed_max = 25
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.012
        var_turn_RL = '右'
        func_Turn()
    #巡线
    if True:
        # 左，右，十字，时间
        var_ray_choose = '路口'
        var_ray_speed = 10
        var_ray_Kp = 0.002
        var_ray_Kd = 0
        func_ray()
    #前进
    if True:
        var_cm = (14.3 * var_1cm)
        var_cm_up = (4 * var_1cm)
        var_cm_down = (4 * var_1cm)
        var_speed_max = 10
        var_speed_min = 3
        var_Ki = 0.001
        var_Kp = 0.01
        func_forward()
    #自转
    if True:
        var_angle = robot.ceil((88 * var_1angle))
        var_angle_up = robot.ceil((20 * var_1angle))
        var_angle_down = robot.ceil((40 * var_1angle))
        var_turn_speed_max = 20
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.012
        var_turn_RL = '左'
        func_Turn()
    robot.set_double_motor_encoder(1,robot.clamp(-10, -100, 100),2,robot.clamp(-10, -100, 100),1,robot.clamp(770, -99999, 99999))
    robot.set_motor_time(3,robot.clamp(5, -100, 100),robot.clamp(1.3, 0, 3600))
    time.sleep(0.25)
    robot.set_double_motor_encoder(1,robot.clamp(15, -100, 100),2,robot.clamp(15, -100, 100),1,robot.clamp(1320, -99999, 99999))
    #自转
    if True:
        var_angle = robot.ceil((120 * var_1angle))
        var_angle_up = robot.ceil((10 * var_1angle))
        var_angle_down = robot.ceil((10 * var_1angle))
        var_turn_speed_max = 25
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.012
        var_turn_RL = '左'
        func_Turn()
    func_name2()
    pass

def func_name2():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    robot.reset_timer(1)
    while True:
        if robot.get_timer_ms(1) <= 600:
            robot.set_motor(1,robot.clamp(60, -100, 100))
            robot.set_motor(2,robot.clamp(60, -100, 100))
        else:
            while True:
                if robot.get_timer_ms(1) <= 950:
                    robot.set_motor(2,robot.clamp(50, -100, 100))
                    robot.set_motor(1,robot.clamp(0, -100, 100))
                else:
                    while True:
                        if robot.get_timer_ms(1) <= 1300:
                            robot.set_motor(1,robot.clamp(100, -100, 100))
                            robot.set_motor(2,robot.clamp(100, -100, 100))
                        else:
                            robot.set_motor(1,robot.clamp(0, -100, 100))
                            robot.set_motor(2,robot.clamp(0, -100, 100))
                            break
                    break
            break
    pass

def func_green_end():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    #自转
    if True:
        var_angle = robot.ceil((10 * var_1angle))
        var_angle_up = robot.ceil((5 * var_1angle))
        var_angle_down = robot.ceil((10 * var_1angle))
        var_turn_speed_max = 20
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.012
        var_turn_RL = '左'
        func_Turn()
    #前进
    if True:
        var_cm = (51 * var_1cm)
        var_cm_up = (10 * var_1cm)
        var_cm_down = (10 * var_1cm)
        var_speed_max = 45
        var_speed_min = 4
        var_Ki = 0.001
        var_Kp = 0.01
        func_forward()
    #自转
    if True:
        var_angle = robot.ceil((99 * var_1angle))
        var_angle_up = robot.ceil((5 * var_1angle))
        var_angle_down = robot.ceil((19 * var_1angle))
        var_turn_speed_max = 20
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.012
        var_turn_RL = '右'
        func_Turn()
    #巡线
    if True:
        #选择模式  矩离，时间，路口
        if True:
            # 左，右，十字，时间
            var_ray_choose = '时间'
        #时间模式
        if True:
            var_ray_return_time = 1
        var_ray_speed = 10
        var_ray_Kp = 0.005
        var_ray_Kd = 0.001
        func_ray()
    robot.set_motor_time(4,robot.clamp(6, -100, 100),robot.clamp(1.6, 0, 3600))
    time.sleep(0.39)
    robot.set_double_motor_encoder(1,robot.clamp(-5, -100, 100),2,robot.clamp(-5, -100, 100),1,robot.clamp(1200, -99999, 99999))
    func_green_end_1()
    pass

def func_green_end_1():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    #自转
    if True:
        var_angle = robot.ceil((90 * var_1angle))
        var_angle_up = robot.ceil((45 * var_1angle))
        var_angle_down = robot.ceil((45 * var_1angle))
        var_turn_speed_max = 15
        var_turn_speed_min = 2
        var_turn_Ki = 0.001
        var_turn_Kp = 0.012
        var_turn_RL = '左'
        func_Turn()
    #前进
    if True:
        var_cm = (9 * var_1cm)
        var_cm_up = (3 * var_1cm)
        var_cm_down = (3 * var_1cm)
        var_speed_max = 13
        var_speed_min = 2
        var_Ki = 0.001
        var_Kp = 0.01
        func_forward()
    #自转
    if True:
        var_angle = robot.ceil((90 * var_1angle))
        var_angle_up = robot.ceil((45 * var_1angle))
        var_angle_down = robot.ceil((45 * var_1angle))
        var_turn_speed_max = 15
        var_turn_speed_min = 2
        var_turn_Ki = 0.001
        var_turn_Kp = 0.012
        var_turn_RL = '右'
        func_Turn()
    robot.set_motor_time(3,robot.clamp(5, -100, 100),robot.clamp(1.3, 0, 3600))
    time.sleep(0.2)
    #自转
    if True:
        var_angle = robot.ceil((65 * var_1angle))
        var_angle_up = robot.ceil((12 * var_1angle))
        var_angle_down = robot.ceil((20 * var_1angle))
        var_turn_speed_max = 30
        var_turn_speed_min = 3
        var_turn_Ki = 0.001
        var_turn_Kp = 0.012
        var_turn_RL = '右'
        func_Turn()
    robot.set_double_motor_time(1,robot.clamp(80, -100, 100),2,robot.clamp(80, -100, 100),robot.clamp(0.75, 0, 3600))
    pass

def func_Path_green_1():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    #自转
    if True:
        var_angle = robot.ceil((20 * var_1angle))
        var_angle_up = robot.ceil((5 * var_1angle))
        var_angle_down = robot.ceil((10 * var_1angle))
        var_turn_speed_max = 20
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.012
        var_turn_RL = '右'
        func_Turn()
    #前进
    if True:
        var_cm = (83 * var_1cm)
        var_cm_up = (30 * var_1cm)
        var_cm_down = (30 * var_1cm)
        var_speed_max = 80
        var_speed_min = 4
        var_Ki = 0.001
        var_Kp = 0.01
        func_forward()
    #自转
    if True:
        var_angle = robot.ceil((70 * var_1angle))
        var_angle_up = robot.ceil((5 * var_1angle))
        var_angle_down = robot.ceil((10 * var_1angle))
        var_turn_speed_max = 30
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.012
        var_turn_RL = '右'
        func_Turn()
    #巡线
    if True:
        # 左，右，十字，时间
        var_ray_choose = '路口'
        var_ray_speed = 15
        var_ray_Kp = 0.007
        var_ray_Kd = 0.001
        func_ray()
    #前进
    if True:
        var_cm = (10 * var_1cm)
        var_cm_up = (2 * var_1cm)
        var_cm_down = (4 * var_1cm)
        var_speed_max = 10
        var_speed_min = 4
        var_Ki = 0.001
        var_Kp = 0.012
        func_forward()
    #自转
    if True:
        var_angle = robot.ceil((89.5 * var_1angle))
        var_angle_up = robot.ceil((45 * var_1angle))
        var_angle_down = robot.ceil((45 * var_1angle))
        var_turn_speed_max = 20
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.01
        var_turn_RL = '右'
        func_Turn()
    robot.set_double_motor_encoder(1,robot.clamp(-10, -100, 100),2,robot.clamp(-10, -100, 100),1,robot.clamp(1500, -99999, 99999))
    func_take_white()
    pass

def func_Path_green_3():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    #自转
    if True:
        var_angle = robot.ceil((166 * var_1angle))
        var_angle_up = robot.ceil((30 * var_1angle))
        var_angle_down = robot.ceil((30 * var_1angle))
        var_turn_speed_max = 25
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.01
        var_turn_RL = '左'
        func_Turn()
    #前进
    if True:
        var_cm = (25 * var_1cm)
        var_cm_up = (10 * var_1cm)
        var_cm_down = (15 * var_1cm)
        var_speed_max = 40
        var_speed_min = 5
        var_Ki = 0.001
        var_Kp = 0.012
        func_forward()
    #自转
    if True:
        var_angle = robot.ceil((17 * var_1angle))
        var_angle_up = robot.ceil((5 * var_1angle))
        var_angle_down = robot.ceil((12 * var_1angle))
        var_turn_speed_max = 20
        var_turn_speed_min = 3
        var_turn_Ki = 0.001
        var_turn_Kp = 0.01
        var_turn_RL = '右'
        func_Turn()
    #前进
    if True:
        var_cm = (48 * var_1cm)
        var_cm_up = (10 * var_1cm)
        var_cm_down = (20 * var_1cm)
        var_speed_max = 50
        var_speed_min = 5
        var_Ki = 0.001
        var_Kp = 0.012
        func_forward()
    #自转
    if True:
        var_angle = robot.ceil((66 * var_1angle))
        var_angle_up = robot.ceil((10 * var_1angle))
        var_angle_down = robot.ceil((20 * var_1angle))
        var_turn_speed_max = 25
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.01
        var_turn_RL = '右'
        func_Turn()
    #前进
    if True:
        var_cm = (40 * var_1cm)
        var_cm_up = (10 * var_1cm)
        var_cm_down = (10 * var_1cm)
        var_speed_max = 50
        var_speed_min = 5
        var_Ki = 0.001
        var_Kp = 0.012
        func_forward()
    func_Path_green_4()
    pass

def func_take_white():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    robot.set_motor_time(4,robot.clamp(14, -100, 100),robot.clamp(0.7, 0, 3600))
    robot.set_motor_time(4,robot.clamp(-14, -100, 100),robot.clamp(0.1, 0, 3600))
    robot.set_motor_time(4,robot.clamp(14, -100, 100),robot.clamp(0.1, 0, 3600))
    time.sleep(0.4)
    robot.set_motor_time(3,robot.clamp(20, -100, 100),robot.clamp(1, 0, 3600))
    time.sleep(0.5)
    robot.set_motor_time(4,robot.clamp(-13, -100, 100),robot.clamp(1.2, 0, 3600))
    #前进
    if True:
        var_cm = (12 * var_1cm)
        var_cm_up = (0 * var_1cm)
        var_cm_down = (0 * var_1cm)
        var_speed_max = 20
        var_speed_min = 4
        var_Ki = 0.001
        var_Kp = 0.012
        func_forward()
    robot.set_motor(4,robot.clamp(0, -100, 100))
    #自转
    if True:
        var_angle = robot.ceil((90 * var_1angle))
        var_angle_up = robot.ceil((5 * var_1angle))
        var_angle_down = robot.ceil((30 * var_1angle))
        var_turn_speed_max = 30
        var_turn_speed_min = 2
        var_turn_Ki = 0.001
        var_turn_Kp = 0.01
        var_turn_RL = '左'
        func_Turn()
    robot.set_motor(4,robot.clamp(0, -100, 100))
    #巡线
    if True:
        # 左，右，十字，时间
        var_ray_choose = '矩离'
        var_cm = (80 * var_1cm)
        var_cm_up = (20 * var_1cm)
        var_cm_down = (20 * var_1cm)
        var_speed_max = 60
        var_speed_min = 3
        var_ray_Kp = 0.04
        var_ray_Kd = 0.003
        func_ray()
    robot.set_motor(4,robot.clamp(0, -100, 100))
    func_Path_green_2()
    pass

def func_Path_green_2():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    #巡线
    if True:
        # 左，右，十字，时间
        var_ray_choose = '路口'
        var_ray_speed = 10
        var_ray_Kp = 0.01
        var_ray_Kd = 0.001
        func_ray()
    #前进
    if True:
        var_cm = (11 * var_1cm)
        var_cm_up = (2 * var_1cm)
        var_cm_down = (4 * var_1cm)
        var_speed_max = 10
        var_speed_min = 4
        var_Ki = 0.001
        var_Kp = 0.012
        func_forward()
    #自转
    if True:
        var_angle = robot.ceil((90 * var_1angle))
        var_angle_up = robot.ceil((20 * var_1angle))
        var_angle_down = robot.ceil((30 * var_1angle))
        var_turn_speed_max = 30
        var_turn_speed_min = 5
        var_turn_Ki = 0.001
        var_turn_Kp = 0.01
        var_turn_RL = '左'
        func_Turn()
    #巡线
    if True:
        # 左，右，十字，时间
        var_ray_choose = '时间'
        var_ray_return_time = 1
        var_ray_speed = 20
        var_ray_Kp = 0.003
        var_ray_Kd = 0.0001
        func_ray()
    robot.set_double_motor_encoder(1,robot.clamp(-10, -100, 100),2,robot.clamp(-10, -100, 100),1,robot.clamp(1100, -99999, 99999))
    func_Path_green_3()
    pass

def func_Path_green_4():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    #巡线
    if True:
        # 左，右，十字，时间
        var_ray_choose = '路口'
        var_ray_speed = 30
        var_ray_Kp = 0.005
        var_ray_Kd = 0
        func_ray()
    robot.reset_timer(1)
    while True:
        if robot.get_timer_ms(1) >= 200:
            robot.set_motor(1,robot.clamp(0, -100, 100))
            robot.set_motor(2,robot.clamp(0, -100, 100))
            robot.reset_timer(1)
            while True:
                if robot.get_timer_ms(1) >= 300:
                    robot.set_motor(1,robot.clamp(0, -100, 100))
                    robot.set_motor(2,robot.clamp(0, -100, 100))
                    robot.reset_timer(1)
                    while True:
                        if robot.get_timer_ms(1) >= 400:
                            robot.set_motor(1,robot.clamp(0, -100, 100))
                            robot.set_motor(2,robot.clamp(0, -100, 100))
                            robot.reset_timer(1)
                            while True:
                                if robot.get_timer_ms(1) >= 500:
                                    robot.set_motor(1,robot.clamp(0, -100, 100))
                                    robot.set_motor(2,robot.clamp(0, -100, 100))
                                    break
                                else:
                                    robot.set_motor(1,robot.clamp(50, -100, 100))
                                    robot.set_motor(2,robot.clamp(50, -100, 100))
                            break
                        else:
                            robot.set_motor(2,robot.clamp(50, -100, 100))
                    break
                else:
                    robot.set_motor(1,robot.clamp(30, -100, 100))
                    robot.set_motor(2,robot.clamp(30, -100, 100))
            break
        else:
            robot.set_motor(1,robot.clamp(50, -100, 100))
    robot.print('hello world\n')
    pass

def func_backwards():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    func_Motter_Zero()
    var_Kp = 0.005
    var_speed = -2
    while True:
        if robot.get_gray(7) >= 2000:
            func_Motter_Zero()
            break
        var_Error = (robot.abs(robot.get_encoder(1)) - robot.abs(robot.get_encoder(2)))
        robot.set_motor(1,robot.clamp((var_speed + (var_Kp * var_Error)), -100, 100))
        robot.set_motor(2,robot.clamp((var_speed - (var_Kp * var_Error)), -100, 100))
        var_speed = (var_speed if isinstance(var_speed, Number) else 0) + -0.04
        time.sleep(0.01)
    pass

def func_main():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    if robot.get_touch(1):
        time.sleep(0.01)
        func_Path_green_1()
        while True:
            if robot.get_touch(1):
                time.sleep(0.01)
                func_green_end()
                while True:
                    if robot.get_touch(1):
                        time.sleep(0.01)
                        func_end()
    pass

def func_Library():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    #前进
    if True:
        var_cm = (100 * var_1cm)
        var_cm_up = (20 * var_1cm)
        var_cm_down = (10 * var_1cm)
        var_speed_max = 80
        var_speed_min = 20
        var_Ki = 0.001
        var_Kp = 0.012
        func_forward()
    #自转
    if True:
        var_angle = robot.ceil((360 * var_1angle))
        var_angle_up = robot.ceil((110 * var_1angle))
        var_angle_down = robot.ceil((250 * var_1angle))
        var_turn_speed_max = 20
        var_turn_speed_min = 3
        var_turn_Ki = 0.001
        var_turn_Kp = 0.01
        var_turn_RL = '左'
        func_Turn()
    #巡线
    if True:
        #选择模式  矩离，时间，路口
        if True:
            # 左，右，十字，时间
            var_ray_choose = '矩离'
        #矩离模式
        if True:
            var_cm = (60 * var_1cm)
            var_cm_up = (20 * var_1cm)
            var_cm_down = (20 * var_1cm)
            var_speed_max = 80
            var_speed_min = 15
        #时间模式
        if True:
            var_ray_return_time = 1
        var_ray_speed = 50
        var_ray_Kp = 0.01
        var_ray_Kd = 0.001
        func_ray()
    pass

def func_forward():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    func_Motter_Zero()
    var_Error_Ki = 0
    while not robot.get_encoder(1) >= var_cm_up:
        var_Error = (robot.get_encoder(1) - robot.get_encoder(2))
        var_Error_Ki = (var_Error_Ki + var_Error)
        if var_Error_Ki < -2000:
            var_Error_Ki = -2000
        if var_Error_Ki > 2000:
            var_Error_Ki = 2000
        var_PI = ((var_Kp * var_Error) + (var_Ki * var_Error_Ki))
        var_speed = (var_speed_min + ((var_speed_max - var_speed_min) * robot.sin(((((robot.get_encoder(1) + robot.get_encoder(2)) / 2) / var_cm_up) * 90) / 180.0 * robot.pi())))
        robot.set_motor(1,robot.clamp(((var_speed * 1) - var_PI), -100, 100))
        robot.set_motor(2,robot.clamp(((var_speed * 1) + var_PI), -100, 100))
        time.sleep(0.01)
    while not robot.get_encoder(1) >= (var_cm - var_cm_down):
        var_Error = (robot.get_encoder(1) - robot.get_encoder(2))
        var_Error_Ki = (var_Error_Ki + var_Error)
        if var_Error_Ki < -2000:
            var_Error_Ki = -2000
        if var_Error_Ki > 2000:
            var_Error_Ki = 2000
        var_PI = ((var_Kp * var_Error) + (var_Ki * var_Error_Ki))
        var_speed = var_speed_max
        robot.set_motor(1,robot.clamp(((var_speed * 1) - var_PI), -100, 100))
        robot.set_motor(2,robot.clamp(((var_speed * 1) + var_PI), -100, 100))
        time.sleep(0.01)
    while not robot.get_encoder(1) >= var_cm:
        var_Error = (robot.get_encoder(1) - robot.get_encoder(2))
        var_Error_Ki = (var_Error_Ki + var_Error)
        if var_Error_Ki < -2000:
            var_Error_Ki = -2000
        if var_Error_Ki > 2000:
            var_Error_Ki = 2000
        var_PI = ((var_Kp * var_Error) + (var_Ki * var_Error_Ki))
        var_speed = (var_speed_min + ((var_speed_max - var_speed_min) * robot.cos((((((robot.get_encoder(1) + robot.get_encoder(2)) / 2) - (var_cm - var_cm_down)) / var_cm_down) * 90) / 180.0 * robot.pi())))
        robot.set_motor(1,robot.clamp(((var_speed * 1) - var_PI), -100, 100))
        robot.set_motor(2,robot.clamp(((var_speed * 1) + var_PI), -100, 100))
        time.sleep(0.01)
    robot.set_double_motor_encoder(1,robot.clamp(-20, -100, 100),2,robot.clamp(-20, -100, 100),1,robot.clamp(20, -99999, 99999))
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    pass

def func_Turn():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    func_Motter_Zero()
    var_turn_Error_Ki = 0
    if var_turn_RL == '左':
        while not robot.abs(robot.get_encoder(1)) >= var_angle_up:
            var_turn_Error = (robot.abs(robot.get_encoder(1)) - robot.abs(robot.get_encoder(2)))
            var_turn_Error_Ki = (var_turn_Error_Ki + var_turn_Error)
            if var_turn_Error_Ki < -2000:
                var_turn_Error_Ki = -2000
            if var_turn_Error_Ki > 2000:
                var_turn_Error_Ki = 2000
            var_turn_PI = ((var_turn_Kp * var_turn_Error) + (var_turn_Ki * var_turn_Error_Ki))
            var_turn_speed = (var_turn_speed_min + ((var_turn_speed_max - var_turn_speed_min) * robot.sin(((((robot.abs(robot.get_encoder(1)) + robot.abs(robot.get_encoder(2))) / 2) / var_angle_up) * 90) / 180.0 * robot.pi())))
            robot.set_motor(1,robot.clamp(((var_turn_speed * -1) + var_turn_PI), -100, 100))
            robot.set_motor(2,robot.clamp(((var_turn_speed * 1) + var_turn_PI), -100, 100))
            time.sleep(0.01)
        while not robot.abs(robot.get_encoder(1)) >= (var_angle - var_angle_down):
            var_turn_Error = (robot.abs(robot.get_encoder(1)) - robot.abs(robot.get_encoder(2)))
            var_turn_Error_Ki = (var_turn_Error_Ki + var_turn_Error)
            if var_turn_Error_Ki < -2000:
                var_turn_Error_Ki = -2000
            if var_turn_Error_Ki > 2000:
                var_turn_Error_Ki = 2000
            var_turn_PI = ((var_turn_Kp * var_turn_Error) + (var_turn_Ki * var_turn_Error_Ki))
            var_turn_speed = var_turn_speed_max
            robot.set_motor(1,robot.clamp(((var_turn_speed * -1) + var_turn_PI), -100, 100))
            robot.set_motor(2,robot.clamp(((var_turn_speed * 1) + var_turn_PI), -100, 100))
            time.sleep(0.01)
        while not robot.abs(robot.get_encoder(1)) >= var_angle:
            var_turn_Error = (robot.abs(robot.get_encoder(1)) - robot.abs(robot.get_encoder(2)))
            var_turn_Error = (robot.get_encoder(1) - robot.get_encoder(2))
            var_turn_Error_Ki = (var_turn_Error_Ki + var_turn_Error)
            if var_turn_Error_Ki < -2000:
                var_turn_Error_Ki = -2000
            if var_turn_Error_Ki > 2000:
                var_turn_Error_Ki = 2000
            var_turn_PI = ((var_turn_Kp * var_turn_Error) + (var_turn_Ki * var_turn_Error_Ki))
            var_turn_speed = (var_turn_speed_min + ((var_turn_speed_max - var_turn_speed_min) * robot.cos((((((robot.abs(robot.get_encoder(1)) + robot.abs(robot.get_encoder(2))) / 2) - (var_angle - var_angle_down)) / var_angle_down) * 90) / 180.0 * robot.pi())))
            robot.set_motor(1,robot.clamp(((var_turn_speed * -1) + 0), -100, 100))
            robot.set_motor(2,robot.clamp(((var_turn_speed * 1) + 0), -100, 100))
            time.sleep(0.01)
        robot.set_double_motor_encoder(1,robot.clamp(20, -100, 100),2,robot.clamp(-20, -100, 100),1,robot.clamp(20, -99999, 99999))
        robot.set_motor(1,robot.clamp(0, -100, 100))
        robot.set_motor(2,robot.clamp(0, -100, 100))
    if var_turn_RL == '右':
        while not robot.abs(robot.get_encoder(1)) >= var_angle_up:
            var_turn_Error = (robot.abs(robot.get_encoder(1)) - robot.abs(robot.get_encoder(2)))
            var_turn_Error_Ki = (var_turn_Error_Ki + var_turn_Error)
            if var_turn_Error_Ki < -2000:
                var_turn_Error_Ki = -2000
            if var_turn_Error_Ki > 2000:
                var_turn_Error_Ki = 2000
            var_turn_PI = ((var_turn_Kp * var_turn_Error) + (var_turn_Ki * var_turn_Error_Ki))
            var_turn_speed = (var_turn_speed_min + ((var_turn_speed_max - var_turn_speed_min) * robot.sin(((((robot.abs(robot.get_encoder(1)) + robot.abs(robot.get_encoder(2))) / 2) / var_angle_up) * 90) / 180.0 * robot.pi())))
            robot.set_motor(1,robot.clamp(((var_turn_speed * 1) - var_turn_PI), -100, 100))
            robot.set_motor(2,robot.clamp(((var_turn_speed * -1) - var_turn_PI), -100, 100))
            time.sleep(0.01)
        while not robot.abs(robot.get_encoder(1)) >= (var_angle - var_angle_down):
            var_turn_Error = (robot.abs(robot.get_encoder(1)) - robot.abs(robot.get_encoder(2)))
            var_turn_Error_Ki = (var_turn_Error_Ki + var_turn_Error)
            if var_turn_Error_Ki < -2000:
                var_turn_Error_Ki = -2000
            if var_turn_Error_Ki > 2000:
                var_turn_Error_Ki = 2000
            var_turn_PI = ((var_turn_Kp * var_turn_Error) + (var_turn_Ki * var_turn_Error_Ki))
            var_turn_speed = var_turn_speed_max
            robot.set_motor(1,robot.clamp(((var_turn_speed * 1) - var_turn_PI), -100, 100))
            robot.set_motor(2,robot.clamp(((var_turn_speed * -1) - var_turn_PI), -100, 100))
            time.sleep(0.01)
        while not robot.abs(robot.get_encoder(1)) >= var_angle:
            var_turn_Error = (robot.abs(robot.get_encoder(1)) - robot.abs(robot.get_encoder(2)))
            var_turn_Error = (robot.get_encoder(1) - robot.get_encoder(2))
            var_turn_Error_Ki = (var_turn_Error_Ki + var_turn_Error)
            if var_turn_Error_Ki < -2000:
                var_turn_Error_Ki = -2000
            if var_turn_Error_Ki > 2000:
                var_turn_Error_Ki = 2000
            var_turn_PI = ((var_turn_Kp * var_turn_Error) + (var_turn_Ki * var_turn_Error_Ki))
            var_turn_speed = (var_turn_speed_min + ((var_turn_speed_max - var_turn_speed_min) * robot.cos((((((robot.abs(robot.get_encoder(1)) + robot.abs(robot.get_encoder(2))) / 2) - (var_angle - var_angle_down)) / var_angle_down) * 90) / 180.0 * robot.pi())))
            robot.set_motor(1,robot.clamp(((var_turn_speed * 1) + 0), -100, 100))
            robot.set_motor(2,robot.clamp(((var_turn_speed * -1) + 0), -100, 100))
            time.sleep(0.01)
        robot.set_double_motor_encoder(1,robot.clamp(-20, -100, 100),2,robot.clamp(20, -100, 100),1,robot.clamp(20, -99999, 99999))
        robot.set_motor(1,robot.clamp(0, -100, 100))
        robot.set_motor(2,robot.clamp(0, -100, 100))
    pass

def func_ON():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    robot.set_motor(1,robot.clamp(10, -100, 100))
    robot.set_motor(2,robot.clamp(10, -100, 100))
    time.sleep(0.1)
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    pass

def func_ray():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    if var_ray_choose == '时间':
        func_ray_Time()
    else:
        if var_ray_choose == '矩离':
            func_ray_forward()
        else:
            if var_ray_choose == '路口':
                func_ray_Path()
            else:
                func_ray_Path()
    pass

def func_ray_forward_PID():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    var_ray_left_Error = (var_ray_light_9 - robot.get_gray(9))
    var_ray_right_Error = (var_ray_light_10 - robot.get_gray(10))
    var_ray_left_PID = (var_ray_Kp * var_ray_left_Error)
    var_ray_right_PID = (var_ray_Kp * var_ray_right_Error)
    var_ray_left_last_Error = (var_ray_left_last_Error + var_ray_left_Error)
    var_ray_right_last_Error = (var_ray_right_last_Error + var_ray_right_Error)
    pass

def func_ray_forward():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    func_Motter_Zero()
    func_Last_light_Error()
    var_ray_Kp = 0.007
    var_ray_Kd = 0.001
    while not robot.get_encoder(1) >= var_cm_up:
        var_speed = (var_speed_min + ((var_speed_max - var_speed_min) * robot.sin(((((robot.get_encoder(1) + robot.get_encoder(2)) / 2) / var_cm_up) * 90) / 180.0 * robot.pi())))
        func_ray_forward_PID()
        #电机运行
        if True:
            robot.set_motor(1,robot.clamp((((var_speed + var_ray_left_PID) - 0) + (var_ray_Kd * ((var_ray_left_Error - var_ray_left_last_Error) * 0.01))), -100, 100))
            robot.set_motor(2,robot.clamp((((var_speed + var_ray_right_PID) - 0) + ((var_ray_Kd * ((var_ray_right_Error - var_ray_right_last_Error) * 0.01)) * -1)), -100, 100))
        #Ray Error = 0
        if True:
            var_ray_left_last_Error = 0
            var_ray_right_last_Error = 0
        time.sleep(0.01)
    while not robot.get_encoder(1) >= (var_cm - var_cm_down):
        var_speed = var_speed_max
        func_ray_forward_PID()
        #电机运行
        if True:
            robot.set_motor(1,robot.clamp(((var_speed + var_ray_left_PID) + (var_ray_Kd * ((var_ray_left_Error - var_ray_left_last_Error) * 0.01))), -100, 100))
            robot.set_motor(2,robot.clamp(((var_speed + var_ray_right_PID) + ((var_ray_Kd * ((var_ray_right_Error - var_ray_right_last_Error) * 0.01)) * -1)), -100, 100))
        #Ray Error = 0
        if True:
            var_ray_left_last_Error = 0
            var_ray_right_last_Error = 0
        time.sleep(0.01)
    while not robot.get_encoder(1) >= var_cm:
        var_speed = (var_speed_min + ((var_speed_max - var_speed_min) * robot.cos((((robot.get_encoder(1) - (var_cm - var_cm_down)) / var_cm_down) * 90) / 180.0 * robot.pi())))
        func_ray_forward_PID()
        #电机运行
        if True:
            robot.set_motor(1,robot.clamp(((var_speed + var_ray_left_PID) + (var_ray_Kd * ((var_ray_left_Error - var_ray_left_last_Error) * 0.01))), -100, 100))
            robot.set_motor(2,robot.clamp(((var_speed + var_ray_right_PID) + ((var_ray_Kd * ((var_ray_right_Error - var_ray_right_last_Error) * 0.01)) * -1)), -100, 100))
        #Ray Error = 0
        if True:
            var_ray_left_last_Error = 0
            var_ray_right_last_Error = 0
        time.sleep(0.01)
    robot.set_double_motor_encoder(1,robot.clamp(-20, -100, 100),2,robot.clamp(-20, -100, 100),1,robot.clamp(20, -99999, 99999))
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    func_Motter_Zero()
    pass

def func_Motter_Zero():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    time.sleep(0.02)
    robot.reset_encoder(1);
    robot.reset_encoder(2);
    pass

def func_ray_PID():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    var_ray_left_Error = (var_ray_light_9 - robot.get_gray(9))
    var_ray_right_Error = (var_ray_light_10 - robot.get_gray(10))
    var_ray_left_PID = (var_ray_Kp * var_ray_left_Error)
    var_ray_right_PID = (var_ray_Kp * var_ray_right_Error)
    var_ray_left_last_Error = (var_ray_left_last_Error + var_ray_left_Error)
    var_ray_right_last_Error = (var_ray_right_last_Error + var_ray_right_Error)
    robot.set_motor(1,robot.clamp(((var_ray_speed + var_ray_left_PID) + (var_ray_Kd * ((var_ray_left_Error - var_ray_left_last_Error) * 0.01))), -100, 100))
    robot.set_motor(2,robot.clamp(((var_ray_speed + var_ray_right_PID) - ((var_ray_Kd * ((var_ray_right_Error - var_ray_right_last_Error) * 0.01)) * -1)), -100, 100))
    time.sleep(0.01)
    pass

def func_value():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    var_ray_white = 1300
    var_1cm = 90.4
    var_1angle = 17.8
    var_ray_light_9 = robot.get_ee(9)
    var_ray_light_10 = robot.get_ee(10)
    var_ray_left_last_Error = 0
    var_ray_right_last_Error = 0
    robot.reset_encoder(4);
    pass

def func_Last_light_Error():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    var_ray_left_last_Error = 0
    var_ray_right_last_Error = 0
    pass

def func_ray_backwards_PID():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    var_ray_left_Error = (var_ray_light_9 - robot.get_gray(9))
    var_ray_right_Error = (var_ray_light_10 - robot.get_gray(10))
    var_ray_left_PID = (var_ray_Kp * var_ray_left_Error)
    var_ray_right_PID = (var_ray_Kp * var_ray_right_Error)
    var_ray_left_last_Error = (var_ray_left_last_Error + var_ray_left_Error)
    var_ray_right_last_Error = (var_ray_right_last_Error + var_ray_right_Error)
    robot.set_motor(1,robot.clamp(((var_ray_speed + var_ray_right_PID) + (var_ray_Kd * ((var_ray_right_Error - var_ray_right_last_Error) * 0.01))), -100, 100))
    robot.set_motor(2,robot.clamp(((var_ray_speed + var_ray_left_PID) + ((var_ray_Kd * ((var_ray_left_Error - var_ray_left_last_Error) * 0.01)) * -1)), -100, 100))
    time.sleep(0.01)
    pass

def func_ray_Path():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    while True:
        if robot.get_gray(7) >= var_ray_white or robot.get_gray(8) >= var_ray_white:
            func_Motter_Zero()
            break
        else:
            func_ray_Path_PID()
    #Ray Error = 0
    if True:
        var_ray_left_last_Error = 0
        var_ray_right_last_Error = 0
    func_Motter_Zero()
    pass

def func_ray_Path_PID():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    var_ray_left_Error = (var_ray_light_9 - robot.get_gray(9))
    var_ray_right_Error = (var_ray_light_10 - robot.get_gray(10))
    var_ray_left_PID = (var_ray_Kp * var_ray_left_Error)
    var_ray_right_PID = (var_ray_Kp * var_ray_right_Error)
    var_ray_left_last_Error = (var_ray_left_last_Error + var_ray_left_Error)
    var_ray_right_last_Error = (var_ray_right_last_Error + var_ray_right_Error)
    robot.set_motor(1,robot.clamp(((var_ray_speed + var_ray_left_PID) + (var_ray_Kd * ((var_ray_left_Error - var_ray_left_last_Error) * 0.01))), -100, 100))
    robot.set_motor(2,robot.clamp(((var_ray_speed + var_ray_right_PID) + ((var_ray_Kd * ((var_ray_right_Error - var_ray_right_last_Error) * 0.01)) * -1)), -100, 100))
    pass

def func_ray_Time():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    var_ray_time = 0
    if var_ray_speed > 0:
        while not var_ray_time >= var_ray_return_time:
            var_ray_time = (var_ray_time + 0.01)
            func_ray_PID()
        var_ray_time = 0
        #Ray Error = 0
        if True:
            var_ray_left_last_Error = 0
            var_ray_right_last_Error = 0
        func_Motter_Zero()
    else:
        while not var_ray_time >= var_ray_return_time:
            var_ray_time = (var_ray_time + 0.01)
            func_ray_backwards_PID()
        var_ray_time = 0
        #Ray Error = 0
        if True:
            var_ray_left_last_Error = 0
            var_ray_right_last_Error = 0
        func_Motter_Zero()
    pass


def main():
    global var_ray_left_PID, var_ray_right_PID, var_ray_left_Error, var_ray_white, var_ray_left_last_Error, var_ray_time, var_angle, var_ray_choose, var_Kp, var_cm, var_Error_Ki, var_turn_Error_Ki, var_ray_right_Error, var_1cm, var_ray_right_last_Error, var_angle_up, var_ray_speed, var_speed, var_cm_up, var_ray_light_9, var_ray_Kp, var_1angle, var_angle_down, var_cm_down, var_Error, var_ray_light_10, var_ray_Kd, var_turn_speed_max, var_speed_max, var_turn_RL, var_turn_Error, var_ray_return_time, var_turn_speed_min, var_speed_min, var_turn_Ki, var_Ki, var_turn_Kp, var_PI, var_turn_PI, var_turn_speed
    func_value()
    func_ON()
    while True:
        func_main()

main()#program entry