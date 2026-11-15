#<SKCON9><USB><WERFuncLib>

import threading
import time
import libstarpy

robot = Robot()

cm = None
deg = None
speedL = None
speedR = None
sec = None
text = None
var_1cm = None
var_err_9 = None
var_1angle = None
var_ready = None
var_err_10 = None
var_err_last_9 = None
var_speed = None
var_arm_speed = None
var_arm_time = None
var_ee_white_9 = None
var_pid_9 = None
var_err_last_10 = None
var_straight_Kp = None
var_enc_diff = None
var_ee_white_10 = None
var_pid_10 = None
var_turn_speed = None
var_ray_Kp = None
var_ray_Kd = None
var_ray_white = None
var_ray_speed = None

def func_Init():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    #初始化：设定校准参数、读 EEPROM 灰度白值、停车、编码器清零。
    var_1cm = 90.4
    var_1angle = 17.8
    var_speed = 40
    var_straight_Kp = 0.005
    var_turn_speed = 25
    var_arm_speed = 30
    var_arm_time = 0.5
    var_ray_white = 1300
    var_ray_speed = 30
    var_ray_Kp = 0.01
    var_ray_Kd = 0.001
    #EEPROM 9/10 = 标定程序写入的左/右灰度白值；没标定过就退回默认 1300。
    var_ee_white_9 = robot.get_ee(9)
    var_ee_white_10 = robot.get_ee(10)
    if var_ee_white_9 < 100:
        var_ee_white_9 = 1300
    if var_ee_white_10 < 100:
        var_ee_white_10 = 1300
    var_err_last_9 = 0
    var_err_last_10 = 0
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    time.sleep(0.05)
    robot.reset_encoder(1);
    robot.reset_encoder(2);
    #标记已初始化；各个动作函数检测到未初始化会自动调用本函数。
    var_ready = 1
    pass

def func_Stop():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    #停止：左右驱动电机速度清零。
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    time.sleep(0.05)
    pass

def func_ResetEncoder():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    #驱动电机编码器清零（1=左轮 2=右轮）。
    robot.reset_encoder(1);
    robot.reset_encoder(2);
    pass

def func_ForwardCM(cm):
    global deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #前进 cm 厘米：编码器定距 + 两轮差值纠偏；cm 必须 > 0。
    func_ResetEncoder()
    while not robot.abs(robot.get_encoder(1)) >= (cm * var_1cm):
        var_enc_diff = (robot.get_encoder(1) - robot.get_encoder(2))
        robot.set_motor(1,robot.clamp((var_speed - (var_straight_Kp * var_enc_diff)), -100, 100))
        robot.set_motor(2,robot.clamp((var_speed + (var_straight_Kp * var_enc_diff)), -100, 100))
        time.sleep(0.01)
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    time.sleep(0.05)
    pass

def func_BackwardCM(cm):
    global deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #后退 cm 厘米：编码器定距 + 两轮差值纠偏；cm 必须 > 0。
    func_ResetEncoder()
    while not robot.abs(robot.get_encoder(1)) >= (cm * var_1cm):
        var_enc_diff = (robot.get_encoder(1) - robot.get_encoder(2))
        robot.set_motor(1,robot.clamp((-(var_speed) - (var_straight_Kp * var_enc_diff)), -100, 100))
        robot.set_motor(2,robot.clamp((-(var_speed) + (var_straight_Kp * var_enc_diff)), -100, 100))
        time.sleep(0.01)
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    time.sleep(0.05)
    pass

def func_TurnLeft(deg):
    global cm, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #原地左转 deg 度：左轮反转、右轮正转，编码器定角度。
    func_ResetEncoder()
    while not robot.abs(robot.get_encoder(1)) >= (deg * var_1angle):
        robot.set_motor(1,robot.clamp(-(var_turn_speed), -100, 100))
        robot.set_motor(2,robot.clamp(var_turn_speed, -100, 100))
        time.sleep(0.01)
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    time.sleep(0.05)
    pass

def func_TurnRight(deg):
    global cm, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #原地右转 deg 度：左轮正转、右轮反转，编码器定角度。
    func_ResetEncoder()
    while not robot.abs(robot.get_encoder(1)) >= (deg * var_1angle):
        robot.set_motor(1,robot.clamp(var_turn_speed, -100, 100))
        robot.set_motor(2,robot.clamp(-(var_turn_speed), -100, 100))
        time.sleep(0.01)
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    time.sleep(0.05)
    pass

def func_DriveTime(speedL, speedR, sec):
    global cm, deg, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #双电机按时间行驶：左速度 speedL %、右速度 speedR %，持续 sec 秒后自动停。
    robot.set_double_motor_time(1,robot.clamp(speedL, -100, 100),2,robot.clamp(speedR, -100, 100),robot.clamp(sec, 0, 3600))
    pass

def func_DriveSpeed(speedL, speedR):
    global cm, deg, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #双电机持续转：左 speedL %、右 speedR %；不会自己停，要配 等待/重复/停止。
    robot.set_motor(1,robot.clamp(speedL, -100, 100))
    robot.set_motor(2,robot.clamp(speedR, -100, 100))
    pass

