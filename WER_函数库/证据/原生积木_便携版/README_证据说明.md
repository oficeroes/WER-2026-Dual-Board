# 原生函数积木 · 便携版 · 证据说明（README）

本目录是「原生函数积木」方案免管理员便携版的真机端到端验证证据。
完整步骤与校验值见 `步骤记录.txt`；正式报告见 `WER_函数库\_协作\报告_便携版_原生积木.md`。

- 验证日期：2026-11-11
- 机位：Windows 11，屏幕 2880×1800 @200% DPI（截图为物理像素整屏 PNG）
- 便携副本：`C:\Users\s1325\AbilixScratch3.0_FuncLib`（纯 ASCII 路径）
- 真实安装（只读）：`D:\Program Files\AbilixScratch3.0`

## 一、截图清单与对应函数库

| 截图 | 对应函数库 | 内容 |
| --- | --- | --- |
| `截图\01_IDE启动.png` | 我的函数库.srhs（1 函数） | 便携副本 IDE 启动后界面：左侧分类栏、主函数区、右侧 Python 面板（项目 MyFuncLib）。**首版曾截到 PowerPoint 前台，已重拍为 IDE 前台版** |
| `截图\02_点击我的函数分类.png` | 我的函数库.srhs（1 函数） | **关键证据**：点左侧「我的函数」分类后，flyout 出现紫色原生块 `func_Hello`；主函数内已含该块；右侧 Python 面板显示 `def func_Hello():` 与主函数中的 `func_Hello()` 调用 |
| `截图\03_文件菜单.png` | 我的函数库.srhs（1 函数） | 文件菜单展开（新建/打开/保存/另存为/例程/退出 及快捷键） |
| `截图\crop_文件菜单.png` | 我的函数库.srhs（1 函数） | 文件菜单放大图（菜单项文字清晰可读） |
| `截图\04_新建项目.png` | 我的函数库.srhs（1 函数） | 点「新建」时弹出「当前程序已修改，是否保存？」对话框 |
| `截图\05_新项目空白.png` | 我的函数库.srhs（1 函数） | 选择「不保存」后新建的空白项目（Scratch-7）：主函数仅含注释与「显示 hello world」，Python 面板无 `def func_Hello` |
| `截图\06_我的函数flyout_重拍.png` | 我的函数库.srhs（1 函数） | **flyout 证据（重拍）**：IDE 前台、左侧「我的函数」高亮、flyout 紫色 `func_Hello`。**原 06 截到 DSH 窗口前台已弃用，此为 13:59:05 重拍版** |
| `截图\07_重启IDE.png` | 我的函数库.srhs（1 函数） | IDE 意外退出（13:56:32）后重新启动，自动加载项目、界面正常 |
| `截图\08_拖入主函数.png` | 我的函数库.srhs（1 函数） | 第一次拖拽后的画面：func_Hello 块被拖入工作区但呈**虚线悬浮（尚未接到插槽）**，右侧 Python 面板尚无 `func_Hello()` 调用；随后第二次拖拽才连接成功（见 13） |
| `截图\13_拖拽完成_Python证据.png` | 我的函数库.srhs（1 函数） | **关键证据（整屏）**：拖拽完成后 IDE 前台、主函数内原生块、右侧 Python 面板完整代码 |
| `截图\crop_13_python面板_放大.png` | 我的函数库.srhs（1 函数） | **关键证据（放大）**：Python 面板逐行可读——`def func_Hello():` + 主函数中 `func_Hello()` |
| `截图\14_示例库20函数_flyout.png` | WER函数库.srhs（示例，20 函数） | **20 函数 flyout 证据**：flyout 竖向列出全部 20 个紫色原生块（func_Init … func_Beep，含参数） |
| `截图\15_示例库20函数_Python代码.png` | WER函数库.srhs（示例，20 函数） | 20 函数构建启动后空项目的 Python 面板（对照） |
| `截图\crop_左侧分类栏.png` | 我的函数库.srhs（1 函数） | 左侧分类栏放大（「我的函数」紫色高亮、各分类彩条） |

## 二、关于「重拍」与前台遮挡

验证初期 IDE 窗口会被其他窗口（PowerPoint、本会话 DSH 网页等）抢占前台，
出现过 3 张无效图：

- 首版 `01_IDE启动.png`：拍到 PowerPoint 前台 → 已用「激活 + 校验前台 + 立即截图」重拍；
- 首版 `06_...flyout.png`：拍到 DSH 网页前台（只露出 Abilix 标签栏）→ 已弃用并重拍为
  `06_我的函数flyout_重拍.png`；
- `02b.png`（DSH 前台）：已删除，不作为证据。

之后的自动化流程固定为：**每次点击/拖拽/截图前先 activate()**（ShowWindow(SW_RESTORE)
+ SetForegroundWindow，必要时 ALT 键解锁、AppActivate 回退），并用
`GetForegroundWindow()==IDE hwnd` 校验；截图前再激活一次。
`SetForegroundWindow` 实测返回 1（成功），校验等待 0.0s 即满足。详见 `脚本\win32_ui.py`。

## 三、其它文件

- `步骤记录.txt`：完整时间线、命令、核心工具 build/verify 明细、安全校验值。
- `python代码_1函数版本.txt`：1 函数版本 IDE 生成的 Python 代码逐字记录。
- `创建报告.json` / `更新报告_示例库20函数.json`：工具运行的结构化报告（含 sha256、
  build 参数、verify 输出摘要、快捷方式信息）。
- `AppData备份\AbilixProjects.备份-20261111-134507\`：测试前 AppData 项目目录快照
  （13 文件 / 297,670 B），测试后已用它恢复并核对 config sha 一致。
- `脚本\`：自动化脚本
  - `win32_ui.py`：ctypes 版（activate/click/dclick/drag/key/shot/rect/state/proc），最终使用；
  - `ui_自动化.ps1`、`e2e_01_launch.ps1`：PowerShell 版（启动/等待窗口/截图/关闭）；
  - `_run_flyout20.py`、`_e2e_cleanup1.py`、`_cleanup2_restore_appdata.py`、
    `_cleanup3_checks.py`、`_check_lib.py`：本次验证用的一次性辅助脚本（保留备查）。
- `_临时\build_test.json`：核心工具独立 build 测试的 JSON（大文件 .bin 已删除）。

## 四、安全结论

- 真实安装 `D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets`
  全程保持 **85,271,033 B / sha256 DF6DB241752D42BFF2995FCD24521E070ADF9EB5D96E870148F9DC51690EDC40** 未变。
- AppData 项目列表：启动前备份 + clear_app_data_switch 确认为 0；测试期间 IDE 自行新增
  临时项目，结束后已从备份完整恢复，config sha 回到
  `5A52DD18D8DE191648C1EB87F847183A3D1C8372DCB2FFDC5E05510EEFACE310`。
- 便携副本与桌面快捷方式已按任务要求删除；`我的函数库.srhs` 未被本工具修改
  （测试期间 IDE 打开「我的函数库」标签后其 mtime/大小有变化，属 IDE 行为）。
