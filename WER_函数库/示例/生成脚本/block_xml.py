# -*- coding: utf-8 -*-
"""
AbilixScratch3.0 / Blockly 项目 XML 构造 DSL
================================================

用途：用 Python 代码"搭积木"，生成软件能识别的项目 XML（.srh / .srhs）。
本文件只负责把结构序列化成 Blockly XML，不做语义检查（语义检查用工具/验证/run_validate.py）。

设计：
- 值节点（Value）：Num / Text / VarGet / Op / Cmp / LogicAnd / LogicOr / Negate /
  Bool / Gray / Touch / Sonic / Key / Encoder / EncoderRT / TimerMs / EE / Unary / Round
- 语句节点（Stmt）：Set / Change / Motor / MotorTime / MotorAngle / DualTime / DualAngle /
  ResetEncoder / ResetTimer / Wait / If / IfElse / WhileCmp / WhileForever / WhileN /
  Break / WaitUntil / Print / PrintNum / PrintfText / PlaySound / SetDO / Servo /
  Annotation / BlockMod / Call
- 顶层：DefProc(name, params, body) / Start(body)
- Project：收集 variables、分配 block id、序列化成 <xml> 根，并写出 .srh / .srhs

变量与参数：
- VarGet('var_x') / Set('var_x', ...) 会自动登记变量并分配 id；
- DefProc 的 params 也会登记为变量（type=""），函数体内用 VarGet('cm') 引用参数；
- 变量名必须是 ASCII（生成 Python 时会做 safeName，中文会变成 _E5_... 乱码）。
"""

from collections import OrderedDict
import zipfile
import xml.etree.ElementTree as ET

NS = 'http://www.w3.org/1999/xhtml'
PROJECT_VERSION = '1.0.3.4'
ROBOT_TYPE_ZIP_COMMENT = {'SKCON9': '111', 'SKCON5': '110', 'SKCON2': '112'}

# Blockly 块 id 字符集（避免 XML 属性转义问题，且保证唯一即可）
_ID_ALPHABET = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'


# ---------------------------------------------------------------------------
# 值节点
# ---------------------------------------------------------------------------

class Value(object):
    """能插进 <value> 的积木（有输出连接）。"""
    block_type = None

    def to_xml(self, project):
        raise NotImplementedError


class _SimpleValue(Value):
    """只有字段、没有子块的简单值积木。"""

    def __init__(self, block_type, fields=None):
        self.block_type = block_type
        self.fields = fields or {}

    def to_xml(self, project):
        return project._make_block_element(self.block_type, fields=self.fields)


class Num(_SimpleValue):
    def __init__(self, value):
        # 数字格式：整数不带小数点，浮点用 repr（Blockly 可解析）
        if isinstance(value, float):
            if value.is_integer():
                text = str(int(value))
            else:
                text = repr(value)
        else:
            text = str(int(value))
        _SimpleValue.__init__(self, 'math_number', {'NUM': text})


class Text(_SimpleValue):
    """文本常量积木 block_conststring -> '...'"""

    def __init__(self, text):
        _SimpleValue.__init__(self, 'block_conststring', {'NAME': text})


class Bool(Value):
    def __init__(self, value=True):
        self.value = bool(value)

    def to_xml(self, project):
        return project._make_block_element('logic_boolean', fields={'BOOL': 'TRUE' if self.value else 'FALSE'})


class VarGet(Value):
    def __init__(self, name):
        self.name = name

    def to_xml(self, project):
        return project._make_block_element('variables_get', var_field=('VAR', self.name))


class Gray(Value):
    def __init__(self, channel):
        self.channel = channel

    def to_xml(self, project):
        return project._make_block_element('getai_glay', fields={'channel': str(self.channel)})


class Touch(Value):
    def __init__(self, channel):
        self.channel = channel

    def to_xml(self, project):
        return project._make_block_element('getai_touch', fields={'channel': str(self.channel)})


class Sonic(Value):
    def __init__(self, channel):
        self.channel = channel

    def to_xml(self, project):
        return project._make_block_element('getai_sonic', fields={'channel': str(self.channel)})


class Key(Value):
    def __init__(self, port=1):
        self.port = port

    def to_xml(self, project):
        return project._make_block_element('get_key', fields={'port': str(self.port)})


class Encoder(Value):
    def __init__(self, port):
        self.port = port

    def to_xml(self, project):
        return project._make_block_element('getencoder', fields={'port': str(self.port)})


