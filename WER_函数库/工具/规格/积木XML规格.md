# WER 函数库积木 XML 规格（人读版）

> 本文件与 `block_schemas.json`（机器可读，**唯一的字段级权威数据**）配套。JSON 里每块含：block_def 行号、append_fields、字段全量下拉值、输入 check、生成器行号、Python 模板、xml_min/xml_real、证据级别。本 MD 从 JSON 生成，便于人读与复制片段。

## 0. 适用环境与来源

- IDE：能力风暴 **AbilixScratch3.0**（本机 SKCON9，Blockly 2018 前后版本 + PartnerX 自定义生成器）。
- 积木定义：`_分析临时/blockly_utf8/blocks/myrobotrun.js`（自定义块，经典 `Blockly.Blocks['x'] = {...}` 写法）、`blocks/procedures.js`（函数）、`blocks/{logic,math,text,variables,loops}.js`（标准块，`defineBlocksWithJsonArray` JSON 写法）。
- Python 生成器：`_分析临时/blockly_utf8/generators/myrobotpythoncode.js`（自定义块）+ `generators/python/*.js`（标准块 + 函数）。
- 中文文案：`msg/js/zh-hans.js`（含 PartnerX 追加的 `ABILIX_SCRATCH_*`）。
- 工具箱与默认值：`maingui.html` 的 `<xml id="toolbox_skcon9">`。
- 真实样本：`_分析临时/PI/abilixProject.srh`（1328 块/31 类/26 函数）、`_分析临时/实验/abilixProject.srh`、`_分析临时/Scratch-3/abilixProject.srh`。

证据级别定义（与 JSON 的 `meta.conventions.evidence_levels` 一致）：

| 级别 | 含义 |
|---|---|
| **A+** | 生成器/积木定义源码 + 真实项目样本双重确认 |
| **A** | 生成器/积木定义源码直接可证，无真实样本 |
| **B** | 源码可证，但运行期行为（渲染/flyout/下载）尚待实测 |
| **C** | 推测，需实测 |

## 1. 项目 XML（.srh）通用结构

```xml
<Abilix.ScratchProject.Info>
<?xml version="1.0" encoding="utf-8"?>
<ScratchProjectInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Version>1.0.3.4</Version>
  <RobotType>SKCON9</RobotType>
  <DownloadProgramName>WERFuncLib</DownloadProgramName>
</ScratchProjectInfo>
</Abilix.ScratchProject.Info>

<Abilix.ScratchProject.ProjectString>
<xml xmlns="http://www.w3.org/1999/xhtml">
  <variables>
    <variable type="" id="v_1_var_1cm">var_1cm</variable>
    <variable type="" id="v_17_cm">cm</variable>
  </variables>
  <block type="procedures_defnoreturn" x="0" y="0">…函数定义…</block>
  <block type="start" deletable="false" x="0" y="800">…主函数…</block>
</xml>
</Abilix.ScratchProject.ProjectString>
```

- `.srhs` = zip，唯一条目 `abilixProject.srh`，zip 注释 = 机器人类型枚举（SKCON9=111 / SKCON5=110 / SKCON2=112）。
- **读取现有 .srh 时只取第一个 `<xml …>` 到第一个 `</xml>`**：三个真实样本的 .srh 尾部都有旧版保存残留（覆盖写未截断，第一个 `</xml>` 之后是若干旧版中段残片），不能 `rfind('</xml>')`。
- `<variables>` 必须在所有 `<block>` 之前（Blockly 按文档顺序处理；字段 VAR 会按 id/名字查找或现场创建变量）。
- 变量：`<variable type="" id="ID">名字</variable>`；变量字段：`<field name="VAR" id="与声明一致的ID" variabletype="">名字</field>`（`id` 可省，会按名字兜底）。
- 名字必须 ASCII：生成 Python 时 `Blockly.Names.safeName_` 会把中文名转成 `_E5_...` 之类乱码（core/names.js:173-187）。

## 2. 加载器易错点（重要）

1. **写错字段名/输入名不会报错**：`Blockly.Xml.domToBlock` 遇到不存在的 `<field>`/`<value>`/`<statement>` 只 `console.warn` 并忽略（core/xml.js `domToField_` 等），看起来“加载成功”但值丢了。写完务必用 `check_library_xml.py` 核对。
2. **下拉字段写的是“值”不是界面文案**：`FieldDropdown.setValue()` 只匹配选项值；匹配不到会保持原值（默认第一项），例如 `math_compare.comparison_operator` 必须写 `==` 而不是 `=`。
3. `disabled="true"` 的积木**不生成代码**（core/generator.js:170-172 直接跳过并继续 next 链）——遗留禁用块会造成“代码凭空少一段”。
4. 语句积木只能进 `<statement>`/`<next>`；值积木只能进 `<value>`；放反了连接不会成立（Blockly 会丢弃该子块）。
5. 表达式类积木（有输出）没有 previous/next，不能直接放在语句链上。
6. `start` 应当 `deletable="false"`（block def 里 `setDeletable(false)`）；缺这个属性不影响生成，但 UI 里可被误删。
7. 一个工程只有 1 个 `start`（多个会各自生成 `def main()`，Python 重复定义）。
8. 真实样本里很多块带 `disabled="true"`（作者停用的旧逻辑）——抄样本片段时要主动去掉。
9. **block id 在真实 IDE 存盘项目里会大量重复**（含 shadow 块；PI 样本上千处），Blockly 加载容忍；但工具生成的新工程建议保持 id 唯一，避免潜在的连接/撤销问题。
10. `shadow` 块也要合法：真实样本中 `<shadow type="math_number">` 等出现在 `<value>` 里表示默认值；XML 载入时按普通块创建，字段名同样要写对。

## 3. 函数（自定义积木）机制专章

### 3.1 “函数”分类（flyout）如何生成

- `maingui.html` 的工具箱里函数分类是 `<category name="函数" custom="PROCEDURE">`；`core/toolbox.js:325-328` 见到 `custom` 就交给动态回调；`core/workspace_svg.js:119-121` 注册 `PROCEDURE → Blockly.Procedures.flyoutCategory`。
- `core/procedures.js:212 flyoutCategory()` 生成两类积木：
  1. 一个**新建函数**模板：`procedures_defnoreturn` + `<field name="NAME">func_name</field>`（参数编辑 mutator 被注释掉，界面无法给函数加参数）；
  2. 为工作区里每个已有函数定义生成一个**调用块** `procedures_callnoreturn`（带 `<mutation name=…><arg…/></mutation>`）；若有 `procedures_defreturn` 定义，还会为它生成 `procedures_callreturn` 调用块（第 166 行 `populateProcedures(tuple[1], 'procedures_callreturn')` 未被注释）。
- 因此：**工程 XML 里放好 N 个函数定义，打开 IDE 的“函数”分类就能看到并拖动 N 个调用块**——这正是本函数库做法。

### 3.2 `procedures_defnoreturn`（无返回值函数定义）

- 字段：`NAME`（函数名，ASCII）；语句输入：`STACK`（函数体，注意不是 `code`）；`PARAMS` 是运行时自动渲染的字段，不要写进 XML。
- 参数化：`<mutation><arg name="cm" varid="v_17_cm"></arg></mutation>`（`varid` 可省；保存时 def 的 mutation **不带 name 属性**）。
- 参数名/函数名必须 ASCII；界面改名规则 `Blockly.Procedures.rename`（core/procedures.js:44-90）只保留 `\w` 并自动加 `func_` 前缀，但 XML 载入不走这个校验，**生成 Python 时仍会经 safeName_**。
- 函数体内用 `variables_get` 引用参数名即可；生成器会把参数名排除在 `global` 之外。

### 3.3 `procedures_callnoreturn`（无返回值函数调用）

- 函数名与参数全部由 `<mutation name="func_x"><arg name="cm"></arg></mutation>` 恢复；**不要写 `<field name="NAME">`**（init 里 NAME 字段初始值是块 id，domToMutation 会把它改成 mutation 的函数名）。
- 有参数的调用块会按 arg 顺序出现 `ARG0..ARGn` 值输入；缺输入时生成器填 `None`。
- **调用 mutation 的 arg 必须与定义 mutation 的名称/顺序完全一致**：不一致时调用块的 onchange 会认为“没有匹配定义”并自动新建一个同名 def 块（会产生重复函数）。

### 3.4 `procedures_defreturn`（有返回值函数）——本 IDE 可用性结论

| 能力 | 是否可用 | 证据 |
|---|---|---|
| 块定义/参数 mutator | ✅（该块上 mutator 未被注释，可 XML 载入后手动加参数） | `blocks/procedures.js:393-448` |
| Python 生成（def + return） | ✅ | `generators/python/procedures.js:32-88`；`procedures_defnoreturn` 在 92-93 行直接别名到它 |
| 从工具箱新建 | ❌ 入口被注释 | `core/procedures.js:114-127` |
| 已有 defreturn 的调用块出现在“函数”分类 | ✅（源码未注释） | `core/procedures.js:166`；真实 flyout 实例化未单独实测（B 级待验证） |

结论：**defreturn 通过 XML 加载 + 生成 Python + 显示调用块都可用，只是不能在 IDE 里从工具箱新建**。函数库如需“带返回值函数”，只能由工具生成 XML 写入工程。

### 3.5 Python 生成的整体流程（函数库输出长什么样）

`maingui.js:204/214` 调 `Blockly.Python.workspaceToCode(workspace)`；`generators/python.js`：

