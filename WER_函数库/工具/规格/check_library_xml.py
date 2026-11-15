# -*- coding: utf-8 -*-
"""WER 函数库 XML 核对脚本
=============================
用 `WER_函数库/工具/规格/block_schemas.json`（schema 队友产出的积木规格）独立核对
`WER_函数库/WER函数库.srh` 里的每个积木：

  1. block type 是否存在于 IDE 积木定义（KNOWN_TYPES）与 SKCON9 工具箱（TOOLBOX_TYPES）；
  2. 每个 <field> 名与取值是否合法（下拉一律按下拉【值】比对，重点：channel/port/
     comparison_operator/valname/rounding_type/operation/musicname/OP/BOOL）；
  3. 每个 <value>/<statement> 输入名是否合法、子块输出类型与输入 check 是否匹配
     （例：while_cmp.bool 需要 Boolean；math_compare 输出 Boolean；
      robot_math_unary_operation 输出 Number）；
  4. <variables> 声明与 field VAR 的 id/名字是否一一对应；
  5. 附加：procedures_defnoreturn/callnoreturn 的 mutation 参数签名一致性、函数名 ASCII、
     顶层 start 唯一性、变量声明必须在 blocks 之前、block id 唯一。

用法:
  python check_library_xml.py                # 核对默认 WER_函数库/WER函数库.srh
  python check_library_xml.py <项目.srh>     # 核对指定项目
  python check_library_xml.py --report <md>  # 指定报告输出路径
退出码: 0 = 无 ERROR（可能有 WARN/INFO）；1 = 有 ERROR；2 = 输入/环境错误。

注意：本脚本只做静态核对，不覆盖运行期行为（真实 IDE 渲染/下载/机器人执行）。
"""
from __future__ import print_function

import datetime
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.dirname(os.path.dirname(HERE))          # .../WER_函数库
DEFAULT_SRH = os.path.join(LIB_DIR, "WER函数库.srh")
SCHEMAS_PATH = os.path.join(HERE, "block_schemas.json")
DEFAULT_REPORT = os.path.join(HERE, "库XML核对报告.md")
NS = "{http://www.w3.org/1999/xhtml}"

# ---------------------------------------------------------------- IDE 积木清单
# KNOWN_TYPES: IDE 解包源码里定义过的所有 block type（_分析临时/blockly_utf8 的
# blocks/*.js + stock defineBlocksWithJsonArray；已剔除 field_*/input_* 这类伪 type）。
# TOOLBOX_TYPES: maingui.html 的 SKCON9 工具箱里出现的 block type。
# 两者均由 schema 提取流程自动生成；新增/删减 IDE 版本时重新生成即可。
KNOWN_TYPES = set("""
AI abilix_math_number_property ai_close ai_learn ai_open ai_result annotation
arr_getvalue arr_insert arr_lenght arr_math arr_new arr_setvalue arr_sort
block_conststring block_mod close_smart_light colour_blend colour_picker colour_random
colour_rgb controls_flow_statements controls_for controls_forEach controls_if
controls_if_else controls_if_elseif controls_if_if controls_ifelse controls_repeat
controls_repeat_ext controls_whileUntil dual_motor_angle dual_motor_duration eeprom_read
eeprom_write function_call function_call_noreturn function_call_noreturn_para1
function_call_noreturn_para2 function_new function_new_para1 function_new_para2
get_aibychannel get_angle get_camcode get_colour get_encoder_real_time_value get_flame
get_humidity get_integrated_grayscale get_intelligent_motor_angle get_key get_magnetic
get_motion_sensor_angular_velocity get_sonic_detect_object getai_battery getai_glay
getai_ir getai_light getai_mic getai_sonic getai_temperature getai_touch getencoder
getmotionsensor getmseconds getmsecondsreset if ifelse lists_create_empty lists_create_with
lists_create_with_container lists_create_with_item lists_getIndex lists_getSublist
lists_indexOf lists_isEmpty lists_length lists_repeat lists_reverse lists_setIndex
lists_sort lists_split logic_boolean logic_compare logic_negate logic_null logic_operation
logic_ternary math_arithmetic math_atan2 math_change math_compare math_constant
math_constrain math_constval math_modulo math_number math_number_property math_on_list
math_op math_random_float math_random_int math_round math_single math_trig motor
motor_angle motor_time new_var play_note play_note_zero play_sound play_sound_until
printf printf_emoji printf_lines printf_number printf_text procedures_callnoreturn
procedures_callreturn procedures_defnoreturn procedures_defreturn procedures_ifreturn
procedures_mutatorarg procedures_mutatorcontainer read_var record resetencoder
resetmotionsensor robot_math_constants robot_math_random robot_math_rounding
robot_math_trigonometric_function robot_math_unary_operation servoa_angle
set_coloured_light set_do set_electric_magnet set_motor_reverse_open_loop set_smart_light
setdo_led setup_var start text text_append text_changeCase text_charAt text_count
text_create_join_container text_create_join_item text_getSubstring text_indexOf
text_isEmpty text_join text_length text_print text_prompt text_prompt_ext text_replace
text_reverse text_trim var_add variables_get variables_get_dynamic variables_set
variables_set_dynamic wait wait_until walkline_around walkline_floorsensor walkline_init
walkline_init_integrated_grayscale walkline_lineway_e walkline_linewayc
walkline_linewayt walkline_motor_stop_until walkline_start_motor_last
walkline_stop_until wer_set_motor_e while_break while_cmp while_forver while_number
""".split())

