# -*- coding: utf-8 -*-
"""
WER 函数库生成器
=================
用 block_xml.py 的 DSL 搭出整套"函数"积木，输出：
  WER_函数库/WER函数库.srh      （软件内部项目格式，可直接作为临时项目使用）
  WER_函数库/WER函数库.srhs     （zip 项目包，软件 文件→打开 可直接打开）

函数清单见 函数库清单与参数.md（本脚本是唯一事实来源，改函数改这里再重跑）。
运行：
  python build_library.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # WER_函数库/
WORKSPACE = os.path.dirname(ROOT)                  # 2026普级赛/
sys.path.insert(0, HERE)

from block_xml import (  # noqa: E402
    Project, DefProc, Start, Call,
    Set, Change, Motor, MotorTime, DualTime, DualAngle, ResetEncoder, ResetTimer,
    Wait, If, IfElse, WhileCmp, WhileForever, WhileN, Break, WaitUntil,
    PrintfText, PrintfNumber, Print, PlaySound, SetDO, Servo, Annotation, BlockMod,
    Num, Text, VarGet, Op, Cmp, LogicAnd, LogicOr, Negate, Bool, Abs, Neg, Unary, Round,
    Gray, Touch, Sonic, Key, Encoder, EncoderRT, TimerMs, EE, guard,
)

# ---------------------------------------------------------------------------
# 常量（会写进 func_Init，可在软件的"函数"分类里打开 func_Init 直接改数字）
# ---------------------------------------------------------------------------
DEFAULTS = [
    ('var_1cm', 90.4),          # 1 厘米 = 多少个编码器计数（实测标定）
    ('var_1angle', 17.8),       # 1 度 = 多少个编码器计数（实测标定）
    ('var_speed', 40),          # 直行默认速度 %
    ('var_straight_Kp', 0.005), # 直行纠偏比例系数（两轮编码器差值）
    ('var_turn_speed', 25),     # 原地转向默认速度 %
    ('var_arm_speed', 30),      # 抬升/夹爪默认速度 %
    ('var_arm_time', 0.5),      # 抬升/夹爪默认持续时间 秒
    ('var_ray_white', 1300),    # 灰度白值阈值（>= 视为白/路口）
    ('var_ray_speed', 30),      # 巡线默认速度 %
    ('var_ray_Kp', 0.01),       # 巡线比例系数
    ('var_ray_Kd', 0.001),      # 巡线微分系数
]

# EEPROM 9/10 是标定程序写入的左右灰度白值地址（见主程序 func_value）
EEPROM_WHITE_LEFT = 9
EEPROM_WHITE_RIGHT = 10

# 巡线灰度 / 路口灰度 / 驱动电机 / 抬升电机 / 夹爪电机（与主程序推断一致）
RAY_LEFT_CH = 9
RAY_RIGHT_CH = 10
CROSS_LEFT_CH = 7
CROSS_RIGHT_CH = 8
MOTOR_L = 1
MOTOR_R = 2
MOTOR_ARM = 3
MOTOR_CLAW = 4
KEY_CONFIRM = 1
TOUCH_START = 1   # 主程序.py 用触碰传感器 1 作为启动/分段键
TIMER_LINE = 2   # 巡线计时的定时器编号（避免占用常用的 1 号）

# beep 用内置声音（PlayList.js 里的真实文件名）
BEEP_SOUND = 'dazhaohu_c0.mp3'


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def drive_loop(target_expr, base_speed_expr):
    """带直行纠偏的定距循环：
       重复执行直到 |编码器1| >= target：
          差值 = 编码器1 - 编码器2
          电机1 = base - Kp*差值 ; 电机2 = base + Kp*差值
          等待 0.01 秒
    """
    diff = VarGet('var_enc_diff')
    kp = VarGet('var_straight_Kp')
    return WhileCmp(
        Cmp(Abs(Encoder(MOTOR_L)), '>=', target_expr),
        [
            Set('var_enc_diff', Op(Encoder(MOTOR_L), '-', Encoder(MOTOR_R))),
            Motor(MOTOR_L, Op(base_speed_expr, '-', Op(kp, '*', diff))),
            Motor(MOTOR_R, Op(base_speed_expr, '+', Op(kp, '*', diff))),
            Wait(0.01),
        ],
    )


def turn_loop(target_expr, left_speed_expr, right_speed_expr):
    """原地转向循环：重复执行直到 |编码器1| >= target（目标 = 角度 × var_1angle）。"""
    return WhileCmp(
        Cmp(Abs(Encoder(MOTOR_L)), '>=', target_expr),
        [
            Motor(MOTOR_L, left_speed_expr),
            Motor(MOTOR_R, right_speed_expr),
            Wait(0.01),
        ],
    )


def reset_line_state():
    """清空巡线 PID 的历史误差。"""
    return [
        Set('var_err_last_9', Num(0)),
        Set('var_err_last_10', Num(0)),
    ]


# ---------------------------------------------------------------------------
# 1) func_Init —— 初始化 / 参数设置
# ---------------------------------------------------------------------------

def build_init():
    body = [Annotation('初始化：设定校准参数、读 EEPROM 灰度白值、停车、编码器清零。')
            ]
    for name, value in DEFAULTS:
        body.append(Set(name, Num(value)))
    body += [
        Annotation('EEPROM 9/10 = 标定程序写入的左/右灰度白值；没标定过就退回默认 1300。'),
        Set('var_ee_white_9', EE(EEPROM_WHITE_LEFT)),
        Set('var_ee_white_10', EE(EEPROM_WHITE_RIGHT)),
        If(Cmp(VarGet('var_ee_white_9'), '<', Num(100)), [Set('var_ee_white_9', Num(1300))]),
        If(Cmp(VarGet('var_ee_white_10'), '<', Num(100)), [Set('var_ee_white_10', Num(1300))]),
        Set('var_err_last_9', Num(0)),
        Set('var_err_last_10', Num(0)),
        Motor(MOTOR_L, Num(0)),
        Motor(MOTOR_R, Num(0)),
        Wait(0.05),
        ResetEncoder(MOTOR_L),
        ResetEncoder(MOTOR_R),
        Annotation('标记已初始化；各个动作函数检测到未初始化会自动调用本函数。'),
        Set('var_ready', Num(1)),
    ]
    return DefProc('func_Init', [], body)


# ---------------------------------------------------------------------------
# 2) 基础动作
# ---------------------------------------------------------------------------

def build_stop():
    return DefProc('func_Stop', [], [
        Annotation('停止：左右驱动电机速度清零。'),
        Motor(MOTOR_L, Num(0)),
        Motor(MOTOR_R, Num(0)),
        Wait(0.05),
    ])


def build_reset_encoder():
    return DefProc('func_ResetEncoder', [], [
        Annotation('驱动电机编码器清零（1=左轮 2=右轮）。'),
        ResetEncoder(MOTOR_L),
        ResetEncoder(MOTOR_R),
    ])


def build_forward():
    cm = VarGet('cm')
    return DefProc('func_ForwardCM', ['cm'], [
        guard(),
        Annotation('前进 cm 厘米：编码器定距 + 两轮差值纠偏；cm 必须 > 0。'),
        Call('func_ResetEncoder'),
        drive_loop(Op(cm, '*', VarGet('var_1cm')), VarGet('var_speed')),
        Motor(MOTOR_L, Num(0)),
        Motor(MOTOR_R, Num(0)),
        Wait(0.05),
    ])


def build_backward():
    cm = VarGet('cm')
    return DefProc('func_BackwardCM', ['cm'], [
        guard(),
        Annotation('后退 cm 厘米：编码器定距 + 两轮差值纠偏；cm 必须 > 0。'),
        Call('func_ResetEncoder'),
        drive_loop(Op(cm, '*', VarGet('var_1cm')),
                   Neg(VarGet('var_speed'))),
        Motor(MOTOR_L, Num(0)),
        Motor(MOTOR_R, Num(0)),
        Wait(0.05),
    ])


def build_turn_left():
    deg = VarGet('deg')
    return DefProc('func_TurnLeft', ['deg'], [
        guard(),
        Annotation('原地左转 deg 度：左轮反转、右轮正转，编码器定角度。'),
        Call('func_ResetEncoder'),
        turn_loop(Op(deg, '*', VarGet('var_1angle')),
                  Neg(VarGet('var_turn_speed')), VarGet('var_turn_speed')),
        Motor(MOTOR_L, Num(0)),
        Motor(MOTOR_R, Num(0)),
        Wait(0.05),
    ])


def build_turn_right():
    deg = VarGet('deg')
    return DefProc('func_TurnRight', ['deg'], [
        guard(),
        Annotation('原地右转 deg 度：左轮正转、右轮反转，编码器定角度。'),
        Call('func_ResetEncoder'),
        turn_loop(Op(deg, '*', VarGet('var_1angle')),
                  VarGet('var_turn_speed'), Neg(VarGet('var_turn_speed'))),
        Motor(MOTOR_L, Num(0)),
        Motor(MOTOR_R, Num(0)),
        Wait(0.05),
    ])


def build_drive_time():
    return DefProc('func_DriveTime', ['speedL', 'speedR', 'sec'], [
        guard(),
        Annotation('双电机按时间行驶：左速度 speedL %、右速度 speedR %，持续 sec 秒后自动停。'),
        DualTime(MOTOR_L, VarGet('speedL'), MOTOR_R, VarGet('speedR'), VarGet('sec')),
    ])


def build_drive_speed():
    return DefProc('func_DriveSpeed', ['speedL', 'speedR'], [
        guard(),
        Annotation('双电机持续转：左 speedL %、右 speedR %；不会自己停，要配 等待/重复/停止。'),
        Motor(MOTOR_L, VarGet('speedL')),
        Motor(MOTOR_R, VarGet('speedR')),
    ])


# ---------------------------------------------------------------------------
# 3) 抬升 / 夹爪（端口按主程序推断：3=抬升，4=夹爪；如不对请改函数体里的端口）
# ---------------------------------------------------------------------------

def build_arm_up():
    return DefProc('func_ArmUp', [], [
        guard(),
        Annotation('抬升电机（端口3）正转 var_arm_time 秒（默认 30% 速度）。'),
        MotorTime(MOTOR_ARM, VarGet('var_arm_speed'), VarGet('var_arm_time')),
    ])


def build_arm_down():
    return DefProc('func_ArmDown', [], [
        guard(),
        Annotation('抬升电机（端口3）反转 var_arm_time 秒。'),
        MotorTime(MOTOR_ARM, Neg(VarGet('var_arm_speed')), VarGet('var_arm_time')),
    ])


def build_grab():
    return DefProc('func_Grab', [], [
        guard(),
        Annotation('夹爪电机（端口4）正转 var_arm_time 秒（夹紧/取物）。'),
        MotorTime(MOTOR_CLAW, VarGet('var_arm_speed'), VarGet('var_arm_time')),
    ])


def build_release():
    return DefProc('func_Release', [], [
        guard(),
        Annotation('夹爪电机（端口4）反转 var_arm_time 秒（松开/放下）。'),
        MotorTime(MOTOR_CLAW, Neg(VarGet('var_arm_speed')), VarGet('var_arm_time')),
    ])


# ---------------------------------------------------------------------------
# 4) 巡线（灰度 9/10 巡线，7/8 找路口；参数仿自主程序 func_ray_*）
# ---------------------------------------------------------------------------

def build_line_step():
    err9 = VarGet('var_err_9')
    err10 = VarGet('var_err_10')
    last9 = VarGet('var_err_last_9')
    last10 = VarGet('var_err_last_10')
    pid9 = VarGet('var_pid_9')
    pid10 = VarGet('var_pid_10')
    kp = VarGet('var_ray_Kp')
    kd = VarGet('var_ray_Kd')
    return DefProc('func_LineStep', [], [
        Annotation('内部函数：巡线 PID 走一步（由 func_LineTime / func_LineUntilCross 调用）。'),
        Set('var_err_9', Op(VarGet('var_ee_white_9'), '-', Gray(RAY_LEFT_CH))),
        Set('var_err_10', Op(VarGet('var_ee_white_10'), '-', Gray(RAY_RIGHT_CH))),
        Set('var_pid_9', Op(Op(kp, '*', err9), '+', Op(kd, '*', Op(err9, '-', last9)))),
        Set('var_pid_10', Op(Op(kp, '*', err10), '+', Op(kd, '*', Op(err10, '-', last10)))),
        Set('var_err_last_9', err9),
        Set('var_err_last_10', err10),
        Motor(MOTOR_L, Op(VarGet('var_ray_speed'), '+', pid9)),
        Motor(MOTOR_R, Op(VarGet('var_ray_speed'), '+', pid10)),
        Wait(0.01),
    ])


def build_line_time():
    sec = VarGet('sec')
    return DefProc('func_LineTime', ['sec'], [
        guard(),
        Annotation('巡线行驶 sec 秒：灰度9/10 PID 巡线，到时间停车。'),
        *reset_line_state(),
        ResetTimer(TIMER_LINE),
        WhileCmp(Cmp(TimerMs(TIMER_LINE), '>=', Op(sec, '*', Num(1000))),
                 [Call('func_LineStep')]),
        Motor(MOTOR_L, Num(0)),
        Motor(MOTOR_R, Num(0)),
        Wait(0.05),
        *reset_line_state(),
    ])


def build_line_until_cross():
    # 注意：生成器把 while_cmp 的条件拼成 "while not <条件>:"，如果条件里直接放
    # or 会出现运算符优先级错误（not a or b ≠ not (a or b)）。所以这里改用
    # "重复执行直到左灰度7变白；循环体里如果右灰度8变白就跳出" 的等价结构。
    return DefProc('func_LineUntilCross', [], [
        guard(),
        Annotation('巡线到路口：灰度7 或 灰度8 读到白值（>= var_ray_white）时停车。'),
        *reset_line_state(),
        WhileCmp(
            Cmp(Gray(CROSS_LEFT_CH), '>=', VarGet('var_ray_white')),
            [
                If(Cmp(Gray(CROSS_RIGHT_CH), '>=', VarGet('var_ray_white')), [Break()]),
                Call('func_LineStep'),
            ]),
        Motor(MOTOR_L, Num(0)),
        Motor(MOTOR_R, Num(0)),
        Wait(0.05),
        *reset_line_state(),
    ])


# ---------------------------------------------------------------------------
# 5) 交互 / 显示 / 声音
# ---------------------------------------------------------------------------

def build_wait_start_key():
    return DefProc('func_WaitStartKey', [], [
        Annotation('等待按下主板的 Start(确认)键 1 再继续（如果你的车没有该按键，改用 func_WaitTouch）。'),
        WhileCmp(Cmp(Key(KEY_CONFIRM), '==', Num(1)), [Wait(0.02)]),
        Wait(0.2),
    ])


def build_wait_touch():
    return DefProc('func_WaitTouch', [], [
        Annotation('等待触碰传感器（端口1）被按下再继续；主程序.py 就是用触碰1当启动/分段键。'),
        WhileCmp(Cmp(Touch(TOUCH_START), '==', Num(1)), [Wait(0.02)]),
        Wait(0.2),
    ])


def build_show():
    return DefProc('func_Show', ['text'], [
        Annotation('在机器人屏幕显示一段文字（text 里放一个文本块）。'),
        Print(VarGet('text')),
    ])


def build_beep():
    return DefProc('func_Beep', [], [
        Annotation('播放内置提示音（打招呼声）。'),
        PlaySound(BEEP_SOUND),
    ])


# ---------------------------------------------------------------------------
# 6) 主程序示例（start 积木）
# ---------------------------------------------------------------------------

def build_start():
    return Start([
        Annotation('WER 函数库示例。做法：左边工具箱 → 函数 分类，把函数块拖进来；'),
        Annotation('下面 3 个动作块是示例，直接删掉换成你的任务即可。'),
        Annotation('① 初始化（必须第一步）'),
        Call('func_Init'),
        Annotation('② 前进 10 厘米（把 10 改成你要的厘米数）'),
        Call('func_ForwardCM', ['cm'], [Num(10)]),
        Annotation('③ 原地右转 90 度（把 90 改成你要的角度）'),
        Call('func_TurnRight', ['deg'], [Num(90)]),
        Call('func_Stop'),
        Annotation('其他常用：func_LineUntilCross 巡线到路口 / func_LineTime 巡线 N 秒 /'),
        Annotation('func_ArmUp func_Grab 取物 / func_WaitStartKey 等 Start 键 / func_WaitTouch 等触碰 / func_Show 显示文字。'),
    ])


# ---------------------------------------------------------------------------
# 组装 + 输出
# ---------------------------------------------------------------------------

def build_tops():
    return [
        build_init(),           # 0
        build_stop(),           # 1
        build_reset_encoder(),  # 2
        build_forward(),        # 3
        build_backward(),       # 4
        build_turn_left(),      # 5
        build_turn_right(),     # 6
        build_drive_time(),     # 7
        build_drive_speed(),    # 8
        build_arm_up(),         # 9
        build_arm_down(),       # 10
        build_grab(),           # 11
        build_release(),        # 12
        build_line_step(),      # 13
        build_line_time(),      # 14
        build_line_until_cross(),  # 15
        build_wait_start_key(), # 16
        build_wait_touch(),     # 17
        build_show(),           # 18
        build_beep(),           # 19
        build_start(),          # 20
    ]


def main():
    project = Project(robot_type='SKCON9', download_name='WERFuncLib')
    tops = build_tops()
    out_srh = os.path.join(ROOT, 'WER函数库.srh')
    out_srhs = os.path.join(ROOT, 'WER函数库.srhs')
    project.save_srh(out_srh, tops)
    project.save_srhs(out_srhs, tops)
    print('OK')
    print('  ', out_srh)
    print('  ', out_srhs)
    print('variables (%d):' % len(project.variables))
    for name, vid in project.variables.items():
        print('   ', name, '->', vid)
    try:
        print('project xml chars:', len(project.build_project_string(tops)))
    except Exception as e:  # noqa: BLE001
        print('re-serialize failed:', e)


if __name__ == '__main__':
    main()
