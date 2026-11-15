# -*- coding: utf-8 -*-
"""生成 WER_函数库/工具/规格/block_schemas.json（机器可读积木规格）。
数据来源（全部只读）：
  _分析临时/blockly_utf8/blocks/myrobotrun.js, blocks/procedures.js, blocks/*.js (stock)
  _分析临时/blockly_utf8/generators/myrobotpythoncode.js, generators/python/*.js
  _分析临时/blockly_utf8/msg/js/zh-hans.js
  _分析临时/blockly_utf8/maingui.html (SKCON9 工具箱)
  _分析临时/PI|实验|Scratch-3/abilixProject.srh (真实项目样本)
用法: python build_schemas.py [priority|all]
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SPEC_DIR)))
SRC = os.path.join(ROOT, "_分析临时", "blockly_utf8")


def load(name):
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))


def read_bytes(rel):
    return open(os.path.join(SRC, rel), "rb").read().decode("utf-8", "replace")


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def match_delim(text, start, open_ch="{", close_ch="}"):
    i, n, depth = start, len(text), 0
    while i < n:
        c = text[i]
        if c in "\"'`":
            q = c
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == "/" and i + 1 < n:
            k = i - 1
            while k >= 0 and text[k] in " \t\r\n":
                k -= 1
            if k < 0 or text[k] in "=(,:[!&|?{};+-*%<>~^":
                i += 1
                in_cls = False
                while i < n:
                    ch = text[i]
                    if ch == "\\":
                        i += 2
                        continue
                    if ch == "[":
                        in_cls = True
                    elif ch == "]":
                        in_cls = False
                    elif ch == "/" and not in_cls:
                        i += 1
                        break
                    i += 1
                continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def comment_spans(text):
    spans = [(m.start(), m.end()) for m in re.finditer(r"/\*.*?\*/", text, re.S)]
    spans += [(m.start(), m.end()) for m in re.finditer(r"//[^\n]*", text)]
    return spans


def _in_span(pos, spans):
    return any(a <= pos < b for a, b in spans)


LOC = {}


def _locations():
    """精确行号：{('BLOCK'|'GEN', type): {'file','start_line','end_line'}}"""
    if LOC:
        return LOC
    block_files = ["blocks/myrobotrun.js", "blocks/procedures.js"]
    gen_files = ["generators/myrobotpythoncode.js", "generators/python/procedures.js",
                 "generators/python/logic.js", "generators/python/math.js",
                 "generators/python/variables.js", "generators/python/text.js"]
    for rel in block_files:
        t = read_bytes(rel)
        spans = comment_spans(t)
        for m in re.finditer(r"Blockly\.Blocks\['([^']+)'\]\s*=\s*\{", t):
            if _in_span(m.start(), spans):
                continue
            e = match_delim(t, t.find("{", m.end() - 1))
            LOC.setdefault(("BLOCK", m.group(1)), {"file": rel, "start_line": line_of(t, m.start()),
                                                   "end_line": line_of(t, e)})
    for rel in gen_files:
        t = read_bytes(rel)
        spans = comment_spans(t)
        for m in re.finditer(r"Blockly\.Python\['([^']+)'\]\s*=\s*function[^{]*\{", t):
            if _in_span(m.start(), spans):
                continue
            e = match_delim(t, t.find("{", m.end() - 1))
            LOC.setdefault(("GEN", m.group(1)), {"file": rel, "start_line": line_of(t, m.start()),
                                                 "end_line": line_of(t, e)})
    return LOC


def loc(kind, typ):
    return _locations().get((kind, typ))


MSGS = load("msgs_zh.json")
STOCK = load("stock_blocks.json")
GENSRC = load("gens_clean.json")
REAL = load("real_samples.json")
TOOLBOX = load("toolboxes.json")

# ---------------------------------------------------------------- 基础工具
MSG_RE = re.compile(r"Blockly\.Msg(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[\"([A-Za-z_][A-Za-z0-9_]*)\"\]|\['([A-Za-z_][A-Za-z0-9_]*)'\])")


def msg_of(expr):
    """把 JS 表达式里的 Blockly.Msg 引用替换成 Python 字符串字面量。"""
    def rep(m):
        key = m.group(1) or m.group(2) or m.group(3)
        return json.dumps(MSGS.get(key, "<MISSING:" + key + ">"), ensure_ascii=False)
    return MSG_RE.sub(rep, expr)


def xml_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def resolve_str(expr, env=None):
    """解析 label 表达式（字符串/消息拼接）→ 文本。解析失败返回原始表达式。"""
    e = msg_of(expr).strip()
    if env:
        for k, v in env.items():
            e = re.sub(r"\b" + re.escape(k) + r"\b", v, e)
    try:
        v = eval(e, {"__builtins__": {}}, {})  # 只用于本仓库源码里受控的字符串/数组字面量
        if isinstance(v, str):
            return v
    except Exception:
        pass
    return expr.strip()


def resolve_options(expr, env=None):
    """解析下拉选项表达式 → [[label, value], ...] 或 None。"""
    e = msg_of(expr).strip()
    if env:
        for k, v in env.items():
            e = re.sub(r"\b" + re.escape(k) + r"\b", v[e], e) if False else re.sub(r"\b" + re.escape(k) + r"\b", v, e)
    try:
        v = eval(e, {"__builtins__": {}}, {})
        if isinstance(v, list) and v and isinstance(v[0], list):
            return [[str(x[0]), str(x[1])] for x in v]
    except Exception:
        pass
    return None


# ---------------- 已知动态下拉列表（来自 blocks/myrobotrun.js 头部，行 28-96）
HELPER_OPTIONS = {
    "GetPortAToDList()": [["端口A", "1"], ["端口B", "2"], ["端口C", "3"], ["端口D", "4"]],
    "GetPort1To12List()": [["端口%d" % i, str(i)] for i in range(1, 13)],
    "GetIntelligentMotorIDList(true)": [["ID%d" % i, str(i)] for i in range(1, 12)] + [["所有智能电机", "254"]],
    "GetIntelligentMotorIDList(false)": [["ID%d" % i, str(i)] for i in range(1, 12)],
    "GetTimerList()": [["计时器%d" % i, str(i)] for i in range(1, 13)],
    "KeyList": [["Enter键", "1"], ["Left键", "2"], ["Right键", "3"]],
    "GetEmojiNameList()": [["胆小", "danxiao"], ["高兴", "gaoxing"], ["加油", "jiayou"],
                           ["可爱", "keai"], ["哭泣", "kuqi"], ["委屈", "weiqu"], ["眨眼", "zhayanjing"]],
    "ComparativeSymbolList": [["<", "1"], ["<=", "2"], ["==", "3"], ["!=", "4"], [">", "5"], [">=", "6"]],
}


def parse_playlist():
    """从 blocks/PlayList.js 解析 play_sound 的 musicname 选项。"""
    global ROOT
    p = os.path.join(SRC, "blocks", "PlayList.js")
    txt = open(p, "rb").read().decode("utf-8", "replace")
    m = re.search(r"var PlayList\s*=\s*\[([\s\S]*?)\];", txt)
    out = []
    if m:
        for line in m.group(1).split("\n"):
            lm = re.search(r"\[\s*(.*?)\s*,\s*\"([^\"]+)\"\s*\]", line)
            if lm:
                out.append([resolve_str(lm.group(1)), lm.group(2)])
    return out


HELPER_OPTIONS["PlayList"] = parse_playlist()

STOCK_LABEL_OVERRIDES = {
    "variables_get": "变量",
    "variables_set": "赋值",
}


# ---------------------------------------------------------------- 解析 classic block def
def split_top_args(s):
    """把函数调用参数串按顶层逗号拆分。"""
    args, depth, buf, q = [], 0, "", None
    i = 0
    while i < len(s):
        c = s[i]
        if q:
            buf += c
            if c == "\\":
                buf += s[i + 1]
                i += 2
                continue
            if c == q:
                q = None
        else:
            if c in "\"'`":
                q = c
                buf += c
            elif c in "([{":
                depth += 1
                buf += c
            elif c in ")]}":
                depth -= 1
                buf += c
            elif c == "," and depth == 0:
                args.append(buf.strip())
                buf = ""
            else:
                buf += c
        i += 1
    if buf.strip():
        args.append(buf.strip())
    return args


def find_call_args(src, start):
    """start 指向 '('，返回括号内文本与右括号后一位置。"""
    depth, i = 0, start
    q = None
    while i < len(src):
        c = src[i]
        if q:
            if c == "\\":
                i += 2
                continue
            if c == q:
                q = None
        elif c in "\"'`":
            q = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return src[start + 1:i], i + 1
        i += 1
    return "", len(src)


INPUT_OPEN_RE = re.compile(r"this\.append(Dummy|Value|Statement)Input\(\s*(?:'([^']*)'|\"([^\"]*)\")?\s*\)")
APPEND_FIELD_RE = re.compile(r"\.appendField\(")
SET_CHECK_RE = re.compile(r"\.setCheck\(\s*(null|\"[^\"]*\"|'[^']*')\s*\)")


def strip_comments(s):
    """去掉 JS 注释（保留换行以维持偏移），避免把被注释掉的 appendField 也解析进来。"""
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in "\"'`":
            q = c
            out.append(c)
            i += 1
            while i < n:
                out.append(s[i])
                if s[i] == "\\":
                    if i + 1 < n:
                        out.append(s[i + 1])
                        i += 2
                        continue
                elif s[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            j = s.find("\n", i)
            if j < 0:
                break
            out.append("\n")
            i = j + 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            j = s.find("*/", i + 2)
            if j < 0:
                break
            out.append("\n" * s.count("\n", i, j))
            i = j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def local_vars(src):
    """收集 var X = <expr>; 声明（用于解析 dropdown 变量）。"""
    env = {}
    for m in re.finditer(r"\bvar\s+([A-Za-z_]\w*)\s*=\s*", src):
        i = m.end()
        # 从 = 之后扫描到顶层 ';'（跳过字符串/括号）
        depth, j, q = 0, i, None
        while j < len(src):
            c = src[j]
            if q:
                if c == "\\":
                    j += 2
                    continue
                if c == q:
                    q = None
            elif c in "\"'`":
                q = c
            elif c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            elif c == ";" and depth == 0:
                break
            j += 1
        env[m.group(1)] = src[i:j].strip()
    return env


def parse_field_expr(expr, env):
    """解析 appendField 的第一个参数 → dict。"""
    expr = expr.strip()
    if expr in env:
        return parse_field_expr(env[expr], env)
    m = re.match(r"new\s+Blockly\.Field(?P<cls>\w+)\((.*)\)\s*$", expr, re.S)
    if m:
        cls, argstr = m.group("cls"), m.group(2)
        args = split_top_args(argstr)
        if cls == "Image":
            return {"kind": "image", "src": resolve_str(args[0]) if args else ""}
        if cls == "TextInput":
            return {"kind": "field_text_input", "default": resolve_str(args[0]) if args else ""}
        if cls == "Number":
            nums = [a for a in args if re.match(r"^[-\d.]+$", a.strip())]
            return {"kind": "field_number",
                    "default": nums[0].strip() if nums else "0",
                    **({"min": nums[1]} if len(nums) > 1 else {}),
                    **({"max": nums[2]} if len(nums) > 2 else {})}
        if cls == "Checkbox":
            val = args[0].strip() if args else "false"
            return {"kind": "field_checkbox", "default": "TRUE" if val in ("true", "1") else "FALSE"}
        if cls == "Dropdown":
            opts = None
            if args:
                a0 = args[0].strip()
                if a0 in HELPER_OPTIONS:
                    opts = HELPER_OPTIONS[a0]
                else:
                    if a0 in env:
                        a0 = env[a0]
                    opts = resolve_options(a0)
            return {"kind": "field_dropdown", "options": opts}
        if cls == "Colour":
            return {"kind": "field_colour", "default": resolve_str(args[0]) if args else "#ff0000"}
        if cls == "Variable":
            return {"kind": "field_variable"}
        return {"kind": "field_" + cls.lower(), "raw": argstr[:120]}
    txt = resolve_str(expr, env)
    return {"kind": "label", "text": txt}


def parse_classic_block(src):
    """解析 myrobotrun.js 风格 block def → [(input_open, [appendField items])], conn。"""
    env = local_vars(src)
    opens = []
    for m in INPUT_OPEN_RE.finditer(src):
        kind = {"Dummy": "dummy", "Value": "value", "Statement": "statement"}[m.group(1)]
        name = m.group(2) if m.group(2) is not None else m.group(3)
        opens.append({"pos": m.start(), "end": m.end(), "kind": kind, "name": name})
    checks = [{"pos": m.start(), "val": m.group(1)} for m in SET_CHECK_RE.finditer(src)]
    groups = []
    for idx, op in enumerate(opens):
        stop = opens[idx + 1]["pos"] if idx + 1 < len(opens) else len(src)
        check = None
        for c in checks:
            if op["end"] <= c["pos"] < stop:
                check = None if c["val"] == "null" else resolve_str(c["val"])
                break
        items = []
        for f in APPEND_FIELD_RE.finditer(src, op["end"], stop):
            argstr, _ = find_call_args(src, f.end() - 1)
            args = split_top_args(argstr)
            if not args:
                continue
            item = parse_field_expr(args[0], env)
            if len(args) >= 2 and re.match(r"^[\"'][^\"']*[\"']$", args[1].strip()):
                item["field"] = args[1].strip()[1:-1]
            items.append(item)
        groups.append({"kind": op["kind"], "name": op["name"], "check": check, "items": items})
    conn = {
        "previous": bool(re.search(r"setPreviousStatement\(\s*true", src)),
        "next": bool(re.search(r"setNextStatement\(\s*true", src)),
        "output": None,
    }
    m = re.search(r"setOutput\(\s*true\s*(?:,\s*([^)]*))?\)", src)
    if m:
        conn["output"] = resolve_str(m.group(1)) if m.group(1) else None
    return groups, conn


def finalize_segments(groups):
    """把输入组整理为 append_fields + fields + inputs。"""
    append_fields, fields, inputs = [], {}, {"value": {}, "statement": {}}
    for g in groups:
        kind, name = g["kind"], g["name"]
        if kind in ("value", "statement"):
            prefix = []
            for it in g["items"]:
                if it["kind"] == "image":
                    prefix.append({"kind": "image", "src": it["src"]})
                elif it["kind"] == "label":
                    prefix.append({"kind": "label", "text": it["text"]})
                elif it.get("field"):
                    entry = {"kind": it["kind"], "field": it["field"]}
                    if it.get("options"):
                        entry["options"] = it["options"]
                    if "default" in it:
                        entry["default"] = it["default"]
                    prefix.append(dict(entry))
                    fields[it["field"]] = dict(entry)
            item = {"kind": "input_" + kind, "name": name}
            if kind == "value":
                item["check"] = g["check"]
                inputs["value"][name] = {"check": g["check"]}
            else:
                inputs["statement"][name] = {}
            if prefix:
                item["prefix"] = prefix
            append_fields.append(item)
            continue
        # dummy input：逐项
        for it in g["items"]:
            if it["kind"] == "image":
                append_fields.append({"kind": "image", "src": it["src"]})
            elif it["kind"] == "label":
                append_fields.append({"kind": "label", "text": it["text"]})
            elif it.get("field"):
                entry = {"kind": it["kind"], "field": it["field"]}
                if it.get("options"):
                    entry["options"] = it["options"]
                if "default" in it:
                    entry["default"] = it["default"]
                append_fields.append(entry)
                fields[it["field"]] = dict(entry)
            else:
                append_fields.append({"kind": "anonymous_" + it["kind"], "raw": it.get("raw", "")})
    return append_fields, fields, inputs


def clean_stock_json(src):
    src = re.sub(r"^\s*//[^\n]*$", "", src, flags=re.M)
    src = re.sub(r",(\s*[}\]])", r"\1", src)
    try:
        d = json.loads(src)
    except Exception:
        return None
    return d


def stock_append(d):
    """由 stock JSON 定义（message0/args0）构造 append_fields。"""
    m0 = d.get("message0", "")
    # 先把 %{BKY_xxx} 消息引用换成中文，再按 %1/%2 切分
    m0 = re.sub(r"%\{BKY_([A-Za-z0-9_]+)\}", lambda m: MSGS.get(m.group(1), m.group(0)), m0)
    args = d.get("args0", []) or []
    segments, fields, inputs = [], {}, {"value": {}, "statement": {}}
    tokens = re.split(r"%(\d+)", m0)
    ai = 0
    for i, tok in enumerate(tokens):
        if i % 2 == 0:
            if tok.strip():
                segments.append({"kind": "label", "text": tok})
            continue
        if ai >= len(args):
            continue
        a = args[ai]
        ai += 1
        t = a.get("type")
        if t == "input_value":
            nm = a.get("name")
            segments.append({"kind": "input_value", "name": nm, "check": a.get("check")})
            inputs["value"][nm] = {"check": a.get("check")}
        elif t == "input_statement":
            nm = a.get("name")
            segments.append({"kind": "input_statement", "name": nm})
            inputs["statement"][nm] = {}
        elif t == "field_dropdown":
            nm = a.get("name")
            opts = []
            for label, value in a.get("options", []):
                label = re.sub(r"%\{BKY_([A-Za-z0-9_]+)\}",
                               lambda m: MSGS.get(m.group(1), m.group(0)), label)
                opts.append([label, value])
            segments.append({"kind": "field_dropdown", "field": nm, "options": opts})
            fields[nm] = {"kind": "field_dropdown", "field": nm, "options": opts}
        elif t == "field_number":
            nm = a.get("name")
            v = str(a.get("value", 0))
            segments.append({"kind": "field_number", "field": nm, "default": v})
            fields[nm] = {"kind": "field_number", "field": nm, "default": v}
        elif t == "field_variable":
            nm = a.get("name")
            segments.append({"kind": "field_variable", "field": nm})
            fields[nm] = {"kind": "field_variable", "field": nm}
        elif t == "field_checkbox":
            nm = a.get("name")
            v = "TRUE" if a.get("checked") else "FALSE"
            segments.append({"kind": "field_checkbox", "field": nm, "default": v})
            fields[nm] = {"kind": "field_checkbox", "field": nm, "default": v}
        elif t == "field_textinput":
            nm = a.get("name")
            v = a.get("text", "")
            segments.append({"kind": "field_text_input", "field": nm, "default": v})
            fields[nm] = {"kind": "field_text_input", "field": nm, "default": v}
    # 连接属性（stock JSON 里 previousStatement:null 也表示“有连接”）
    conn = {"previous": "previousStatement" in d,
            "next": "nextStatement" in d,
            "output": d.get("output") if "output" in d else None,
            "has_output": "output" in d}
    return segments, fields, inputs, conn


# ---------------------------------------------------------------- Python 模板（人工整理，逐条对照生成器源码）
PY = {
    "start": ("def main():\n"
              "    global <工作区所有用到的变量名, 逗号分隔>   # 仅当有变量时\n"
              "    <语句输入 code 的代码>\n"
              "    pass                # 仅当 code 为空或全部是注释时",
              "整个文件入口；def main 由 start 生成，函数定义由 procedures_* 生成。global 行列出【整个工作区】allUsedVarModels，不只是函数体内变量。"),
    "annotation": ("#<text>\n", "text 原样拼在 # 后面，不加空格；语句输入 code 即使有内容也被忽略。"),
    "block_mod": ("#<NAME>\nif True:\n<语句输入 code>", "本质是带标题的 if True 折叠块；body 为空时补 '    pass\\n'。"),
    "motor": ("robot.set_motor(<Number(channel)>, robot.clamp(<speed 表达式>, -100, 100))\n",
              "channel 出 XML 前已由 Number() 转 int；speed 无论写什么都会再包一层 robot.clamp。"),
    "motor_time": ("robot.set_motor_time(<Number(channel)>, robot.clamp(<speed>, -100, 100), robot.clamp(<time>, 0, 3600))\n", ""),
    "motor_angle": ("robot.set_motor_encoder(<Number(channel)>, robot.clamp(<speed>, -100, 100), robot.clamp(<angle>, -99999, 99999))\n", ""),
    "dual_motor_duration": ("robot.set_double_motor_time(<Number(port_1)>, robot.clamp(<speed_1>, -100, 100), <Number(port_2)>, robot.clamp(<speed_2>, -100, 100), robot.clamp(<time>, 0, 3600))\n", ""),
    "dual_motor_angle": ("robot.set_double_motor_encoder(<Number(port_1)>, robot.clamp(<speed_1>, -100, 100), <Number(port_2)>, robot.clamp(<speed_2>, -100, 100), <Number(port_3)>, robot.clamp(<angle>, -99999, 99999))\n", "port_3 会被 UI 的 onChange 限制为 port_1/port_2 之一。"),
    "servoa_angle": ("robot.set_servo(<channel>, robot.clamp(<speed>, 0, 100), robot.clamp(<angle>, -90, 90))\n", "channel 是字符串直接拼入（不转 Number）。"),
    "resetencoder": ("robot.reset_encoder(<port>);\n", "注意生成器里带一个分号：';\\n'（Python 里合法但多余）。"),
    "getencoder": ("robot.get_encoder(<port>)", "输出表达式"),
    "get_encoder_real_time_value": ("SKCON9/其它: robot.get_instant_incoder(<port>)\nSKCON2:      robot.get_instant_encoder(<port>)",
                                    "注意 SKCON9 分支的 'incoder' 是固件拼写，必须照抄。输出表达式。"),
    "getai_glay": ("robot.get_gray(<channel>)", "输出表达式"),
    "getai_touch": ("robot.get_touch(<channel>)", "输出表达式"),
    "getai_sonic": ("robot.get_ultra_sonic(<channel>)", "输出表达式"),
    "get_sonic_detect_object": ("(robot.get_ultra_sonic(<port>) > 50 and robot.get_ultra_sonic(<port>) < 200)",
                                 "输出 Boolean；固定 50~200 区间，没有可调阈值。"),
    "eeprom_read": ("robot.get_ee(<address>)", "输出表达式"),
    "eeprom_write": ("robot.set_ee(<address>, robot.clamp(<data>, -99999, 99999))\n", ""),
    "wait": ("SKCON9/其它: time.sleep(<time>)\nSKCON2:      robot.sleep(<time>)",
             "生成器分 maingui.robotType 判断；本机 SKCON9 走 time.sleep。"),
    "if": ("if <logic_val>:\n<语句输入 code>", "body 为空时补 '    pass\\n'。"),
    "ifelse": ("if <logic_val>:\n<语句输入 code>else:\n<语句输入 else_code>", "两个 body 为空时各自补 '    pass\\n'。"),
    "while_cmp": ("while not <bool>:\n<语句输入 code>", "注意是 while not：bool 为假时继续循环。"),
    "while_forver": ("while True:\n<语句输入 NAME>", "语句输入名是 NAME（不是 code）。"),
    "while_number": ("for <自动生成的 loopVar> in range(<TIMES>):\n<语句输入 code>",
                     "TIMES 是值输入（不是字段！）。若 TIMES 是数字字面量则直接用；否则包 int(...)。loopVar 由 getDistinctName('count') 生成 → count/count2/count3…。"),
    "wait_until": ("while not <bool>:\n    pass\n", "固定只生成 pass 死等（没有 body）。"),
    "while_break": ("break\n", ""),
    "variables_get": ("<变量安全名>", "表达式；名字经 Blockly.Names.safeName_（ASCII 名原样保留，中文会被转成 _E5_... 之类）。"),
    "variables_set": ("<变量安全名> = <VALUE 或 '0'>\n", ""),
    "math_number": ("<数字字面量>", "parseFloat；13 → 13，-5.5 → -5.5；Infinity 特殊处理。"),
    "math_op": ("+ - * / %: (<A> <operator> <B>)\n^:        robot.pow(<A>, <B>)",
                "operator 直接取字段值（+ - * / % ^），^ 特判为 robot.pow。"),
    "math_compare": ("<A> <comparison_operator> <B>",
                     "comparison_operator 字段【值】是 ==/!=/</<=/>/>=（界面上显示 =/≠/</≤/>/≥）。XML 里必须写 == 等，写 '=' 会被当成不存在的选项而静默回退到第一项。"),
    "logic_compare": ("<A> <op> <B>   # op: EQ→==, NEQ→!=, LT→<, LTE→<=, GT→>, GTE→>=",
                      "字段 OP 的值是 EQ/NEQ/LT/LTE/GT/GTE（不是符号本身）。"),
    "logic_operation": ("<A> and <B>  |  <A> or <B>", "字段 OP = AND/OR。缺输入时补 True/False。"),
    "logic_boolean": ("True  (BOOL=TRUE)\nFalse (BOOL=FALSE)", "表达式。"),
    "logic_negate": ("not <BOOL>", "表达式。"),
    "math_modulo": ("<DIVIDEND> % <DIVISOR>", "表达式。"),
    "math_change": ("from numbers import Number\n<var> = (<var> if isinstance(<var>, Number) else 0) + <DELTA>\n",
                    "会在 definitions_ 里追加 import 'from numbers import Number'（出现即置顶）。"),
    "robot_math_rounding": ("round: robot.round(<param>)\nceil:  robot.ceil(<param>)\nfloor: robot.floor(<param>)", "表达式。"),
    "robot_math_unary_operation": ("sqrt:  robot.sqrt(<operand>)\nfabs:  robot.abs(<operand>)\nnegative: -(<operand>)\nln:    robot.ln(<operand>)\nlog10: robot.log10(<operand>)\ne^:    robot.exp(<operand>)\n10^:   robot.pow(10, <operand>)", "表达式。"),
    "robot_math_constants": ("sqrt(2)    → robot.sqrt(2)\nsqrt(1/2)  → robot.sqrt(1 / 2)",
                             "当前下拉只有 sqrt(2)/sqrt(1/2)；源码另有 pi→robot.pi()、e→robot.e() 分支，但选项被注释掉了（XML 里写 pi/e 无效）。"),
    "robot_math_trigonometric_function": ("sin/cos/tan: robot.sin|cos|tan(<param> / 180.0 * robot.pi())\nasin/acos/atan: robot.asin|acos|atan(<param>) / robot.pi() * 180.0",
                                          "SKCON9 用 robot.pi()；SKCON2 用 robot.pi（无括号）。表达式。"),
    "robot_math_random": ("robot.random(<FROM>, <TO>)", "表达式。"),
    "abilix_math_number_property": ("EVEN: <N> % 2 == 0\nODD: <N> % 2 == 1\nPRIME: robot.isprime(<N>)\nWHOLE: <N> % 1 == 0\nPOSITIVE: <N> > 0\nNEGATIVE: <N> < 0\nDIVISIBLE_BY: <N> % <DIVISOR> == 0",
                                     "DIVISIBLE_BY 时需要 mutation divisor_input=true 才会出现 DIVISOR 值输入。"),
    "printf_text": ("robot.print('<text 中的单引号转义为 \\'>\\n')\n", "注意生成的是字符串里带 \\n 的换行。"),
    "printf_number": ("robot.print('<dataname> ' + str(<data>) + '\\n')\n", "dataname 后面固定带一个空格。"),
    "printf_lines": ("robot.clear()\nif True:\n<语句输入 code>\n", "多行显示 = 先 clear 再显示。"),
    "printf": ("robot.print(<para1>, '\\n')\n", "值输入 para1 直接作为 print 第一个参数。"),
    "printf_emoji": ("robot.print_expression('<emoji_name>')\n", "emoji_name 取值为 danxiao/gaoxing/jiayou/keai/kuqi/weiqu/zhayanjing。"),
    "play_sound": ("robot.play('<musicname>')\n", "musicname 是 PlayList 的值（如 luyin_p2、dongwu_p0.mp3）。"),
    "play_sound_until": ("robot.play_until('<musicname>')\n", ""),
    "record": ("robot.record_audio(<record_ID>, <record_time>)\n", ""),
    "set_do": ("robot.set_do(<PORT>, <STATE>)\n", "STATE: 0=OFF, 1=ON。"),
    "set_electric_magnet": ("robot.set_do(<channel>, <status>)\n", "电磁铁复用 robot.set_do；status: 1=吸合, 0=断开。"),
    "getmseconds": ("robot.get_timer_ms(<timer_ID>)", "表达式。"),
    "getmsecondsreset": ("robot.reset_timer(<timer_ID>)\n", ""),
    "get_key": ("robot.check_key(<port>)", "表达式；port: 1=Enter, 2=Left, 3=Right。"),
    "block_conststring": ("'<NAME 中的单引号转义>'\n", "表达式（字符串常量）。"),
    "procedures_defnoreturn": (
        "def <NAME>(<参数名, 逗号分隔>):\n"
        "    global <工作区用到的变量名, 排除参数名>\n"
        "    <STACK 语句代码>\n"
        "    pass                          # 生成器总会在函数体末尾追加一个 pass\n",
        "生成到 Blockly.Python.definitions_['%'+name]，排在 main 之前。procedures_defnoreturn 与 procedures_defreturn 共用同一个生成器。"),
    "procedures_defreturn": (
        "def <NAME>(<参数名>):\n"
        "    global <工作区用到的变量名, 排除参数名>\n"
        "    <STACK 语句代码>\n"
        "    pass\n"
        "    return <RETURN 值输入>          # 仅当 RETURN 有连接时才生成\n",
        "函数声明与 defnoreturn 共用生成器；RETURN 是值输入。飞函数分类的“新建返回函数”入口被注释，但 XML 加载/生成完全支持。"),
    "procedures_callnoreturn": ("<NAME>(<ARG0>, <ARG1>, ...)\n", "缺参数的输入位置生成 None。调用块字段 NAME 由 <mutation name> 恢复，不需要 <field name=\"NAME\">。"),
    "procedures_callreturn": ("<NAME>(<ARG0>, ...)", "有返回值版调用：表达式，order = ORDER_FUNCTION_CALL。"),
}

# 特殊块的附加说明/证据级别
EVIDENCE = {}
NOTES = {}


def real_shallow(typ):
    """取真实样本中该块的本体 XML（清理命名空间/坐标/禁用态），优先 PI → 实验 → Scratch-3。"""
    for proj in ("PI", "实验", "Scratch-3"):
        pr = REAL.get(proj) or {}
        b = pr.get("blocks", {}).get(typ)
        if b:
            s = b["shallow_xml"]
            s = re.sub(r'\sxmlns:html="[^"]*"', "", s)
            s = s.replace("html:", "")
            # 只清理根 <block ...> 起始标签上的坐标/ID/disabled；field 的 id 必须保留
            m = re.match(r"<block\b[^>]*>", s)
            if m:
                head = m.group(0)
                head2 = re.sub(r'\s(?:x|y|id|disabled)="[^"]*"', "", head)
                s = head2 + s[len(head):]
            return proj, s
    return None, None


def _clean_attrs(s):
    s = re.sub(r'\s(?:x|y|id)="[^"]*"', "", s)
    return s


def xml_min_for(typ, fields, inputs, conn, extra_attrs=""):
    parts = ['<block type="%s"%s>' % (typ, extra_attrs)]
    for name, f in fields.items():
        if f["kind"] == "field_dropdown" and f.get("options"):
            val = f["options"][0][1]
            parts.append('  <field name="%s">%s</field>' % (name, xml_escape(val)))
        elif f["kind"] == "field_text_input":
            parts.append('  <field name="%s">%s</field>' % (name, xml_escape(f.get("default", ""))))
        elif f["kind"] == "field_number":
            parts.append('  <field name="%s">%s</field>' % (name, xml_escape(f.get("default", "0"))))
        elif f["kind"] == "field_checkbox":
            parts.append('  <field name="%s">%s</field>' % (name, f.get("default", "FALSE")))
        elif f["kind"] == "field_colour":
            parts.append('  <field name="%s">%s</field>' % (name, f.get("default", "#ff0000")))
        elif f["kind"] == "field_variable":
            parts.append('  <field name="%s" id="var_id_1" variabletype="">var_name</field>' % name)
    for name, i in inputs["value"].items():
        chk = i.get("check")
        if chk == "Boolean":
            parts.append('  <value name="%s"><shadow type="logic_boolean"><field name="BOOL">TRUE</field></shadow></value>' % name)
        else:
            parts.append('  <value name="%s"><shadow type="math_number"><field name="NUM">0</field></shadow></value>' % name)
    parts.append("</block>")
    return "\n".join(parts)


# ---------------------------------------------------------------- 目标清单
PRIORITY = """start annotation block_mod motor motor_time motor_angle dual_motor_duration
dual_motor_angle resetencoder getencoder getai_glay getai_touch eeprom_read wait
if ifelse while_cmp while_forver while_number while_break
variables_get variables_set math_number math_op math_compare logic_compare logic_operation
logic_boolean robot_math_rounding robot_math_unary_operation
printf_text printf_number play_sound procedures_defnoreturn procedures_callnoreturn""".split()

EXTRA = """servoa_angle set_do set_electric_magnet printf_lines wait_until logic_negate math_modulo
robot_math_constants get_encoder_real_time_value getai_sonic get_sonic_detect_object
getmseconds getmsecondsreset eeprom_write get_key math_change procedures_defreturn
block_conststring printf printf_emoji play_sound_until record robot_math_trigonometric_function
robot_math_random abilix_math_number_property""".split()

# 工具箱分类（一个块可能出现在多个分类；如在注释里的分类（例：事件→start）不算）
def toolbox_index():
    idx = {}
    src = TOOLBOX["toolbox_skcon9"]["source"]
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    for m in re.finditer(r'<category name="([^"]+)"[^>]*>(.*?)</category>', src, re.S):
        cat = m.group(1)
        catmsg = re.search(r"%\{BKY_([A-Za-z0-9_]+)\}", cat)
        name = MSGS.get(catmsg.group(1), cat) if catmsg else cat
        for bm in re.finditer(r'<block\s+type\s*=\s*["\']([^"\']+)["\']', m.group(2)):
            idx.setdefault(bm.group(1), [])
            if name not in idx[bm.group(1)]:
                idx[bm.group(1)].append(name)
    return idx


TB_IDX = toolbox_index()

# 不在 SKCON9 工具箱但属于动态/默认代码的块：手工标分类
CATEGORY_FALLBACK = {
    "start": ["主函数（不在工具箱，由新建项目默认模板/工程 XML 提供）"],
    "procedures_defnoreturn": ["函数（动态分类 custom=\"PROCEDURE\"，含“新建函数”模板）"],
    "procedures_callnoreturn": ["函数（动态分类 custom=\"PROCEDURE\"，每个已有函数生成一个调用块）"],
    "procedures_defreturn": ["函数（仅当工程 XML 已有 defreturn 时，其调用块出现在动态分类里）"],
    "variables_get": ["变量（动态分类 custom=\"VARIABLE\"）"],
    "variables_set": ["变量（动态分类 custom=\"VARIABLE\"）"],
    "math_change": ["变量（动态分类 custom=\"VARIABLE\"）"],
}

EVIDENCE_BONUS = {
    # 运行期行为未实测、或只由源码推断的点
    "procedures_defnoreturn": "A+（参数化 mutation 已由 harness headless 实测通过：工具/验证/证据/参数化函数/）",
    "procedures_defreturn": "A（块定义存在且生成器可用；工具箱不提供新建，仅 XML 载入；调用块是否在飞函数分类出现待实测）",
    "while_number": "A+（TIMES 为值输入由块定义+工具箱+生成器三方确认）",
    "math_compare": "A+（下拉 value 语义由块定义+真实样本+生成器三方确认）",
}

# 真实样本/工具链里缺失、但按源码可标出的补充分类说明
CATEGORY_FALLBACK["get_key"] = ["（不在 SKCON9 工具箱；blocks/ 中定义存在，应属 SKCON2/5 或旧版遗留，函数库不要用）"]
CATEGORY_FALLBACK["robot_math_trigonometric_function"] = ["运算"]


def block_entry(typ):
    ent = {"type": typ}
    custom = load("blocks_clean.json")
    if typ in ("procedures_defnoreturn", "procedures_callnoreturn", "procedures_defreturn"):
        return procedures_entry(typ)
    loc_b = loc("BLOCK", typ)
    loc_g = loc("GEN", typ)
    if typ in custom:
        src = strip_comments(custom[typ]["source"])
        segs, conn = parse_classic_block(src)
        append_fields, fields, inputs = finalize_segments(segs)
        ent["block_def"] = dict(loc_b) if loc_b else {
            "file": custom[typ]["file"], "start_line": custom[typ]["start_line"],
            "end_line": custom[typ]["end_line"]}
        ev = "A+"
    elif typ in STOCK:
        d = clean_stock_json(STOCK[typ]["source"])
        if not d:
            raise RuntimeError("stock parse fail: " + typ)
        segs, fields, inputs, conn = stock_append(d)
        append_fields = segs
        ent["block_def"] = {"file": STOCK[typ]["file"],
                            "start_line": STOCK[typ]["start_line"],
                            "end_line": STOCK[typ]["end_line"]}
        ev = "A"
    else:
        raise RuntimeError("unknown block: " + typ)
    # 代码里用 jsonInit 定义的个例（经典解析器抓不到）
    if typ == "robot_math_random":
        append_fields = [{"kind": "label", "text": "从"},
                         {"kind": "input_value", "name": "FROM", "check": "Number"},
                         {"kind": "label", "text": " 到 "},
                         {"kind": "input_value", "name": "TO", "check": "Number"},
                         {"kind": "label", "text": " 范围内的随机整数"}]
        fields = {}
        inputs = {"value": {"FROM": {"check": "Number"}, "TO": {"check": "Number"}}, "statement": {}}
    cat = TB_IDX.get(typ) or CATEGORY_FALLBACK.get(typ)
    ent["category_skcon9"] = cat  # null = 不在 SKCON9 工具箱
    ent["append_fields"] = append_fields
    ent["fields"] = fields
    ent["inputs"] = inputs
    ent["connection"] = conn
    if typ == "abilix_math_number_property":
        ent["mutation"] = {
            "xml": '<mutation divisor_input="true"></mutation>',
            "rules": ["仅当 PROPERTY=DIVISIBLE_BY 时需要；为 true 时块上才出现 DIVISOR 值输入，否则没有该输入",
                      "domToMutation 读属性 divisor_input=='true'；保存时 mutationToDom 会写该属性"],
        }
    if loc_g:
        ent["generator"] = dict(loc_g)
    if typ in PY:
        tmpl, note = PY[typ]
        ent["python"] = tmpl
        if note:
            ent["python_notes"] = note
    proj, rx = real_shallow(typ)
    if rx:
        ent["xml_real"] = {"project": proj, "xml": rx}
        ev = "A+" if ev == "A" else ev
    # xml_min
    if typ == "start":
        ent["xml_min"] = ('<block type="start" deletable="false" x="0" y="0">\n'
                          '  <statement name="code"></statement>\n</block>')
    else:
        ent["xml_min"] = xml_min_for(typ, fields, inputs, conn)
    ent["evidence"] = EVIDENCE_BONUS.get(typ, ev)
    return ent


def procedures_entry(typ):
    ent = {"type": typ, "category_skcon9": TB_IDX.get(typ)}
    if typ == "procedures_defnoreturn":
        ent["block_def"] = {"file": "blocks/procedures.js", "start_line": 33, "end_line": 391}
        ent["append_fields"] = [
            {"kind": "label", "text": "函数"},
            {"kind": "field_text_input", "field": "NAME", "default": ""},
            {"kind": "field_label", "field": "PARAMS", "note": "由 mutation 的 arg 列表自动渲染，XML 中不要手写"},
            {"kind": "input_statement", "name": "STACK"},
        ]
        ent["fields"] = {"NAME": {"kind": "field_text_input", "rule": "必须 ASCII，界面改名会自动加 func_ 前缀并过滤非 \\w"}}
        ent["inputs"] = {"value": {}, "statement": {"STACK": {}}}
        ent["mutation"] = {
            "xml": '<mutation><arg name="cm" varid="PARAM_VAR_ID_OPTIONAL"></arg></mutation>',
            "rules": [
                "无参数可完全省略 <mutation>",
                "参数名必须 ASCII；界面被禁用改参数（setMutator 被注释，blocks/procedures.js:47 附近），但 XML 加载会走 domToMutation 恢复参数",
                "domToMutation 会为每个 arg 调 Blockly.Variables.getOrCreateVariablePackage(workspace, varid, name, '') 创建/复用变量，之后函数体内用 variables_get 引用参数名即可",
                "建议把参数变量也声明进 <variables>（如 <variable type=\"\" id=\"PARAM_VAR_ID\">cm</variable>），并让 mutation 的 varid 与之一致；不声明也能加载（会现场创建变量）",
                "保存时 def 的 mutation 不带 name 属性（name 在 <field name=\"NAME\">）；mutationToDom(true) 才带 name，仅用于内部 mutateCallers",
            ],
            "xml_param_example": (
                '<block type="procedures_defnoreturn" x="0" y="0">\n'
                '  <mutation><arg name="cm" varid="v_param_cm"></arg></mutation>\n'
                '  <field name="NAME">func_MoveForward</field>\n'
                '  <statement name="STACK">\n'
                '    <block type="motor">\n'
                '      <field name="channel">1</field>\n'
                '      <value name="speed"><block type="variables_get">'
                '<field name="VAR" id="v_param_cm" variabletype="">cm</field></block></value>\n'
                '    </block>\n'
                '  </statement>\n'
                '</block>'),
            "xml_noparam_example": '<block type="procedures_defnoreturn" x="0" y="0"><field name="NAME">func_Stop</field><statement name="STACK"></statement></block>',
        }
        ent["generator"] = {"file": "generators/python/procedures.js", "start_line": 32,
                            "end_line": 88, "alias_line": 92,
                            "symbol": "Blockly.Python['procedures_defreturn']（procedures_defnoreturn 在第 92-93 行直接别名到它）"}
        ent["python"] = PY[typ][0]
        ent["python_notes"] = PY[typ][1]
        ent["connection"] = {"previous": False, "next": False, "output": None}
        ent["xml_min"] = ent["mutation"]["xml_noparam_example"]
        ent["evidence"] = ("A+（参数化 mutation 已由 harness headless 实测通过：加载/flyout 调用块/ARG0/Python 生成/py_compile "
                          "16/16 PASS；证据 工具/验证/证据/参数化函数/20261110_131824_param_test.report.txt）")
        proj, rx = real_shallow(typ)
        if rx:
            ent["xml_real"] = {"project": proj, "xml": rx}
        return ent
    if typ == "procedures_defreturn":
        ent["block_def"] = {"file": "blocks/procedures.js", "start_line": 393, "end_line": 448}
        ent["append_fields"] = [
            {"kind": "label", "text": "函数（有返回值）"},
            {"kind": "field_text_input", "field": "NAME", "default": ""},
            {"kind": "field_label", "field": "PARAMS"},
            {"kind": "input_value", "name": "RETURN",
             "prefix": [{"kind": "label", "text": "返回"}]},
            {"kind": "input_statement", "name": "STACK"},
        ]
        ent["fields"] = {"NAME": {"kind": "field_text_input"}}
        ent["inputs"] = {"value": {"RETURN": {"check": None}}, "statement": {"STACK": {}}}
        ent["mutation"] = {'xml': '<mutation><arg name="cm"></arg></mutation>',
                           "rules": ["与 defnoreturn 共用的 domToMutation/mutationToDom（blocks/procedures.js:426-427）",
                                     "该块的参数 mutator 在 IDE 里是【可用】的（未注释 setMutator），但工具箱不再提供“新建返回函数”积木；只能通过 XML 载入",
                                     "core/procedures.js:114-127 的“新建”入口被注释；但 flyoutCategory 第 166 行仍会对已有 defreturn 生成 procedures_callreturn 调用块（在“函数”分类可见）"]}
        ent["generator"] = {"file": "generators/python/procedures.js", "start_line": 32, "end_line": 88,
                            "symbol": "Blockly.Python['procedures_defreturn']"}
        ent["python"] = PY[typ][0]
        ent["python_notes"] = PY[typ][1]
        ent["connection"] = {"previous": False, "next": False, "output": None}
        ent["xml_min"] = ('<block type="procedures_defreturn" x="0" y="0">\n'
                          '  <mutation><arg name="cm"></arg></mutation>\n'
                          '  <field name="NAME">func_Distance</field>\n'
                          '  <statement name="STACK"><block type="motor"><field name="channel">1</field>'
                          '<value name="speed"><block type="variables_get">'
                          '<field name="VAR" id="PARAM_VAR_ID" variabletype="">cm</field></block></value></block></statement>\n'
                          '  <value name="RETURN"><block type="getencoder"><field name="port">1</field></block></value>\n'
                          '</block>')
        ent["evidence"] = "A（块定义+生成器源码可证；工具箱不提供新建，仅 XML 载入；flyout 调用块渲染未单独实测 → B 级待验证）"
        return ent
    if typ == "procedures_callnoreturn":
        ent["block_def"] = {"file": "blocks/procedures.js", "start_line": 626, "end_line": 972}
        ent["append_fields"] = [
            {"kind": "field_label", "field": "NAME", "note": "init 时显示 this.id，domToMutation 用 mutation 的 name 调 renameProcedure 填真实函数名"},
            {"kind": "field_label", "field": "WITH", "note": "有参数时追加 '与：'；参数输入为 ARG0..ARGn，各带一个 FieldLabel"},
            {"kind": "input_value", "name": "ARG0", "note": "参数个数由 mutation 的 arg 数量决定"},
        ]
        ent["fields"] = {"NAME": {"kind": "field_label",
                                  "note": "不需要在 XML 写；由 <mutation name=...> 恢复"}}
        ent["inputs"] = {"value": {"ARG0": {"check": None},
                                   "ARG1": {"check": None},
                                   "ARGn": {"check": None}},
                         "statement": {}}
        ent["mutation"] = {
            "xml": '<mutation name="func_MoveForward"><arg name="cm"></arg></mutation>',
            "rules": [
                "无参数：<mutation name=\"func_x\"></mutation>（真实样本即这种形式）",
                "有参数：arg 顺序/名字必须与 def 的 mutation 完全一致；否则调用块的 onchange 会认为签名不符并自动新建同名 def 块（会重复定义）",
                "paramId 属性可省（真实样本没有）；domToMutation 对 null paramId 也能正确建出 ARG0.. 输入",
            ],
            "xml_noparam_example": '<block type="procedures_callnoreturn"><mutation name="func_Stop"></mutation></block>',
            "xml_param_example": ('<block type="procedures_callnoreturn"><mutation name="func_MoveForward">'
                                  '<arg name="cm"></arg></mutation>'
                                  '<value name="ARG0"><block type="math_number"><field name="NUM">30</field></block></value>'
                                  '</block>'),
        }
        ent["generator"] = {"file": "generators/python/procedures.js", "start_line": 108, "end_line": 119}
        ent["python"] = PY[typ][0]
        ent["python_notes"] = PY[typ][1]
        ent["connection"] = {"previous": True, "next": True, "output": None}
        ent["xml_min"] = '<block type="procedures_callnoreturn"><mutation name="func_Stop"></mutation></block>'
        ent["evidence"] = "A+"
        proj, rx = real_shallow(typ)
        if rx:
            ent["xml_real"] = {"project": proj, "xml": rx}
        return ent
    raise RuntimeError(typ)


META = {
    "name": "WER 函数库积木 XML 规格",
    "ide": "能力风暴 AbilixScratch3.0（SKCON9，Blockly 2018 前后版本 + PartnerX 自定义生成器）",
    "workspace": r"D:\UserData\Documents\WER\2026普级赛",
    "generated_by": "schema 队友（task-1）。重建命令：python WER_函数库/工具/规格/_work/build_schemas.py all；"
                    "再生成人读版：python WER_函数库/工具/规格/_work/gen_md.py；校验：python WER_函数库/工具/规格/check_library_xml.py",
    "regenerate": {
        "inputs": "_work/ 下的 msgs_zh.json / stock_blocks.json / gens_clean.json / real_samples.json / toolboxes.json / blocks_clean.json "
                  "均由 _分析临时/blockly_utf8 只读提取，行号由脚本直接从源码按 \\n 重新计算",
        "commands": [
            "python WER_函数库/工具/规格/_work/build_schemas.py all",
            "python WER_函数库/工具/规格/_work/gen_md.py",
            "python WER_函数库/工具/规格/check_library_xml.py",
        ],
    },
    "sources": {
        "block_defs_custom": "_分析临时/blockly_utf8/blocks/myrobotrun.js（原文另有 GBK 原始版 _分析临时/blockly_web/Blockly_Code/）",
        "block_defs_procedures": "_分析临时/blockly_utf8/blocks/procedures.js",
        "block_defs_stock": "_分析临时/blockly_utf8/blocks/{logic,math,text,variables,loops}.js（Blockly.defineBlocksWithJsonArray）",
        "python_generators": "_分析临时/blockly_utf8/generators/myrobotpythoncode.js + generators/python/*.js",
        "blockly_python_runtime": "Blockly.Python = new Blockly.Generator('Python')（generators/python.js:36）；Python 输出 = definitions_ 前置 + 顶层块代码；maingui.js:204/214 调 Blockly.Python.workspaceToCode(workspace)",
        "msg_zh": "_分析临时/blockly_utf8/msg/js/zh-hans.js（含 PartnerX 追加的 ABILIX_SCRATCH_* 文案）",
        "toolbox": "_分析临时/blockly_utf8/maingui.html 的 <xml id=\"toolbox_skcon9\">",
        "real_samples": {
            "PI": "_分析临时/PI/abilixProject.srh（当前保存 1328 块 / 31 类 / 26 个 procedures_defnoreturn）",
            "实验": "_分析临时/实验/abilixProject.srh（17 块 / 13 类）",
            "Scratch-3": "_分析临时/Scratch-3/abilixProject.srh（2 块）",
        },
    },
    "conventions": {
        "xml_root": '<xml xmlns="http://www.w3.org/1999/xhtml">…</xml>；变量声明在最前：<variables><variable type="" id="ID">名字</variable>…</variables>',
        "line_numbers": "generator / block_def 行号均为 1-based，与 grep/read 工具一致（按 \\n 计，UTF-8 副本文件）",
        "python_placeholders": "<...> 是模板占位符；换行以 \\n 结尾；表达式类块返回 [code, order]，语句类块返回带 \\n 的语句",
        "statement_order": "语句类积木的 next 链由 Blockly 自动拼接，XML 中 <next> 只表示同一积木栈的下一块",
        "evidence_levels": {
            "A+": "生成器/积木定义源码 + 真实项目样本双重确认",
            "A": "生成器/积木定义源码直接可证，无真实样本",
            "B": "源码可证但运行期行为（如参数化函数在 IDE 中的加载/渲染）尚待 headless 实测",
            "C": "推断，需实测",
        },
    },
}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "priority"
    types = PRIORITY if which == "priority" else PRIORITY + EXTRA
    blocks = {}
    warnings = []
    for t in types:
        try:
            blocks[t] = block_entry(t)
        except Exception as e:
            warnings.append((t, repr(e)))
    data = {"meta": META, "block_count": len(blocks),
            "blocks": blocks,
            "procedures_design_rules": {
                "定义块语句输入名": "STACK（不是 code）",
                "调用块参数输入": "ARG0..ARGn，由 <mutation> 的 <arg> 个数/顺序决定",
                "函数名规则": "界面改名只保留 \\w 且自动加 func_ 前缀（core/procedures.js:47-63）；XML 载入不走 rename 校验，但生成 Python 时经 Blockly.Names.safeName_，中文名会变成 _E5_... 乱码 → 函数名/参数名/变量名必须 ASCII",
                "函数分类(flyout)显示逻辑": "toolbox 分类 custom=\"PROCEDURE\" → core/toolbox.js:325 走动态回调 → core/procedures.js:212 flyoutCategory；内容 = 1 个新建 defnoreturn 模板 + 每个已有定义一个调用块（callnoreturn；若存在 defreturn 则还有 callreturn）",
                "生成顺序": "python.js finish()：变量初始化(var_x = None) → import → 各函数 def（definitions_）→ main()（start 块代码），导入来自 math_change 等",
                "main()": "由唯一 start 块生成；空/纯注释 body 会补 pass；global 行列出整个工作区用到的变量（参数变量也会出现在顶层 var 初始化里，属预期噪音，不影响语义）",
            }}
    out = os.path.join(SPEC_DIR, "block_schemas.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("written:", out, "blocks:", len(blocks), "warnings:", warnings)
    # 自检
    bad = []
    for t, b in blocks.items():
        try:
            ET.fromstring('<xml xmlns="http://www.w3.org/1999/xhtml">' + b.get("xml_min", "") + "</xml>")
        except Exception as e:
            bad.append((t, "xml_min", repr(e)))
        if "xml_real" in b:
            try:
                ET.fromstring('<xml xmlns="http://www.w3.org/1999/xhtml">' + b["xml_real"]["xml"] + "</xml>")
            except Exception as e:
                bad.append((t, "xml_real", repr(e)))
    print("xml self-check problems:", bad)


if __name__ == "__main__":
    main()
