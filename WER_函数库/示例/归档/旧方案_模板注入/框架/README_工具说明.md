# 函数库框架 · 工具说明

> 目标：**你自己搭的函数库，装进 AbilixScratch3.0（能力风暴）软件本身**。
> 之后每次在软件里新建项目，工作区就自带这些函数定义，「函数」分类里可以直接拖下来用。
> 本目录是完成这件事的 Python 工具（不包含具体函数——函数由你自己在 IDE 里搭）。
>
> 工作目录：`WER_函数库/`　·　工具目录：`WER_函数库/工具/框架/`
> 文件编码 UTF-8　·　路径全部相对定位（整个 `WER_函数库/` 拷到别的电脑也能用）

---

## 1. 一句话原理

软件新建项目时会执行内置的默认模板：

```
新建项目 → 读取软件资源包 browser_assets 里 Blockly_Code/maingui_init.js 的
           defaultcode 字符串 → 把它加载进空工作区
```

本工具把「我的函数库」里的 **全部函数定义 + 变量声明 + start 主函数** 写成这个
`defaultcode` 字符串（只改 `browser_assets` 里 **6645 个条目中的 1 个**），
所以之后**每个新建项目**都自带函数库。改完可以一键还原。

> 更完整的原理、格式细节、其它电脑移植步骤见 `WER_函数库/修改软件说明/`（Lead 编写）。
> 本文件只讲工具怎么用。

---

## 2. 使用前准备

1. **Python 3.8+**（只需标准库，不用 pip 装任何东西）。
   - Windows 下建议装 python.org 官方版并勾选 “Add Python to PATH”；
   - 命令行里 `py -3 --version` 或 `python --version` 能显示版本即可。
   - `.cmd` 会先找 `py`，再找 `python`；找不到会给出明确提示。
2. **函数库源文件**：`WER_函数库/我的函数库.srhs`（或 `.srh`）。
   - 就是你在 IDE 里搭好函数后保存的项目文件；
   - 也可以放到别处，用 `--library` 指定。
   - 若没有这个文件，工具会在 `WER_函数库/示例/WER函数库.srh` 上做“演示”，
     并在输出里提示（示例只是测试数据，真正要同步自己的函数请创建 `我的函数库`）。
3. **打补丁/还原前先完全关闭 IDE**（软件运行时会占用资源包/回写配置；关闭最稳妥）。
4. 安装目录默认自动扫描（本机示例：
   `X:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets`）。
   自动找不到时用 `--assets` 指定，或设环境变量 `ABILIX_ASSETS` 指向该文件。

---

## 3. 快速上手（推荐顺序）

### 第一步：准备你的函数库

1. 打开 AbilixScratch3.0 → 新建项目；
2. 用「函数 → 新建函数」搭好你的函数（建议 `func_` 开头 + 英文名）；
3. 保留 **恰好 1 个 start 块**（主函数，建议只放说明注释）；
4. 保存项目 → 在 IDE 项目目录里找到 `abilixProject.srhs`，复制到
   `WER_函数库/我的函数库.srhs`（或直接“另存为”到该路径）。

### 第二步：体检

```bat
python WER_函数库\工具\框架\校验我的函数库.py
:: 或双击  校验我的函数库.cmd
```

输出会列出全部函数/参数/变量和问题。**ERROR=0** 才能同步；WARN 只是提醒。

### 第三步：演练（绝不写安装目录）

```bat
python WER_函数库\工具\框架\同步我的函数库.py --dry-run
:: 或：python 框架核心.py sync --dry-run
```

会生成补丁包到 `_分析临时/framework_work/browser_assets.patched`（可用 `--out` 改），
并做三重自检（纯 roundtrip 逐字节一致 / 除 maingui_init.js 外所有条目 sha256 不变 /
回读 defaultcode 与期望片段逐字符相同）。

### 第四步：真正安装（需要管理员）

**最简单**：双击 `同步我的函数库(管理员).cmd`，UAC 弹窗点“是”。

或者：右键“以管理员身份运行” PowerShell，执行：

