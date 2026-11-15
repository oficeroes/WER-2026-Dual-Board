# 原生函数积木 —— 真实引擎验证证据

本目录是 WER 2026「原生函数积木」方案的 harness 真实引擎验证证据，全部由
`WER_函数库/工具/验证/run_validate.py`（新增 --native-test 模式）在无头 Chrome 中真实运行真实 Blockly 页面产出。

## 子目录

| 目录 | 被测工程 | web root | 验证内容 | 结果 |
| --- | --- | --- | --- | --- |
| `native_hello/` | `_分析临时/native_work/evidence/native_test.srh` | `patched_web`（1 函数） | 我的函数分类→flyout→拖出→接入 start→生成 | ok，32/32 |
| `native_ex20/` | `_分析临时/native_work/evidence/native_ex20.srh` | `patched_web_ex20`（20 函数 27 变量） | 同上，覆盖带参函数 | ok，32/32 |
| `pi_regression/` | 真实用户 `PI.srhs` | `patched_web` | 无原生块工程生成结果与 PI.py 逐字节比对 | ok，逐字节相同 |
| `no_prelude/` | `_分析临时/PI/abilixProject.srh` | `patched_web` | 无原生块工程不注入 prelude | ok，未注入且逐字节相同 |
| `backward_compat/` | `--param-test` / `--drag-test` / 无 userlib 的 `--native-test` | 默认 web root | 原有模式行为不变 | ok / ok / 预期退出 2 |

每个子目录包含 run_validate 自动写出的 `{时间戳}_*.json`（完整结构化证据）、`.report.txt`（中文报告）、
`.py`（真实生成的 Python）；native 两组另有 5 张 1600x1800 截图与 `说明.md`/`断言清单`/`prelude_sha256.txt`。
顶层 `sha256sums.txt` 列出全部证据文件哈希。

## 关键数字
- native_hello：nativeTest 32/32；生成 203 字节，与 Lead 手工验证产出的 `evidence/native_test.py` 逐字节相同。
- native_ex20：nativeTest 32/32；生成 15544 字节；prelude 14064 字符，sha256=d4e1f1261cd8653712f6ad87bd5ece2cf822ccf9367ac5133e7cdd3ab26ae721。
- pi_regression：生成 50618 字节，sha256=30a0bab0625e3dd1c1bd1fd167a27b1601bc15e0a26439b2ba5afff7e7a3df4a，与 PI.py 逐字节相同。
- no_prelude：生成 50618 字节，同 sha256；nativePrelude{projectNativeBlockCount:0, expected/detected:False, ok:True}。

## 复现命令
见 `WER_函数库/_协作/报告_harness_原生积木.md` 的「可复现命令」一节，或各子目录 `说明.md`。