class EncoderRT(Value):
    def __init__(self, port):
        self.port = port

    def to_xml(self, project):
        return project._make_block_element('get_encoder_real_time_value', fields={'port': str(self.port)})


class TimerMs(Value):
    def __init__(self, timer_id):
        self.timer_id = timer_id

    def to_xml(self, project):
        return project._make_block_element('getmseconds', fields={'timer_ID': str(self.timer_id)})


class EE(Value):
    def __init__(self, address):
        self.address = address

    def to_xml(self, project):
        return project._make_block_element('eeprom_read', fields={'address': str(self.address)})


class Op(Value):
    """math_op: A +/-/*// B（^ 由生成器转 robot.pow）"""

    def __init__(self, a, operator, b):
        assert operator in ('+', '-', '*', '/', '^'), operator
        self.a, self.operator, self.b = a, operator, b

    def to_xml(self, project):
        return project._make_block_element(
            'math_op', fields={'valname': self.operator}, values={'A': self.a, 'B': self.b})


class Cmp(Value):
    """math_compare: 生成 Python 比较表达式（= 号用 ==）。"""

    def __init__(self, a, operator, b):
        assert operator in ('<', '<=', '==', '>', '>='), operator
        self.a, self.operator, self.b = a, operator, b

    def to_xml(self, project):
        return project._make_block_element(
            'math_compare', fields={'comparison_operator': self.operator},
            values={'A': self.a, 'B': self.b})


class LogicAnd(Value):
    def __init__(self, a, b):
        self.a, self.b = a, b

    def to_xml(self, project):
        return project._make_block_element(
            'logic_operation', fields={'OP': 'AND'}, values={'A': self.a, 'B': self.b})


class LogicOr(Value):
    def __init__(self, a, b):
        self.a, self.b = a, b

    def to_xml(self, project):
        return project._make_block_element(
            'logic_operation', fields={'OP': 'OR'}, values={'A': self.a, 'B': self.b})


class Negate(Value):
    def __init__(self, a):
        self.a = a

    def to_xml(self, project):
        return project._make_block_element('logic_negate', values={'BOOL': self.a})


class Unary(Value):
    """robot_math_unary_operation: sqrt/fabs/negative/ln/log10/e^/10^"""

    OPS = ('sqrt', 'fabs', 'negative', 'ln', 'log10', 'e^', '10^')

    def __init__(self, operation, operand):
        assert operation in self.OPS, operation
        self.operation, self.operand = operation, operand

    def to_xml(self, project):
        return project._make_block_element(
            'robot_math_unary_operation', fields={'operation': self.operation},
            values={'operand': self.operand})


class Round(Value):
    """robot_math_rounding: round/ceil/floor"""

    def __init__(self, rounding_type, param):
        assert rounding_type in ('round', 'ceil', 'floor'), rounding_type
        self.rounding_type, self.param = rounding_type, param

    def to_xml(self, project):
        return project._make_block_element(
            'robot_math_rounding', fields={'rounding_type': self.rounding_type},
            values={'param': self.param})


def Abs(x):
    return Unary('fabs', x)


def Neg(x):
    return Unary('negative', x)


# ---------------------------------------------------------------------------
# 语句节点
# ---------------------------------------------------------------------------

class Stmt(object):
    """能插进语句链的积木（有上一个/下一个连接）。"""

    def to_xml(self, project):
        raise NotImplementedError


class _SimpleStmt(Stmt):
    def __init__(self, block_type, fields=None, values=None, var_field=None):
        self.block_type = block_type
        self.fields = fields or {}
        self.values = values or {}
        self.var_field = var_field

    def to_xml(self, project):
        return project._make_block_element(
            self.block_type, fields=self.fields, values=self.values, var_field=self.var_field)


class Set(Stmt):
    def __init__(self, name, value):
        self.name, self.value = name, value

    def to_xml(self, project):
        return project._make_block_element(
            'variables_set', values={'VALUE': self.value}, var_field=('VAR', self.name))


class Change(Stmt):
    def __init__(self, name, delta):
        self.name, self.delta = name, delta

    def to_xml(self, project):
        return project._make_block_element(
            'math_change', values={'DELTA': self.delta}, var_field=('VAR', self.name))


class Motor(Stmt):
    def __init__(self, port, speed):
        self.port, self.speed = port, speed

    def to_xml(self, project):
        return project._make_block_element(
            'motor', fields={'channel': str(self.port)}, values={'speed': self.speed})