```
1) init(): 为工作区所有用到的变量生成 `var_x = None`（python.js:174-180）；
2) 顶层块按位置(y,x)生成：procedures_def* 生成到 definitions_['%'+name]，返回 null；start 返回 `def main(): ...`；
3) finish(): definitions_（变量初始化 + import + 各函数 def）拼在前面，main 代码接在最后；
4) 头部的 `#<SKCON9><USB><ProgramName>`、import threading/time/libstarpy、`robot = Robot()` 由 maingui.js 的 getPythonCode 另加。
```

- 函数体生成器**恒在末尾追加 `    pass`**（stock `branch = branch + Blockly.Python.PASS`），空函数也合法。
- `start` 的 `global` 行列出**整个工作区**用到的变量（不是仅函数体）；参数变量也会在文件顶部出现一行 `cm = None`，并在 main 的 global 里出现——这是实测确认的预期噪音（harness 证据：`工具/验证/证据/参数化函数/20261110_131824_param_test.py`），不影响语义。

## 4. 优先块规格（第一批，35 个）

> 函数库第一批“必需块”。每个块的小节格式：分类/定义行号/连接/视觉结构/字段/输入/生成 Python/最小 XML/证据。

### `start`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 主函数（不在工具箱，由新建项目默认模板/工程 XML 提供） |
| 积木定义 | `blocks/myrobotrun.js:110-124` |
| 连接 | 前连接(previous)❌；后连接(next)❌；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/main.png` → “主函数” → ⟦语句输入 `code`⟧ |
| 输入 | 语句 `code` |

生成器：`generators/myrobotpythoncode.js:7-38`

生成 Python：
```python
def main():
    global <工作区所有用到的变量名, 逗号分隔>   # 仅当有变量时
    <语句输入 code 的代码>
    pass                # 仅当 code 为空或全部是注释时
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="start" deletable="false" />
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="start" deletable="false" x="0" y="0">
  <statement name="code"></statement>
</block>
```

**备注**：整个文件入口；def main 由 start 生成，函数定义由 procedures_* 生成。global 行列出【整个工作区】allUsedVarModels，不只是函数体内变量。

证据级别：**A+**

### `annotation`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 注释 |
| 积木定义 | `blocks/myrobotrun.js:127-139` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/ic_feedback_white_24dp.png` → [文本框 `text`: “注释说明”] |
| 字段 | `text` 文本框，默认 `'注释说明'` |

生成器：`generators/myrobotpythoncode.js:41-51`

生成 Python：
```python
#<text>

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="annotation">
  <field name="text">注释说明</field>
</block>
```

**备注**：text 原样拼在 # 后面，不加空格；语句输入 code 即使有内容也被忽略。

证据级别：**A+**

### `block_mod`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 注释 |
| 积木定义 | `blocks/myrobotrun.js:142-157` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic\ic_list_white_24dp.png` → “模块组” → [文本框 `NAME`: “简要说明”] → ⟦语句输入 `code`⟧ |
| 字段 | `NAME` 文本框，默认 `'简要说明'` |
| 输入 | 语句 `code` |

生成器：`generators/myrobotpythoncode.js:53-63`

生成 Python：
```python
#<NAME>
if True:
<语句输入 code>
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="block_mod"><field name="NAME">自转</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="block_mod">
  <field name="NAME">简要说明</field>
</block>
```

**备注**：本质是带标题的 if True 折叠块；body 为空时补 '    pass\n'。

证据级别：**A+**

### `motor`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运动 |
| 积木定义 | `blocks/myrobotrun.js:162-180` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic\block_icon\motor.png` → “电机” → [下拉 `channel`: 端口A(1)、端口B(2)、端口C(3)、端口D(4)] → “速度” 〈值输入 `speed`，check=Number〉 → “%” |
| 字段 | `channel` 下拉：`端口A`=`1` / `端口B`=`2` / `端口C`=`3` / `端口D`=`4` |
| 输入 | 值 `speed`（check=Number） |

生成器：`generators/myrobotpythoncode.js:74-81`

生成 Python：
```python
robot.set_motor(<Number(channel)>, robot.clamp(<speed 表达式>, -100, 100))

```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="motor"><field name="channel">1</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="motor">
  <field name="channel">1</field>
  <value name="speed"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：channel 出 XML 前已由 Number() 转 int；speed 无论写什么都会再包一层 robot.clamp。

证据级别：**A+**

### `motor_time`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运动 |
| 积木定义 | `blocks/myrobotrun.js:183-206` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic\block_icon\motor.png` → “电机” → [下拉 `channel`: 端口A(1)、端口B(2)、端口C(3)、端口D(4)] → “速度” 〈值输入 `speed`，check=Number〉 → “%” → “持续” 〈值输入 `time`，check=Number〉 → “秒” |
| 字段 | `channel` 下拉：`端口A`=`1` / `端口B`=`2` / `端口C`=`3` / `端口D`=`4` |
| 输入 | 值 `speed`（check=Number）；值 `time`（check=Number） |

生成器：`generators/myrobotpythoncode.js:84-93`

生成 Python：
```python
robot.set_motor_time(<Number(channel)>, robot.clamp(<speed>, -100, 100), robot.clamp(<time>, 0, 3600))

```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="motor_time"><field name="channel">3</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="motor_time">
  <field name="channel">1</field>
  <value name="speed"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="time"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

证据级别：**A+**

### `motor_angle`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运动 |
| 积木定义 | `blocks/myrobotrun.js:209-232` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic\block_icon\motor.png` → “电机” → [下拉 `channel`: 端口A(1)、端口B(2)、端口C(3)、端口D(4)] → “速度” 〈值输入 `speed`，check=Number〉 → “%” → “直到编码器读数超过” 〈值输入 `angle`，check=Number〉 → “停止” |
| 字段 | `channel` 下拉：`端口A`=`1` / `端口B`=`2` / `端口C`=`3` / `端口D`=`4` |
| 输入 | 值 `speed`（check=Number）；值 `angle`（check=Number） |

生成器：`generators/myrobotpythoncode.js:143-152`

生成 Python：
```python
robot.set_motor_encoder(<Number(channel)>, robot.clamp(<speed>, -100, 100), robot.clamp(<angle>, -99999, 99999))

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="motor_angle">
  <field name="channel">1</field>
  <value name="speed"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="angle"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

证据级别：**A+**

### `dual_motor_duration`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运动 |
| 积木定义 | `blocks/myrobotrun.js:279-356` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic\block_icon\motor.png` → “电机” → [下拉 `port_1`: 端口A(1)、端口B(2)、端口C(3)、端口D(4)] → “速度” 〈值输入 `speed_1`，check=Number〉 → “%” → “,” → “电机” → [下拉 `port_2`: 端口A(1)、端口B(2)、端口C(3)、端口D(4)] → “速度” 〈值输入 `speed_2`，check=Number〉 → “%” → “,” → “持续” 〈值输入 `time`，check=Number〉 → “秒” |
| 字段 | `port_1` 下拉：`端口A`=`1` / `端口B`=`2` / `端口C`=`3` / `端口D`=`4`<br>`port_2` 下拉：`端口A`=`1` / `端口B`=`2` / `端口C`=`3` / `端口D`=`4` |
| 输入 | 值 `speed_1`（check=Number）；值 `speed_2`（check=Number）；值 `time`（check=Number） |

生成器：`generators/myrobotpythoncode.js:96-116`

生成 Python：
```python
robot.set_double_motor_time(<Number(port_1)>, robot.clamp(<speed_1>, -100, 100), <Number(port_2)>, robot.clamp(<speed_2>, -100, 100), robot.clamp(<time>, 0, 3600))

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="dual_motor_duration">
  <field name="port_1">1</field>
  <field name="port_2">1</field>
  <value name="speed_1"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="speed_2"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="time"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

证据级别：**A+**

### `dual_motor_angle`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运动 |
| 积木定义 | `blocks/myrobotrun.js:359-450` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic\block_icon\motor.png` → “电机” → [下拉 `port_1`: 端口A(1)、端口B(2)、端口C(3)、端口D(4)] → “速度” 〈值输入 `speed_1`，check=Number〉 → “%” → “,” → “电机” → [下拉 `port_2`: 端口A(1)、端口B(2)、端口C(3)、端口D(4)] → “速度” 〈值输入 `speed_2`，check=Number〉 → “%” → “,” → “直到电机” → [下拉 `port_3`: 端口A(1)、端口B(2)、端口C(3)、端口D(4)] → “编码器读数超过” → 〈值输入 `angle`，check=Number〉 → “停止” |
| 字段 | `port_1` 下拉：`端口A`=`1` / `端口B`=`2` / `端口C`=`3` / `端口D`=`4`<br>`port_2` 下拉：`端口A`=`1` / `端口B`=`2` / `端口C`=`3` / `端口D`=`4`<br>`port_3` 下拉：`端口A`=`1` / `端口B`=`2` / `端口C`=`3` / `端口D`=`4` |
| 输入 | 值 `speed_1`（check=Number）；值 `speed_2`（check=Number）；值 `angle`（check=Number） |

生成器：`generators/myrobotpythoncode.js:119-140`

生成 Python：
```python
robot.set_double_motor_encoder(<Number(port_1)>, robot.clamp(<speed_1>, -100, 100), <Number(port_2)>, robot.clamp(<speed_2>, -100, 100), <Number(port_3)>, robot.clamp(<angle>, -99999, 99999))

```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="dual_motor_angle"><field name="port_1">1</field><field name="port_2">2</field><field name="port_3">1</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="dual_motor_angle">
  <field name="port_1">1</field>
  <field name="port_2">1</field>
  <field name="port_3">1</field>
  <value name="speed_1"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="speed_2"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="angle"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：port_3 会被 UI 的 onChange 限制为 port_1/port_2 之一。

证据级别：**A+**

### `resetencoder`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 传感 |
| 积木定义 | `blocks/myrobotrun.js:1375-1389` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/motor_encoder.png` → “电机编码器” → [下拉 `port`: 端口A(1)、端口B(2)、端口C(3)、端口D(4)] → “清零” |
| 字段 | `port` 下拉：`端口A`=`1` / `端口B`=`2` / `端口C`=`3` / `端口D`=`4` |

生成器：`generators/myrobotpythoncode.js:516-521`

生成 Python：
```python
robot.reset_encoder(<port>);

```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="resetencoder"><field name="port">1</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="resetencoder">
  <field name="port">1</field>