```bat
python WER_函数库\工具\框架\同步我的函数库.py --install
```

安装时会把原文件自动备份成 `browser_assets.备份-<时间戳>`（与 browser_assets 同目录），
安装后再校验 sha256 并回读。**完全关闭并重启 IDE**，然后“文件 → 新建项目”，
「函数」分类里就能看到你的函数，直接拖用。

### 第五步：查看 / 还原

```bat
python WER_函数库\工具\框架\查看当前新建模板.py       :: 看当前模板里有哪些函数
python WER_函数库\工具\框架\还原新建模板.py --list    :: 列出所有备份
python WER_函数库\工具\框架\还原新建模板.py --yes     :: 还原（管理员）
:: 或双击 还原新建模板(管理员).cmd
```

---

## 4. 工具清单

全部位于 `WER_函数库/工具/框架/`。`.py` 是命令行工具，`.cmd` 是给不熟悉命令行的
用户准备的一键入口（`.cmd` 内容纯 ASCII，内部自动找 Python 并调用 `框架核心.py`）。

| 文件 | 作用 | 是否写文件 | 退出码 |
|---|---|---|---|
| `框架核心.py` | 核心库（可 import）；也是 CLI：`locate/validate/sync/restore/inspect/gen` | 看子命令 | 0/1/2 |
| `校验我的函数库.py` | 校验函数库源文件并列出函数/变量 | 只读 | 0 通过 / 1 有 ERROR / 2 文件缺失 |
| `同步我的函数库.py` | 同步到软件新建项目默认模板（默认演练） | 演练：只写补丁包；`--install`：写安装目录（先备份） | 0 成功 / 1 校验或自检失败 / 2 需管理员或文件缺失 |
| `还原新建模板.py` | 从 `browser_assets.备份-*` 还原 | `--list`/默认只读；`--yes` 写安装目录 | 0 成功/仅计划 / 1 失败 / 2 找不到备份或无权限 |
| `查看当前新建模板.py` | 查看软件当前默认模板内容，可与函数库对比 | 只读 | 0 / 1 内容异常 / 2 找不到资源包 |
| `生成新项目文件.py` | 把函数库打包成可直接打开的 `.srhs`（不装补丁也能用） | 只写输出文件 | 0 / 1 打包失败 / 2 函数库缺失 |
| `同步我的函数库(管理员).cmd` | UAC 自提升 → `sync --install`；窗口会显示 `[DONE]`/`[NOT APPLIED]`，并写 `sync_log.txt` | 同 sync | 同 sync |
| `同步状态检查.py` / `.cmd` | **只读诊断**：当前是否已提权/在管理员组、软件是否运行、模板是原始还是已打补丁、与函数库差异、下一步建议 | 只读 | 0 正常 / 2 找不到安装包 |
| `还原新建模板(管理员).cmd` | UAC 自提升 → `restore --list` + `restore --yes` | 同 restore | 同 restore |
| `查看当前新建模板.cmd` | 双击查看 | 只读 | 同 inspect |
| `校验我的函数库.cmd` | 双击校验 | 只读 | 同 validate |
| `生成新项目文件.cmd` | 双击生成新项目文件 | 只写输出文件 | 同 gen |

> `.cmd` 支持把参数原样传进去，例如
> `同步我的函数库(管理员).cmd --library "D:\x\我的函数库.srh" --langs all`。

---

## 5. 各工具详细用法

### 5.1 `校验我的函数库.py`

```bat
python 校验我的函数库.py
python 校验我的函数库.py --library "D:\path\我的函数库.srh"
python 校验我的函数库.py --json --json-out 校验结果.json
```

检查内容：

- 文件能否读取 / 是否合法 `.srh`、`.srhs`；XML 是否合法；
- **恰好 1 个 start 块**（多了少了都是 ERROR）；
- 函数定义必须在顶层；函数名不重复、参数名不重复、变量 id/名字不重复；
- 能生成 defaultcode 片段；
- WARN（不阻止同步）：函数名不是 `func_` 前缀或非 ASCII、参数/变量名非 ASCII、
  孤立调用（调用了没定义的函数）、顶层注释不会被同步、start 里预置了块、
  存在有返回值函数块等。

