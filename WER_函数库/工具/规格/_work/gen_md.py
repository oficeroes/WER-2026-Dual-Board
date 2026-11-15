# -*- coding: utf-8 -*-
"""从 block_schemas.json 生成人读版《积木XML规格.md》。"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.dirname(HERE)
SCHEMAS = json.load(open(os.path.join(SPEC, "block_schemas.json"), encoding="utf-8"))
B = SCHEMAS["blocks"]

OUT = os.path.join(SPEC, "积木XML规格.md")

PRIORITY = """start annotation block_mod motor motor_time motor_angle dual_motor_duration
dual_motor_angle resetencoder getencoder getai_glay getai_touch eeprom_read wait
if ifelse while_cmp while_forver while_number while_break
variables_get variables_set math_number math_op math_compare logic_compare logic_operation
logic_boolean robot_math_rounding robot_math_unary_operation
printf_text printf_number play_sound procedures_defnoreturn procedures_callnoreturn""".split()
EXTRA = [t for t in B if t not in PRIORITY]


def fmt_options(opts):
    return " / ".join("`%s`=`%s`" % (lbl, val) for lbl, val in opts)


def fmt_field(fname, f):
    k = f.get("kind")
    if k == "field_dropdown":
        return "`%s` 下拉：%s" % (fname, fmt_options(f.get("options") or []))
    if k == "field_text_input":
        return "`%s` 文本框，默认 `%r`" % (fname, f.get("default", ""))
    if k == "field_number":
        return "`%s` 数字框，默认 `%s`%s" % (
            fname, f.get("default", "0"),
            ("（建议范围 %s~%s）" % (f.get("min"), f.get("max")) if f.get("min") or f.get("max") else ""))
    if k == "field_checkbox":
        return "`%s` 复选框，默认 `%s`" % (fname, f.get("default", "FALSE"))
    if k == "field_variable":
        return "`%s` 变量下拉（引用 `<variables>` 里的变量）" % fname
    if k == "field_colour":
        return "`%s` 颜色选择，默认 `%s`" % (fname, f.get("default", "#ff0000"))
    if f.get("note"):
        return "`%s`（%s）" % (fname, f["note"])
    return "`%s` %s" % (fname, k)


def fmt_append(seg):
    k = seg.get("kind")
    if k == "image":
        return "🖼 `%s`" % seg.get("src", "")
    if k == "label":
        return "“%s”" % seg.get("text", "")
    if k == "field_dropdown":
        opts = seg.get("options") or []
        short = "、".join("%s(%s)" % (lbl, val) for lbl, val in opts[:4])
        if len(opts) > 4:
            short += "…共%d项" % len(opts)
        return "[下拉 `%s`: %s]" % (seg.get("field"), short)
    if k == "field_text_input":
        return "[文本框 `%s`: “%s”]" % (seg.get("field"), seg.get("default", ""))
    if k == "field_number":
        return "[数字框 `%s`: %s]" % (seg.get("field"), seg.get("default", "0"))
    if k == "field_checkbox":
        return "[复选框 `%s`: %s]" % (seg.get("field"), seg.get("default", "FALSE"))
    if k == "field_variable":
        return "[变量下拉 `%s`]" % seg.get("field")
    if k == "field_colour":
        return "[颜色 `%s`]" % seg.get("field")
    if k == "field_label":
        return "[动态字段 `%s`]" % seg.get("field")
    if k == "input_value":
        pre = " ".join(fmt_append(p) for p in seg.get("prefix") or [])
        chk = seg.get("check") or "任意"
        return "%s〈值输入 `%s`，check=%s〉" % ((pre + " ") if pre else "", seg.get("name"), chk)
    if k == "input_statement":
        pre = " ".join(fmt_append(p) for p in seg.get("prefix") or [])
        return "%s⟦语句输入 `%s`⟧" % ((pre + " ") if pre else "", seg.get("name"))
    return "[%s]" % k


def fmt_conn(conn):
    parts = []
    parts.append("前连接(previous)" + ("✅" if conn.get("previous") else "❌"))
    parts.append("后连接(next)" + ("✅" if conn.get("next") else "❌"))
    if conn.get("has_output") or conn.get("output") is not None:
        parts.append("输出 `%s`" % (conn.get("output") or "（无类型）"))
    else:
        parts.append("无输出")
    return "；".join(parts)


def block_section(t):
    b = B[t]
    md = []
    title = b.get("append_fields") and "`%s`" % t or "`%s`" % t
    md.append("### `%s`" % t)
    md.append("")
    md.append("| 项 | 内容 |")
    md.append("|---|---|")
    cat = b.get("category_skcon9")
    md.append("| SKCON9 分类 | %s |" % ("、".join(cat) if cat else "（不在 SKCON9 静态工具箱）"))
    bd = b.get("block_def") or {}
    if bd:
        md.append("| 积木定义 | `%s:%s-%s` |" % (bd.get("file"), bd.get("start_line"), bd.get("end_line")))
    md.append("| 连接 | %s |" % fmt_conn(b.get("connection") or {}))
    md.append("| 视觉结构（appendField 顺序） | %s |" % " → ".join(fmt_append(s) for s in b.get("append_fields") or []) or "—")
    flds = b.get("fields") or {}
    if flds:
        md.append("| 字段 | %s |" % "<br>".join(fmt_field(n, f) for n, f in flds.items()))
    inputs = b.get("inputs") or {}
    v = inputs.get("value") or {}
    s = inputs.get("statement") or {}
    if v or s:
        io = []
        for n, d in v.items():
            io.append("值 `%s`（check=%s）" % (n, d.get("check") or "任意"))
        for n in s:
            io.append("语句 `%s`" % n)
        md.append("| 输入 | %s |" % "；".join(io))
    md.append("")
    if b.get("generator"):
        g = b["generator"]
        md.append("生成器：`%s:%s-%s`%s" % (
            g.get("file"), g.get("start_line"), g.get("end_line"),
            ("（%s）" % g["symbol"] if g.get("symbol") else "")))
        md.append("")
    if b.get("python"):
        md.append("生成 Python：")
        md.append("```python")
        md.append(b["python"])
        md.append("```")
        md.append("")
    if b.get("mutation"):
        m = b["mutation"]
        md.append("**mutation 结构（参数化）**：")
        if m.get("xml"):
            md.append("```xml")
            md.append(m["xml"])
            md.append("```")
        for r in m.get("rules") or []:
            md.append("- " + r)
        for k, label in (("xml_param_example", "带参数示例"), ("xml_noparam_example", "无参数示例")):
            if m.get(k):
                md.append("")
                md.append("%s：" % label)
                md.append("```xml")
                md.append(m[k])
                md.append("```")
        md.append("")
    if b.get("xml_real"):
        md.append("最小合法 XML（真实样本，来自 `%s` 项目，已清理 xmlns/坐标/disabled）：" % b["xml_real"]["project"])
        md.append("```xml")
        md.append(b["xml_real"]["xml"])
        md.append("```")
        md.append("")
    if b.get("xml_min") and (not b.get("xml_real") or _norm(b["xml_min"]) != _norm(b["xml_real"]["xml"])):
        md.append("构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：")
        md.append("```xml")
        md.append(b["xml_min"])
        md.append("```")
        md.append("")
    if b.get("python_notes"):
        md.append("**备注**：" + b["python_notes"])
        md.append("")
    md.append("证据级别：**%s**" % b.get("evidence", "?"))
    md.append("")
    return "\n".join(md)


def _norm(x):
    return re.sub(r"\s+", " ", x).strip()


def main():
    md = []
    md.append("# WER 函数库积木 XML 规格（人读版）")
    md.append("")
    md.append("> 本文件与 `block_schemas.json`（机器可读，**唯一的字段级权威数据**）配套。"
              "JSON 里每块含：block_def 行号、append_fields、字段全量下拉值、输入 check、生成器行号、Python 模板、"
              "xml_min/xml_real、证据级别。本 MD 从 JSON 生成，便于人读与复制片段。")
    md.append("")
    md.append("## 0. 适用环境与来源")
    md.append("")
    md.append("- IDE：能力风暴 **AbilixScratch3.0**（本机 SKCON9，Blockly 2018 前后版本 + PartnerX 自定义生成器）。")
    md.append("- 积木定义：`_分析临时/blockly_utf8/blocks/myrobotrun.js`（自定义块，经典 `Blockly.Blocks['x'] = {...}` 写法）、"
              "`blocks/procedures.js`（函数）、`blocks/{logic,math,text,variables,loops}.js`（标准块，`defineBlocksWithJsonArray` JSON 写法）。")
    md.append("- Python 生成器：`_分析临时/blockly_utf8/generators/myrobotpythoncode.js`（自定义块）+ `generators/python/*.js`（标准块 + 函数）。")
    md.append("- 中文文案：`msg/js/zh-hans.js`（含 PartnerX 追加的 `ABILIX_SCRATCH_*`）。")
    md.append("- 工具箱与默认值：`maingui.html` 的 `<xml id=\"toolbox_skcon9\">`。")
    md.append("- 真实样本：`_分析临时/PI/abilixProject.srh`（1328 块/31 类/26 函数）、`_分析临时/实验/abilixProject.srh`、`_分析临时/Scratch-3/abilixProject.srh`。")
    md.append("")
    md.append("证据级别定义（与 JSON 的 `meta.conventions.evidence_levels` 一致）：")
    md.append("")
    md.append("| 级别 | 含义 |")
    md.append("|---|---|")
    md.append("| **A+** | 生成器/积木定义源码 + 真实项目样本双重确认 |")
    md.append("| **A** | 生成器/积木定义源码直接可证，无真实样本 |")
    md.append("| **B** | 源码可证，但运行期行为（渲染/flyout/下载）尚待实测 |")
    md.append("| **C** | 推测，需实测 |")
    md.append("")
    md.append("## 1. 项目 XML（.srh）通用结构")
    md.append("")
    md.append("```xml")
    md.append("<Abilix.ScratchProject.Info>")
    md.append('<?xml version="1.0" encoding="utf-8"?>')
    md.append('<ScratchProjectInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">')
    md.append("  <Version>1.0.3.4</Version>")
    md.append("  <RobotType>SKCON9</RobotType>")
    md.append("  <DownloadProgramName>WERFuncLib</DownloadProgramName>")
    md.append("</ScratchProjectInfo>")
    md.append("</Abilix.ScratchProject.Info>")
    md.append("")
    md.append("<Abilix.ScratchProject.ProjectString>")
    md.append('<xml xmlns="http://www.w3.org/1999/xhtml">')
    md.append('  <variables>')
    md.append('    <variable type="" id="v_1_var_1cm">var_1cm</variable>')
    md.append('    <variable type="" id="v_17_cm">cm</variable>')
    md.append('  </variables>')
    md.append('  <block type="procedures_defnoreturn" x="0" y="0">…函数定义…</block>')
    md.append('  <block type="start" deletable="false" x="0" y="800">…主函数…</block>')
    md.append("</xml>")
    md.append("</Abilix.ScratchProject.ProjectString>")
    md.append("```")
    md.append("")
    md.append("- `.srhs` = zip，唯一条目 `abilixProject.srh`，zip 注释 = 机器人类型枚举（SKCON9=111 / SKCON5=110 / SKCON2=112）。")
    md.append("- **读取现有 .srh 时只取第一个 `<xml …>` 到第一个 `</xml>`**：三个真实样本的 .srh 尾部都有旧版保存残留"
              "（覆盖写未截断，第一个 `</xml>` 之后是若干旧版中段残片），不能 `rfind('</xml>')`。")
    md.append("- `<variables>` 必须在所有 `<block>` 之前（Blockly 按文档顺序处理；字段 VAR 会按 id/名字查找或现场创建变量）。")
    md.append("- 变量：`<variable type=\"\" id=\"ID\">名字</variable>`；变量字段："
              "`<field name=\"VAR\" id=\"与声明一致的ID\" variabletype=\"\">名字</field>`（`id` 可省，会按名字兜底）。")
    md.append("- 名字必须 ASCII：生成 Python 时 `Blockly.Names.safeName_` 会把中文名转成 `_E5_...` 之类乱码（core/names.js:173-187）。")
    md.append("")
    md.append("## 2. 加载器易错点（重要）")
    md.append("")
    md.append("1. **写错字段名/输入名不会报错**：`Blockly.Xml.domToBlock` 遇到不存在的 `<field>`/`<value>`/`<statement>` 只 `console.warn` 并忽略"
              "（core/xml.js `domToField_` 等），看起来“加载成功”但值丢了。写完务必用 `check_library_xml.py` 核对。")
    md.append("2. **下拉字段写的是“值”不是界面文案**：`FieldDropdown.setValue()` 只匹配选项值；匹配不到会保持原值（默认第一项），例如 "
              "`math_compare.comparison_operator` 必须写 `==` 而不是 `=`。")
    md.append("3. `disabled=\"true\"` 的积木**不生成代码**（core/generator.js:170-172 直接跳过并继续 next 链）——遗留禁用块会造成“代码凭空少一段”。")
    md.append("4. 语句积木只能进 `<statement>`/`<next>`；值积木只能进 `<value>`；放反了连接不会成立（Blockly 会丢弃该子块）。")
    md.append("5. 表达式类积木（有输出）没有 previous/next，不能直接放在语句链上。")
    md.append("6. `start` 应当 `deletable=\"false\"`（block def 里 `setDeletable(false)`）；缺这个属性不影响生成，但 UI 里可被误删。")
    md.append("7. 一个工程只有 1 个 `start`（多个会各自生成 `def main()`，Python 重复定义）。")
    md.append("8. 真实样本里很多块带 `disabled=\"true\"`（作者停用的旧逻辑）——抄样本片段时要主动去掉。")
    md.append("9. **block id 在真实 IDE 存盘项目里会大量重复**（含 shadow 块；PI 样本上千处），Blockly 加载容忍；"
              "但工具生成的新工程建议保持 id 唯一，避免潜在的连接/撤销问题。")
    md.append("10. `shadow` 块也要合法：真实样本中 `<shadow type=\"math_number\">` 等出现在 `<value>` 里表示默认值；"
              "XML 载入时按普通块创建，字段名同样要写对。")
    md.append("")
    md.append("## 3. 函数（自定义积木）机制专章")
    md.append("")
    md.append("### 3.1 “函数”分类（flyout）如何生成")
    md.append("")
    md.append("- `maingui.html` 的工具箱里函数分类是 `<category name=\"函数\" custom=\"PROCEDURE\">`；"
              "`core/toolbox.js:325-328` 见到 `custom` 就交给动态回调；`core/workspace_svg.js:119-121` 注册 `PROCEDURE → Blockly.Procedures.flyoutCategory`。")
    md.append("- `core/procedures.js:212 flyoutCategory()` 生成两类积木：")
    md.append("  1. 一个**新建函数**模板：`procedures_defnoreturn` + `<field name=\"NAME\">func_name</field>`（参数编辑 mutator 被注释掉，"
              "界面无法给函数加参数）；")
    md.append("  2. 为工作区里每个已有函数定义生成一个**调用块** `procedures_callnoreturn`（带 `<mutation name=…><arg…/></mutation>`）；"
              "若有 `procedures_defreturn` 定义，还会为它生成 `procedures_callreturn` 调用块（第 166 行 `populateProcedures(tuple[1], 'procedures_callreturn')` 未被注释）。")
    md.append("- 因此：**工程 XML 里放好 N 个函数定义，打开 IDE 的“函数”分类就能看到并拖动 N 个调用块**——这正是本函数库做法。")
    md.append("")
    md.append("### 3.2 `procedures_defnoreturn`（无返回值函数定义）")
    md.append("")
    md.append("- 字段：`NAME`（函数名，ASCII）；语句输入：`STACK`（函数体，注意不是 `code`）；`PARAMS` 是运行时自动渲染的字段，不要写进 XML。")
    md.append("- 参数化：`<mutation><arg name=\"cm\" varid=\"v_17_cm\"></arg></mutation>`（`varid` 可省；保存时 def 的 mutation **不带 name 属性**）。")
    md.append("- 参数名/函数名必须 ASCII；界面改名规则 `Blockly.Procedures.rename`（core/procedures.js:44-90）只保留 `\\w` 并自动加 `func_` 前缀，"
              "但 XML 载入不走这个校验，**生成 Python 时仍会经 safeName_**。")
    md.append("- 函数体内用 `variables_get` 引用参数名即可；生成器会把参数名排除在 `global` 之外。")
    md.append("")
    md.append("### 3.3 `procedures_callnoreturn`（无返回值函数调用）")
    md.append("")
    md.append("- 函数名与参数全部由 `<mutation name=\"func_x\"><arg name=\"cm\"></arg></mutation>` 恢复；**不要写 `<field name=\"NAME\">`**（init 里 NAME 字段初始值是块 id，domToMutation 会把它改成 mutation 的函数名）。")
    md.append("- 有参数的调用块会按 arg 顺序出现 `ARG0..ARGn` 值输入；缺输入时生成器填 `None`。")
    md.append("- **调用 mutation 的 arg 必须与定义 mutation 的名称/顺序完全一致**：不一致时调用块的 onchange 会认为“没有匹配定义”并自动新建一个同名 def 块（会产生重复函数）。")
    md.append("")
    md.append("### 3.4 `procedures_defreturn`（有返回值函数）——本 IDE 可用性结论")
    md.append("")
    md.append("| 能力 | 是否可用 | 证据 |")
    md.append("|---|---|---|")
    md.append("| 块定义/参数 mutator | ✅（该块上 mutator 未被注释，可 XML 载入后手动加参数） | `blocks/procedures.js:393-448` |")
    md.append("| Python 生成（def + return） | ✅ | `generators/python/procedures.js:32-88`；`procedures_defnoreturn` 在 92-93 行直接别名到它 |")
    md.append("| 从工具箱新建 | ❌ 入口被注释 | `core/procedures.js:114-127` |")
    md.append("| 已有 defreturn 的调用块出现在“函数”分类 | ✅（源码未注释） | `core/procedures.js:166`；真实 flyout 实例化未单独实测（B 级待验证） |")
    md.append("")
    md.append("结论：**defreturn 通过 XML 加载 + 生成 Python + 显示调用块都可用，只是不能在 IDE 里从工具箱新建**。函数库如需“带返回值函数”，只能由工具生成 XML 写入工程。")
    md.append("")
    md.append("### 3.5 Python 生成的整体流程（函数库输出长什么样）")
    md.append("")
    md.append("`maingui.js:204/214` 调 `Blockly.Python.workspaceToCode(workspace)`；`generators/python.js`：")
    md.append("")
    md.append("```")
    md.append("1) init(): 为工作区所有用到的变量生成 `var_x = None`（python.js:174-180）；")
    md.append("2) 顶层块按位置(y,x)生成：procedures_def* 生成到 definitions_['%'+name]，返回 null；start 返回 `def main(): ...`；")
    md.append("3) finish(): definitions_（变量初始化 + import + 各函数 def）拼在前面，main 代码接在最后；")
    md.append("4) 头部的 `#<SKCON9><USB><ProgramName>`、import threading/time/libstarpy、`robot = Robot()` 由 maingui.js 的 getPythonCode 另加。")
    md.append("```")
    md.append("")
    md.append("- 函数体生成器**恒在末尾追加 `    pass`**（stock `branch = branch + Blockly.Python.PASS`），空函数也合法。")
    md.append("- `start` 的 `global` 行列出**整个工作区**用到的变量（不是仅函数体）；参数变量也会在文件顶部出现一行 `cm = None`，"
              "并在 main 的 global 里出现——这是实测确认的预期噪音（harness 证据：`工具/验证/证据/参数化函数/20261110_131824_param_test.py`），不影响语义。")
    md.append("")
    md.append("## 4. 优先块规格（第一批，35 个）")
    md.append("")
    md.append("> 函数库第一批“必需块”。每个块的小节格式：分类/定义行号/连接/视觉结构/字段/输入/生成 Python/最小 XML/证据。")
    md.append("")
    for t in PRIORITY:
        if t in B:
            md.append(block_section(t))
    md.append("## 5. 其余常用块规格（25 个）")
    md.append("")
    for t in EXTRA:
        md.append(block_section(t))
    md.append("## 6. 真实样本来源标注")
    md.append("")
    md.append("各块 `xml_real` 的来源项目见下表（同一块优先取 PI；PI 没有的取实验/Scratch-3；都没有的只给构造版）：")
    md.append("")
    md.append("| 块 | 真实样本项目 |")
    md.append("|---|---|")
    for t in list(PRIORITY) + EXTRA:
        if t in B:
            r = B[t].get("xml_real")
            md.append("| `%s` | %s |" % (t, r["project"] if r else "—（无真实样本）"))
    md.append("")
    md.append("## 7. 已确认坑 / 待实测清单（与 `_协作/报告_schema.md` 同步）")
    md.append("")
    md.append("已确认（A/A+）：")
    md.append("")
    md.append("- `math_compare` 下拉值是 `==/!=/</<=/>/>=`；写 `=` 会静默回退第一项。")
    md.append("- `while_number` 的 `TIMES` 是**值输入**（`<value name=\"TIMES\">`），不是字段；循环变量 `count/count2/…` 自动生成。")
    md.append("- `while_cmp` 生成 `while not <bool>:`；`while_forver` 语句输入名是 `NAME`；`while_break` 生成 `break`。")
    md.append("- `resetencoder` 生成 `robot.reset_encoder(port);`（带分号）；`get_encoder_real_time_value` 在 SKCON9 下是 `robot.get_instant_incoder`（固件拼写，照抄）。")
    md.append("- `wait` 在 SKCON9 下是 `time.sleep`，SKCON2 才走 `robot.sleep`。")
    md.append("- `printf_text` 生成 `robot.print('…\\n')`；`printf_number` 生成 `robot.print('data= ' + str(<data>) + '\\n')`。")
    md.append("- `play_sound` 的 `musicname` 是 PlayList 的**文件值**（如 `dazhaohu_c0.mp3`、`luyin_p2`），共 78 项，完整表在 `block_schemas.json`。")
    md.append("- 参数化函数（defnoreturn）已由 harness headless 实测通过（加载/flyout 调用块/Python 生成/py_compile 16 项全 PASS）。")
    md.append("")
    md.append("待实测（B）：")
    md.append("")
    md.append("- `procedures_defreturn` 的真实 flyout 实例化（调用块是否在“函数”分类中渲染成功、能否拖出）——源码可证但需 harness 加用例。")
    md.append("- `get_key` 不在 SKCON9 工具箱：生成器 `robot.check_key` 存在，但真机是否有 Start/Left/Right 键需实机确认。")
    md.append("- `dual_motor_angle.port_3` 的 UI onChange 动态下拉只允许 port_1/port_2；纯 XML 载入不做合法性限制（不会报错）。")
    md.append("")
    open(OUT, "w", encoding="utf-8").write("\n".join(md))
    print("written:", OUT, len("\n".join(md)), "chars")


if __name__ == "__main__":
    main()