</block>
```

**备注**：注意生成器里带一个分号：';\n'（Python 里合法但多余）。

证据级别：**A+**

### `getencoder`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 传感 |
| 积木定义 | `blocks/myrobotrun.js:1392-1404` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/motor_encoder.png` → “获取电机编码器累计值” → [下拉 `port`: 端口A(1)、端口B(2)、端口C(3)、端口D(4)] |
| 字段 | `port` 下拉：`端口A`=`1` / `端口B`=`2` / `端口C`=`3` / `端口D`=`4` |

生成器：`generators/myrobotpythoncode.js:492-497`

生成 Python：
```python
robot.get_encoder(<port>)
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="getencoder"><field name="port">2</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="getencoder">
  <field name="port">1</field>
</block>
```

**备注**：输出表达式

证据级别：**A+**

### `getai_glay`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 传感、巡线 |
| 积木定义 | `blocks/myrobotrun.js:1004-1017` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/gray_scale_sensor.png` → “灰度” → [下拉 `channel`: 端口1(1)、端口2(2)、端口3(3)、端口4(4)…共12项] → “地面灰度” |
| 字段 | `channel` 下拉：`端口1`=`1` / `端口2`=`2` / `端口3`=`3` / `端口4`=`4` / `端口5`=`5` / `端口6`=`6` / `端口7`=`7` / `端口8`=`8` / `端口9`=`9` / `端口10`=`10` / `端口11`=`11` / `端口12`=`12` |

生成器：`generators/myrobotpythoncode.js:345-350`

生成 Python：
```python
robot.get_gray(<channel>)
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="getai_glay"><field name="channel">9</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="getai_glay">
  <field name="channel">1</field>
</block>
```

**备注**：输出表达式

证据级别：**A+**

### `getai_touch`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 传感 |
| 积木定义 | `blocks/myrobotrun.js:1199-1212` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Boolean` |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/touch_sensor.png` → “碰撞” → [下拉 `channel`: 端口1(1)、端口2(2)、端口3(3)、端口4(4)…共12项] → “碰到物体” |
| 字段 | `channel` 下拉：`端口1`=`1` / `端口2`=`2` / `端口3`=`3` / `端口4`=`4` / `端口5`=`5` / `端口6`=`6` / `端口7`=`7` / `端口8`=`8` / `端口9`=`9` / `端口10`=`10` / `端口11`=`11` / `端口12`=`12` |

生成器：`generators/myrobotpythoncode.js:437-442`

生成 Python：
```python
robot.get_touch(<channel>)
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="getai_touch"><field name="channel">1</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="getai_touch">
  <field name="channel">1</field>
</block>
```

**备注**：输出表达式

证据级别：**A+**

### `eeprom_read`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 传感 |
| 积木定义 | `blocks/myrobotrun.js:1455-1467` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/read_and_write_data.png` → “读取数据 地址” → [数字框 `address`: 1] |
| 字段 | `address` 数字框，默认 `1` |

生成器：`generators/myrobotpythoncode.js:540-545`

生成 Python：
```python
robot.get_ee(<address>)
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="eeprom_read"><field name="address">9</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="eeprom_read">
  <field name="address">1</field>
</block>
```

**备注**：输出表达式

证据级别：**A+**

### `wait`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 控制 |
| 积木定义 | `blocks/myrobotrun.js:787-802` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/delay.png` “等待” 〈值输入 `time`，check=Number〉 → “秒” |
| 输入 | 值 `time`（check=Number） |

生成器：`generators/myrobotpythoncode.js:673-686`

生成 Python：
```python
SKCON9/其它: time.sleep(<time>)
SKCON2:      robot.sleep(<time>)
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="wait" />
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="wait">
  <value name="time"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：生成器分 maingui.robotType 判断；本机 SKCON9 走 time.sleep。

证据级别：**A+**

### `if`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 控制 |
| 积木定义 | `blocks/myrobotrun.js:807-825` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/if_else.png` “如果” 〈值输入 `logic_val`，check=Boolean〉 → “那么” → ⟦语句输入 `code`⟧ |
| 输入 | 值 `logic_val`（check=Boolean）；语句 `code` |

生成器：`generators/myrobotpythoncode.js:583-591`

生成 Python：
```python
if <logic_val>:
<语句输入 code>
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="if" />
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="if">
  <value name="logic_val"><shadow type="logic_boolean"><field name="BOOL">TRUE</field></shadow></value>
</block>
```

**备注**：body 为空时补 '    pass\n'。

证据级别：**A+**

### `ifelse`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 控制 |
| 积木定义 | `blocks/myrobotrun.js:828-849` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/if_else.png` “如果” 〈值输入 `logic_val`，check=Boolean〉 → “那么” → ⟦语句输入 `code`⟧ → “否则” ⟦语句输入 `else_code`⟧ |
| 输入 | 值 `logic_val`（check=Boolean）；语句 `code`；语句 `else_code` |

生成器：`generators/myrobotpythoncode.js:594-608`

生成 Python：
```python
if <logic_val>:
<语句输入 code>else:
<语句输入 else_code>
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="ifelse" />
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="ifelse">
  <value name="logic_val"><shadow type="logic_boolean"><field name="BOOL">TRUE</field></shadow></value>
</block>
```

**备注**：两个 body 为空时各自补 '    pass\n'。

证据级别：**A+**

### `while_cmp`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 控制 |
| 积木定义 | `blocks/myrobotrun.js:869-884` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/loop_until.png` “重复执行直到” 〈值输入 `bool`，check=Boolean〉 → ⟦语句输入 `code`⟧ |
| 输入 | 值 `bool`（check=Boolean）；语句 `code` |

生成器：`generators/myrobotpythoncode.js:621-629`

生成 Python：
```python
while not <bool>:
<语句输入 code>
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="while_cmp" />
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="while_cmp">
  <value name="bool"><shadow type="logic_boolean"><field name="BOOL">TRUE</field></shadow></value>
</block>
```

**备注**：注意是 while not：bool 为假时继续循环。

证据级别：**A+**

### `while_forver`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 控制 |
| 积木定义 | `blocks/myrobotrun.js:852-866` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/infinite_loop.png` → “重复执行” → ⟦语句输入 `NAME`⟧ |
| 输入 | 语句 `NAME` |

生成器：`generators/myrobotpythoncode.js:611-618`

生成 Python：
```python
while True:
<语句输入 NAME>
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="while_forver" />
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="while_forver">
</block>
```

**备注**：语句输入名是 NAME（不是 code）。

证据级别：**A+**

### `while_number`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 控制 |
| 积木定义 | `blocks/myrobotrun.js:887-904` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/loop.png` “重复” 〈值输入 `TIMES`，check=Number〉 → “次” → ⟦语句输入 `code`⟧ |
| 输入 | 值 `TIMES`（check=Number）；语句 `code` |

生成器：`generators/myrobotpythoncode.js:632-655`

生成 Python：
```python
for <自动生成的 loopVar> in range(<TIMES>):
<语句输入 code>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="while_number">
  <value name="TIMES"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：TIMES 是值输入（不是字段！）。若 TIMES 是数字字面量则直接用；否则包 int(...)。loopVar 由 getDistinctName('count') 生成 → count/count2/count3…。

证据级别：**A+（TIMES 为值输入由块定义+工具箱+生成器三方确认）**

### `while_break`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 控制 |
| 积木定义 | `blocks/myrobotrun.js:925-937` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/exit_loop.png` → “退出循环” |

生成器：`generators/myrobotpythoncode.js:667-671`

生成 Python：
```python
break

```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="while_break" />
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="while_break">
</block>
```

证据级别：**A+**

### `variables_get`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 变量（动态分类 custom="VARIABLE"） |
| 积木定义 | `blocks/variables.js:47-62` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `（无类型）` |
| 视觉结构（appendField 顺序） | [变量下拉 `VAR`] |
| 字段 | `VAR` 变量下拉（引用 `<variables>` 里的变量） |

生成器：`generators/python/variables.js:32-37`

生成 Python：
```python
<变量安全名>
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="variables_get"><field name="VAR" id="%lZZ$hn^M*oIp_,)#:6r" variabletype="">var_1cm</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="variables_get">
  <field name="VAR" id="var_id_1" variabletype="">var_name</field>
</block>
```

**备注**：表达式；名字经 Blockly.Names.safeName_（ASCII 名原样保留，中文会被转成 _E5_... 之类）。

证据级别：**A+**

### `variables_set`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 变量（动态分类 custom="VARIABLE"） |
| 积木定义 | `blocks/variables.js:64-84` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | “赋值 ” → [变量下拉 `VAR`] → “ 为 ” → 〈值输入 `VALUE`，check=任意〉 |
| 字段 | `VAR` 变量下拉（引用 `<variables>` 里的变量） |
| 输入 | 值 `VALUE`（check=任意） |

生成器：`generators/python/variables.js:39-46`

生成 Python：
```python
<变量安全名> = <VALUE 或 '0'>

```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="variables_set"><field name="VAR" id="xh{|)jB=Qw*X)LD:#OkE" variabletype="">var_angle</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="variables_set">
  <field name="VAR" id="var_id_1" variabletype="">var_name</field>
  <value name="VALUE"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

证据级别：**A+**

### `math_number`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 巡线、运算 |
| 积木定义 | `blocks/math.js:47-61` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | [数字框 `NUM`: 0] |
| 字段 | `NUM` 数字框，默认 `0` |

生成器：`generators/python/math.js:35-50`

生成 Python：
```python
<数字字面量>
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="math_number"><field name="NUM">13</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="math_number">
  <field name="NUM">0</field>
</block>
```

**备注**：parseFloat；13 → 13，-5.5 → -5.5；Infinity 特殊处理。

证据级别：**A+**

### `math_op`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/myrobotrun.js:2226-2240` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | 〈值输入 `A`，check=Number〉 → [下拉 `valname`: +(+)、-(-)、*(*)、/(/)…共6项] → 〈值输入 `B`，check=Number〉 |
| 字段 | `valname` 下拉：`+`=`+` / `-`=`-` / `*`=`*` / `/`=`/` / `^`=`^` / `%`=`%` |
| 输入 | 值 `A`（check=Number）；值 `B`（check=Number） |

生成器：`generators/myrobotpythoncode.js:1055-1066`