### 5.2 `同步我的函数库.py`

```bat
:: 演练（默认行为，不写安装目录）
python 同步我的函数库.py --dry-run
:: 生成补丁包到指定位置（便于留证/拷贝到别的电脑）
python 同步我的函数库.py --dry-run --out 证据\browser_assets.patched --json-out 证据\sync.json
:: 安装（需管理员）
python 同步我的函数库.py --install
:: 只替换英文模板
python 同步我的函数库.py --install --langs en
```

| 参数 | 说明 |
|---|---|
| `--library` | 函数库源文件；默认自动找 `WER_函数库/我的函数库.srh(.srhs)` |
| `--assets` | browser_assets 路径；默认自动扫描本机安装目录 |
| `--install` | 真正写回安装目录（需管理员；自动备份原文件） |
| `--dry-run` | 只生成补丁包并自检（默认行为，写上更清楚） |
| `--langs` | `zh-hans`（默认）/ `zh-hant` / `en` / `all`，多个用逗号分隔 |
| `--out` | 补丁包输出路径；默认 `<工作区>/_分析临时/framework_work/browser_assets.patched` |
| `--keep-work` | 保留临时解包目录（排错用） |
| `--json` / `--json-out` | 输出 JSON 结果到屏幕 / 文件 |

安装模式下会做这些事（任一步失败都不会写安装目录）：

1. 校验函数库源文件；2. 生成 defaultcode 片段并验证；3. 校验 `browser_assets` 格式；
4. 纯 roundtrip 自检（解包→原样重打包，必须逐字节一致）；
5. 解包 → 只替换 `Blockly_Code/maingui_init.js` 里指定语言的 `defaultcode` → 重打包；
6. 逐条目 sha256 自检（除该条目外 6644 个条目必须完全不变）；
7. **框架层独立复核**：重新读补丁包，比较全部条目 sha256、回读 defaultcode 与片段逐字符相同；
8. 备份原文件 → 写入安装目录 → 校验 sha256 → 回读安装后的 defaultcode。

### 5.3 `查看当前新建模板.py`

```bat
python 查看当前新建模板.py
python 查看当前新建模板.py --json --json-out 当前模板.json
python 查看当前新建模板.py --library 我的函数库.srh
```

读的是**软件安装目录里当前真实生效**的默认模板（只读）。会显示三种语言
（简中/繁中/英文）的 `defaultcode` 摘要：函数列表与参数、变量、顶层块/start 数，
并判定当前是“原始模板（0 个函数）”还是“已打过补丁（N 个函数）”。
若找到函数库源文件/最近备份，还会对比：同步后会新增/移除哪些函数、参数差异、
当前模板与函数库片段是否完全一致（是否需要同步）。

### 5.4 `还原新建模板.py`

```bat
python 还原新建模板.py --list      :: 列出所有备份（浏览器资源包不读，很快）
python 还原新建模板.py             :: 只显示还原计划（不写文件）
python 还原新建模板.py --yes       :: 真正还原（管理员）
python 还原新建模板.py --yes --backup "…\browser_assets.备份-20261110-132909"
```

还原流程：找备份 → 校验备份格式 → 对比当前包与备份包（确认只差 `maingui_init.js`）
→ 把**当前**文件另存为 `browser_assets.还原前备份-<时间戳>` → 用备份覆盖 → 校验 sha256
→ 回读 defaultcode。

> **注意**：每同步一次就多一份备份，**最新备份 = 上一次同步之前的状态**（可能也是打过
> 补丁的）。要回到“出厂原始模板”，用 `--list` 找到**最早**的那份备份，再
> `--yes --backup <它>`。

### 5.5 `生成新项目文件.py`

```bat
python 生成新项目文件.py
python 生成新项目文件.py --library 我的函数库.srh --out 我的新项目.srhs
python 生成新项目文件.py --program ProgramA --robot SKCON9 --force
```