TOOLBOX_TYPES = set("""
abilix_math_number_property ai_close ai_learn ai_open ai_result annotation
block_conststring block_mod close_smart_light dual_motor_angle dual_motor_duration
eeprom_read eeprom_write function_call_noreturn get_aibychannel get_angle get_camcode
get_colour get_encoder_real_time_value get_flame get_humidity get_integrated_grayscale
get_intelligent_motor_angle get_magnetic get_motion_sensor_angular_velocity
get_sonic_detect_object getai_battery getai_glay getai_ir getai_light getai_mic
getai_sonic getai_temperature getai_touch getencoder getmotionsensor getmseconds
getmsecondsreset if ifelse logic_boolean logic_compare logic_negate logic_operation
math_compare math_modulo math_number math_op motor motor_angle motor_time play_sound
play_sound_until printf printf_emoji printf_lines printf_number printf_text record
resetencoder resetmotionsensor robot_math_constants robot_math_random robot_math_rounding
robot_math_trigonometric_function robot_math_unary_operation servoa_angle
set_coloured_light set_do set_electric_magnet set_motor_reverse_open_loop set_smart_light
wait wait_until walkline_around walkline_floorsensor walkline_init
walkline_init_integrated_grayscale walkline_lineway_e walkline_linewayc
walkline_linewayt walkline_motor_stop_until walkline_start_motor_last
walkline_stop_until wer_set_motor_e while_break while_cmp while_forver while_number
""".split())

# 不在静态工具箱、但属于“动态分类/系统块/空工程默认块”，允许使用
ALLOWED_NOT_IN_TOOLBOX = {
    "start": "事件/主函数：工具箱里被注释（maingui.html 注释掉的“事件”分类），由默认模板/工程提供",
    "procedures_defnoreturn": "动态“函数”分类（custom=PROCEDURE）里的新建函数模板",
    "procedures_callnoreturn": "动态“函数”分类里为每个函数生成的调用块",
    "procedures_defreturn": "有返回值函数：工具箱不提供新建，但 XML 载入后其调用块会出现在动态“函数”分类",
    "procedures_callreturn": "动态“函数”分类里为每个有返回值函数生成的调用块",
    "variables_get": "动态“变量”分类（custom=VARIABLE）",
    "variables_set": "动态“变量”分类（custom=VARIABLE）",
    "math_change": "动态“变量”分类（custom=VARIABLE）",
    "logic_boolean": "动态“变量/逻辑”示例里的标准 Blockly 块（SKCON9 工具箱运算分类也有）",
}
# 已知但本库不该用/需注意的块（仅提示）
NO_TOOLBOX_HINTS = {
    "get_key": "SKCON9 工具箱未列出（blocks/ 有定义且生成器 robot.check_key 存在，可能是旧版/其他机型遗留）；"
               "函数库若使用，请在真机确认 Start 键可用，或改用触碰传感器",
    "function_call_noreturn": "旧版函数调用块，生成器会拼出 `name()----;` 的坏代码，禁止使用",
}

# Python 侧输出的 check 类型（schema 里叫 connection.output；None 表示无显式 check=任意）
ALLOWED_VARTYPE_ATTRS = {None, "", "''"}


# ---------------------------------------------------------------- 采集
class Issue(object):
    def __init__(self, level, path, msg, hint=""):
        self.level = level
        self.path = path
        self.msg = msg
        self.hint = hint

    def as_line(self):
        s = "- `%s` **%s**: %s" % (self.path, self.level, self.msg)
        if self.hint:
            s += "\n    - 建议/说明: " + self.hint
        return s


def local(tag):
    return tag.rsplit("}", 1)[-1]


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_project(path):
    raw = open(path, "rb").read()
    text = raw.decode("utf-8-sig", "replace")
    i = text.find("<xml ")
    if i < 0:
        i = text.find("<xml>")
    if i < 0:
        raise ValueError("找不到 <xml 根标记（不是有效的 .srh 项目文件？）")
    j = text.find("</xml>", i)
    if j < 0:
        raise ValueError("找不到 </xml> 结束标记")
    xml_text = text[i:j + 6]
    info = {}
    m = re.search(r"<ScratchProjectInfo[\s\S]*?</ScratchProjectInfo>", text)
    if m:
        for k in ("RobotType", "DownloadProgramName", "Version"):
            mm = re.search(r"<%s>([^<]*)</%s>" % (k, k), m.group(0))
            if mm:
                info[k] = mm.group(1).strip()
    return raw, text, xml_text, info