生成 Python：
```python
+ - * / %: (<A> <operator> <B>)
^:        robot.pow(<A>, <B>)
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="math_op"><field name="valname">*</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="math_op">
  <field name="valname">+</field>
  <value name="A"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="B"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：operator 直接取字段值（+ - * / % ^），^ 特判为 robot.pow。

证据级别：**A+**

### `math_compare`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/myrobotrun.js:2243-2257` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Boolean` |
| 视觉结构（appendField 顺序） | 〈值输入 `A`，check=任意〉 → [下拉 `comparison_operator`: =(==)、!=(!=)、<(<)、<=(<=)…共6项] → 〈值输入 `B`，check=任意〉 |
| 字段 | `comparison_operator` 下拉：`=`=`==` / `!=`=`!=` / `<`=`<` / `<=`=`<=` / `>`=`>` / `>=`=`>=` |
| 输入 | 值 `A`（check=任意）；值 `B`（check=任意） |

生成器：`generators/myrobotpythoncode.js:1069-1076`

生成 Python：
```python
<A> <comparison_operator> <B>
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="math_compare"><field name="comparison_operator">&gt;=</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="math_compare">
  <field name="comparison_operator">==</field>
  <value name="A"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="B"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：comparison_operator 字段【值】是 ==/!=/</<=/>/>=（界面上显示 =/≠/</≤/>/≥）。XML 里必须写 == 等，写 '=' 会被当成不存在的选项而静默回退到第一项。

证据级别：**A+（下拉 value 语义由块定义+真实样本+生成器三方确认）**

### `logic_compare`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 巡线、AI |
| 积木定义 | `blocks/logic.js:123-153` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Boolean` |
| 视觉结构（appendField 顺序） | 〈值输入 `A`，check=任意〉 → [下拉 `OP`: =(EQ)、≠(NEQ)、‏<(LT)、‏≤(LTE)…共6项] → 〈值输入 `B`，check=任意〉 |
| 字段 | `OP` 下拉：`=`=`EQ` / `≠`=`NEQ` / `‏<`=`LT` / `‏≤`=`LTE` / `‏>`=`GT` / `‏≥`=`GTE` |
| 输入 | 值 `A`（check=任意）；值 `B`（check=任意） |

生成器：`generators/python/logic.js:56-72`

生成 Python：
```python
<A> <op> <B>   # op: EQ→==, NEQ→!=, LT→<, LTE→<=, GT→>, GTE→>=
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="logic_compare">
  <field name="OP">EQ</field>
  <value name="A"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="B"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：字段 OP 的值是 EQ/NEQ/LT/LTE/GT/GTE（不是符号本身）。

证据级别：**A**

### `logic_operation`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/logic.js:155-184` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Boolean` |
| 视觉结构（appendField 顺序） | 〈值输入 `A`，check=Boolean〉 → [下拉 `OP`: 并且(AND)、或(OR)] → 〈值输入 `B`，check=Boolean〉 |
| 字段 | `OP` 下拉：`并且`=`AND` / `或`=`OR` |
| 输入 | 值 `A`（check=Boolean）；值 `B`（check=Boolean） |

生成器：`generators/python/logic.js:74-97`

生成 Python：
```python
<A> and <B>  |  <A> or <B>
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="logic_operation"><field name="OP">OR</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="logic_operation">
  <field name="OP">AND</field>
  <value name="A"><shadow type="logic_boolean"><field name="BOOL">TRUE</field></shadow></value>
  <value name="B"><shadow type="logic_boolean"><field name="BOOL">TRUE</field></shadow></value>
</block>
```

**备注**：字段 OP = AND/OR。缺输入时补 True/False。

证据级别：**A+**

### `logic_boolean`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/logic.js:46-64` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Boolean` |
| 视觉结构（appendField 顺序） | [下拉 `BOOL`: 真(TRUE)、假(FALSE)] |
| 字段 | `BOOL` 下拉：`真`=`TRUE` / `假`=`FALSE` |

生成器：`generators/python/logic.js:107-111`

生成 Python：
```python
True  (BOOL=TRUE)
False (BOOL=FALSE)
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="logic_boolean">
  <field name="BOOL">TRUE</field>
</block>
```

**备注**：表达式。

证据级别：**A**

### `robot_math_rounding`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/myrobotrun.js:2305-2319` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | [下拉 `rounding_type`: 四舍五入(round)、向上舍入(ceil)、向下舍入(floor)] → 〈值输入 `param`，check=Number〉 |
| 字段 | `rounding_type` 下拉：`四舍五入`=`round` / `向上舍入`=`ceil` / `向下舍入`=`floor` |
| 输入 | 值 `param`（check=Number） |

生成器：`generators/myrobotpythoncode.js:1128-1140`

生成 Python：
```python
round: robot.round(<param>)
ceil:  robot.ceil(<param>)
floor: robot.floor(<param>)
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="robot_math_rounding"><field name="rounding_type">ceil</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="robot_math_rounding">
  <field name="rounding_type">round</field>
  <value name="param"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：表达式。

证据级别：**A+**

### `robot_math_unary_operation`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/myrobotrun.js:2260-2280` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | [下拉 `operation`: 平方根(sqrt)、绝对值(fabs)、-(negative)、ln(ln)…共7项] → 〈值输入 `operand`，check=Number〉 |
| 字段 | `operation` 下拉：`平方根`=`sqrt` / `绝对值`=`fabs` / `-`=`negative` / `ln`=`ln` / `log10`=`log10` / `e^`=`e^` / `10^`=`10^` |
| 输入 | 值 `operand`（check=Number） |

生成器：`generators/myrobotpythoncode.js:1079-1099`

生成 Python：
```python
sqrt:  robot.sqrt(<operand>)
fabs:  robot.abs(<operand>)
negative: -(<operand>)
ln:    robot.ln(<operand>)
log10: robot.log10(<operand>)
e^:    robot.exp(<operand>)
10^:   robot.pow(10, <operand>)
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="robot_math_unary_operation"><field name="operation">fabs</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="robot_math_unary_operation">
  <field name="operation">sqrt</field>
  <value name="operand"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：表达式。

证据级别：**A+**

### `printf_text`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 输出 |
| 积木定义 | `blocks/myrobotrun.js:535-548` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/display.png` → “显示” → [文本框 `text`: “hello world”] |
| 字段 | `text` 文本框，默认 `'hello world'` |

生成器：`generators/myrobotpythoncode.js:202-208`

生成 Python：
```python
robot.print('<text 中的单引号转义为 \'>\n')

```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="printf_text"><field name="text">hello world</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="printf_text">
  <field name="text">hello world</field>
</block>
```

**备注**：注意生成的是字符串里带 \n 的换行。

证据级别：**A+**

### `printf_number`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 输出 |
| 积木定义 | `blocks/myrobotrun.js:551-565` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/display.png` “显示” [文本框 `dataname`: “data=”] 〈值输入 `data`，check=任意〉 |
| 字段 | `dataname` 文本框，默认 `'data='` |
| 输入 | 值 `data`（check=任意） |

生成器：`generators/myrobotpythoncode.js:211-222`

生成 Python：
```python
robot.print('<dataname> ' + str(<data>) + '\n')

```

最小合法 XML（真实样本，来自 `实验` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="printf_number"><field name="dataname">黑线S2</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="printf_number">
  <field name="dataname">data=</field>
  <value name="data"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：dataname 后面固定带一个空格。

证据级别：**A+**

### `play_sound`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 声光 |
| 积木定义 | `blocks/myrobotrun.js:620-634` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/speaker.png` → “播放” → [下拉 `musicname`: 打招呼-你好(dazhaohu_c0.mp3)、打招呼-再见(dazhaohu_c1.mp3)、打招呼-反对(dazhaohu_c2.mp3)、打招呼-欢迎(dazhaohu_c3.mp3)…共78项] |
| 字段 | `musicname` 下拉：`打招呼-你好`=`dazhaohu_c0.mp3` / `打招呼-再见`=`dazhaohu_c1.mp3` / `打招呼-反对`=`dazhaohu_c2.mp3` / `打招呼-欢迎`=`dazhaohu_c3.mp3` / `打招呼-请多关照`=`dazhaohu_c4.mp3` / `动物海豹`=`dongwu_p0.mp3` / `动物鹦鹉`=`dongwu_p1.mp3` / `动物青蛙`=`dongwu_p2.mp3` / `动物羊`=`dongwu_p3.mp3` / `动物鸡`=`dongwu_p4.mp3` / `动物鸭子`=`dongwu_p5.mp3` / `动物狗`=`dongwu_p6.mp3` / `动物天鹅`=`dongwu_p7.mp3` / `动物蜜蜂`=`dongwu_p8.mp3` / `交通摩托车`=`jiaotong_p0.mp3` / `交通赛车`=`jiaotong_p1.mp3` / `交通火车`=`jiaotong_p2.mp3` / `交通汽车`=`jiaotong_p3.mp3` / `交通飞机`=`jiaotong_p4.mp3` / `交通轮船`=`jiaotong_p5.mp3` / `交通自行车`=`jiaotong_p6.mp3` / `交通直升机`=`jiaotong_p7.mp3` / `钢琴-do`=`gangqin_p0.mp3` / `钢琴-ri`=`gangqin_p1.mp3` / `钢琴-mi`=`gangqin_p2.mp3` / `钢琴-fa`=`gangqin_p3.mp3` / `钢琴-so`=`gangqin_p4.mp3` / `钢琴-la`=`gangqin_p5.mp3` / `钢琴-si`=`gangqin_p6.mp3` / `钢琴-Hdo`=`gangqin_p7.mp3` / `表情生气`=`biaoqing_c0.mp3` / `表情傲慢`=`biaoqing_c1.mp3` / `表情哭泣`=`biaoqing_c2.mp3` / `表情激动`=`biaoqing_c3.mp3` / `表情惊吓`=`biaoqing_c4.mp3` / `表情委屈`=`biaoqing_c5.mp3` / `表情高兴`=`biaoqing_c6.mp3` / `表情可爱`=`biaoqing_c7.mp3` / `表情大笑`=`biaoqing_c8.mp3` / `表情悲伤`=`biaoqing_c9.mp3` / `表情愤怒`=`biaoqing_c10.mp3` / `表情调皮`=`biaoqing_c11.mp3` / `动作打寒颤`=`dongzuo_c0.mp3` / `动作卖萌`=`dongzuo_c1.mp3` / `动作赞成`=`dongzuo_c2.mp3` / `动作求抱抱`=`dongzuo_c3.mp3` / `动作打哈欠`=`dongzuo_c4.mp3` / `动作加油`=`dongzuo_c5.mp3` / `动作睡觉`=`dongzuo_c6.mp3` / `动作休息`=`dongzuo_c7.mp3` / `动作鬼鬼祟祟`=`dongzuo_c8.mp3` / `小提琴-1`=`xiaotiqin_p0.mp3` / `小提琴-2`=`xiaotiqin_p1.mp3` / `小提琴-3`=`xiaotiqin_p2.mp3` / `小提琴-4`=`xiaotiqin_p3.mp3` / `小提琴-5`=`xiaotiqin_p4.mp3` / `小提琴-6`=`xiaotiqin_p5.mp3` / `小提琴-7`=`xiaotiqin_p6.mp3` / `小提琴-8`=`xiaotiqin_p7.mp3` / `架子鼓低音大鼓`=`jiazigu_p0.mp3` / `架子鼓军鼓`=`jiazigu_p1.mp3` / `架子鼓落地鼓`=`jiazigu_p2.mp3` / `架子鼓嗵嗵鼓1`=`jiazigu_p3.mp3` / `架子鼓嗵嗵鼓2`=`jiazigu_p4.mp3` / `架子鼓踩镲`=`jiazigu_p5.mp3` / `架子鼓吊镲`=`jiazigu_p6.mp3` / `架子鼓节奏镲`=`jiazigu_p7.mp3` / `架子鼓镲片`=`jiazigu_p8.mp3` / `录音-1`=`luyin_p1` / `录音-2`=`luyin_p2` / `录音-3`=`luyin_p3` / `录音-4`=`luyin_p4` / `录音-5`=`luyin_p5` / `录音-6`=`luyin_p5` / `录音-7`=`luyin_p7` / `录音-8`=`luyin_p8` / `录音-9`=`luyin_p9` / `录音-10`=`luyin_p10` |

生成器：`generators/myrobotpythoncode.js:254-259`

生成 Python：
```python
robot.play('<musicname>')

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="play_sound">
  <field name="musicname">dazhaohu_c0.mp3</field>