def func_ArmUp():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #抬升电机（端口3）正转 var_arm_time 秒（默认 30% 速度）。
    robot.set_motor_time(3,robot.clamp(var_arm_speed, -100, 100),robot.clamp(var_arm_time, 0, 3600))
    pass

def func_ArmDown():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #抬升电机（端口3）反转 var_arm_time 秒。
    robot.set_motor_time(3,robot.clamp(-(var_arm_speed), -100, 100),robot.clamp(var_arm_time, 0, 3600))
    pass

def func_Grab():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #夹爪电机（端口4）正转 var_arm_time 秒（夹紧/取物）。
    robot.set_motor_time(4,robot.clamp(var_arm_speed, -100, 100),robot.clamp(var_arm_time, 0, 3600))
    pass

def func_Release():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #夹爪电机（端口4）反转 var_arm_time 秒（松开/放下）。
    robot.set_motor_time(4,robot.clamp(-(var_arm_speed), -100, 100),robot.clamp(var_arm_time, 0, 3600))
    pass

def func_LineStep():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    #内部函数：巡线 PID 走一步（由 func_LineTime / func_LineUntilCross 调用）。
    var_err_9 = (var_ee_white_9 - robot.get_gray(9))
    var_err_10 = (var_ee_white_10 - robot.get_gray(10))
    var_pid_9 = ((var_ray_Kp * var_err_9) + (var_ray_Kd * (var_err_9 - var_err_last_9)))
    var_pid_10 = ((var_ray_Kp * var_err_10) + (var_ray_Kd * (var_err_10 - var_err_last_10)))
    var_err_last_9 = var_err_9
    var_err_last_10 = var_err_10
    robot.set_motor(1,robot.clamp((var_ray_speed + var_pid_9), -100, 100))
    robot.set_motor(2,robot.clamp((var_ray_speed + var_pid_10), -100, 100))
    time.sleep(0.01)
    pass

def func_LineTime(sec):
    global cm, deg, speedL, speedR, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #巡线行驶 sec 秒：灰度9/10 PID 巡线，到时间停车。
    var_err_last_9 = 0
    var_err_last_10 = 0
    robot.reset_timer(2)
    while not robot.get_timer_ms(2) >= (sec * 1000):
        func_LineStep()
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    time.sleep(0.05)
    var_err_last_9 = 0
    var_err_last_10 = 0
    pass

def func_LineUntilCross():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    if var_ready == 1:
        pass
    else:
        func_Init()
    #巡线到路口：灰度7 或 灰度8 读到白值（>= var_ray_white）时停车。
    var_err_last_9 = 0
    var_err_last_10 = 0
    while not robot.get_gray(7) >= var_ray_white:
        if robot.get_gray(8) >= var_ray_white:
            break
        func_LineStep()
    robot.set_motor(1,robot.clamp(0, -100, 100))
    robot.set_motor(2,robot.clamp(0, -100, 100))
    time.sleep(0.05)
    var_err_last_9 = 0
    var_err_last_10 = 0
    pass

def func_WaitStartKey():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    #等待按下主板的 Start(确认)键 1 再继续（如果你的车没有该按键，改用 func_WaitTouch）。
    while not robot.check_key(1) == 1:
        time.sleep(0.02)
    time.sleep(0.2)
    pass

def func_WaitTouch():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    #等待触碰传感器（端口1）被按下再继续；主程序.py 就是用触碰1当启动/分段键。
    while not robot.get_touch(1) == 1:
        time.sleep(0.02)
    time.sleep(0.2)
    pass

def func_Show(text):
    global cm, deg, speedL, speedR, sec, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    #在机器人屏幕显示一段文字（text 里放一个文本块）。
    robot.print(text,'\n')
    pass

def func_Beep():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    #播放内置提示音（打招呼声）。
    robot.play('dazhaohu_c0.mp3')
    pass


def main():
    global cm, deg, speedL, speedR, sec, text, var_1cm, var_err_9, var_1angle, var_ready, var_err_10, var_err_last_9, var_speed, var_arm_speed, var_arm_time, var_ee_white_9, var_pid_9, var_err_last_10, var_straight_Kp, var_enc_diff, var_ee_white_10, var_pid_10, var_turn_speed, var_ray_Kp, var_ray_Kd, var_ray_white, var_ray_speed
    #WER 函数库示例。做法：左边工具箱 → 函数 分类，把函数块拖进来；
    #下面 3 个动作块是示例，直接删掉换成你的任务即可。
    #① 初始化（必须第一步）
    func_Init()
    #② 前进 10 厘米（把 10 改成你要的厘米数）
    func_ForwardCM(10)
    #③ 原地右转 90 度（把 90 改成你要的角度）
    func_TurnRight(90)
    func_Stop()
    #其他常用：func_LineUntilCross 巡线到路口 / func_LineTime 巡线 N 秒 /
    #func_ArmUp func_Grab 取物 / func_WaitStartKey 等 Start 键 / func_WaitTouch 等触碰 / func_Show 显示文字。

main()#program entry