class MotorTime(Stmt):
    def __init__(self, port, speed, seconds):
        self.port, self.speed, self.seconds = port, speed, seconds

    def to_xml(self, project):
        return project._make_block_element(
            'motor_time', fields={'channel': str(self.port)},
            values={'speed': self.speed, 'time': self.seconds})


class MotorAngle(Stmt):
    def __init__(self, port, speed, angle):
        self.port, self.speed, self.angle = port, speed, angle

    def to_xml(self, project):
        return project._make_block_element(
            'motor_angle', fields={'channel': str(self.port)},
            values={'speed': self.speed, 'angle': self.angle})


class DualTime(Stmt):
    def __init__(self, port1, speed1, port2, speed2, seconds):
        self.port1, self.speed1, self.port2, self.speed2, self.seconds = port1, speed1, port2, speed2, seconds

    def to_xml(self, project):
        return project._make_block_element(
            'dual_motor_duration',
            fields={'port_1': str(self.port1), 'port_2': str(self.port2)},
            values={'speed_1': self.speed1, 'speed_2': self.speed2, 'time': self.seconds})


class DualAngle(Stmt):
    def __init__(self, port1, speed1, port2, speed2, encoder_port, target):
        self.port1, self.speed1, self.port2, self.speed2 = port1, speed1, port2, speed2
        self.encoder_port, self.target = encoder_port, target

    def to_xml(self, project):
        return project._make_block_element(
            'dual_motor_angle',
            fields={'port_1': str(self.port1), 'port_2': str(self.port2), 'port_3': str(self.encoder_port)},
            values={'speed_1': self.speed1, 'speed_2': self.speed2, 'angle': self.target})


class ResetEncoder(Stmt):
    def __init__(self, port):
        self.port = port

    def to_xml(self, project):
        return project._make_block_element('resetencoder', fields={'port': str(self.port)})


class ResetTimer(Stmt):
    def __init__(self, timer_id):
        self.timer_id = timer_id

    def to_xml(self, project):
        return project._make_block_element('getmsecondsreset', fields={'timer_ID': str(self.timer_id)})


class Wait(Stmt):
    def __init__(self, seconds):
        self.seconds = seconds

    def to_xml(self, project):
        return project._make_block_element('wait', values={'time': self.seconds})


class If(Stmt):
    def __init__(self, cond, body):
        self.cond, self.body = cond, list(body)

    def to_xml(self, project):
        return project._make_block_element(
            'if', values={'logic_val': self.cond}, statements={'code': self.body})


class IfElse(Stmt):
    def __init__(self, cond, then_body, else_body):
        self.cond, self.then_body, self.else_body = cond, list(then_body), list(else_body)

    def to_xml(self, project):
        return project._make_block_element(
            'ifelse', values={'logic_val': self.cond},
            statements={'code': self.then_body, 'else_code': self.else_body})


class WhileCmp(Stmt):
    """重复执行直到 <cond>（cond 为"直到成立"的条件；生成 while not cond:）"""

    def __init__(self, cond, body):
        self.cond, self.body = cond, list(body)

    def to_xml(self, project):
        return project._make_block_element(
            'while_cmp', values={'bool': self.cond}, statements={'code': self.body})


class WhileForever(Stmt):
    def __init__(self, body):
        self.body = list(body)

    def to_xml(self, project):
        return project._make_block_element('while_forver', statements={'NAME': self.body})


class WhileN(Stmt):
    def __init__(self, times, body):
        self.times, self.body = times, list(body)

    def to_xml(self, project):
        return project._make_block_element(
            'while_number', values={'TIMES': self.times}, statements={'code': self.body})


class WaitUntil(Stmt):
    def __init__(self, cond):
        self.cond = cond

    def to_xml(self, project):
        return project._make_block_element('wait_until', values={'bool': self.cond})


class Break(Stmt):
    def to_xml(self, project):
        return project._make_block_element('while_break')


class PrintfText(Stmt):
    def __init__(self, text):
        self.text = text

    def to_xml(self, project):
        return project._make_block_element('printf_text', fields={'text': self.text})


class PrintfNumber(Stmt):
    def __init__(self, label, value):
        self.label, self.value = label, value

    def to_xml(self, project):
        return project._make_block_element(
            'printf_number', fields={'dataname': self.label}, values={'data': self.value})


class Print(Stmt):
    """显示 <表达式>（printf -> robot.print(expr, '\\n')）"""

    def __init__(self, value):
        self.value = value

    def to_xml(self, project):
        return project._make_block_element('printf', values={'para1': self.value})