</block>
```

**备注**：musicname 是 PlayList 的值（如 luyin_p2、dongwu_p0.mp3）。

证据级别：**A+**

### `procedures_defnoreturn`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | （不在 SKCON9 静态工具箱） |
| 积木定义 | `blocks/procedures.js:33-391` |
| 连接 | 前连接(previous)❌；后连接(next)❌；无输出 |
| 视觉结构（appendField 顺序） | “函数” → [文本框 `NAME`: “”] → [动态字段 `PARAMS`] → ⟦语句输入 `STACK`⟧ |
| 字段 | `NAME` 文本框，默认 `''` |
| 输入 | 语句 `STACK` |

生成器：`generators/python/procedures.js:32-88`（Blockly.Python['procedures_defreturn']（procedures_defnoreturn 在第 92-93 行直接别名到它））

生成 Python：
```python
def <NAME>(<参数名, 逗号分隔>):
    global <工作区用到的变量名, 排除参数名>
    <STACK 语句代码>
    pass                          # 生成器总会在函数体末尾追加一个 pass

```

**mutation 结构（参数化）**：
```xml
<mutation><arg name="cm" varid="PARAM_VAR_ID_OPTIONAL"></arg></mutation>
```
- 无参数可完全省略 <mutation>
- 参数名必须 ASCII；界面被禁用改参数（setMutator 被注释，blocks/procedures.js:47 附近），但 XML 加载会走 domToMutation 恢复参数
- domToMutation 会为每个 arg 调 Blockly.Variables.getOrCreateVariablePackage(workspace, varid, name, '') 创建/复用变量，之后函数体内用 variables_get 引用参数名即可
- 建议把参数变量也声明进 <variables>（如 <variable type="" id="PARAM_VAR_ID">cm</variable>），并让 mutation 的 varid 与之一致；不声明也能加载（会现场创建变量）
- 保存时 def 的 mutation 不带 name 属性（name 在 <field name="NAME">）；mutationToDom(true) 才带 name，仅用于内部 mutateCallers

带参数示例：
```xml
<block type="procedures_defnoreturn" x="0" y="0">
  <mutation><arg name="cm" varid="v_param_cm"></arg></mutation>
  <field name="NAME">func_MoveForward</field>
  <statement name="STACK">
    <block type="motor">
      <field name="channel">1</field>
      <value name="speed"><block type="variables_get"><field name="VAR" id="v_param_cm" variabletype="">cm</field></block></value>
    </block>
  </statement>
</block>
```

无参数示例：
```xml
<block type="procedures_defnoreturn" x="0" y="0"><field name="NAME">func_Stop</field><statement name="STACK"></statement></block>
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="procedures_defnoreturn"><field name="NAME">func_end</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="procedures_defnoreturn" x="0" y="0"><field name="NAME">func_Stop</field><statement name="STACK"></statement></block>
```

**备注**：生成到 Blockly.Python.definitions_['%'+name]，排在 main 之前。procedures_defnoreturn 与 procedures_defreturn 共用同一个生成器。

证据级别：**A+（参数化 mutation 已由 harness headless 实测通过：加载/flyout 调用块/ARG0/Python 生成/py_compile 16/16 PASS；证据 工具/验证/证据/参数化函数/20261110_131824_param_test.report.txt）**

### `procedures_callnoreturn`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | （不在 SKCON9 静态工具箱） |
| 积木定义 | `blocks/procedures.js:626-972` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | [动态字段 `NAME`] → [动态字段 `WITH`] → 〈值输入 `ARG0`，check=任意〉 |
| 字段 | `NAME`（不需要在 XML 写；由 <mutation name=...> 恢复） |
| 输入 | 值 `ARG0`（check=任意）；值 `ARG1`（check=任意）；值 `ARGn`（check=任意） |

生成器：`generators/python/procedures.js:108-119`

生成 Python：
```python
<NAME>(<ARG0>, <ARG1>, ...)

```

**mutation 结构（参数化）**：
```xml
<mutation name="func_MoveForward"><arg name="cm"></arg></mutation>
```
- 无参数：<mutation name="func_x"></mutation>（真实样本即这种形式）
- 有参数：arg 顺序/名字必须与 def 的 mutation 完全一致；否则调用块的 onchange 会认为签名不符并自动新建同名 def 块（会重复定义）
- paramId 属性可省（真实样本没有）；domToMutation 对 null paramId 也能正确建出 ARG0.. 输入

带参数示例：
```xml
<block type="procedures_callnoreturn"><mutation name="func_MoveForward"><arg name="cm"></arg></mutation><value name="ARG0"><block type="math_number"><field name="NUM">30</field></block></value></block>
```

无参数示例：
```xml
<block type="procedures_callnoreturn"><mutation name="func_Stop"></mutation></block>
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="procedures_callnoreturn"><mutation name="func_forward" /></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="procedures_callnoreturn"><mutation name="func_Stop"></mutation></block>
```

**备注**：缺参数的输入位置生成 None。调用块字段 NAME 由 <mutation name> 恢复，不需要 <field name="NAME">。

证据级别：**A+**

## 5. 其余常用块规格（25 个）

### `servoa_angle`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运动 |
| 积木定义 | `blocks/myrobotrun.js:236-257` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic\block_icon\intelligent_motor.png` → “智能电机” → [下拉 `channel`: ID1(1)、ID2(2)、ID3(3)、ID4(4)…共12项] → “速度” 〈值输入 `speed`，check=Number〉 → “%” → “角度-90~90” 〈值输入 `angle`，check=Number〉 |
| 字段 | `channel` 下拉：`ID1`=`1` / `ID2`=`2` / `ID3`=`3` / `ID4`=`4` / `ID5`=`5` / `ID6`=`6` / `ID7`=`7` / `ID8`=`8` / `ID9`=`9` / `ID10`=`10` / `ID11`=`11` / `所有智能电机`=`254` |
| 输入 | 值 `speed`（check=Number）；值 `angle`（check=Number） |

生成器：`generators/myrobotpythoncode.js:155-164`

生成 Python：
```python
robot.set_servo(<channel>, robot.clamp(<speed>, 0, 100), robot.clamp(<angle>, -90, 90))

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="servoa_angle">
  <field name="channel">1</field>
  <value name="speed"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="angle"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：channel 是字符串直接拼入（不转 Number）。

证据级别：**A+**

### `set_do`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 输出 |
| 积木定义 | `blocks/myrobotrun.js:518-532` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/digital_output.png` → “数字输出” → [下拉 `PORT`: 端口1(1)、端口2(2)、端口3(3)、端口4(4)…共12项] → [下拉 `STATE`: OFF(0)、ON(1)] |
| 字段 | `PORT` 下拉：`端口1`=`1` / `端口2`=`2` / `端口3`=`3` / `端口4`=`4` / `端口5`=`5` / `端口6`=`6` / `端口7`=`7` / `端口8`=`8` / `端口9`=`9` / `端口10`=`10` / `端口11`=`11` / `端口12`=`12`<br>`STATE` 下拉：`OFF`=`0` / `ON`=`1` |

生成器：`generators/myrobotpythoncode.js:193-199`

生成 Python：
```python
robot.set_do(<PORT>, <STATE>)

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="set_do">
  <field name="PORT">1</field>
  <field name="STATE">0</field>
</block>
```

**备注**：STATE: 0=OFF, 1=ON。

证据级别：**A+**