不依赖安装目录、不需要管理员：把函数库打包成一个标准 `.srhs`
（唯一 zip 条目 `abilixProject.srh`，zip 注释 = 机器人枚举，SKCON9=111）。
在 IDE 里 **文件 → 打开** 它，工作区就自带函数库。
适合：临时用一次、不想改软件、或拿到别的电脑上直接用。

输出默认在函数库同目录：`<库名>_新项目.srhs`；已存在会拒绝覆盖（加 `--force`）。

---

## 6. 安全性 / 可回滚

- **默认演练**：`.py` 不加 `--install` / `--yes` 绝不写安装目录；`.cmd` 必须双击并点 UAC。
- **写前预检**：目录不可写时明确报错并给出管理员运行的具体命令，不会静默失败。
- **安装前自动备份**：`browser_assets.备份-<时间戳>`；安装后校验 sha256 并回读。
- **还原前再备份**：`browser_assets.还原前备份-<时间戳>`，还原失败也能手工恢复。
- **只改 1 个条目**：强制自检其余 6644 个条目 sha256 完全不变。
- **升级/重装软件会覆盖补丁**：升级后需要重新同步一次（备份也会随之更新）。
- **杀毒软件**可能提示“修改应用资源文件”，选择允许即可（内容只改一个 JS 字符串）。

---

## 7. 常见问题（FAQ）

**Q1. 双击 .cmd 一闪而过 / 中文乱码？**
`.cmd` 已内置 `chcp 65001`；如果仍闪退，打开“命令提示符”手动运行同名工具，看报错。
`pause` 一般会让窗口停住。
**注意**：`同步我的函数库(管理员).cmd` 会先申请管理员权限（UAC 弹窗）。如果你点了“否”或取消，
同步**不会执行**，原始窗口现在会明确显示 `[NOT APPLIED]`，并把结果写进 `sync_log.txt`。

**Q1.5 怎么一眼确认“同步到底成没成”？**
双击 `同步状态检查.cmd`（只读）：会显示“当前进程是否已提升/账户是否在管理员组、软件是否运行、
模板是原始模板还是已打过补丁、函数库与模板差异、下一步该做什么”。同步成功时它应显示
“已打过补丁：函数分类里有 N 个函数调用块”且“还需要同步吗：不需要”。

**Q2. 提示“没有写入安装目录的权限”？**
安装目录在 `Program Files` 下，普通用户只读。请双击 `同步我的函数库(管理员).cmd`
（会弹 UAC），或在“以管理员身份运行”的 PowerShell/CMD 里执行 `--install`。
工具在无权限时也会先做好演练（生成补丁包），不会白跑。

**Q3. 提示“没有自动找到 browser_assets”？**
用 `--assets` 指过去，例如：
`--assets "D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets"`
（注意 Data 目录名是带点的 `AbilixScratch3.0_Data`）。也可以只给安装根目录
`"D:\Program Files\AbilixScratch3.0"` 让工具自己找。

**Q4. 同步成功了，但 IDE 里看不到函数？**
① 是否完全关闭并重启了 IDE（不是只关项目窗口）；
② 是否“文件 → 新建项目”（旧项目不会自动变化，可用 `合并到现有项目.py` 合并进旧项目）；
③ 用 `查看当前新建模板.py` 确认安装目录里的模板确实有函数（能区分“已安装”与“没装成”）。

**Q5. 我的函数库文件在哪？怎么换？**
默认 `WER_函数库/我的函数库.srh` 或 `.srhs`。也可以放任意位置并用 `--library` 指定。
注意：`.srhs` 是压缩包、`.srh` 是 XML，两者都能直接用。

**Q6. 想恢复出厂模板？**
`还原新建模板.py --list` 找**最早**的 `browser_assets.备份-*`，然后
`还原新建模板.py --yes --backup <最早那份>`。若从未打过补丁，当前就是原始模板。

**Q7. 换电脑 / 拷给别人用？**
把整个 `WER_函数库/` 文件夹拷过去（含 `工具/底层/` 两个文件，不能只拷 `框架/`），
装好 Python 3，按上面步骤即可；安装目录会自动扫描，找不到就 `--assets` 指定。
`.cmd`、`.py` 里没有写死任何本机路径。