class PlaySound(Stmt):
    def __init__(self, musicname):
        self.musicname = musicname

    def to_xml(self, project):
        return project._make_block_element('play_sound', fields={'musicname': self.musicname})


class SetDO(Stmt):
    def __init__(self, port, state):
        # state: 'ON'/'OFF'? 见 set_do 积木定义；这里传原样字符串
        self.port, self.state = port, state

    def to_xml(self, project):
        return project._make_block_element(
            'set_do', fields={'PORT': str(self.port), 'STATE': self.state})


class Servo(Stmt):
    def __init__(self, sid, speed, angle):
        self.sid, self.speed, self.angle = sid, speed, angle

    def to_xml(self, project):
        return project._make_block_element(
            'servoa_angle', fields={'channel': str(self.sid)},
            values={'speed': self.speed, 'angle': self.angle})


class Annotation(Stmt):
    def __init__(self, text):
        self.text = text

    def to_xml(self, project):
        return project._make_block_element('annotation', fields={'text': self.text})


class BlockMod(Stmt):
    def __init__(self, name, body):
        self.name, self.body = name, list(body)

    def to_xml(self, project):
        return project._make_block_element(
            'block_mod', fields={'NAME': self.name}, statements={'code': self.body})


class Call(Stmt):
    """调用自定义函数（procedures_callnoreturn）。

    params: 函数定义时的参数名列表（必须与 DefProc 一致，用于写 mutation）
    args:   传值列表（Value 或 None；None 表示空槽，用户自己填）
    """

    def __init__(self, name, params=None, args=None):
        self.name = name
        self.params = list(params or [])
        self.args = list(args or [])

    def to_xml(self, project):
        values = OrderedDict()
        for i, arg in enumerate(self.args):
            if arg is not None:
                values['ARG%d' % i] = arg
        return project._make_block_element(
            'procedures_callnoreturn',
            mutation=('name', self.name, self.params),
            values=values)


# ---------------------------------------------------------------------------
# 顶层节点
# ---------------------------------------------------------------------------

class TopLevel(object):
    def to_xml(self, project):
        raise NotImplementedError


class DefProc(TopLevel):
    """procedures_defnoreturn 自定义函数定义。"""

    def __init__(self, name, params, body):
        if not name.startswith('func_'):
            name = 'func_' + name
        self.name = name
        self.params = list(params or [])
        self.body = list(body)

    def to_xml(self, project):
        el = project._make_block_element(
            'procedures_defnoreturn',
            mutation=('def', None, self.params),
            fields={'NAME': self.name},
            statements={'STACK': self.body})
        return el


class Start(TopLevel):
    def __init__(self, body):
        self.body = list(body)

    def to_xml(self, project):
        el = project._make_block_element(
            'start', statements={'code': self.body}, deletable='false')
        return el


# ---------------------------------------------------------------------------
# 项目
# ---------------------------------------------------------------------------