### `set_electric_magnet`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运动 |
| 积木定义 | `blocks/myrobotrun.js:259-276` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic\block_icon\electromagnet.png` → “电磁铁” → [下拉 `channel`: 端口1(1)、端口2(2)、端口3(3)、端口4(4)…共12项] → [下拉 `status`: 吸合(1)、断开(0)] |
| 字段 | `channel` 下拉：`端口1`=`1` / `端口2`=`2` / `端口3`=`3` / `端口4`=`4` / `端口5`=`5` / `端口6`=`6` / `端口7`=`7` / `端口8`=`8` / `端口9`=`9` / `端口10`=`10` / `端口11`=`11` / `端口12`=`12`<br>`status` 下拉：`吸合`=`1` / `断开`=`0` |

生成器：`generators/myrobotpythoncode.js:166-171`

生成 Python：
```python
robot.set_do(<channel>, <status>)

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="set_electric_magnet">
  <field name="channel">1</field>
  <field name="status">1</field>
</block>
```

**备注**：电磁铁复用 robot.set_do；status: 1=吸合, 0=断开。

证据级别：**A+**

### `printf_lines`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 输出 |
| 积木定义 | `blocks/myrobotrun.js:568-582` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/display.png` → “多行显示” → ⟦语句输入 `code`⟧ |
| 输入 | 语句 `code` |

生成器：`generators/myrobotpythoncode.js:225-234`

生成 Python：
```python
robot.clear()
if True:
<语句输入 code>

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="printf_lines">
</block>
```

**备注**：多行显示 = 先 clear 再显示。

证据级别：**A+**

### `wait_until`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 控制 |
| 积木定义 | `blocks/myrobotrun.js:907-922` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/delay.png` “等待直到” 〈值输入 `bool`，check=Boolean〉 → “继续” |
| 输入 | 值 `bool`（check=Boolean） |

生成器：`generators/myrobotpythoncode.js:658-664`

生成 Python：
```python
while not <bool>:
    pass

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="wait_until">
  <value name="bool"><shadow type="logic_boolean"><field name="BOOL">TRUE</field></shadow></value>
</block>
```

**备注**：固定只生成 pass 死等（没有 body）。

证据级别：**A+**

### `logic_negate`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/logic.js:186-202` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Boolean` |
| 视觉结构（appendField 顺序） | “非” → 〈值输入 `BOOL`，check=Boolean〉 |
| 输入 | 值 `BOOL`（check=Boolean） |

生成器：`generators/python/logic.js:99-105`

生成 Python：
```python
not <BOOL>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="logic_negate">
  <value name="BOOL"><shadow type="logic_boolean"><field name="BOOL">TRUE</field></shadow></value>
</block>
```

**备注**：表达式。

证据级别：**A**

### `math_modulo`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/math.js:295-316` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | “取 ” → 〈值输入 `DIVIDEND`，check=Number〉 → “ ÷ ” → 〈值输入 `DIVISOR`，check=Number〉 → “ 的余数” |
| 输入 | 值 `DIVIDEND`（check=Number）；值 `DIVISOR`（check=Number） |

生成器：`generators/python/math.js:371-379`

生成 Python：
```python
<DIVIDEND> % <DIVISOR>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="math_modulo">
  <value name="DIVIDEND"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="DIVISOR"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：表达式。

证据级别：**A**

### `robot_math_constants`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/myrobotrun.js:2431-2444` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | [下拉 `constant_type`: sqrt(2)(sqrt(2))、sqrt(1/2)(sqrt(1/2))] |
| 字段 | `constant_type` 下拉：`sqrt(2)`=`sqrt(2)` / `sqrt(1/2)`=`sqrt(1/2)` |

生成器：`generators/myrobotpythoncode.js:1196-1215`

生成 Python：
```python
sqrt(2)    → robot.sqrt(2)
sqrt(1/2)  → robot.sqrt(1 / 2)
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="robot_math_constants">
  <field name="constant_type">sqrt(2)</field>
</block>
```

**备注**：当前下拉只有 sqrt(2)/sqrt(1/2)；源码另有 pi→robot.pi()、e→robot.e() 分支，但选项被注释掉了（XML 里写 pi/e 无效）。

证据级别：**A+**

### `get_encoder_real_time_value`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 传感 |
| 积木定义 | `blocks/myrobotrun.js:1407-1419` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/motor_encoder.png` → “获取电机编码器实时值” → [下拉 `port`: 端口A(1)、端口B(2)、端口C(3)、端口D(4)] |
| 字段 | `port` 下拉：`端口A`=`1` / `端口B`=`2` / `端口C`=`3` / `端口D`=`4` |

生成器：`generators/myrobotpythoncode.js:500-513`

生成 Python：
```python
SKCON9/其它: robot.get_instant_incoder(<port>)
SKCON2:      robot.get_instant_encoder(<port>)
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="get_encoder_real_time_value">
  <field name="port">1</field>
</block>
```

**备注**：注意 SKCON9 分支的 'incoder' 是固件拼写，必须照抄。输出表达式。

证据级别：**A+**

### `getai_sonic`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 传感 |
| 积木定义 | `blocks/myrobotrun.js:1037-1050` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/ultrasonic.png` → “超声” → [下拉 `channel`: 端口1(1)、端口2(2)、端口3(3)、端口4(4)…共12项] → “测距” |
| 字段 | `channel` 下拉：`端口1`=`1` / `端口2`=`2` / `端口3`=`3` / `端口4`=`4` / `端口5`=`5` / `端口6`=`6` / `端口7`=`7` / `端口8`=`8` / `端口9`=`9` / `端口10`=`10` / `端口11`=`11` / `端口12`=`12` |

生成器：`generators/myrobotpythoncode.js:362-367`

生成 Python：
```python
robot.get_ultra_sonic(<channel>)
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="getai_sonic">
  <field name="channel">1</field>
</block>
```

**备注**：输出表达式

证据级别：**A+**

### `get_sonic_detect_object`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 传感 |
| 积木定义 | `blocks/myrobotrun.js:1053-1066` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Boolean` |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/ultrasonic.png` → “超声” → [下拉 `port`: 端口1(1)、端口2(2)、端口3(3)、端口4(4)…共12项] → “探测到物体” |
| 字段 | `port` 下拉：`端口1`=`1` / `端口2`=`2` / `端口3`=`3` / `端口4`=`4` / `端口5`=`5` / `端口6`=`6` / `端口7`=`7` / `端口8`=`8` / `端口9`=`9` / `端口10`=`10` / `端口11`=`11` / `端口12`=`12` |

生成器：`generators/myrobotpythoncode.js:370-376`

生成 Python：
```python
(robot.get_ultra_sonic(<port>) > 50 and robot.get_ultra_sonic(<port>) < 200)
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="get_sonic_detect_object">
  <field name="port">1</field>
</block>
```

**备注**：输出 Boolean；固定 50~200 区间，没有可调阈值。

证据级别：**A+**

### `getmseconds`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 传感 |
| 积木定义 | `blocks/myrobotrun.js:1439-1451` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/timer.png` → [下拉 `timer_ID`: 计时器1(1)、计时器2(2)、计时器3(3)、计时器4(4)…共12项] → “的读数(毫秒)” |
| 字段 | `timer_ID` 下拉：`计时器1`=`1` / `计时器2`=`2` / `计时器3`=`3` / `计时器4`=`4` / `计时器5`=`5` / `计时器6`=`6` / `计时器7`=`7` / `计时器8`=`8` / `计时器9`=`9` / `计时器10`=`10` / `计时器11`=`11` / `计时器12`=`12` |

生成器：`generators/myrobotpythoncode.js:532-537`

生成 Python：
```python
robot.get_timer_ms(<timer_ID>)
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="getmseconds">
  <field name="timer_ID">1</field>
</block>
```

**备注**：表达式。

证据级别：**A+**

### `getmsecondsreset`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 传感 |
| 积木定义 | `blocks/myrobotrun.js:1423-1436` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/timer.png` → [下拉 `timer_ID`: 计时器1(1)、计时器2(2)、计时器3(3)、计时器4(4)…共12项] → “清零” |
| 字段 | `timer_ID` 下拉：`计时器1`=`1` / `计时器2`=`2` / `计时器3`=`3` / `计时器4`=`4` / `计时器5`=`5` / `计时器6`=`6` / `计时器7`=`7` / `计时器8`=`8` / `计时器9`=`9` / `计时器10`=`10` / `计时器11`=`11` / `计时器12`=`12` |

生成器：`generators/myrobotpythoncode.js:524-529`

生成 Python：
```python
robot.reset_timer(<timer_ID>)

```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="getmsecondsreset"><field name="timer_ID">1</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="getmsecondsreset">
  <field name="timer_ID">1</field>
</block>
```

证据级别：**A+**

### `eeprom_write`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 传感 |
| 积木定义 | `blocks/myrobotrun.js:1470-1486` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/read_and_write_data.png` → “写入数据 地址” → [数字框 `address`: 1] → “=” 〈值输入 `data`，check=Number〉 |
| 字段 | `address` 数字框，默认 `1` |
| 输入 | 值 `data`（check=Number） |

生成器：`generators/myrobotpythoncode.js:548-554`

生成 Python：
```python
robot.set_ee(<address>, robot.clamp(<data>, -99999, 99999))

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="eeprom_write">
  <field name="address">1</field>
  <value name="data"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

证据级别：**A+**

### `get_key`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | （不在 SKCON9 工具箱；blocks/ 中定义存在，应属 SKCON2/5 或旧版遗留，函数库不要用） |
| 积木定义 | `blocks/myrobotrun.js:1101-1114` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/key.png` → “Start按键” → [下拉 `port`: Enter键(1)、Left键(2)、Right键(3)] → “被按下” |
| 字段 | `port` 下拉：`Enter键`=`1` / `Left键`=`2` / `Right键`=`3` |

生成器：`generators/myrobotpythoncode.js:1252-1258`

生成 Python：
```python
robot.check_key(<port>)
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="get_key">
  <field name="port">1</field>
</block>
```

**备注**：表达式；port: 1=Enter, 2=Left, 3=Right。

证据级别：**A+**

### `math_change`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 变量（动态分类 custom="VARIABLE"） |
| 积木定义 | `blocks/math.js:213-233` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | “将 ” → [变量下拉 `VAR`] → “ 增加 ” → 〈值输入 `DELTA`，check=Number〉 |
| 字段 | `VAR` 变量下拉（引用 `<variables>` 里的变量） |
| 输入 | 值 `DELTA`（check=Number） |

