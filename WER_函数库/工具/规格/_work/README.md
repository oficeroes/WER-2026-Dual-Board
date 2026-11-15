# _work 说明（block_schemas.json 的生成脚本与材料）

本目录**不是交付物**，是 `block_schemas.json` / `积木XML规格.md` 的可复现生成链。

## 文件

| 文件 | 作用 |
|---|---|
| `build_schemas.py` | 生成 `../block_schemas.json`（机器可读积木规格）。直接从 `_分析临时/blockly_utf8` 只读提取积木定义/生成器并用**字节级 `\n` 计数**重算行号；下拉选项解析支持 `GetPortAToDList()` 等动态列表、`PlayList`、`Blockly.Msg` 中文替换。 |
| `gen_md.py` | 从 `block_schemas.json` 生成人读版 `../积木XML规格.md`（附加通用 XML 规则、函数机制专章、易错点等前言）。 |
| `validate_schemas.py` | 自检：60 个块的必需键、block_def/generator 行号范围、xml_min/xml_real 合法性、append_fields 与 fields/inputs 一致性。 |
| `msgs_zh.json` | 从 `_分析临时/blockly_utf8/msg/js/zh-hans.js` 提取的全部中文文案（含 `ABILIX_SCRATCH_*`）。 |
| `blocks_clean.json` | 自定义积木定义源码（注释感知提取，含行号）。 |
| `gens_clean.json` | `Blockly.Python['x']` 生成器源码（含行号）。 |
| `stock_blocks.json` | 标准块 `defineBlocksWithJsonArray` JSON 定义源码（logic/math/variables/text 等）。 |
| `real_samples.json` | 三个真实 `.srh` 样本逐块提取结果（fields/io/mutation/shallow_xml/full_xml）。 |
| `toolboxes.json` | `maingui.html` 里 3 个机器人工具箱原 XML。 |
| `toolbox_skcon9_parsed.json` | SKCON9 工具箱解析结果（分类/块/默认字段/影子值）。 |

## 重建

```powershell
$py = 'C:\Users\s1325\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
& $py 'WER_函数库\工具\规格\_work\build_schemas.py' all
& $py 'WER_函数库\工具\规格\_work\gen_md.py'
& $py 'WER_函数库\工具\规格\_work\validate_schemas.py'
& $py 'WER_函数库\工具\规格\check_library_xml.py'
```

## 材料来源（均为只读）

- `_分析临时/blockly_utf8/blocks/myrobotrun.js`、`blocks/procedures.js`、`blocks/*.js`
- `_分析临时/blockly_utf8/generators/myrobotpythoncode.js`、`generators/python/*.js`、`generators/python.js`
- `_分析临时/blockly_utf8/msg/js/zh-hans.js`、`maingui.html`
- `_分析临时/{PI,实验,Scratch-3}/abilixProject.srh`

注意：真实 `.srh` 尾部是**旧保存残留**（覆盖写未截断），提取时只取第一个 `<xml>` 到第一个 `</xml>`，否则会把旧版残片当成当前工程块。