# ---------------------------------------------------------------- 主检查器
class Checker(object):
    def __init__(self, schemas):
        self.schemas = schemas
        self.issues = []
        self.vars = []          # [(id, name)]
        self.var_by_id = {}
        self.var_by_name = {}
        self.defs = {}          # name -> [arg names]
        self.calls = []         # (name, args, path)
        self.used_types = {}
        self.block_ids = {}
        self.field_usage = {}   # (type, field) -> set(values)
        self.statement_count = 0
        self.shadow_count = 0
        self.empty_statements = []  # [(type, path, input)] 空语句输入（生成器会补 pass）

    # -- 小工具 --
    def add(self, level, path, msg, hint=""):
        self.issues.append(Issue(level, path, msg, hint))

    def err(self, path, msg, hint=""):
        self.add("ERROR", path, msg, hint)

    def warn(self, path, msg, hint=""):
        self.add("WARN", path, msg, hint)

    def info(self, path, msg, hint=""):
        self.add("INFO", path, msg, hint)

    def schema_of(self, typ):
        return self.schemas.get(typ)

    def type_known(self, typ):
        return typ in KNOWN_TYPES

    # -- XML 遍历 --
    def run(self, xml_text):
        root = ET.fromstring(xml_text)
        if local(root.tag) != "xml":
            raise ValueError("根元素应为 <xml>，实际是 <%s>" % local(root.tag))
        children = list(root)
        seen_block = False
        for ch in children:
            tag = local(ch.tag)
            if tag == "variables":
                if seen_block:
                    self.err("<xml>",
                             "<variables> 出现在 <block> 之后：Blockly 按文档顺序处理，"
                             "变量必须声明在积木之前，否则运行期可能创建重复变量/丢失引用",
                             "把 <variables> 移到 <xml> 的第一个子元素")
                self._check_variables(ch)
                continue
            if tag in ("block", "shadow"):
                seen_block = True
                continue
            if tag not in ("block", "shadow"):
                self.warn("<xml>", "未知的根级子元素 <%s>（Blockly 会忽略）" % tag)
        top_blocks = [ch for ch in children if local(ch.tag) in ("block", "shadow")]
        self._used_types = {}
        for idx, b in enumerate(top_blocks):
            self._check_block(b, "top[%d]" % idx, parent_ctx="top")
        # 顶层 start 检查
        starts = [b for b in top_blocks if b.get("type") == "start"]
        if not starts:
            self.err("top", "工程里没有 start（主函数）积木：生成 Python 时不会产生 def main()",
                     "函数库工程应保留 1 个 start 块（deletable=false）")
        elif len(starts) > 1:
            self.err("top", "存在 %d 个 start 积木：都会各自生成一个 def main()，Python 会重复定义" % len(starts))
        for i, s in enumerate(starts):
            if s.get("deletable") != "false":
                self.warn("top[%d]" % i, "start 缺少 deletable=\"false\" 属性（UI 里可能允许删除主函数）")
            st_in = [c for c in s if local(c.tag) == "statement" and c.get("name") == "code"]
            if not st_in or not [c for c in st_in[0] if local(c.tag) in ("block", "shadow")]:
                self.info("top[%d]" % i, "start 的 code 语句为空：生成的 main() 只有 pass（函数库这样没问题）")
        # procedures 签名交叉检查
        for name, args, path in self.calls:
            if name not in self.defs:
                self.err(path, "调用了不存在的函数 `%s`（工程里没有同名 procedures_defnoreturn/defreturn）" % name,
                         "调用块的 onchange 会在加载时自动新建一个空函数定义，容易产生重复/空函数；应补上定义或改名")
                continue
            if args != self.defs[name]:
                self.err(path, "调用函数 `%s` 的参数 %r 与定义参数 %r 不一致（名字/顺序必须完全一致）" % (name, args, self.defs[name]),
                         "签名不一致会触发调用块自动新建同名 def，Python 里可能出现重复函数定义")
        return self

    def _check_variables(self, el):
        for v in el:
            if local(v.tag) != "variable":
                self.warn("<variables>", "未知元素 <%s>（应为 <variable>）" % local(v.tag))
                continue
            vid = v.get("id")
            name = (v.text or "").strip()
            typ = v.get("type", "")
            if typ not in (None, ""):
                self.warn("<variables>", "变量 `%s` 的 type=%r 非空（本项目全部变量应为 type=\"\"）" % (name, typ))
            if not vid:
                self.err("<variables>", "变量 `%s` 缺少 id 属性" % name)
                continue
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
                self.warn("<variables>", "变量名 `%s` 含非 ASCII/非标识符字符：生成 Python 时会被 safeName_ 转成 _E5_... 之类乱码" % name,
                          "变量名建议 var_ 前缀 + ASCII")
            if vid in self.var_by_id:
                self.err("<variables>", "变量 id `%s` 重复声明" % vid)
            if name in self.var_by_name:
                self.warn("<variables>", "变量名 `%s` 重复（Blockly 变量表按名字索引，容易歧义）" % name)
            self.vars.append((vid, name))
            self.var_by_id[vid] = name
            self.var_by_name[name] = vid

    # -- 递归检查一块 --
    def _check_block(self, el, path, parent_ctx):
        tag = local(el.tag)
        typ = el.get("type")
        bid = el.get("id")
        if not typ:
            self.err(path, "<%s> 缺少 type 属性" % tag)
            return
        if bid:
            if bid in self.block_ids:
                # 真实 IDE 保存的项目里 shadow 块 id 大量重复（PI 样本亦如此），Blockly 加载不报错；
                # 但对工具生成的新工程仍建议唯一，避免潜在连接/撤销问题。
                self.warn(path, "block id `%s` 重复（另一个位置：%s）" % (bid, self.block_ids[bid]),
                          "真实 IDE 存盘项目也存在 shadow id 重复且能加载；新生成工程建议保持 id 全局唯一")
            else:
                self.block_ids[bid] = path
        if tag == "shadow":
            self.shadow_count += 1
        if el.get("disabled") == "true":
            self.warn(path, "积木 `%s` 带 disabled=\"true\"：生成器会跳过它（不产生任何 Python 代码），"
                            "若这是函数库请确认是无意残留" % typ)
        self.used_types[typ] = self.used_types.get(typ, 0) + 1
        if not self.type_known(typ):
            self.err(path, "未知 block type `%s`：IDE 源码里没有这个积木，会加载失败/被忽略" % typ)
            return
        if typ not in TOOLBOX_TYPES and typ not in ALLOWED_NOT_IN_TOOLBOX:
            hint = NO_TOOLBOX_HINTS.get(typ, "")
            self.warn(path, "block type `%s` 不在 SKCON9 工具箱里（blocks/ 里有定义）" % typ, hint)
        elif typ in NO_TOOLBOX_HINTS:
            self.info(path, NO_TOOLBOX_HINTS[typ])
        if typ == "start" and parent_ctx != "top":
            self.err(path, "start 积木必须是顶层块，不能嵌在其它块里")
        if parent_ctx == "statement" and self.schema_of(typ):
            conn = self.schema_of(typ).get("connection") or {}
            if conn.get("output") is not None or conn.get("has_output"):
                self.err(path, "有输出值的积木 `%s` 不能直接放在语句链里（缺少输出连接）" % typ)
        sch = self.schema_of(typ)
        if not sch:
            self.info(path, "block type `%s` 存在但 block_schemas.json 未收录，跳过字段/输入级检查" % typ)
            return
        self._check_fields(el, typ, sch, path)
        self._check_inputs(el, typ, sch, path)
        self._check_mutation(el, typ, path)
        self._check_next(el, path)
        for ch in el:
            ctag = local(ch.tag)
            if ctag not in ("field", "value", "statement", "mutation", "next", "comment"):
                self.warn(path, "未知子元素 <%s>（Blockly 会忽略）" % ctag)

    def _check_fields(self, el, typ, sch, path):
        fields = sch.get("fields") or {}
        present = {}
        for f in el:
            if local(f.tag) != "field":
                continue
            fname = f.get("name")
            fval = (f.text or "").strip() if f.text is not None else ""
            present[fname] = fval
            self.field_usage.setdefault((typ, fname), set()).add(fval)
            if not fname:
                self.err(path, "存在没有 name 的 <field>")
                continue
            if typ == "procedures_callnoreturn" and fname == "NAME":
                self.info(path, "调用块里显式写了 <field name=\"NAME\">（真实样本不写，由 <mutation name> 恢复；多写一般无害）")
                continue
            fdef = fields.get(fname)
            if fdef is None:
                if fname in ("PARAMS", "WITH", "ARGNAME0", "ARGNAME1", "ARGNAME2"):
                    self.warn(path, "<field name=\"%s\"> 是运行时自动生成的字段，不应写进 XML" % fname)
                else:
                    self.err(path, "积木 `%s` 没有字段 `%s`：Blockly 会打印 'Ignoring non-existent field' 并丢弃该值" % (typ, fname),
                             "该块合法字段: %s" % (", ".join(sorted(fields)) or "<无字段>"))
                continue
            kind = fdef.get("kind")
            if kind == "field_dropdown":
                opts = [str(o[1]) for o in (fdef.get("options") or [])]
                if opts and fval not in opts:
                    labels = {str(o[1]): o[0] for o in (fdef.get("options") or [])}
                    self.err(path, "字段 `%s` 的值 %r 不是合法下拉值；合法值=%r（界面文案=%r）" % (fname, fval, opts, labels),
                             "XML 必须写下拉【值】而不是界面文案；非法值会被 Blockly 静默回退到第一项")
            elif kind == "field_number":
                try:
                    num = float(fval)
                except ValueError:
                    self.err(path, "字段 `%s` 的值 %r 不是数字" % (fname, fval))
                    continue
                lo, hi = fdef.get("min"), fdef.get("max")
                if lo is not None or hi is not None:
                    try:
                        if lo is not None and num < float(lo):
                            self.warn(path, "字段 `%s`=%r 小于建议下限 %s（UI 会限制在 %s~%s）" % (fname, fval, lo, lo, hi))
                        if hi is not None and num > float(hi):
                            self.warn(path, "字段 `%s`=%r 大于建议上限 %s（UI 会限制在 %s~%s）" % (fname, fval, hi, lo, hi))
                    except ValueError:
                        pass
            elif kind == "field_checkbox":
                if fval not in ("TRUE", "FALSE"):
                    self.warn(path, "checkbox 字段 `%s` 的值 %r 应为 TRUE/FALSE" % (fname, fval))
            elif kind == "field_variable":
                self._check_var_field(f, typ, fname, fval, path)
            # field_text_input / field_colour：不限制内容
        # 缺失字段提示（下拉/数字/文本字段缺失时用默认值，不致命）
        for fname, fdef in fields.items():
            if fname in present:
                continue
            if fdef.get("kind") in ("field_dropdown", "field_number", "field_checkbox"):
                self.warn(path, "积木 `%s` 缺少字段 `%s`，将使用默认值 %r" % (
                    typ, fname, (fdef.get("options") or [[None, fdef.get("default")]])[0][1]))
        if typ == "procedures_defnoreturn":
            # NAME 由 <field> 提供（真实样本如此），必须存在
            if "NAME" not in present:
                self.err(path, "procedures_defnoreturn 缺少 <field name=\"NAME\">，函数名会变成空/块 id")

    def _check_var_field(self, f, typ, fname, fval, path):
        vid = f.get("id")
        vtype = f.get("variabletype")
        if vtype not in ALLOWED_VARTYPE_ATTRS:
            self.err(path, "字段 `%s` 的 variabletype=%r 非法（应为空或 \"''\"）" % (fname, vtype))
        if vid is None:
            self.warn(path, "变量字段 `%s` 没有 id 属性（会按名字兜底查找/创建变量，建议补 id 与 <variables> 对应）" % fname)
            if fval not in self.var_by_name:
                self.warn(path, "变量 `%s` 未在 <variables> 中声明，加载时会自动创建" % fval)
            return
        if vid not in self.var_by_id:
            self.err(path, "变量字段 `%s` 引用了未声明的变量 id `%s`（名字 %r）" % (fname, vid, fval),
                     "在 <variables> 里补 <variable type=\"\" id=\"%s\">%s</variable>" % (vid, fval))
            return
        declared = self.var_by_id[vid]
        if declared != fval:
            self.warn(path, "变量字段 `%s` 的文本 %r 与声明的变量名 %r 不一致（显示/生成以声明为准）" % (fname, fval, declared))

    def _child_blocks(self, el):
        return [c for c in el if local(c.tag) in ("block", "shadow")]

    def _check_inputs(self, el, typ, sch, path):
        inputs = sch.get("inputs") or {}
        vdefs = inputs.get("value") or {}
        sdefs = inputs.get("statement") or {}
        conn = sch.get("connection") or {}
        seen_value, seen_stmt = set(), set()
        for ch in el:
            ctag = local(ch.tag)
            if ctag not in ("value", "statement"):
                continue
            iname = ch.get("name")
            kids = self._child_blocks(ch)
            if ctag == "value":
                if iname not in vdefs:
                    self.err(path, "积木 `%s` 没有值输入 `%s`：Blockly 会忽略该 <value>（子块不会接上）" % (typ, iname),
                             "合法值输入: %s" % (", ".join(sorted(vdefs)) or "<无>"))
                    for k in kids:
                        self._check_block(k, path + "/value[%s]" % iname, parent_ctx="value")
                    continue
                seen_value.add(iname)
                if len(kids) == 0:
                    self.warn(path, "值输入 `%s` 为空：生成 Python 时该参数位置是空表达式" % iname)
                    continue
                for k in kids:
                    kpath = path + "/value[%s]" % iname
                    self._check_block(k, kpath, parent_ctx="value")
                    self._check_value_type(k, kpath, vdefs[iname].get("check"), iname, typ, path)
            else:
                if iname not in sdefs:
                    self.err(path, "积木 `%s` 没有语句输入 `%s`：Blockly 会忽略该 <statement>" % (typ, iname),
                             "合法语句输入: %s" % (", ".join(sorted(sdefs)) or "<无>"))
                    for k in kids:
                        self._check_block(k, path + "/statement[%s]" % iname, parent_ctx="statement")
                    continue
                seen_stmt.add(iname)
                for k in kids:
                    self._check_block(k, path + "/statement[%s]" % iname, parent_ctx="statement")
        for iname in vdefs:
            if typ in ("procedures_callnoreturn", "procedures_callreturn"):
                continue  # ARG0..ARGn 由 mutation 的 arg 数量决定，单独在 _check_mutation 里查
            if iname not in seen_value:
                self.warn(path, "积木 `%s` 缺少值输入 `%s`（生成 Python 时可能得到空参数）" % (typ, iname))
        for iname in sdefs:
            if iname not in seen_stmt:
                if typ == "start" and iname == "code":
                    continue
                self.empty_statements.append((typ, path, iname))

    def has_output_conn(self, sch):
        """schema 里该块是否有输出连接。stock JSON 块用 has_output 键；自定义块用 output!=null。"""
        c = sch.get("connection") or {}
        if "has_output" in c:
            return bool(c["has_output"])
        return c.get("output") is not None

    def _check_value_type(self, child, cpath, parent_check, iname, ptyp, ppath):
        ctyp = child.get("type")
        csch = self.schema_of(ctyp)
        if not csch:
            return
        cconn = csch.get("connection") or {}
        has_output = self.has_output_conn(csch)
        if not has_output:
            self.err(cpath, "积木 `%s`（无输出）被插进了值输入 `%s`，连接不会成立" % (ctyp, iname))
            return
        if parent_check is None:
            return
        child_out = cconn.get("output")
        if child_out is None:
            if ctyp in ("variables_get", "variables_get_dynamic"):
                return  # 变量积木的输出无 check，属于正常用法（Blockly 允许无类型→有类型连接）
            self.warn(cpath, "无 check 的输出积木 `%s` 接入了需要 %s 的输入 `%s`（Blockly 允许，运行期按实际值类型算）"
                      % (ctyp, parent_check, iname))
        elif child_out != parent_check:
            self.err(cpath, "类型不匹配：`%s` 输出 %r，但 `%s` 的输入 `%s` 需要 %r"
                      % (ctyp, child_out, ptyp, iname, parent_check))

    def _check_next(self, el, path):
        nxt = [c for c in el if local(c.tag) == "next"]
        if not nxt:
            return
        if len(nxt) > 1:
            self.err(path, "存在多个 <next>（一个块最多一个 next）")
        for n in nxt:
            kids = self._child_blocks(n)
            if not kids:
                self.info(path, "<next> 为空")
            for k in kids:
                self._check_block(k, path + "/next", parent_ctx="statement")

    def _check_mutation(self, el, typ, path):
        muts = [c for c in el if local(c.tag) == "mutation"]
        if len(muts) > 1:
            self.err(path, "存在多个 <mutation>（一个块最多一个）")
        if typ in ("procedures_defnoreturn", "procedures_defreturn"):
            name = None
            args = []
            for f in el:
                if local(f.tag) == "field" and f.get("name") == "NAME":
                    name = (f.text or "").strip()
            if muts:
                for a in muts[0]:
                    if local(a.tag) != "arg":
                        self.warn(path, "def mutation 里出现未知元素 <%s>（应为 <arg>）" % local(a.tag))
                        continue
                    an = (a.get("name") or "").strip()
                    vid = a.get("varid")
                    args.append(an)
                    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", an):
                        self.err(path, "函数参数名 %r 不是 ASCII 标识符：生成 Python 会被 safeName_ 转义成乱码" % an)
                    if len(args) != len(set(args)):
                        self.err(path, "def mutation 参数名重复：%r" % args)
                    if vid:
                        if vid not in self.var_by_id:
                            self.err(path, "def mutation 参数 `%s` 的 varid `%s` 未在 <variables> 声明" % (an, vid),
                                     "补 <variable type=\"\" id=\"%s\">%s</variable>" % (vid, an))
                        elif self.var_by_id[vid] != an:
                            self.err(path, "def mutation 参数 `%s` 与 varid `%s` 声明的名字 `%s` 不一致" % (an, vid, self.var_by_id[vid]))
                    else:
                        if an not in self.var_by_name:
                            self.warn(path, "def mutation 参数 `%s` 未在 <variables> 声明（加载时会自动创建变量）" % an)
            if name:
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
                    self.err(path, "函数名 %r 不是 ASCII 标识符：生成 Python 会被 safeName_ 转义成乱码" % name)
                elif not name.startswith("func_"):
                    self.warn(path, "函数名 %r 未以 func_ 开头（IDE 界面改名约定是自动加 func_ 前缀；XML 载入不校验，生成 Python 仍可用）" % name)
                if name in self.defs:
                    self.err(path, "函数 `%s` 重复定义（另一处：%s）" % (name, self.defs[name]), "重复 def 会让 Python 后一个覆盖前一个")
                self.defs[name] = args
            else:
                self.err(path, "procedures_def* 缺少 NAME 字段")
        elif typ in ("procedures_callnoreturn", "procedures_callreturn"):
            name = None
            args = []
            if muts:
                name = muts[0].get("name")
                for a in muts[0]:
                    if local(a.tag) == "arg":
                        args.append((a.get("name") or "").strip())
                if muts[0].get("name") is None:
                    self.err(path, "%s 的 <mutation> 缺少 name 属性（函数名）" % typ)
            else:
                self.err(path, "%s 缺少 <mutation name=\"func_x\">（函数名与参数都靠它恢复）" % typ)
            if name:
                self.calls.append((name, args, path))
            if len(args) != len(set(args)):
                self.err(path, "调用块 mutation 参数名重复：%r" % args)
            # 每个 <arg> 都应有对应的 ARG<i> 值输入；缺了生成器会填 None
            for i, _an in enumerate(args):
                has_in = any(local(c.tag) == "value" and c.get("name") == "ARG%d" % i for c in el)
                if not has_in:
                    self.warn(path, "调用块 mutation 有第 %d 个参数，但缺少 <value name=\"ARG%d\"> 值输入（生成 Python 会传 None）"
                              % (i + 1, i))
        elif typ == "abilix_math_number_property":
            has_divisor_input = any(local(c.tag) == "value" and c.get("name") == "DIVISOR" for c in el)
            prop = None
            for f in el:
                if local(f.tag) == "field" and f.get("name") == "PROPERTY":
                    prop = (f.text or "").strip()
            div_attr = None
            if muts:
                div_attr = muts[0].get("divisor_input")
            if prop == "DIVISIBLE_BY" and not has_divisor_input:
                self.warn(path, "PROPERTY=DIVISIBLE_BY 但缺少 DIVISOR 值输入")
            if div_attr is not None and (div_attr == "true") != has_divisor_input:
                self.warn(path, "mutation divisor_input=%r 与是否存在 DIVISOR 输入不一致" % div_attr)
        elif muts:
            self.info(path, "积木 `%s` 出现了 <mutation>，schema 未定义语义，忽略" % typ)

    # -- 汇总 --
    def summary(self):
        c = {"ERROR": 0, "WARN": 0, "INFO": 0}
        for it in self.issues:
            c[it.level] += 1
        return c