生成器：`generators/python/math.js:240-262`

生成 Python：
```python
from numbers import Number
<var> = (<var> if isinstance(<var>, Number) else 0) + <DELTA>

```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="math_change"><field name="VAR" id="Usgx-)nm)).0rG9ni-(c" variabletype="">var_speed</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="math_change">
  <field name="VAR" id="var_id_1" variabletype="">var_name</field>
  <value name="DELTA"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：会在 definitions_ 里追加 import 'from numbers import Number'（出现即置顶）。

证据级别：**A+**

### `procedures_defreturn`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | （不在 SKCON9 静态工具箱） |
| 积木定义 | `blocks/procedures.js:393-448` |
| 连接 | 前连接(previous)❌；后连接(next)❌；无输出 |
| 视觉结构（appendField 顺序） | “函数（有返回值）” → [文本框 `NAME`: “”] → [动态字段 `PARAMS`] → “返回” 〈值输入 `RETURN`，check=任意〉 → ⟦语句输入 `STACK`⟧ |
| 字段 | `NAME` 文本框，默认 `''` |
| 输入 | 值 `RETURN`（check=任意）；语句 `STACK` |

生成器：`generators/python/procedures.js:32-88`（Blockly.Python['procedures_defreturn']）

生成 Python：
```python
def <NAME>(<参数名>):
    global <工作区用到的变量名, 排除参数名>
    <STACK 语句代码>
    pass
    return <RETURN 值输入>          # 仅当 RETURN 有连接时才生成

```

**mutation 结构（参数化）**：
```xml
<mutation><arg name="cm"></arg></mutation>
```
- 与 defnoreturn 共用的 domToMutation/mutationToDom（blocks/procedures.js:426-427）
- 该块的参数 mutator 在 IDE 里是【可用】的（未注释 setMutator），但工具箱不再提供“新建返回函数”积木；只能通过 XML 载入
- core/procedures.js:114-127 的“新建”入口被注释；但 flyoutCategory 第 166 行仍会对已有 defreturn 生成 procedures_callreturn 调用块（在“函数”分类可见）

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="procedures_defreturn" x="0" y="0">
  <mutation><arg name="cm"></arg></mutation>
  <field name="NAME">func_Distance</field>
  <statement name="STACK"><block type="motor"><field name="channel">1</field><value name="speed"><block type="variables_get"><field name="VAR" id="PARAM_VAR_ID" variabletype="">cm</field></block></value></block></statement>
  <value name="RETURN"><block type="getencoder"><field name="port">1</field></block></value>
</block>
```

**备注**：函数声明与 defnoreturn 共用生成器；RETURN 是值输入。飞函数分类的“新建返回函数”入口被注释，但 XML 加载/生成完全支持。

证据级别：**A（块定义+生成器源码可证；工具箱不提供新建，仅 XML 载入；flyout 调用块渲染未单独实测 → B 级待验证）**

### `block_conststring`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | AI、运算 |
| 积木定义 | `blocks/myrobotrun.js:2210-2222` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `null` |
| 视觉结构（appendField 顺序） | “"” → [文本框 `NAME`: “string”] → “"” |
| 字段 | `NAME` 文本框，默认 `'string'` |

生成器：`generators/myrobotpythoncode.js:1046-1052`

生成 Python：
```python
'<NAME 中的单引号转义>'

```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="block_conststring"><field name="NAME">右</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="block_conststring">
  <field name="NAME">string</field>
</block>
```

**备注**：表达式（字符串常量）。

证据级别：**A+**

### `printf`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 输出 |
| 积木定义 | `blocks/myrobotrun.js:584-597` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/display.png` “显示” 〈值输入 `para1`，check=任意〉 |
| 输入 | 值 `para1`（check=任意） |

生成器：`generators/myrobotpythoncode.js:237-243`

生成 Python：
```python
robot.print(<para1>, '\n')

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="printf">
  <value name="para1"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：值输入 para1 直接作为 print 第一个参数。

证据级别：**A+**

### `printf_emoji`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 输出 |
| 积木定义 | `blocks/myrobotrun.js:600-613` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/display.png` → “显示表情” → [下拉 `emoji_name`: 胆小(danxiao)、高兴(gaoxing)、加油(jiayou)、可爱(keai)…共7项] |
| 字段 | `emoji_name` 下拉：`胆小`=`danxiao` / `高兴`=`gaoxing` / `加油`=`jiayou` / `可爱`=`keai` / `哭泣`=`kuqi` / `委屈`=`weiqu` / `眨眼`=`zhayanjing` |

生成器：`generators/myrobotpythoncode.js:246-251`

生成 Python：
```python
robot.print_expression('<emoji_name>')

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="printf_emoji">
  <field name="emoji_name">danxiao</field>
</block>
```

**备注**：emoji_name 取值为 danxiao/gaoxing/jiayou/keai/kuqi/weiqu/zhayanjing。

证据级别：**A+**

### `play_sound_until`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 声光 |
| 积木定义 | `blocks/myrobotrun.js:636-651` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/speaker.png` → “播放” → [下拉 `musicname`: 打招呼-你好(dazhaohu_c0.mp3)、打招呼-再见(dazhaohu_c1.mp3)、打招呼-反对(dazhaohu_c2.mp3)、打招呼-欢迎(dazhaohu_c3.mp3)…共78项] → “直到播放完毕” |
| 字段 | `musicname` 下拉：`打招呼-你好`=`dazhaohu_c0.mp3` / `打招呼-再见`=`dazhaohu_c1.mp3` / `打招呼-反对`=`dazhaohu_c2.mp3` / `打招呼-欢迎`=`dazhaohu_c3.mp3` / `打招呼-请多关照`=`dazhaohu_c4.mp3` / `动物海豹`=`dongwu_p0.mp3` / `动物鹦鹉`=`dongwu_p1.mp3` / `动物青蛙`=`dongwu_p2.mp3` / `动物羊`=`dongwu_p3.mp3` / `动物鸡`=`dongwu_p4.mp3` / `动物鸭子`=`dongwu_p5.mp3` / `动物狗`=`dongwu_p6.mp3` / `动物天鹅`=`dongwu_p7.mp3` / `动物蜜蜂`=`dongwu_p8.mp3` / `交通摩托车`=`jiaotong_p0.mp3` / `交通赛车`=`jiaotong_p1.mp3` / `交通火车`=`jiaotong_p2.mp3` / `交通汽车`=`jiaotong_p3.mp3` / `交通飞机`=`jiaotong_p4.mp3` / `交通轮船`=`jiaotong_p5.mp3` / `交通自行车`=`jiaotong_p6.mp3` / `交通直升机`=`jiaotong_p7.mp3` / `钢琴-do`=`gangqin_p0.mp3` / `钢琴-ri`=`gangqin_p1.mp3` / `钢琴-mi`=`gangqin_p2.mp3` / `钢琴-fa`=`gangqin_p3.mp3` / `钢琴-so`=`gangqin_p4.mp3` / `钢琴-la`=`gangqin_p5.mp3` / `钢琴-si`=`gangqin_p6.mp3` / `钢琴-Hdo`=`gangqin_p7.mp3` / `表情生气`=`biaoqing_c0.mp3` / `表情傲慢`=`biaoqing_c1.mp3` / `表情哭泣`=`biaoqing_c2.mp3` / `表情激动`=`biaoqing_c3.mp3` / `表情惊吓`=`biaoqing_c4.mp3` / `表情委屈`=`biaoqing_c5.mp3` / `表情高兴`=`biaoqing_c6.mp3` / `表情可爱`=`biaoqing_c7.mp3` / `表情大笑`=`biaoqing_c8.mp3` / `表情悲伤`=`biaoqing_c9.mp3` / `表情愤怒`=`biaoqing_c10.mp3` / `表情调皮`=`biaoqing_c11.mp3` / `动作打寒颤`=`dongzuo_c0.mp3` / `动作卖萌`=`dongzuo_c1.mp3` / `动作赞成`=`dongzuo_c2.mp3` / `动作求抱抱`=`dongzuo_c3.mp3` / `动作打哈欠`=`dongzuo_c4.mp3` / `动作加油`=`dongzuo_c5.mp3` / `动作睡觉`=`dongzuo_c6.mp3` / `动作休息`=`dongzuo_c7.mp3` / `动作鬼鬼祟祟`=`dongzuo_c8.mp3` / `小提琴-1`=`xiaotiqin_p0.mp3` / `小提琴-2`=`xiaotiqin_p1.mp3` / `小提琴-3`=`xiaotiqin_p2.mp3` / `小提琴-4`=`xiaotiqin_p3.mp3` / `小提琴-5`=`xiaotiqin_p4.mp3` / `小提琴-6`=`xiaotiqin_p5.mp3` / `小提琴-7`=`xiaotiqin_p6.mp3` / `小提琴-8`=`xiaotiqin_p7.mp3` / `架子鼓低音大鼓`=`jiazigu_p0.mp3` / `架子鼓军鼓`=`jiazigu_p1.mp3` / `架子鼓落地鼓`=`jiazigu_p2.mp3` / `架子鼓嗵嗵鼓1`=`jiazigu_p3.mp3` / `架子鼓嗵嗵鼓2`=`jiazigu_p4.mp3` / `架子鼓踩镲`=`jiazigu_p5.mp3` / `架子鼓吊镲`=`jiazigu_p6.mp3` / `架子鼓节奏镲`=`jiazigu_p7.mp3` / `架子鼓镲片`=`jiazigu_p8.mp3` / `录音-1`=`luyin_p1` / `录音-2`=`luyin_p2` / `录音-3`=`luyin_p3` / `录音-4`=`luyin_p4` / `录音-5`=`luyin_p5` / `录音-6`=`luyin_p5` / `录音-7`=`luyin_p7` / `录音-8`=`luyin_p8` / `录音-9`=`luyin_p9` / `录音-10`=`luyin_p10` |