**Q8. 影响中文/英文界面吗？**
默认只替换简中 `defaultcode`，繁中 `defaultcodeTr`、英文 `defaultcodeEn` 保持原样。
需要时用 `--langs zh-hant,en,zh-hans` 或 `all`。

**Q9. 函数名用中文行不行？**
不行。IDE 生成 Python 时会把函数名/参数名转成 Python 标识符，中文会变成乱码名。
请用 `func_` 前缀 + 英文字母/数字/下划线（参数同理）；变量建议 `var_` 前缀。
`校验我的函数库.py` 会对非 ASCII 名字给 WARN。

**Q10. 框架工具本身能 import 复用吗？**
可以。`框架核心.py` 里都是带中文注释的库函数：
`locate_install / build_fragment / validate_library / sync / restore /
inspect_current_template / make_new_project`。
示例：

```python
import importlib.util, os
here = r'WER_函数库\工具\框架'
spec = importlib.util.spec_from_file_location('wer_core', os.path.join(here, '框架核心.py'))
core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)
print(core.locate_install()['assets'])
print(core.validate_library('WER_函数库/示例/WER函数库.srh')['ok'])
```

---

## 8. 退出码与 JSON

| 退出码 | 含义 |
|---|---|
| 0 | 成功（演练成功也算；`restore` 只显示计划也算） |
| 1 | 校验错误 / 补丁包或产物没通过自检 / 处理失败 |
| 2 | 需要管理员权限，或文件/目录缺失（browser_assets、函数库、备份找不到） |

所有工具都支持 `--json`（只输出 JSON）和 `--json-out <文件>`（把 JSON 写文件），
便于自动化和留证据。JSON 里包含 `ok / exit_code / errors / warnings` 等字段。

---

## 9. 目录结构（本工具相关）

```
WER_函数库/
├─ 我的函数库.srhs                 ← 你的函数库源文件（默认读取；.srh 也行）
├─ 示例/WER函数库.srh(s)           ← 演示/自测数据（不是框架的一部分）
└─ 工具/
   ├─ 底层/                        ← ★ 不能删：本框架依赖这两个文件
   │  ├─ srhs工具.py               ← .srh/.srhs 读写/校验/打包
   │  └─ patch_browser_assets.py   ← browser_assets 补丁器（zfbRes_v1 格式）
   ├─ 框架/                        ← 本目录
   │  ├─ 框架核心.py               ← 核心库 + CLI（locate/validate/sync/restore/inspect/gen）
   │  ├─ 校验我的函数库.py  + .cmd
   │  ├─ 同步我的函数库.py  + 同步我的函数库(管理员).cmd
   │  ├─ 还原新建模板.py    + 还原新建模板(管理员).cmd
   │  ├─ 查看当前新建模板.py + .cmd
   │  ├─ 生成新项目文件.py   + .cmd
   │  └─ README_工具说明.md        ← 本文件
   └─ 验证/                        ← headless 真机引擎验证工具（可选，进阶校验用）
```

> 底层工具（`工具/底层/`）由集成工具工程师提供，本框架只是调用/复用，不修改它们。

---

## 10. 在另一台同款软件上重复这套修改（简版）

1. 确认那台电脑装了 **AbilixScratch3.0**（同样的积木编程软件），并装好 **Python 3.8+**；
2. 把整个 `WER_函数库/` 文件夹拷过去（保留 `工具/底层/` 与你的 `我的函数库.srhs`）；
3. 关闭那台电脑上的 IDE；
4. 双击 `工具/框架/校验我的函数库.py` 对应的 `.cmd` 体检（或命令行跑）；
5. 双击 `工具/框架/同步我的函数库(管理员).cmd`，UAC 点“是”；
6. 重启 IDE → 新建项目 → 确认「函数」分类里有你的函数；
7. 想撤销：双击 `还原新建模板(管理员).cmd`。

（更详细的原理、`browser_assets` 格式、`defaultcode` 机制、手工修改方法，见
`WER_函数库/修改软件说明/`。）