def _xml_escape(text):
    return (str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


class Project(object):
    def __init__(self, robot_type='SKCON9', download_name='ProgramA'):
        self.robot_type = robot_type
        self.download_name = download_name
        self.variables = OrderedDict()   # name -> id
        self._var_seq = 0
        self._block_seq = 0

    # ---- id/变量 ----
    def _new_block_id(self):
        self._block_seq += 1
        n = self._block_seq
        chars = []
        base = len(_ID_ALPHABET)
        while True:
            chars.append(_ID_ALPHABET[n % base])
            n //= base
            if n == 0:
                break
        return 'blk_' + ''.join(reversed(chars))

    def var_id(self, name):
        if name not in self.variables:
            self._var_seq += 1
            self.variables[name] = 'v_%d_%s' % (self._var_seq, name)
        return self.variables[name]

    # ---- 序列化 ----
    def _value_input_xml(self, value):
        return value.to_xml(self)

    def _make_block_element(self, block_type, fields=None, values=None, statements=None,
                            mutation=None, var_field=None, deletable=None):
        el = ET.Element('block', {'type': block_type})
        el.set('id', self._new_block_id())
        if deletable is not None:
            el.set('deletable', deletable)
        if mutation is not None:
            kind, mut_name, params = mutation
            # 无参数的函数定义不写空 <mutation/>（与软件保存的真实文件一致）；
            # 函数调用（即使无参数）必须写 <mutation name="..."/>，否则不知道调谁。
            if kind == 'name' or params:
                mut = ET.SubElement(el, 'mutation')
                if kind == 'name':
                    mut.set('name', mut_name)
                    for p in params:
                        ET.SubElement(mut, 'arg', {'name': p})
                elif kind == 'def':
                    for p in params:
                        ET.SubElement(mut, 'arg', {'name': p, 'varid': self.var_id(p)})
        if var_field is not None:
            fname, vname = var_field
            f = ET.SubElement(el, 'field', {'name': fname, 'id': self.var_id(vname), 'variabletype': ''})
            f.text = vname
        for name, val in (fields or OrderedDict()).items():
            f = ET.SubElement(el, 'field', {'name': name})
            f.text = str(val)
        for name, val in (values or OrderedDict()).items():
            if val is None:
                continue
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                val = Num(val)
            v = ET.SubElement(el, 'value', {'name': name})
            v.append(val.to_xml(self))
        for name, body in (statements or OrderedDict()).items():
            if not body:
                continue
            st = ET.SubElement(el, 'statement', {'name': name})
            st.append(self._chain(list(body)))
        return el

    def _chain(self, stmts):
        """把语句列表串成 block -> next -> block ... 链，返回第一个 block 元素。"""
        first = stmts[0].to_xml(self)
        cur = first
        for s in stmts[1:]:
            nxt = ET.SubElement(cur, 'next')
            blk = s.to_xml(self)
            nxt.append(blk)
            cur = blk
        return first

    def project_xml(self, tops, positions=None):
        """positions: dict index->(x,y)；默认函数定义排成网格，start 放 (0,0)。"""
        root = ET.Element('xml', {'xmlns': NS})
        # variables 元素（在 blocks 之前）
        if self.variables or True:
            vars_el = ET.SubElement(root, 'variables')
            # 注意：变量必须在序列化 blocks 之后才全部登记；这里先占位，最后再补。
        blocks = []
        for i, top in enumerate(tops):
            el = top.to_xml(self)
            if positions and i in positions:
                x, y = positions[i]
                el.set('x', str(x))
                el.set('y', str(y))
            elif isinstance(top, Start):
                el.set('x', '480')
                el.set('y', '-40')
            else:
                col = i % 4
                row = i // 4
                el.set('x', str(-2600 + col * 460))
                el.set('y', str(-2200 + row * 620))
            blocks.append(el)
        # 现在变量已全部登记，填 variables 元素
        for name, vid in self.variables.items():
            v = ET.SubElement(vars_el, 'variable', {'type': '', 'id': vid})
            v.text = name
        for el in blocks:
            root.append(el)
        # 序列化：去掉 ET 自动加的 ns0 前缀（我们用裸标签 + 根 xmlns 声明）
        return ET.tostring(root, encoding='unicode')

    # ---- 输出 ----
    def build_project_string(self, tops, positions=None):
        return self.project_xml(tops, positions)

    def info_xml(self):
        return ('<?xml version="1.0" encoding="utf-8"?>\n'
                '<ScratchProjectInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n'
                '  <Version>%s</Version>\n'
                '  <RobotType>%s</RobotType>\n'
                '  <DownloadProgramName>%s</DownloadProgramName>\n'
                '</ScratchProjectInfo>' % (PROJECT_VERSION, self.robot_type, self.download_name))

    def build_srh(self, tops, positions=None):
        return ('<Abilix.ScratchProject.Info>\n' + self.info_xml() + '\n</Abilix.ScratchProject.Info>\n\n'
                '<Abilix.ScratchProject.ProjectString>\n' + self.build_project_string(tops, positions) +
                '\n</Abilix.ScratchProject.ProjectString>')

    def save_srh(self, path, tops, positions=None):
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(self.build_srh(tops, positions))

    def save_srhs(self, path, tops, positions=None):
        project = self.build_srh(tops, positions)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.writestr('abilixProject.srh', project.encode('utf-8'))
            z.comment = ROBOT_TYPE_ZIP_COMMENT.get(self.robot_type, '111').encode('ascii')


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def guard(init_func='func_Init'):
    """每个动作函数开头的"未初始化就先初始化"保护：
       if var_ready == 1: pass（空） else: func_Init()
       生成：if (var_ready == 1):\n    pass\nelse:\n    func_Init()\n
    """
    return IfElse(Cmp(VarGet('var_ready'), '==', Num(1)), [], [Call(init_func)])


def fabs_encoder(port=1):
    return Abs(Encoder(port))