生成器：`generators/myrobotpythoncode.js:262-267`

生成 Python：
```python
robot.play_until('<musicname>')

```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="play_sound_until">
  <field name="musicname">dazhaohu_c0.mp3</field>
</block>
```

证据级别：**A+**

### `record`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 声光 |
| 积木定义 | `blocks/myrobotrun.js:653-679` |
| 连接 | 前连接(previous)✅；后连接(next)✅；无输出 |
| 视觉结构（appendField 顺序） | 🖼 `pic/block_icon/record.png` → “录音” → [数字框 `record_time`: 5] → “秒” → “保存为文件” → [下拉 `record_ID`: 1(1)、2(2)、3(3)、4(4)…共10项] |
| 字段 | `record_time` 数字框，默认 `5`<br>`record_ID` 下拉：`1`=`1` / `2`=`2` / `3`=`3` / `4`=`4` / `5`=`5` / `6`=`6` / `7`=`7` / `8`=`8` / `9`=`9` / `10`=`10` |

生成器：`generators/myrobotpythoncode.js:270-276`

生成 Python：
```python
robot.record_audio(<record_ID>, <record_time>)

```

最小合法 XML（真实样本，来自 `Scratch-3` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="record"><field name="record_time">5</field><field name="record_ID">2</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="record">
  <field name="record_time">5</field>
  <field name="record_ID">1</field>
</block>
```

证据级别：**A+**

### `robot_math_trigonometric_function`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/myrobotrun.js:2283-2302` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Number` |
| 视觉结构（appendField 顺序） | [下拉 `trigonometric_function_type`: sin(sin)、cos(cos)、tan(tan)、asin(asin)…共6项] → 〈值输入 `param`，check=Number〉 |
| 字段 | `trigonometric_function_type` 下拉：`sin`=`sin` / `cos`=`cos` / `tan`=`tan` / `asin`=`asin` / `acos`=`acos` / `atan`=`atan` |
| 输入 | 值 `param`（check=Number） |

生成器：`generators/myrobotpythoncode.js:1102-1125`

生成 Python：
```python
sin/cos/tan: robot.sin|cos|tan(<param> / 180.0 * robot.pi())
asin/acos/atan: robot.asin|acos|atan(<param>) / robot.pi() * 180.0
```

最小合法 XML（真实样本，来自 `PI` 项目，已清理 xmlns/坐标/disabled）：
```xml
<block type="robot_math_trigonometric_function"><field name="trigonometric_function_type">sin</field></block>
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="robot_math_trigonometric_function">
  <field name="trigonometric_function_type">sin</field>
  <value name="param"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：SKCON9 用 robot.pi()；SKCON2 用 robot.pi（无括号）。表达式。

证据级别：**A+**

### `robot_math_random`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/myrobotrun.js:2390-2428` |
| 连接 | 前连接(previous)❌；后连接(next)❌；无输出 |
| 视觉结构（appendField 顺序） | “从” → 〈值输入 `FROM`，check=Number〉 → “ 到 ” → 〈值输入 `TO`，check=Number〉 → “ 范围内的随机整数” |
| 输入 | 值 `FROM`（check=Number）；值 `TO`（check=Number） |

生成器：`generators/myrobotpythoncode.js:1185-1193`

生成 Python：
```python
robot.random(<FROM>, <TO>)
```

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="robot_math_random">
  <value name="FROM"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="TO"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：表达式。

证据级别：**A+**

### `abilix_math_number_property`

| 项 | 内容 |
|---|---|
| SKCON9 分类 | 运算 |
| 积木定义 | `blocks/myrobotrun.js:2321-2387` |
| 连接 | 前连接(previous)❌；后连接(next)❌；输出 `Boolean` |
| 视觉结构（appendField 顺序） | 〈值输入 `NUMBER_TO_CHECK`，check=Number〉 → [下拉 `PROPERTY`: 是偶数(EVEN)、是奇数(ODD)、是质数(PRIME)、是整数(WHOLE)…共7项] → 〈值输入 `DIVISOR`，check=Number〉 |
| 字段 | `PROPERTY` 下拉：`是偶数`=`EVEN` / `是奇数`=`ODD` / `是质数`=`PRIME` / `是整数`=`WHOLE` / `是正数`=`POSITIVE` / `是负数`=`NEGATIVE` / `可被整除`=`DIVISIBLE_BY` |
| 输入 | 值 `NUMBER_TO_CHECK`（check=Number）；值 `DIVISOR`（check=Number） |

生成器：`generators/myrobotpythoncode.js:1142-1183`

生成 Python：
```python
EVEN: <N> % 2 == 0
ODD: <N> % 2 == 1
PRIME: robot.isprime(<N>)
WHOLE: <N> % 1 == 0
POSITIVE: <N> > 0
NEGATIVE: <N> < 0
DIVISIBLE_BY: <N> % <DIVISOR> == 0
```

**mutation 结构（参数化）**：
```xml
<mutation divisor_input="true"></mutation>
```
- 仅当 PROPERTY=DIVISIBLE_BY 时需要；为 true 时块上才出现 DIVISOR 值输入，否则没有该输入
- domToMutation 读属性 divisor_input=='true'；保存时 mutationToDom 会写该属性

构造版最小合法 XML（字段齐全 + 值输入用 shadow 默认值；语句输入留空）：
```xml
<block type="abilix_math_number_property">
  <field name="PROPERTY">EVEN</field>
  <value name="NUMBER_TO_CHECK"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
  <value name="DIVISOR"><shadow type="math_number"><field name="NUM">0</field></shadow></value>
</block>
```

**备注**：DIVISIBLE_BY 时需要 mutation divisor_input=true 才会出现 DIVISOR 值输入。

证据级别：**A+**

## 6. 真实样本来源标注

各块 `xml_real` 的来源项目见下表（同一块优先取 PI；PI 没有的取实验/Scratch-3；都没有的只给构造版）：

| 块 | 真实样本项目 |
|---|---|
| `start` | PI |
| `annotation` | —（无真实样本） |
| `block_mod` | PI |
| `motor` | PI |
| `motor_time` | PI |
| `motor_angle` | —（无真实样本） |
| `dual_motor_duration` | —（无真实样本） |
| `dual_motor_angle` | PI |
| `resetencoder` | PI |
| `getencoder` | PI |
| `getai_glay` | PI |
| `getai_touch` | PI |
| `eeprom_read` | PI |
| `wait` | PI |
| `if` | PI |
| `ifelse` | PI |
| `while_cmp` | PI |
| `while_forver` | PI |
| `while_number` | —（无真实样本） |
| `while_break` | PI |
| `variables_get` | PI |
| `variables_set` | PI |
| `math_number` | PI |
| `math_op` | PI |
| `math_compare` | PI |
| `logic_compare` | —（无真实样本） |
| `logic_operation` | PI |
| `logic_boolean` | —（无真实样本） |
| `robot_math_rounding` | PI |
| `robot_math_unary_operation` | PI |
| `printf_text` | PI |
| `printf_number` | 实验 |
| `play_sound` | —（无真实样本） |
| `procedures_defnoreturn` | PI |
| `procedures_callnoreturn` | PI |
| `servoa_angle` | —（无真实样本） |
| `set_do` | —（无真实样本） |
| `set_electric_magnet` | —（无真实样本） |
| `printf_lines` | —（无真实样本） |
| `wait_until` | —（无真实样本） |
| `logic_negate` | —（无真实样本） |
| `math_modulo` | —（无真实样本） |
| `robot_math_constants` | —（无真实样本） |
| `get_encoder_real_time_value` | —（无真实样本） |
| `getai_sonic` | —（无真实样本） |
| `get_sonic_detect_object` | —（无真实样本） |
| `getmseconds` | —（无真实样本） |
| `getmsecondsreset` | PI |
| `eeprom_write` | —（无真实样本） |
| `get_key` | —（无真实样本） |
| `math_change` | PI |
| `procedures_defreturn` | —（无真实样本） |
| `block_conststring` | PI |
| `printf` | —（无真实样本） |
| `printf_emoji` | —（无真实样本） |
| `play_sound_until` | —（无真实样本） |
| `record` | Scratch-3 |
| `robot_math_trigonometric_function` | PI |
| `robot_math_random` | —（无真实样本） |
| `abilix_math_number_property` | —（无真实样本） |

## 7. 已确认坑 / 待实测清单（与 `_协作/报告_schema.md` 同步）

已确认（A/A+）：

- `math_compare` 下拉值是 `==/!=/</<=/>/>=`；写 `=` 会静默回退第一项。
- `while_number` 的 `TIMES` 是**值输入**（`<value name="TIMES">`），不是字段；循环变量 `count/count2/…` 自动生成。
- `while_cmp` 生成 `while not <bool>:`；`while_forver` 语句输入名是 `NAME`；`while_break` 生成 `break`。
- `resetencoder` 生成 `robot.reset_encoder(port);`（带分号）；`get_encoder_real_time_value` 在 SKCON9 下是 `robot.get_instant_incoder`（固件拼写，照抄）。
- `wait` 在 SKCON9 下是 `time.sleep`，SKCON2 才走 `robot.sleep`。
- `printf_text` 生成 `robot.print('…\n')`；`printf_number` 生成 `robot.print('data= ' + str(<data>) + '\n')`。
- `play_sound` 的 `musicname` 是 PlayList 的**文件值**（如 `dazhaohu_c0.mp3`、`luyin_p2`），共 78 项，完整表在 `block_schemas.json`。
- 参数化函数（defnoreturn）已由 harness headless 实测通过（加载/flyout 调用块/Python 生成/py_compile 16 项全 PASS）。

待实测（B）：

- `procedures_defreturn` 的真实 flyout 实例化（调用块是否在“函数”分类中渲染成功、能否拖出）——源码可证但需 harness 加用例。
- `get_key` 不在 SKCON9 工具箱：生成器 `robot.check_key` 存在，但真机是否有 Start/Left/Right 键需实机确认。
- `dual_motor_angle.port_3` 的 UI onChange 动态下拉只允许 port_1/port_2；纯 XML 载入不做合法性限制（不会报错）。