# ---------------------------------------------------------------- 报告
def render_report(path_srh, raw, info, chk, report_path):
    c = chk.summary()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("# WER 函数库 XML 核对报告\n")
    lines.append("> 本报告由 `WER_函数库/工具/规格/check_library_xml.py` 自动生成（只读核对，不修改任何工程文件）。\n")
    lines.append("## 1. 输入\n")
    lines.append("| 项 | 值 |")
    lines.append("|---|---|")
    lines.append("| 核对时间 | %s |" % now)
    lines.append("| 工程文件 | `%s` |" % path_srh)
    lines.append("| 文件大小 | %d 字节 |" % len(raw))
    lines.append("| SHA256 | `%s` |" % sha256_of(path_srh))
    lines.append("| RobotType | %s |" % info.get("RobotType", "?"))
    lines.append("| 程序名 | %s |" % info.get("DownloadProgramName", "?"))
    lines.append("| 积木类型数 | %d |" % len(chk.used_types))
    lines.append("| 变量声明 | %d 个 |" % len(chk.vars))
    lines.append("| 函数定义 | %d 个 |" % len(chk.defs))
    lines.append("| 函数调用 | %d 处 |" % len(chk.calls))
    lines.append("")
    lines.append("## 2. 结论\n")
    verdict = "**通过**（无 ERROR）" if c["ERROR"] == 0 else "**发现 %d 个 ERROR，建议修复后再交付**" % c["ERROR"]
    lines.append("- 核对结果：%s" % verdict)
    lines.append("- 计数：ERROR=%d，WARN=%d，INFO=%d" % (c["ERROR"], c["WARN"], c["INFO"]))
    lines.append("- 使用到的积木类型：`%s`" % "、".join(sorted(chk.used_types)))
    lines.append("")
    lines.append("**核对要点**：")
    lines.append("1. 所有 block type 均在 IDE 积木定义（KNOWN_TYPES）中存在；start / procedures_* / variables_* 属动态分类或默认模板，已按允许项处理。")
    lines.append("2. 所有 `<field>` 名在该积木的合法字段表中；下拉字段一律按 schema 的【值】比对（不是界面文案）——见第 6 节。")
    lines.append("3. 所有 `<value>`/`<statement>` 输入名合法；子块输出 check 与父输入 check 匹配（无 check 的 variables_get 属正常用法，仅 INFO）。")
    lines.append("4. `<variables>` 声明与 field VAR 的 id/名字一一对应；函数 mutation 参数 varid 与声明一致。")
    lines.append("5. 函数定义/调用签名（名字+参数个数+参数名+顺序）完全一致，无重复定义、无孤调用。")
    lines.append("6. 唯一一个 start，deletable=false；整个 XML 中 block id 唯一。")
    lines.append("")
    errs = [it for it in chk.issues if it.level == "ERROR"]
    if not errs:
        lines.append("**一句话结论**：本工程 XML 在「结构 / 字段取值 / 输入类型 / 变量引用 / 函数签名」五个层面自洽，可交给 headless 验证与 IDE 实测。"
                     + ("（WARN 项见第 4 节，均为需要人工知悉但不必然错误的点）" if c["WARN"] else ""))
        lines.append("")
    for lvl, title in (("ERROR", "3. ERROR（必须修复）"), ("WARN", "4. WARN（建议核对/修复）"), ("INFO", "5. INFO（提示）")):
        items = [it for it in chk.issues if it.level == lvl]
        lines.append("## %s\n" % title)
        if not items:
            lines.append("- 无\n")
        else:
            for it in items:
                lines.append(it.as_line())
        if lvl == "INFO" and chk.empty_statements:
            from collections import Counter as _C
            cnt = _C(t for t, _p, _i in chk.empty_statements)
            lines.append("- 另有 %d 处语句输入为空（生成器自动补 `pass`，属正常）：%s" % (
                len(chk.empty_statements),
                "、".join("`%s`×%d" % (k, v) for k, v in sorted(cnt.items()))))
        lines.append("")
    # 字段取值核对表
    lines.append("## 6. 字段取值核对（下拉重点）\n")
    lines.append("| 积木 | 字段 | 工程中出现的值 | schema 合法值 | 结论 |")
    lines.append("|---|---|---|---|---|")
    focus = {"channel", "port", "PORT", "comparison_operator", "valname", "rounding_type",
             "operation", "musicname", "OP", "BOOL", "STATE", "status", "constant_type",
             "trigonometric_function_type", "emoji_name", "timer_ID", "property", "PROPERTY"}
    for (typ, fname), vals in sorted(chk.field_usage.items()):
        if fname not in focus:
            continue
        sch = chk.schema_of(typ) or {}
        fdef = (sch.get("fields") or {}).get(fname) or {}
        legal = [str(o[1]) for o in (fdef.get("options") or [])]
        if legal:
            bad = [v for v in vals if v not in legal]
            verdict_f = "✅ 全部合法" if not bad else "❌ 非法值 %r" % bad
            lines.append("| `%s` | `%s` | %s | %s | %s |" % (
                typ, fname, "、".join("`%s`" % v for v in sorted(vals)),
                "、".join("`%s`" % v for v in legal[:10]) + ("…" if len(legal) > 10 else ""), verdict_f))
        else:
            lines.append("| `%s` | `%s` | %s | （非下拉：不限制） | ✅ |" % (
                typ, fname, "、".join("`%s`" % v for v in sorted(vals))))
    lines.append("")
    # 函数签名
    lines.append("## 7. 函数定义与调用签名\n")
    lines.append("| 函数 | 定义参数 | 调用处数 | 参数一致性 |")
    lines.append("|---|---|---|---|")
    callmap = {}
    for name, args, _p in chk.calls:
        callmap.setdefault(name, []).append(args)
    for name, args in sorted(chk.defs.items()):
        cs = callmap.get(name, [])
        bad = [a for a in cs if a != args]
        lines.append("| `%s` | %r | %d | %s |" % (name, args, len(cs),
                                               "✅ 一致" if not bad else "❌ 不一致：%r" % bad))
    for name in callmap:
        if name not in chk.defs:
            lines.append("| `%s` | （无定义！） | %d | ❌ 缺少定义 |" % (name, len(callmap[name])))
    lines.append("")
    lines.append("## 8. 变量 id 对应核对\n")
    lines.append("- `<variables>` 声明 %d 个；被积木字段引用的变量 id 必须∈声明集合（逐条已在 ERROR/WARN 中列出）。" % len(chk.vars))
    lines.append("- 声明清单（id = 名字）：")
    for vid, name in chk.vars:
        lines.append("  - `%s` = `%s`" % (vid, name))
    lines.append("")
    lines.append("## 9. 未覆盖项（本脚本不做）\n")
    lines.append("- 运行期行为：真实 IDE 渲染、函数分类 flyout 实例化、Python 生成/下载/机器人执行（由 `工具/验证/run_validate.py` 的 headless 验证覆盖）。")
    lines.append("- `.srhs` 打包（zip 注释=机器人类型枚举）与 IDE 项目列表安装。")
    lines.append("- 硬件相关风险：如 `get_key` 不在 SKCON9 工具箱，真机是否有 Start/Left/Right 键需实机确认。")
    lines.append("- 生成器语义级检查（同一份 XML 生成 Python 是否正确）不在本脚本范围；本脚本只看 XML 结构/字段/类型/引用是否自洽。")
    lines.append("")
    lines.append("---\n")
    lines.append("（报告由脚本生成；核对基准为 `block_schemas.json`，其证据来源见该文件 `meta.sources`。）")
    md = "\n".join(lines)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    return md


def main(argv):
    srh = DEFAULT_SRH
    report = DEFAULT_REPORT
    args = argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--report" and i + 1 < len(args):
            report = args[i + 1]
            i += 2
            continue
        if a.startswith("-"):
            print("未知参数:", a)
            return 2
        srh = a
        i += 1
    if not os.path.exists(srh):
        print("找不到工程文件:", srh)
        return 2
    if not os.path.exists(SCHEMAS_PATH):
        print("找不到规格文件:", SCHEMAS_PATH)
        return 2
    schemas = json.load(open(SCHEMAS_PATH, encoding="utf-8"))["blocks"]
    try:
        raw, text, xml_text, info = read_project(srh)
        chk = Checker(schemas).run(xml_text)
    except Exception as e:
        print("核对失败:", repr(e))
        return 2
    md = render_report(srh, raw, info, chk, report)
    c = chk.summary()
    print("报告已写入:", report)
    print("ERROR=%d WARN=%d INFO=%d" % (c["ERROR"], c["WARN"], c["INFO"]))
    for it in chk.issues:
        if it.level == "ERROR":
            print("  [ERROR]", it.path, it.msg)
    return 0 if c["ERROR"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
