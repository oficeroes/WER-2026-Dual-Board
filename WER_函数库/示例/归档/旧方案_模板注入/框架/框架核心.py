# -*- coding: utf-8 -*-
"""
框架核心.py —— WER「函数库框架」核心库（可 import，也可直接当 CLI 用）
========================================================================

一句话
------
用户自己在 IDE 里搭好一批函数，保存成“我的函数库.srh / .srhs”；
本模块把这个源文件里的**全部顶层积木 + 变量声明**写进软件内置
`Blockly_Code/maingui_init.js` 的 `defaultcode`（新建项目默认模板）里，
之后在软件里**每新建一个项目，工作区就自带这些函数定义**，
「函数」分类里能直接拖用。还提供还原、查看当前模板、校验、生成新项目文件。

机制（已由 C# 反编译源码 + 真实资源包实证，详见 _协作/项目背景与任务.md §9）
------------------------------------------------------------------------------
* 新建项目：C# CreateNewProject → JS maingui.createProject() → workspace.clear()
  → maingui.importDefaultCode()：读 `maingui_init.getDefaultCode()`（= maingui_init.js
  里的 defaultcode 字符串）+ 当前空工作区 XML 拼接后 domToWorkspace。
* Web 资源包 browser_assets 是自定义 `zfbRes_v1` 二进制格式（6645 个条目）。
  只改其中 `Blockly_Code/maingui_init.js` 一个条目，其余条目逐字节不变（强制自检）。
* 打补丁需要管理员权限（安装在 Program Files 时）；安装前会自动备份
  `browser_assets.备份-<时间戳>`；还原 = 把备份复制回去（还原前再备份当前文件）。

目录约定（全部相对本文件定位，整个 WER_函数库 文件夹拷到别的电脑也能用）
--------------------------------------------------------------------
    WER_函数库/
    ├─ 我的函数库.srh / .srhs     ← 用户的函数库源文件（默认读取）
    ├─ 示例/WER函数库.srh(s)      ← 演示/自测用（没有“我的函数库”时会提示并借用）
    └─ 工具/
       ├─ 底层/srhs工具.py、patch_browser_assets.py   ← 被本模块 import
       └─ 框架/框架核心.py、同步我的函数库.py …        ← 本模块 + 中文 CLI 封装

主要 API（详见函数 docstring）
------------------------------
    locate_install(assets=None)            -> dict   自动找本机 browser_assets
    build_fragment(library)                -> dict   抽取 defaultcode 片段
    validate_library(library)              -> dict   校验函数库源文件（结构化结果）
    sync(library, assets=None, ...)        -> dict   同步到新建项目默认模板（可 dry-run）
    restore(assets=None, backup=None, ...) -> dict   从备份还原
    inspect_current_template(assets, ...)  -> dict   查看当前软件里的默认模板内容
    make_new_project(library, out_path, program='ProgramA') -> dict
                                                     生成可直接「文件→打开」的 .srhs

退出码约定（CLI）
-----------------
    0 = 成功
    1 = 校验错误 / 处理失败（补丁包或产物没通过自检）
    2 = 需要管理员权限，或文件/目录缺失（browser_assets、函数库、备份找不到）

安全性
------
* 本模块所有“写安装目录”的动作都只在 `sync(install=True)` / `restore(apply=True)` 里，
  且先检查目录可写（不可写时明确报错并给出管理员运行建议，绝不静默写）；
* 自检强制：纯 roundtrip 逐字节一致 + 除 maingui_init.js 外全部条目 sha256 不变 +
  回读 defaultcode 与期望片段逐字符相同；
* 默认 dry-run，CLI 里只有加 `--install` / `--yes` 才真正写安装目录。

作者：函数库框架工程师（framework）。依赖：仅 Python 标准库 + 同项目 工具/底层 两个文件。
"""

from __future__ import annotations

import argparse
import ctypes
import glob
import importlib.util
import json
import os
import re
import shutil
import string
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

#: 不在交付目录里留下 __pycache__（加载 工具/底层 的中文名模块时也会生效）
sys.dont_write_bytecode = True

# ============================================================================
# 一、目录与常量（全部相对本文件推导，不写死本机绝对路径）
# ============================================================================

_HERE = os.path.dirname(os.path.abspath(__file__))          # WER_函数库/工具/框架
TOOL_DIR = os.path.dirname(_HERE)                            # WER_函数库/工具
LIB_ROOT = os.path.dirname(TOOL_DIR)                         # WER_函数库
WORKSPACE_ROOT = os.path.dirname(LIB_ROOT)                   # 工作区根目录
BOTTOM_DIR = os.path.join(TOOL_DIR, '底层')                  # srhs工具.py / patch_browser_assets.py
EXAMPLE_DIR = os.path.join(LIB_ROOT, '示例')
README_FILE = os.path.join(_HERE, 'README_工具说明.md')

VERSION = '1.0.0'

#: CLI 退出码
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_NEED = 2

#: browser_assets 里的默认模板脚本条目名（索引里带前导 '/'）
TEMPLATE_ENTRY = '/Blockly_Code/maingui_init.js'
#: 备份 / 还原前备份 文件名前缀（与 底层/patch_browser_assets.py 保持一致）
BACKUP_PREFIX = 'browser_assets.备份-'
PRE_RESTORE_PREFIX = 'browser_assets.还原前备份-'
ASSETS_NAME = 'browser_assets'
#: Data 目录名（点号是正确写法；历史上工具里也出现过下划线写法，两种都兼容）
DATA_DIR_NAMES = ('AbilixScratch3.0_Data', 'AbilixScratch3_0_Data')
#: 默认函数库候选文件名（按优先级）
LIBRARY_FILE_NAMES = ('我的函数库.srh', '我的函数库.srhs',
                      'WER函数库.srh', 'WER函数库.srhs')

#: 调用块（procedures_callnoreturn / callreturn）的 mutation name 解析
_CALL_BLOCK_RE = re.compile(
    r'<block\b[^>]*\btype="(procedures_callnoreturn|procedures_callreturn)"[^>]*>\s*<mutation\b([^>]*)>',
    re.S)
_ANY_CALL_BLOCK_RE = re.compile(
    r'<block\b[^>]*\btype="procedures_call(?:noreturn|return)"')
_ATTR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_.:\-]*)\s*=\s*"([^"]*)"')
_BLOCK_TYPE_RE = re.compile(r'<block\b[^>]*\btype="([^"]+)"')
_PY_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_PROCEDURE_NAME_RE = re.compile(r'^func_[A-Za-z_][A-Za-z0-9_]*$')


# ============================================================================
# 二、异常
# ============================================================================

class FrameworkError(Exception):
    """框架层的可预期错误（消息直接给用户看；exit_code 用于 CLI 退出码）。"""

    def __init__(self, message: str, exit_code: int = EXIT_NEED,
                 suggestions: Optional[Sequence[str]] = None):
        super().__init__(message)
        self.exit_code = exit_code
        self.suggestions: List[str] = list(suggestions or [])


# ============================================================================
# 三、加载 工具/底层 的两个模块（文件名含中文，按文件路径加载）
# ============================================================================

def _load_module_by_path(module_name: str, filename: str) -> Any:
    """在 工具/底层 等候选目录里找 filename 并按路径加载成模块。"""
    candidates = [
        os.path.join(BOTTOM_DIR, filename),   # 标准位置：WER_函数库/工具/底层/
        os.path.join(_HERE, filename),        # 和本文件放一起（拷动过）
        os.path.join(TOOL_DIR, filename),     # 老版本位置：WER_函数库/工具/
    ]
    for path in candidates:
        if os.path.isfile(path):
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise FileNotFoundError('找不到 %s（已尝试：%s）' % (filename, '；'.join(candidates)))


try:
    srhs_tool: Any = _load_module_by_path('wer_srhs_tool', 'srhs工具.py')
except Exception as _exc_srhs:  # noqa: BLE001 - 保留错误，等真正用到时给友好提示
    srhs_tool = None
    _BOTTOM_ERROR = str(_exc_srhs)
else:
    _BOTTOM_ERROR = ''
    try:
        patch: Any = _load_module_by_path('wer_patch_browser_assets', 'patch_browser_assets.py')
    except Exception as _exc_patch:  # noqa: BLE001
        patch = None
        _BOTTOM_ERROR = str(_exc_patch)

# 条目名以底层补丁器为准（两边必须一致）
if patch is not None and getattr(patch, 'MAINGUI_INIT_KEY', None):
    TEMPLATE_ENTRY = patch.MAINGUI_INIT_KEY


def _require_bottom() -> Tuple[Any, Any]:
    """确保底层模块已加载；没有就抛带中文说明的 FrameworkError。"""
    if srhs_tool is None or patch is None:
        raise FrameworkError(
            '底层工具加载失败：%s\n'
            '  本工具需要同项目的 工具/底层/srhs工具.py 与 工具/底层/patch_browser_assets.py。\n'
            '  请确认拷贝时保留了这两个文件（整个 WER_函数库 文件夹一起拷最省事）。'
            % (_BOTTOM_ERROR or '未知原因'),
            EXIT_NEED)
    return srhs_tool, patch


# ============================================================================
# 四、通用小工具
# ============================================================================

def setup_console() -> None:
    """Windows 控制台按 UTF-8 输出中文（和底层工具一致）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


def now_timestamp() -> str:
    return time.strftime('%Y%m%d-%H%M%S')


def is_admin() -> bool:
    """当前进程是否拥有管理员权限（非 Windows / 取不到时按 False）。"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return False


def can_write_dir(path: str) -> bool:
    """试探目录是否可写（真正写入仍可能被 ACL/UAC 拒绝，这里只做预检）。"""
    try:
        probe = os.path.join(path, '.wer_framework_write_test_%d' % os.getpid())
        with open(probe, 'wb') as f:
            f.write(b'x')
        os.remove(probe)
        return True
    except OSError:
        return False


def fmt_bytes(n: int) -> str:
    """字节数变成人看的单位。"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    if n >= 1024 * 1024 * 1024:
        return '%.2f GB' % (n / 1024.0 / 1024.0 / 1024.0)
    if n >= 1024 * 1024:
        return '%.2f MB' % (n / 1024.0 / 1024.0)
    if n >= 1024:
        return '%.1f KB' % (n / 1024.0)
    return '%d B' % n


def sha256_file(path: str) -> str:
    """文件 sha256（调用底层实现，1MB 分块）。"""
    t, _ = _require_bottom()
    return t.sha256_file(path)


def default_work_dir() -> str:
    """
    框架临时/证据目录：优先 <工作区>/_分析临时/framework_work，
    工作区不可写时退回系统临时目录。返回已存在的绝对路径。
    """
    preferred = os.path.join(WORKSPACE_ROOT, '_分析临时', 'framework_work')
    try:
        os.makedirs(preferred, exist_ok=True)
        return preferred
    except OSError:
        pass
    fallback = os.path.join(tempfile.gettempdir(), 'WER_函数库_框架_work')
    os.makedirs(fallback, exist_ok=True)
    return fallback


def write_json(path: str, data: Any) -> str:
    """把结果写成 UTF-8 JSON（自动建目录），返回绝对路径。"""
    out = os.path.abspath(path)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    return out


def _log(enabled: bool, message: str) -> None:
    if enabled:
        print(message)
        sys.stdout.flush()


def _hsep(char: str = '=') -> None:
    print(char * 72)


def _title(text: str) -> None:
    _hsep()
    print(text)
    _hsep('-')


def _check(report: Dict[str, Any], name: str, ok: bool, detail: str = '',
           level: str = 'ERROR') -> None:
    """登记一条检查项；ERROR 进 errors，WARN 进 warnings。"""
    item = {'name': name, 'ok': bool(ok), 'level': level, 'detail': detail}
    report.setdefault('checks', []).append(item)
    if ok:
        return
    msg = ('%s（%s）' % (name, detail)) if detail else name
    if level == 'WARN':
        report.setdefault('warnings', []).append(msg)
    else:
        report.setdefault('errors', []).append(msg)


# ============================================================================
# 五、自动定位 AbilixScratch3.0 的 browser_assets
# ============================================================================

def _env(name: str) -> str:
    return (os.environ.get(name) or '').strip()


def _find_program_files_bases() -> List[str]:
    """收集常见的“程序目录”基路径（Program Files、各盘符 Program Files 等）。"""
    bases: List[str] = []
    seen = set()

    def add(path: str) -> None:
        if not path:
            return
        path = os.path.abspath(path)
        key = os.path.normcase(path)
        if key in seen:
            return
        seen.add(key)
        bases.append(path)

    for var in ('ProgramFiles', 'ProgramW6432', 'ProgramFiles(x86)', 'ProgramFiles(x86)_W6432'):
        add(_env(var))
    drives: List[str] = []
    for letter in string.ascii_uppercase:
        root = letter + ':\\'
        try:
            if os.path.isdir(root):
                drives.append(root)
        except OSError:
            continue
    for root in drives:
        add(os.path.join(root, 'Program Files'))
        add(os.path.join(root, 'Program Files (x86)'))
        add(root)  # 也允许装在盘符根目录（如 D:\\AbilixScratch3.0）
    # 去重后只保留存在的目录（不存在的不必参与 glob）
    return [b for b in bases if os.path.isdir(b)]


def find_install_candidates() -> List[Dict[str, Any]]:
    """
    列出所有“可能是 browser_assets”的候选路径（含不存在项，便于排错）。
    返回值：[{'path','source','exists','is_zfb'}]，按优先级排序。
    """
    candidates: List[Dict[str, Any]] = []
    seen = set()

    def add(path: str, source: str) -> None:
        if not path:
            return
        try:
            p = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
        except (OSError, ValueError):
            return
        key = os.path.normcase(p)
        if key in seen:
            return
        seen.add(key)
        exists = os.path.isfile(p)
        candidates.append({
            'path': p,
            'source': source,
            'exists': exists,
            'is_zfb': _is_zfb_file(p) if exists else False,
        })

    # 1) 环境变量：ABILIX_ASSETS（可指 browser_assets 文件 / Resources / 安装目录）
    env_assets = _env('ABILIX_ASSETS')
    if env_assets:
        for p in _expand_assets_hint(env_assets):
            add(p, '环境变量 ABILIX_ASSETS')
        add(env_assets, '环境变量 ABILIX_ASSETS（原样）')
    # 2) 环境变量：ABILIX_HOME（安装根目录）
    env_home = _env('ABILIX_HOME')
    if env_home:
        for p in _expand_install_root(env_home):
            add(p, '环境变量 ABILIX_HOME')
    # 3) 标准安装位置 + 通配扫描
    for base in _find_program_files_bases():
        for data_name in DATA_DIR_NAMES:
            add(os.path.join(base, 'AbilixScratch3.0', data_name, 'Resources', ASSETS_NAME),
                '标准安装路径')
        # 通配：AbilixScratch3*/AbilixScratch3*_Data/Resources/browser_assets
        for pattern in (os.path.join(base, 'AbilixScratch3*', '*_Data', 'Resources', ASSETS_NAME),
                        os.path.join(base, '*Abilix*', '*_Data', 'Resources', ASSETS_NAME)):
            try:
                for found in glob.glob(pattern):
                    add(found, '通配扫描')
            except OSError:
                continue
    return candidates


def _is_zfb_file(path: str) -> bool:
    """文件头是否像 zfbRes_v1 资源包（读前 64 字节，便宜）。"""
    try:
        with open(path, 'rb') as f:
            head = f.read(64)
        return b'zfbRes_v1' in head
    except OSError:
        return False


def _expand_assets_hint(value: str) -> List[str]:
    """
    把一个“用户给的路径提示”展开成候选 browser_assets 文件路径。
    支持：browser_assets 文件本身 / Resources 目录 / *_Data 目录 / 安装根目录。
    """
    try:
        p = os.path.abspath(os.path.expandvars(os.path.expanduser(value.strip().strip('"'))))
    except (OSError, ValueError):
        return []
    results: List[str] = []
    if os.path.isfile(p):
        results.append(p)
        return results
    if not os.path.isdir(p):
        return results
    results.append(os.path.join(p, ASSETS_NAME))                 # 直接是 browser_assets 所在目录
    results.append(os.path.join(p, 'Resources', ASSETS_NAME))    # 直接是 *_Data / Resources 的上级
    results.extend(_expand_install_root(p))
    return results


def _expand_install_root(value: str) -> List[str]:
    """安装根目录 / *_Data 目录 → browser_assets 候选列表。"""
    try:
        p = os.path.abspath(os.path.expandvars(os.path.expanduser(str(value).strip().strip('"'))))
    except (OSError, ValueError):
        return []
    results = [
        os.path.join(p, ASSETS_NAME),
        os.path.join(p, 'Resources', ASSETS_NAME),
    ]
    base = os.path.basename(os.path.normpath(p))
    if base in DATA_DIR_NAMES:
        results.append(os.path.join(p, 'Resources', ASSETS_NAME))
    for data_name in DATA_DIR_NAMES:
        results.append(os.path.join(p, data_name, 'Resources', ASSETS_NAME))
    try:
        for data_dir in glob.glob(os.path.join(p, '*_Data')):
            results.append(os.path.join(data_dir, 'Resources', ASSETS_NAME))
    except OSError:
        pass
    return results


def locate_install(assets: Optional[str] = None, verbose: bool = False) -> Dict[str, Any]:
    """
    自动找本机 AbilixScratch3.0 的 browser_assets 路径。

    参数
    ----
    assets : 可选，用户显式指定（命令行 --assets / 环境变量 ABILIX_ASSETS）。
             可给 browser_assets 文件、Resources 目录、*_Data 目录或安装根目录。
    verbose : True 时把候选清单也放进返回值（--json 用）。

    返回
    ----
    {'assets': 绝对路径, 'source': 来源说明, 'candidates': [...]}

    找不到时抛 FrameworkError(exit_code=2)，消息里列出尝试过的位置和解决办法。
    """
    candidates: List[Dict[str, Any]] = []
    if assets:
        hints = _expand_assets_hint(assets)
        if not hints:
            raise FrameworkError(
                '--assets 指定的路径不存在或无法识别：%s' % assets,
                EXIT_NEED,
                ['可以直接给 browser_assets 文件本身，或包含它的目录；'
                 '不写 --assets 时会自动扫描本机安装目录。'])
        found = None
        for path in hints:
            if os.path.isfile(path):
                found = path
                break
        if found is None:
            raise FrameworkError(
                '在 --assets 指定的位置里找不到 browser_assets 文件：%s\n'
                '  试过：%s' % (assets, '；'.join(hints[:6])),
                EXIT_NEED,
                ['正确示例：--assets "D:\\Program Files\\AbilixScratch3.0\\'
                 'AbilixScratch3.0_Data\\Resources\\browser_assets"',
                 '或只写安装根目录，让工具自己找：--assets "D:\\Program Files\\AbilixScratch3.0"'])
        candidates = [{'path': p, 'source': '命令行 --assets', 'exists': os.path.isfile(p),
                       'is_zfb': _is_zfb_file(p)} for p in hints]
        if not _is_zfb_file(found):
            raise FrameworkError(
                '找到的文件不是 zfbRes_v1 资源包（可能不是 browser_assets）：%s' % found,
                EXIT_NEED,
                ['请确认路径指向软件安装目录下 *_Data\\Resources\\browser_assets 这个文件。'])
        return {'assets': found, 'source': '命令行 --assets', 'candidates': candidates}

    candidates = find_install_candidates()
    for cand in candidates:
        if cand['exists'] and cand['is_zfb']:
            result = {'assets': cand['path'], 'source': cand['source'],
                      'candidates': candidates}
            if verbose:
                result['tried'] = [c['path'] for c in candidates]
            return result
    # 没找到：给出清晰中文提示
    existing_but_bad = [c['path'] for c in candidates if c['exists'] and not c['is_zfb']]
    suggestions = []
    if existing_but_bad:
        suggestions.append('发现同名文件但格式不对（不是 zfbRes_v1）：%s' % existing_but_bad[0])
    suggestions.extend([
        '用 --assets 显式指定 browser_assets 路径（推荐复制资源管理器里的完整路径）；',
        '或设置环境变量 ABILIX_ASSETS 指向该文件；',
        '正确路径形如：X:\\Program Files\\AbilixScratch3.0\\AbilixScratch3.0_Data\\Resources\\browser_assets',
        '确认本机已安装 AbilixScratch3.0（能力风暴）积木编程软件。'])
    raise FrameworkError(
        '没有自动找到 AbilixScratch3.0 的 browser_assets。\n'
        '  已扫描 %d 个候选位置，例如：\n    %s'
        % (len(candidates),
           '\n    '.join(c['path'] for c in candidates[:8]) or '（无）'),
        EXIT_NEED, suggestions)


# ============================================================================
# 六、函数库源文件：默认路径 / 片段生成 / 校验
# ============================================================================

def find_default_library(require: bool = True) -> Dict[str, Any]:
    """
    按优先级找函数库源文件：
      1. WER_函数库/我的函数库.srh / .srhs          （用户自己的库）
      2. WER_函数库/WER函数库.srh / .srhs           （旧文件名，兼容）
      3. WER_函数库/示例/WER函数库.srh / .srhs      （演示/自测用，会标记 fallback）
      4. 当前工作目录/我的函数库.srh(s)              （在别处打开 cmd 时）
    返回 {'path','label','is_my_library','fallback'}；找不到且 require=True 时抛错。
    """
    candidates: List[Dict[str, Any]] = []
    for name in LIBRARY_FILE_NAMES:
        candidates.append({'path': os.path.join(LIB_ROOT, name),
                           'label': name, 'fallback': False,
                           'is_my_library': name.startswith('我的函数库')})
    for name in ('WER函数库.srh', 'WER函数库.srhs'):
        candidates.append({'path': os.path.join(EXAMPLE_DIR, name),
                           'label': '示例/' + name, 'fallback': True,
                           'is_my_library': False})
    for name in ('我的函数库.srh', '我的函数库.srhs'):
        candidates.append({'path': os.path.join(os.getcwd(), name),
                           'label': './' + name, 'fallback': False,
                           'is_my_library': True})
    for cand in candidates:
        if os.path.isfile(cand['path']):
            cand['path'] = os.path.abspath(cand['path'])
            return cand
    if not require:
        return {}
    raise FrameworkError(
        '找不到函数库源文件（我的函数库.srh / .srhs）。\n'
        '  已找过：\n    %s'
        % '\n    '.join(c['path'] for c in candidates),
        EXIT_NEED,
        ['在 IDE 里搭好你的函数后，把项目另存为/复制到：%s'
         % os.path.join(LIB_ROOT, '我的函数库.srh（或 .srhs）'),
         '或者用 --library 指定任意 .srh/.srhs 项目文件。'])


def default_library_path() -> str:
    """默认函数库源文件路径（找不到抛 FrameworkError）。"""
    return str(find_default_library(require=True)['path'])


def _resolve_library(library: Optional[str]) -> Dict[str, Any]:
    """统一解析函数库路径：命令行给定优先，否则自动找默认库。"""
    if library:
        p = os.path.abspath(os.path.expandvars(os.path.expanduser(library.strip().strip('"'))))
        if not os.path.isfile(p):
            raise FrameworkError(
                '函数库源文件不存在：%s' % p,
                EXIT_NEED,
                ['--library 要指向一个 .srh 或 .srhs 项目文件（IDE 里保存的项目）。'])
        name = os.path.basename(p)
        return {'path': p, 'label': '命令行 --library', 'fallback': False,
                'is_my_library': name.startswith('我的函数库')}
    return find_default_library(require=True)


def build_fragment(library: Optional[str] = None, srh: Any = None) -> Dict[str, Any]:
    """
    从函数库源文件抽取 defaultcode 片段。

    片段 = `<xml xmlns="...">` 根 + `<variables>`（全部变量声明）+ 全部顶层 block
    （原样保留，顺序不变）。要求源文件**恰好 1 个 start 块**（新建项目模板必须有
    且只能有一个 start），否则抛 FrameworkError。

    返回
    ----
    {'fragment','source','top_blocks','start_blocks','functions':[{'name','args','type'}],
     'function_count','defnoreturn_count','defreturn_count',
     'variables','variable_count','chars'}
    """
    t, _ = _require_bottom()
    path = ''
    if srh is None:
        resolved = _resolve_library(library)
        path = resolved['path']
        try:
            srh = t.read_project_file(path)
        except (ValueError, OSError) as exc:
            raise FrameworkError('读取函数库文件失败：%s\n  文件：%s' % (exc, path), EXIT_FAIL)
    else:
        path = getattr(srh, 'source_path', '') or (library or '')

    proj = t.validate_project_xml(srh.project_xml)
    if not proj.get('ok'):
        raise FrameworkError(
            '函数库项目 XML 校验失败（请先用 校验我的函数库.py 查看详情）：\n  - '
            + '\n  - '.join(proj.get('errors') or []), EXIT_FAIL)
    start_count = int(proj.get('start_count', 0) or 0)
    if start_count != 1:
        raise FrameworkError(
            '函数库源文件必须恰好包含 1 个 start 块（当前 %d 个）。\n'
            '  start 块就是新项目里的“主函数”；多个 start 会让新建项目模板出现多个主函数，'
            'IDE 无法正常处理。\n'
            '  请打开源文件，只保留 1 个 start 块（其余删掉或改成普通函数）。' % start_count,
            EXIT_FAIL)
    if int(proj.get('top_block_count', 0) or 0) < 1:
        raise FrameworkError('函数库源文件里没有任何顶层积木（至少要有 1 个 start 块）。', EXIT_FAIL)
    try:
        fragment = t.extract_defaultcode(srh.project_xml, keep_variables=True, require_start=True)
    except ValueError as exc:
        raise FrameworkError('抽取默认模板片段失败：%s' % exc, EXIT_FAIL)
    frag_check = t.validate_project_xml(fragment)
    if not frag_check.get('ok'):
        raise FrameworkError(
            '生成的 defaultcode 片段不是合法项目 XML：\n  - '
            + '\n  - '.join(frag_check.get('errors') or []), EXIT_FAIL)
    if int(frag_check.get('start_count', 0) or 0) != 1:
        raise FrameworkError('生成的片段里 start 块数量异常（%s），已中止。'
                             % frag_check.get('start_count'), EXIT_FAIL)
    try:
        defs = t.find_def_blocks(srh.project_xml, t.DEF_BLOCK_TYPES)
    except ValueError:
        defs = []
    functions = [{'name': d['name'], 'args': list(d['args']), 'type': d['type']}
                 for d in defs]
    return {
        'fragment': fragment,
        'source': path,
        'top_blocks': int(frag_check.get('top_block_count', 0) or 0),
        'start_blocks': int(frag_check.get('start_count', 0) or 0),
        'functions': functions,
        'function_count': len(functions),
        'defnoreturn_count': len([f for f in functions if f['type'] == t.DEFNORETURN]),
        'defreturn_count': len([f for f in functions if f['type'] == t.DEFRETURN]),
        'variables': list(frag_check.get('variable_names') or []),
        'variable_count': len(frag_check.get('variable_names') or []),
        'chars': len(fragment),
    }


def _scan_call_blocks(project_xml: str) -> List[Dict[str, str]]:
    """扫描项目 XML 里所有函数调用块的 mutation name。"""
    calls: List[Dict[str, str]] = []
    for m in _CALL_BLOCK_RE.finditer(project_xml or ''):
        block_type, attrs = m.group(1), m.group(2)
        name = ''
        am = re.search(r'(?:^|\s)name\s*=\s*"([^"]*)"', attrs + ' ')
        if am:
            name = am.group(1)
        calls.append({'type': block_type, 'name': name})
    return calls


def _start_block_info(t: Any, project_xml: str) -> Dict[str, Any]:
    """分析 start 块里预置了哪些块（同步后会成为新项目的初始主函数内容）。"""
    try:
        split = t.split_top_level(project_xml)
    except ValueError:
        return {}
    start_raw = ''
    for seg in split['blocks']:
        if seg.get('type') == t.START_BLOCK:
            start_raw = seg['raw']
            break
    if not start_raw:
        return {}
    types = _BLOCK_TYPE_RE.findall(start_raw)
    return {'nested_block_count': max(0, len(types) - 1), 'nested_block_types': types[1:]}


def validate_library(library: Optional[str] = None) -> Dict[str, Any]:
    """
    校验函数库源文件（.srh / .srhs），返回结构化报告（不会抛异常）。

    检查项
    ------
    ERROR : 文件可读/可解析、XML 合法、恰好 1 个 start 块、无重名函数、
            无重名变量 id、参数名不重复、函数定义必须在顶层、片段可生成；
    WARN  : 函数名不是 ASCII 或不是 func_ 前缀、参数/变量名非 ASCII、
            孤立调用（调用了未定义的函数）、顶层注释不会被同步、start 里预置了块、
            存在有返回值函数块等。

    报告含：functions（名字/参数）、variables、top_block_count、start_count、
    orphan_calls、fragment 概要、checks 明细、ok（=无 ERROR）。
    """
    t, _ = _require_bottom()
    started = time.time()
    report: Dict[str, Any] = {
        'tool_version': VERSION,
        'path': '',
        'label': '',
        'kind': '',
        'exists': False,
        'ok': False,
        'exit_code': EXIT_FAIL,
        'errors': [],
        'warnings': [],
        'checks': [],
        'info': {},
        'robot_type': '',
        'robot_code': None,
        'program_name': '',
        'source_version': '',
        'top_block_count': 0,
        'start_count': 0,
        'block_type_counts': {},
        'functions': [],
        'function_count': 0,
        'defnoreturn_count': 0,
        'defreturn_count': 0,
        'orphan_calls': [],
        'variables': [],
        'variable_count': 0,
        'comment_count': 0,
        'start_body': {},
        'fragment_chars': 0,
        'fragment_top_blocks': 0,
        'fallback_library': False,
        'elapsed_sec': 0.0,
    }
    try:
        resolved = _resolve_library(library)
    except FrameworkError as exc:
        report['errors'].append(str(exc))
        report['exit_code'] = int(exc.exit_code)   # 文件缺失 -> 2
        report['elapsed_sec'] = round(time.time() - started, 3)
        return report
    path = resolved['path']
    report.update({'path': path, 'label': resolved['label'],
                   'fallback_library': bool(resolved.get('fallback'))})
    report['exists'] = True

    # ---- 1) 读文件 ----
    try:
        loaded = t.load_any_project(path)
    except (ValueError, OSError) as exc:
        report['errors'].append('读取函数库项目文件失败：%s' % exc)
        report['elapsed_sec'] = round(time.time() - started, 3)
        return report
    report['kind'] = loaded.get('kind', '')
    for err in loaded.get('errors') or []:
        report['errors'].append(err)
    for warn in loaded.get('warnings') or []:
        report['warnings'].append(warn)
    srh = loaded.get('srh')
    if srh is None:
        report['errors'].append('项目内容解析失败（见上面的错误）。')
        report['elapsed_sec'] = round(time.time() - started, 3)
        return report

    # ---- 2) Info 段 ----
    info_report = t.validate_info(srh.info_xml)
    for err in info_report.get('errors') or []:
        report['errors'].append(err)
    for warn in info_report.get('warnings') or []:
        report['warnings'].append(warn)
    info = info_report.get('info') or {}
    report['info'] = info
    report['robot_type'] = info.get('robot_type', '')
    report['program_name'] = info.get('download_program_name', '')
    report['source_version'] = info.get('version', '')
    try:
        report['robot_code'] = t.robot_code_of(report['robot_type'])
    except ValueError:
        report['robot_code'] = None

    # ---- 3) 项目 XML 结构校验（XML 合法 / 重名函数 / 变量顺序与 id 重复等） ----
    proj = t.validate_project_xml(srh.project_xml)
    for err in proj.get('errors') or []:
        report['errors'].append(err)
    for warn in proj.get('warnings') or []:
        report['warnings'].append(warn)
    report['top_block_count'] = int(proj.get('top_block_count', 0) or 0)
    report['start_count'] = int(proj.get('start_count', 0) or 0)
    report['block_type_counts'] = dict(proj.get('block_type_counts') or {})
    report['variables'] = list(proj.get('variable_names') or [])
    report['variable_count'] = len(report['variables'])

    # ---- 4) 顶层结构：函数定义 / 注释 / start 内容 ----
    defs: List[Dict[str, Any]] = []
    split = None
    try:
        split = t.split_top_level(srh.project_xml)
    except ValueError as exc:
        report['errors'].append('项目 XML 顶层结构解析失败：%s' % exc)
    if split is not None:
        for seg in split['blocks']:
            if seg.get('type') in t.DEF_BLOCK_TYPES:
                args = []
                try:
                    args = list(t.parse_def_args(seg['raw']))
                except ValueError:
                    args = []
                defs.append({'name': seg.get('name', ''), 'args': args,
                             'type': seg.get('type', '')})
        report['comment_count'] = len(split.get('comments') or [])
    report['functions'] = defs
    report['function_count'] = len(defs)
    report['defnoreturn_count'] = len([d for d in defs if d['type'] == t.DEFNORETURN])
    report['defreturn_count'] = len([d for d in defs if d['type'] == t.DEFRETURN])
    report['start_body'] = _start_block_info(t, srh.project_xml)

    # 函数定义块必须都在顶层（被拖进其它块里的定义不会被同步）
    total_def_blocks = len(re.findall(
        r'<block\b[^>]*\btype="procedures_def(?:noreturn|return)"', srh.project_xml or ''))
    _check(report, '函数定义块全部位于顶层',
           total_def_blocks == len(defs),
           '共 %d 个定义块，其中顶层 %d 个（有 %d 个被拖进了别的积木里，不会被同步）'
           % (total_def_blocks, len(defs), total_def_blocks - len(defs)))

    # ---- 5) 业务校验 ----
    _check(report, '恰好 1 个 start 块', report['start_count'] == 1,
           '当前 %d 个；新建项目模板必须恰好 1 个 start' % report['start_count'])
    if report['function_count'] == 0:
        report['warnings'].append(
            '函数库里没有 procedures_defnoreturn 函数定义：同步后新建项目不会带任何函数'
            '（只有 start 主函数）。')

    # 函数名 / 参数名
    bad_name_funcs = []
    bad_prefix_funcs = []
    bad_arg_funcs = []
    seen_names: Dict[str, int] = {}
    for f in defs:
        name = f.get('name') or ''
        if not name:
            continue
        seen_names[name] = seen_names.get(name, 0) + 1
        if not _PY_IDENT_RE.match(name):
            bad_name_funcs.append(name)
        if not name.startswith('func_'):
            bad_prefix_funcs.append(name)
        for arg in f.get('args') or []:
            if not arg or not _PY_IDENT_RE.match(arg):
                bad_arg_funcs.append('%s(%s)' % (name, arg))
    if bad_name_funcs:
        report['warnings'].append(
            '函数名不是 ASCII 标识符（生成 Python 函数名可能变形，建议只用字母数字下划线）：%s'
            % _short_list(bad_name_funcs))
    if bad_prefix_funcs:
        report['warnings'].append(
            '函数名没有句号前缀 func_（IDE 一般会自动加；建议统一用 func_ 开头）：%s'
            % _short_list(bad_prefix_funcs))
    if bad_arg_funcs:
        report['warnings'].append(
            '参数名不是 ASCII 标识符（生成 Python 参数名可能变形）：%s'
            % _short_list(bad_arg_funcs))
    dup_names = [n for n, c in seen_names.items() if c > 1]
    _check(report, '函数名不重复', not dup_names,
           '重复函数名：%s' % _short_list(dup_names))

    # 变量名检查（同名 / 非 ASCII）
    bad_var_names = [v for v in report['variables'] if not _PY_IDENT_RE.match(v or '')]
    if bad_var_names:
        report['warnings'].append(
            '变量名不是 ASCII 标识符（生成 Python 变量名可能变形，建议 var_ 前缀 + 英文）：%s'
            % _short_list(bad_var_names))
    dup_vars = sorted({v for v in report['variables'] if report['variables'].count(v) > 1})
    _check(report, '变量名不重复', not dup_vars,
           '重复变量名：%s' % _short_list(dup_vars))

    # 孤立调用：调用了源文件里没定义的函数（同步到模板后会生成调用未定义函数）
    try:
        calls = _scan_call_blocks(srh.project_xml)
    except Exception:  # noqa: BLE001 - 正则扫描不应崩，兜底
        calls = []
    defined = {f['name'] for f in defs if f.get('name')}
    orphan = sorted({c['name'] for c in calls if c.get('name') and c['name'] not in defined})
    empty_call = [c for c in calls if not c.get('name')]
    report['orphan_calls'] = orphan
    if orphan:
        report['warnings'].append(
            '孤立调用：项目里调用了未定义的函数 %s（同步后新建项目里这些调用会找不到函数）'
            % _short_list(orphan))
    if empty_call:
        report['warnings'].append('有 %d 个调用块的 mutation 缺少 name（可能是手工改坏的 XML）'
                                  % len(empty_call))
    total_call_blocks = len(_ANY_CALL_BLOCK_RE.findall(srh.project_xml or ''))
    if total_call_blocks != len(calls):
        report['warnings'].append(
            '有 %d 个调用块未解析到 mutation 信息（共 %d 个调用块），格式可能异常'
            % (total_call_blocks - len(calls), total_call_blocks))

    # 其它提示
    if report['comment_count']:
        report['warnings'].append(
            '顶层有 %d 个注释块不会被同步进默认模板（只同步函数定义等 block）；'
            '建议把说明写进 start 里的注释块。' % report['comment_count'])
    if report['start_body'].get('nested_block_count'):
        report['warnings'].append(
            'start 主函数里预置了 %d 个块（%s）：同步后每个新建项目都会自带这些块，'
            '建议只放一个“说明”注释。'
            % (report['start_body']['nested_block_count'],
               _short_list(report['start_body'].get('nested_block_types') or [])))
    # 游离顶层块：不属于函数定义/主函数的顶层块（通常是误拖出来的），会被原样同步进新项目
    stray_top: List[str] = []
    if split is not None:
        for seg in split['blocks']:
            stype = seg.get('type') or ''
            if stype in t.DEF_BLOCK_TYPES or stype == 'start':
                continue
            raw = seg.get('raw') or ''
            disabled = ('disabled="true"' in raw) or ("disabled='true'" in raw)
            stray_top.append(stype + ('（已禁用）' if disabled else ''))
    report['stray_top_blocks'] = stray_top
    if stray_top:
        report['warnings'].append(
            '函数库里有 %d 个游离顶层块（%s）：它们会被一起同步进每个新建项目；'
            '如果只是误拖出来的，请先在 IDE 里删除再同步。'
            % (len(stray_top), _short_list(stray_top)))
    if report['defreturn_count']:
        report['warnings'].append(
            '包含 %d 个 procedures_defreturn（有返回值函数）块：IDE 新建项目后'
            '“函数”分类里可能只出现调用块（官方把新建返回块注释掉了），建议优先用无返回值函数。'
            % report['defreturn_count'])

    # ---- 6) 尝试生成 defaultcode 片段（同步前就能确定能生成） ----
    try:
        frag = build_fragment(path, srh=srh)
        report['fragment_chars'] = frag['chars']
        report['fragment_top_blocks'] = frag['top_blocks']
        _check(report, '能生成新建项目默认模板片段', True)
    except FrameworkError as exc:
        report['errors'].append(str(exc))

    report['ok'] = not report['errors']
    report['exit_code'] = EXIT_OK if report['ok'] else EXIT_FAIL
    report['elapsed_sec'] = round(time.time() - started, 3)
    return report


def _short_list(items: Sequence[str], limit: int = 8) -> str:
    items = [str(x) for x in items]
    if len(items) <= limit:
        return '、'.join(items)
    return '、'.join(items[:limit]) + ' …（共 %d 个）' % len(items)


# ============================================================================
# 七、读取 browser_assets 里的 defaultcode（查看 / 自检共用）
# ============================================================================

def _read_assets_entry(assets_path: str, entry_name: str = TEMPLATE_ENTRY,
                       retries: int = 3) -> Dict[str, Any]:
    """
    从 browser_assets 里读出一个条目的内容（85MB 一次性读入，几秒内）。
    Windows 上安装目录偶发瞬时读取失败，这里做几次重试。
    """
    t, p = _require_bottom()
    path = os.path.abspath(assets_path)
    last_exc: Optional[BaseException] = None
    for attempt in range(1, retries + 1):
        try:
            info = p.read_zfb_index(path, with_data=True)
            data = info['data']
            file_sha = t.sha256_bytes(data)
            file_size = len(data)
            count = int(info['count'])
            try:
                blob = p.read_zfb_entry_bytes(info, entry_name)
            except KeyError:
                raise FrameworkError(
                    '资源包里找不到条目 %s（软件版本可能不同，或文件不是 AbilixScratch3.0 的 browser_assets）'
                    % entry_name, EXIT_NEED)
            finally:
                del info
            return {'assets': path, 'entry_name': entry_name, 'entry_bytes': blob,
                    'entry_sha256': t.sha256_bytes(blob), 'entry_bytes_len': len(blob),
                    'file_sha256': file_sha, 'file_size': file_size, 'count': count}
        except FrameworkError:
            raise
        except OSError as exc:  # 瞬时读取失败 -> 重试
            last_exc = exc
            if attempt < retries:
                time.sleep(0.4 * attempt)
        except ValueError as exc:
            raise FrameworkError('解析 browser_assets 失败：%s\n  文件：%s' % (exc, path), EXIT_FAIL)
    raise FrameworkError(
        '读取 browser_assets 失败（已重试 %d 次）：%s\n  文件：%s' % (retries, last_exc, path),
        EXIT_NEED,
        ['如果软件正在升级/杀毒软件正在扫描，请稍后再试；也可先关闭 IDE。'])


def parse_defaultcode_text(js_text: str) -> Dict[str, Any]:
    """
    从 maingui_init.js 文本里解析三种语言的 defaultcode 变量。
    返回 {'langs': {lang: {var,line,chars,xml,stats,functions,...}}, 'errors': []}
    """
    t, p = _require_bottom()
    result: Dict[str, Any] = {'langs': {}, 'errors': []}
    for lang, var_name in p.DEFAULTCODE_VARS.items():
        try:
            lineno, _start, raw = p.find_defaultcode_line(js_text, var_name)
        except ValueError as exc:
            result['errors'].append('找不到 var %s：%s' % (var_name, exc))
            continue
        xml_text = p.js_unescape_js_string(raw)
        stats = t.validate_project_xml(xml_text) if xml_text.strip().startswith('<xml') else {
            'ok': False, 'errors': ['defaultcode 不是以 <xml 开头'], 'warnings': [],
            'top_block_count': 0, 'start_count': 0, 'defnoreturn_names': [],
            'defreturn_names': [], 'variable_names': [], 'block_type_counts': {}}
        funcs: List[Dict[str, Any]] = []
        try:
            for d in t.find_def_blocks(xml_text, t.DEF_BLOCK_TYPES):
                funcs.append({'name': d['name'], 'args': list(d['args']),
                              'type': d['type']})
        except ValueError:
            funcs = []
        result['langs'][lang] = {
            'var': var_name,
            'line': lineno,
            'chars': len(xml_text),
            'xml': xml_text,
            'stats': stats,
            'functions': funcs,
            'function_count': len(funcs),
            'start_count': int(stats.get('start_count', 0) or 0),
            'top_block_count': int(stats.get('top_block_count', 0) or 0),
            'variables': list(stats.get('variable_names') or []),
        }
    return result


def read_template_defaultcode(assets: Optional[str] = None) -> Dict[str, Any]:
    """
    读取“当前软件里的新建项目默认模板”（browser_assets 内 maingui_init.js 的 defaultcode）。

    返回 {'assets','source','file_sha256','file_size','count','entry_sha256',
          'entry_bytes_len','js_lines','langs': {...}, 'errors': []}
    """
    t, _ = _require_bottom()
    loc = locate_install(assets)
    entry = _read_assets_entry(loc['assets'])
    js_text = t.decode_utf8(entry['entry_bytes'])
    parsed = parse_defaultcode_text(js_text)
    return {
        'assets': loc['assets'],
        'source': loc['source'],
        'file_sha256': entry['file_sha256'],
        'file_size': entry['file_size'],
        'count': entry['count'],
        'entry_sha256': entry['entry_sha256'],
        'entry_bytes_len': entry['entry_bytes_len'],
        'js_lines': js_text.count('\n') + 1,
        'langs': parsed['langs'],
        'errors': parsed['errors'],
    }


# ============================================================================
# 八、补丁后独立自检（框架层复核，不依赖底层补丁器的结论）
# ============================================================================

def verify_patched_package(patched_path: str, original_path: str, fragment: str,
                           langs: Sequence[str]) -> Dict[str, Any]:
    """
    对 patch_browser_assets.py 生成的补丁包做**独立**复核：

      1. 补丁包本身是合法 zfbRes_v1；
      2. 与原包逐条目 sha256 比较：只允许 maingui_init.js 变化，其余全部一致；
      3. maingui_init.js 确实变了；
      4. 回读每个被替换语言的 defaultcode，必须与期望片段**逐字符相同**；
      5. 未被替换的语言（繁中/英文）必须原样不动。

    返回 {'ok','errors','warnings','checks','changed_entries'}。
    """
    t, p = _require_bottom()
    report: Dict[str, Any] = {'ok': False, 'errors': [], 'warnings': [], 'checks': [],
                              'changed_entries': []}

    def check(name: str, ok: bool, detail: str = '') -> None:
        _check(report, name, ok, detail)

    # 1) 补丁包格式
    v = p.validate_zfb(patched_path)
    check('补丁包是合法的 zfbRes_v1 资源包', bool(v.get('ok')),
          '; '.join(v.get('errors') or []))

    # 2) 逐条目 sha256
    try:
        cmp_report = p.compare_zfb_packages(original_path, patched_path,
                                            allowed_changed=(TEMPLATE_ENTRY,))
    except (ValueError, OSError) as exc:
        check('逐条目 sha256 对比可执行', False, str(exc))
        report['ok'] = False
        return report
    check('除 maingui_init.js 外全部条目 sha256 不变', bool(cmp_report.get('ok')),
          '; '.join(cmp_report.get('errors') or []))
    changed = list(cmp_report.get('changed') or [])
    report['changed_entries'] = changed
    check('maingui_init.js 确实被修改', len(changed) == 1,
          '变化条目：%s' % _short_list([c.get('name', '') for c in changed]))
    check('条目数量/顺序与原包一致',
          int(cmp_report.get('old_count', -1)) == int(cmp_report.get('new_count', -2)),
          '原 %s / 新 %s' % (cmp_report.get('old_count'), cmp_report.get('new_count')))

    # 3) 回读 defaultcode
    try:
        original_parsed = parse_defaultcode_text(
            t.decode_utf8(_read_assets_entry(original_path)['entry_bytes']))
        patched_parsed = parse_defaultcode_text(
            t.decode_utf8(_read_assets_entry(patched_path)['entry_bytes']))
    except FrameworkError as exc:
        check('回读 maingui_init.js 的 defaultcode', False, str(exc))
        report['ok'] = False
        return report
    for lang in langs:
        old_entry = original_parsed['langs'].get(lang)
        new_entry = patched_parsed['langs'].get(lang)
        if new_entry is None:
            check('回读 %s defaultcode' % lang, False, '补丁包里找不到该语言变量')
            continue
        check('回读 %s defaultcode 与期望片段逐字符相同' % lang,
              new_entry['xml'] == fragment,
              '回读 %d 字符 / 期望 %d 字符' % (new_entry['chars'], len(fragment)))
        if old_entry is not None and old_entry['xml'] == new_entry['xml']:
            check('%s defaultcode 确实发生了变化' % lang, False, '内容与原包相同')
    for lang, new_entry in patched_parsed['langs'].items():
        if lang in langs:
            continue
        old_entry = original_parsed['langs'].get(lang)
        if old_entry is None:
            continue
        check('未替换的 %s defaultcode 保持原样' % lang,
              old_entry['xml'] == new_entry['xml'],
              '%s 与 %s 长度 %d/%d' % (old_entry['var'], new_entry['var'],
                                       old_entry['chars'], new_entry['chars']))
    report['ok'] = not report['errors']
    return report


# ============================================================================
# 九、同步：我的函数库 → 软件新建项目默认模板
# ============================================================================

def _parse_langs(langs: Any) -> List[str]:
    """解析 --langs：'zh-hans' / 'zh-hans,zh-hant,en' / 'all'。"""
    _, p = _require_bottom()
    try:
        return list(p._parse_langs(str(langs)))
    except ValueError as exc:
        raise FrameworkError('--langs 参数错误：%s' % exc, EXIT_FAIL,
                             ['可用：zh-hans / zh-hant / en / all（多个用逗号分隔）'])


def sync(library: Optional[str] = None, assets: Optional[str] = None,
         install: bool = True, dry_run: bool = False, langs: Any = 'zh-hans',
         out_path: Optional[str] = None, keep_work: bool = False,
         progress: bool = True, show_patch_progress: bool = False) -> Dict[str, Any]:
    """
    把函数库源文件同步进软件「新建项目」默认模板。

    参数
    ----
    library : 函数库源文件 .srh/.srhs；None 时自动找 我的函数库.srh(s)（必要时借用示例）。
    assets  : browser_assets 路径；None 时自动定位。
    install : True=请求写回安装目录；dry_run=True 或 install=False 时只生成补丁包。
    langs   : 要替换哪些语言的 defaultcode（默认 'zh-hans'，可 'all'）。
    out_path: 补丁包输出路径（默认 <工作区>/_分析临时/framework_work/browser_assets.patched）。
    progress / show_patch_progress : 控制台打印开关（--json 时应关掉）。

    返回
    ----
    dict，关键字段：ok / exit_code / installed / needs_admin / dry_run /
    library / assets / fragment / patch / self_check / install_readback / backup /
    errors / warnings / suggestions / elapsed_sec
    """
    t, p = _require_bottom()
    started = time.time()
    report: Dict[str, Any] = {
        'tool_version': VERSION,
        'phase': 'init',
        'ok': False,
        'exit_code': EXIT_FAIL,
        'dry_run': bool(dry_run or not install),
        'install_requested': bool(install),
        'installed': False,
        'needs_admin': False,
        'library': '',
        'library_label': '',
        'assets': '',
        'assets_source': '',
        'langs': [],
        'fragment': {},
        'patch': {},
        'self_check': {},
        'install_readback': {},
        'backup': None,
        'out': '',
        'errors': [],
        'warnings': [],
        'suggestions': [],
        'permission': {},
        'elapsed_sec': 0.0,
    }

    # ---- 1) 校验函数库源文件 ----
    _log(progress, '[1/4] 校验函数库源文件 ...')
    validation = validate_library(library)
    report['library'] = validation.get('path', '')
    report['library_label'] = validation.get('label', '')
    if not validation.get('ok'):
        report['phase'] = 'validate'
        report['errors'] = ['函数库源文件校验失败：'] + list(validation.get('errors') or [])
        report['warnings'] = list(validation.get('warnings') or [])
        report['exit_code'] = int(validation.get('exit_code', EXIT_FAIL))
        report['validation'] = _slim_validation(validation)
        report['elapsed_sec'] = round(time.time() - started, 3)
        return report
    report['validation'] = _slim_validation(validation)
    report['warnings'].extend(validation.get('warnings') or [])
    if validation.get('fallback_library'):
        report['warnings'].append(
            '没有找到 WER_函数库/我的函数库.srh(.srhs)，本次使用 %s 作为演示。'
            % validation.get('path'))
    lib_path = validation['path']
    _log(progress, '      函数 %d 个 / 变量 %d 个 / start %d 个 ✓'
         % (validation['function_count'], validation['variable_count'],
            validation['start_count']))

    # ---- 2) 生成片段 + 定位/校验 browser_assets ----
    _log(progress, '[2/4] 生成 defaultcode 片段并检查 browser_assets ...')
    try:
        fragment = build_fragment(lib_path)
    except FrameworkError as exc:
        report['phase'] = 'fragment'
        report['errors'].append(str(exc))
        report['exit_code'] = EXIT_FAIL
        report['elapsed_sec'] = round(time.time() - started, 3)
        return report
    report['fragment'] = {
        'source': fragment['source'],
        'chars': fragment['chars'],
        'top_blocks': fragment['top_blocks'],
        'start_blocks': fragment['start_blocks'],
        'function_count': fragment['function_count'],
        'defnoreturn_count': fragment['defnoreturn_count'],
        'variable_count': fragment['variable_count'],
        'functions': [{'name': f['name'], 'args': f['args']} for f in fragment['functions']],
        'variables': fragment['variables'],
    }
    _log(progress, '      片段 %d 字符：顶层块 %d（函数 %d / start %d），变量 %d 个 ✓'
         % (fragment['chars'], fragment['top_blocks'], fragment['function_count'],
            fragment['start_blocks'], fragment['variable_count']))
    try:
        langs_list = _parse_langs(langs)
        loc = locate_install(assets)
    except FrameworkError as exc:
        report['phase'] = 'locate'
        report['errors'].append(str(exc))
        report['suggestions'].extend(exc.suggestions)
        report['exit_code'] = EXIT_NEED
        report['elapsed_sec'] = round(time.time() - started, 3)
        return report
    report['langs'] = langs_list
    report['assets'] = loc['assets']
    report['assets_source'] = loc['source']
    _log(progress, '      browser_assets：%s（%s）' % (loc['assets'], loc['source']))
    assets_format = p.validate_zfb(loc['assets'])
    if not assets_format.get('ok'):
        report['phase'] = 'assets-format'
        report['errors'].append('browser_assets 格式校验失败：%s'
                                % '; '.join(assets_format.get('errors') or []))
        report['exit_code'] = EXIT_NEED
        report['elapsed_sec'] = round(time.time() - started, 3)
        return report

    # ---- 3) 安装权限预检 ----
    want_install = bool(install) and not dry_run
    assets_dir = os.path.dirname(loc['assets'])
    writable = can_write_dir(assets_dir)
    report['permission'] = {'is_admin': is_admin(), 'assets_dir': assets_dir,
                            'assets_dir_writable': writable}
    if want_install and not writable:
        want_install = False
        report['needs_admin'] = True
        report['warnings'].append(
            '没有写入安装目录的权限，已自动改为“演练模式”（只生成补丁包，不改安装目录）。')
        report['suggestions'].extend([
            '以管理员身份运行（任选其一）：',
            '  · 双击：%s' % os.path.join(_HERE, '同步我的函数库(管理员).cmd'),
            '  · 管理员命令行：python "%s" sync --install --library "%s" --assets "%s"'
            % (os.path.abspath(__file__), lib_path, loc['assets']),
            '如果不想动安装目录，也可使用“便携版”（复制一份软件到可写目录再打补丁）方案。'])
    if want_install and not is_admin():
        report['warnings'].append(
            '当前不是管理员进程，但安装目录可写，将继续安装（便携副本/可写目录场景常见）。')

    # ---- 4) 生成补丁包（先不安装：要先拿“原包”做独立自检，最后才写安装目录） ----
    if out_path is None:
        out_path = os.path.join(default_work_dir(), 'browser_assets.patched')
    out_abs = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_abs) or '.', exist_ok=True)
    report['out'] = out_abs
    report['phase'] = 'patch'
    _log(progress, '[3/4] 生成补丁包并做底层自检（纯 roundtrip / 逐条目 sha256 / 回读）...'
         '（85MB 资源包约需 1~5 分钟，视磁盘和杀毒软件）')
    patch_report = p.patch_assets(
        assets_path=loc['assets'],
        library_path=lib_path,
        out_path=out_abs,
        langs=langs_list,
        keep_variables=True,
        install=False,
        keep_work=keep_work,
        progress=bool(show_patch_progress),
    )
    report['patch'] = patch_report
    report['out'] = patch_report.get('out') or out_abs
    for warn in patch_report.get('warnings') or []:
        report['warnings'].append(warn)
    if not patch_report.get('ok'):
        report['errors'].extend(patch_report.get('errors') or ['补丁生成/自检失败（原因未给出）'])
        report['exit_code'] = EXIT_NEED if report['needs_admin'] else EXIT_FAIL
        report['elapsed_sec'] = round(time.time() - started, 3)
        return report

    # ---- 5) 框架层独立自检（此时安装目录还是原包，可以逐字节对比） ----
    report['phase'] = 'self-check'
    _log(progress, '[4/4] 框架层独立自检（重新读补丁包复核）...')
    self_check = verify_patched_package(report['out'], loc['assets'], fragment['fragment'],
                                        langs_list)
    report['self_check'] = self_check
    if not self_check.get('ok'):
        report['errors'].append('补丁包独立自检未通过：%s'
                                % '; '.join(self_check.get('errors') or []))
        report['exit_code'] = EXIT_FAIL
        report['elapsed_sec'] = round(time.time() - started, 3)
        return report
    _log(progress, '      ✓ 除 maingui_init.js 外其余条目 sha256 全部不变；'
                   '回读 defaultcode 与片段一致；未替换语言保持原样')

    # ---- 6) 真正安装（只有前面全部通过且用户要求时才写安装目录） ----
    if want_install:
        report['phase'] = 'install'
        _log(progress, '安装到安装目录（先自动备份原文件）...')
        install_report = p.install_assets(report['out'], loc['assets'])
        report['install'] = install_report
        if not install_report.get('ok'):
            report['errors'].append('安装失败：%s'
                                    % '; '.join(install_report.get('errors') or []))
            report['exit_code'] = (EXIT_NEED if not can_write_dir(assets_dir)
                                   else EXIT_FAIL)
            report['elapsed_sec'] = round(time.time() - started, 3)
            return report
        report['installed'] = True
        report['backup'] = install_report.get('backup')
        report['installed_sha256'] = install_report.get('sha256')
        _log(progress, '      ✓ 已写入安装目录；原文件备份：%s' % report['backup'])

    # ---- 7) 安装后回读安装目录 ----
    if report['installed']:
        _log(progress, '      回读安装目录里的 browser_assets ...')
        try:
            installed_entry = _read_assets_entry(loc['assets'])
            installed_parsed = parse_defaultcode_text(t.decode_utf8(installed_entry['entry_bytes']))
            readback: Dict[str, Any] = {
                'assets': loc['assets'],
                'file_sha256': installed_entry['file_sha256'],
                'entry_sha256': installed_entry['entry_sha256'],
                'langs': {},
            }
            readback_ok = True
            for lang in langs_list:
                item = installed_parsed['langs'].get(lang)
                same = bool(item and item['xml'] == fragment['fragment'])
                readback['langs'][lang] = {'chars': item['chars'] if item else 0, 'same': same}
                if not same:
                    readback_ok = False
            report['install_readback'] = readback
            if not readback_ok:
                report['errors'].append(
                    '安装后回读安装目录的 defaultcode 与期望片段不一致！请用 还原新建模板.py 还原。')
                report['exit_code'] = EXIT_FAIL
                report['elapsed_sec'] = round(time.time() - started, 3)
                return report
        except FrameworkError as exc:
            report['warnings'].append('安装后回读失败（不影响已安装结果）：%s' % exc)

    report['phase'] = 'done'
    report['ok'] = True
    if report['needs_admin']:
        report['exit_code'] = EXIT_NEED
    else:
        report['exit_code'] = EXIT_OK
    report['elapsed_sec'] = round(time.time() - started, 3)
    return report


def _slim_validation(report: Dict[str, Any]) -> Dict[str, Any]:
    """去掉片段 XML 等大字段，保留 JSON 可读的校验摘要。"""
    keys = ('tool_version', 'path', 'label', 'kind', 'exists', 'ok', 'exit_code',
            'robot_type', 'robot_code', 'program_name', 'source_version', 'top_block_count',
            'start_count', 'block_type_counts', 'function_count', 'defnoreturn_count',
            'defreturn_count', 'orphan_calls', 'variable_count', 'variables',
            'comment_count', 'start_body', 'fragment_chars', 'fragment_top_blocks',
            'fallback_library', 'elapsed_sec', 'functions')
    slim = {k: report.get(k) for k in keys if k in report}
    slim['errors'] = list(report.get('errors') or [])
    slim['warnings'] = list(report.get('warnings') or [])
    slim['checks'] = list(report.get('checks') or [])
    return slim


# ============================================================================
# 十、还原：用 browser_assets.备份-* 恢复
# ============================================================================

def list_backups(assets_path: str) -> List[Dict[str, Any]]:
    """列出与 browser_assets 同目录的备份文件（新的在前）。"""
    assets_path = os.path.abspath(assets_path)
    folder = os.path.dirname(assets_path)
    found: List[Dict[str, Any]] = []
    for pattern in (BACKUP_PREFIX + '*', PRE_RESTORE_PREFIX + '*'):
        for path in glob.glob(os.path.join(folder, pattern)):
            if not os.path.isfile(path):
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            found.append({
                'path': path,
                'name': os.path.basename(path),
                'kind': '备份' if os.path.basename(path).startswith(BACKUP_PREFIX) else '还原前备份',
                'size': st.st_size,
                'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
                '_mtime': st.st_mtime,
            })
    found.sort(key=lambda x: (x['_mtime'], x['name']), reverse=True)
    for item in found:
        item.pop('_mtime', None)
    return found


def restore(assets: Optional[str] = None, backup: Optional[str] = None,
            apply: bool = False, list_only: bool = False,
            progress: bool = True) -> Dict[str, Any]:
    """
    从 `browser_assets.备份-<时间戳>` 还原软件的新建项目默认模板。

    还原流程（先备份再覆盖，出错可回退）：
      1. 找备份（默认取最新的 browser_assets.备份-*；可用 --backup 指定）；
      2. 校验备份是合法 zfbRes_v1；
      3. 对比当前包与备份包（确认只差 maingui_init.js，可安全还原）；
      4. apply=True 时：把当前包另存为 `browser_assets.还原前备份-<时间戳>` →
         复制备份覆盖 browser_assets → 校验 sha256 / 格式 / 回读 defaultcode。

    返回 dict（ok / apply / assets / backup / backups / current_sha256 /
    backup_sha256 / same / diff / wants_admin / restored / errors / warnings /
    suggestions / exit_code）。

    注意：多次同步会产生多份备份；最新备份 = 上一次同步前的状态（可能也是打过补丁的）。
    要回到“出厂原始模板”，请用 --backup 指定最早的那份备份。
    """
    t, p = _require_bottom()
    report: Dict[str, Any] = {
        'tool_version': VERSION, 'ok': False, 'exit_code': EXIT_FAIL, 'apply': bool(apply),
        'list_only': bool(list_only), 'assets': '', 'backup': None, 'backups': [],
        'current_sha256': '', 'backup_sha256': '', 'same': False, 'diff': {},
        'wants_admin': False, 'restored': False, 'restored_template': {},
        'pre_restore_backup': None,
        'errors': [], 'warnings': [], 'suggestions': [], 'elapsed_sec': 0.0,
    }
    started = time.time()
    try:
        loc = locate_install(assets)
    except FrameworkError as exc:
        report['errors'].append(str(exc))
        report['suggestions'].extend(exc.suggestions)
        report['exit_code'] = EXIT_NEED
        return report
    assets_path = loc['assets']
    report['assets'] = assets_path
    report['assets_source'] = loc['source']
    backups = list_backups(assets_path)
    report['backups'] = backups
    if list_only:
        report['ok'] = True
        report['exit_code'] = EXIT_OK
        return report
    if not backups:
        report['errors'].append(
            '没有找到备份文件（%s*）。\n  目录：%s\n'
            '  说明：备份只在“打补丁”时自动生成；如果软件升级/重装过，旧备份可能已丢失。'
            % (BACKUP_PREFIX, os.path.dirname(assets_path)))
        report['suggestions'].append(
            '若之前从未打过补丁，说明当前就是原始模板，不需要还原。')
        report['exit_code'] = EXIT_NEED
        return report

    # 选目标备份
    if backup:
        target = os.path.abspath(os.path.expandvars(os.path.expanduser(backup.strip().strip('"'))))
        if not os.path.isfile(target):
            report['errors'].append('--backup 指定的备份文件不存在：%s' % target)
            report['exit_code'] = EXIT_NEED
            return report
        target_info = {'path': target, 'name': os.path.basename(target), 'kind': '指定备份'}
    else:
        target = backups[0]['path']
        target_info = {'path': target, 'name': backups[0]['name'], 'kind': backups[0]['kind']}
    report['backup'] = target
    report['backup_kind'] = target_info['kind']

    # 校验备份
    backup_validate = p.validate_zfb(target)
    if not backup_validate.get('ok'):
        report['errors'].append('备份文件不是合法的 browser_assets：%s（%s）'
                                % (target, '; '.join(backup_validate.get('errors') or [])))
        report['exit_code'] = EXIT_NEED
        return report
    current_validate = p.validate_zfb(assets_path)
    if not current_validate.get('ok'):
        report['errors'].append('当前 browser_assets 已损坏，无法安全还原：%s'
                                % '; '.join(current_validate.get('errors') or []))
        report['exit_code'] = EXIT_NEED
        return report
    report['current_sha256'] = t.sha256_file(assets_path)
    report['backup_sha256'] = t.sha256_file(target)
    report['current_size'] = os.path.getsize(assets_path)
    report['backup_size'] = os.path.getsize(target)
    report['same'] = report['current_sha256'] == report['backup_sha256']

    # 差异分析（确认可以安全还原）
    if report['same']:
        report['warnings'].append('当前 browser_assets 与这份备份完全相同，无需还原。')
        report['warnings'].append(
            '提示：如果当前已是打过补丁的状态，说明你选到的是“打补丁后”的备份；'
            '要回到出厂模板请换一份更早的备份（--backup）。')
    else:
        try:
            diff = p.compare_zfb_packages(assets_path, target,
                                          allowed_changed=(TEMPLATE_ENTRY,))
        except (ValueError, OSError) as exc:
            report['errors'].append('对比当前包与备份包失败：%s' % exc)
            report['exit_code'] = EXIT_FAIL
            return report
        report['diff'] = {
            'ok': bool(diff.get('ok')),
            'changed': list(diff.get('changed') or []),
            'errors': list(diff.get('errors') or []),
            'warnings': list(diff.get('warnings') or []),
        }
        if not diff.get('ok'):
            report['errors'].append(
                '当前包与备份包的差异不止 maingui_init.js，直接还原可能不安全：\n  - '
                + '\n  - '.join(diff.get('errors') or []))
            report['suggestions'].append(
                '如果确认要用这份备份覆盖，可在管理员命令行加 --backup 指定后重试；'
                '或先把当前 browser_assets 手工复制一份再操作。')
    # 看备份里的模板是不是原始模板（0 函数）
    try:
        parsed = parse_defaultcode_text(
            t.decode_utf8(_read_assets_entry(target)['entry_bytes']))
        zh = parsed['langs'].get('zh-hans') or {}
        report['restored_template'] = {
            'function_count': zh.get('function_count', 0),
            'functions': [f['name'] for f in zh.get('functions') or []],
            'variable_count': len(zh.get('variables') or []),
            'top_block_count': zh.get('top_block_count', 0),
            'is_original': (zh.get('function_count', 0) == 0),
        }
    except FrameworkError as exc:
        report['warnings'].append('读取备份里的默认模板失败（不影响还原）：%s' % exc)

    if not apply:
        report['ok'] = True
        report['exit_code'] = EXIT_OK
        report['elapsed_sec'] = round(time.time() - started, 3)
        return report

    # ---- 真正还原 ----
    folder = os.path.dirname(assets_path)
    if not can_write_dir(folder):
        report['wants_admin'] = True
        report['errors'].append(
            '没有写入安装目录的权限，无法还原。\n  目录：%s\n  当前是否管理员：%s'
            % (folder, is_admin()))
        report['suggestions'].extend([
            '以管理员身份运行（任选其一）：',
            '  · 双击：%s' % os.path.join(_HERE, '还原新建模板(管理员).cmd'),
            '  · 管理员命令行：python "%s" restore --yes --assets "%s"'
            % (os.path.abspath(__file__), assets_path)])
        report['exit_code'] = EXIT_NEED
        return report
    try:
        pre_name = PRE_RESTORE_PREFIX + now_timestamp()
        pre_path = os.path.join(folder, pre_name)
        suffix = 1
        while os.path.exists(pre_path):
            pre_path = os.path.join(folder, PRE_RESTORE_PREFIX + now_timestamp() + '_%d' % suffix)
            suffix += 1
        _log(progress, '  1/3 先把当前 browser_assets 另存为：%s' % pre_path)
        shutil.copy2(assets_path, pre_path)
        if t.sha256_file(pre_path) != report['current_sha256']:
            raise FrameworkError('把当前文件另存为还原前备份后 sha256 校验不一致，已中止（未做还原）。',
                                 EXIT_FAIL)
        report['pre_restore_backup'] = pre_path
        _log(progress, '  2/3 用备份覆盖 browser_assets ...')
        shutil.copy2(target, assets_path)
        new_sha = t.sha256_file(assets_path)
        report['restored_sha256'] = new_sha
        if new_sha != report['backup_sha256']:
            raise FrameworkError(
                '还原后 browser_assets 的 sha256 与备份不一致！请再次运行还原，或手工把备份复制回去：%s'
                % target, EXIT_FAIL)
        check = p.validate_zfb(assets_path)
        if not check.get('ok'):
            raise FrameworkError('还原后资源包格式校验失败：%s'
                                 % '; '.join(check.get('errors') or []), EXIT_FAIL)
        _log(progress, '  3/3 回读还原后的默认模板 ...')
        parsed2 = parse_defaultcode_text(
            t.decode_utf8(_read_assets_entry(assets_path)['entry_bytes']))
        zh2 = parsed2['langs'].get('zh-hans') or {}
        report['restored_template'] = {
            'function_count': zh2.get('function_count', 0),
            'functions': [f['name'] for f in zh2.get('functions') or []],
            'variable_count': len(zh2.get('variables') or []),
            'top_block_count': zh2.get('top_block_count', 0),
            'is_original': (zh2.get('function_count', 0) == 0),
        }
        report['restored'] = True
        report['ok'] = True
        report['exit_code'] = EXIT_OK
    except (FrameworkError, OSError, shutil.Error) as exc:
        report['errors'].append('还原失败：%s' % exc)
        if report.get('pre_restore_backup'):
            report['suggestions'].append(
                '还原前备份在：%s（如当前文件损坏，可用它复制回 browser_assets）'
                % report['pre_restore_backup'])
        report['exit_code'] = EXIT_FAIL
    report['elapsed_sec'] = round(time.time() - started, 3)
    return report


# ============================================================================
# 十一、查看当前软件里的新建项目默认模板
# ============================================================================

def inspect_current_template(assets: Optional[str] = None,
                             library: Optional[str] = None) -> Dict[str, Any]:
    """
    查看“当前软件的新建项目默认模板”里到底是什么（函数/参数/变量/顶层块）。

    读取 browser_assets → Blockly_Code/maingui_init.js → 三种语言的 defaultcode →
    解析 XML。可与函数库源文件对比（新增/缺失/参数不同/变量不同），
    并自动判断当前是“原始模板”还是“已打过补丁”。

    返回 dict：assets 信息、langs（每语言内容摘要）、classification、
    compare（若给了/找到了函数库）、backup（最近备份是否与当前一致）、errors。
    """
    t, _ = _require_bottom()
    report: Dict[str, Any] = {
        'tool_version': VERSION, 'ok': False, 'exit_code': EXIT_FAIL,
        'assets': '', 'assets_source': '', 'file_sha256': '', 'file_size': 0,
        'count': 0, 'entry_sha256': '', 'entry_bytes_len': 0, 'js_lines': 0,
        'langs': {}, 'classification': '', 'template_kind': 'unknown',
        'compare': {}, 'backup': {}, 'errors': [], 'warnings': [],
    }
    try:
        loc = locate_install(assets)
    except FrameworkError as exc:
        report['errors'].append(str(exc))
        report['suggestions'] = list(exc.suggestions)
        report['exit_code'] = EXIT_NEED
        return report
    report['assets'] = loc['assets']
    report['assets_source'] = loc['source']
    try:
        entry = _read_assets_entry(loc['assets'])
        parsed = parse_defaultcode_text(t.decode_utf8(entry['entry_bytes']))
    except FrameworkError as exc:
        report['errors'].append(str(exc))
        report['suggestions'] = list(exc.suggestions)
        report['exit_code'] = EXIT_NEED
        return report
    report.update({
        'file_sha256': entry['file_sha256'],
        'file_size': entry['file_size'],
        'count': entry['count'],
        'entry_sha256': entry['entry_sha256'],
        'entry_bytes_len': entry['entry_bytes_len'],
        'js_lines': t.decode_utf8(entry['entry_bytes']).count('\n') + 1,
    })
    langs_out: Dict[str, Any] = {}
    for lang, item in parsed['langs'].items():
        stats = item.get('stats') or {}
        start_types: List[str] = []
        try:
            split = t.split_top_level(item['xml'])
            for seg in split['blocks']:
                if seg.get('type') == t.START_BLOCK:
                    start_types = _BLOCK_TYPE_RE.findall(seg['raw'])[1:]
                    break
        except ValueError:
            start_types = []
        langs_out[lang] = {
            'var': item['var'],
            'line': item['line'],
            'chars': item['chars'],
            'top_block_count': item['top_block_count'],
            'start_count': item['start_count'],
            'function_count': item['function_count'],
            'functions': item['functions'],
            'variable_count': len(item.get('variables') or []),
            'variables': item.get('variables') or [],
            'start_nested_block_types': start_types,
            'xml_ok': bool(stats.get('ok')),
            'xml_errors': list(stats.get('errors') or []),
        }
    report['langs'] = langs_out
    report['errors'].extend(parsed.get('errors') or [])
    zh = langs_out.get('zh-hans') or next(iter(langs_out.values()), {})
    zh_functions = [f['name'] for f in zh.get('functions') or []]

    # ---- 与最近备份对比：判断是否被改过 ----
    backups = list_backups(loc['assets'])
    if backups:
        latest = backups[0]
        try:
            backup_entry = _read_assets_entry(latest['path'])
            report['backup'] = {
                'path': latest['path'],
                'name': latest['name'],
                'mtime': latest.get('mtime', ''),
                'same_as_current': backup_entry['entry_sha256'] == report['entry_sha256'],
                'entry_sha256': backup_entry['entry_sha256'],
            }
        except FrameworkError as exc:
            report['warnings'].append('读取最近备份失败（不影响查看）：%s' % exc)
    else:
        report['backup'] = {'path': None, 'same_as_current': None}

    # ---- 判定当前模板状态 ----
    # 出厂原始模板的特征（本 IDE 版本实测）：只有 1 个顶层 start、0 函数、0 变量，
    # start 里预置 annotation + printf_text。本机无备份时用这个特征判断“原始模板”。
    zh_start_types = list(zh.get('start_nested_block_types') or [])
    factory_match = (
        not zh_functions
        and int(zh.get('top_block_count', 0) or 0) == 1
        and int(zh.get('start_count', 0) or 0) == 1
        and not (zh.get('variables') or [])
        and zh_start_types == ['annotation', 'printf_text'])
    report['factory_template_signature_match'] = factory_match
    same_as_backup = (report['backup'].get('same_as_current') is True)
    if zh_functions:
        report['classification'] = ('已打过补丁：函数分类里有 %d 个函数调用块' % len(zh_functions))
        report['template_kind'] = 'patched'
        if report['backup'].get('same_as_current') is False:
            report['warnings'].append(
                '当前模板与最近备份不同（最近备份可能是打补丁之前的状态）。')
    elif factory_match:
        report['classification'] = '原始模板（未打补丁）'
        report['template_kind'] = 'original'
        if report['backup'].get('same_as_current') is False:
            report['warnings'].append(
                '当前模板是出厂原始模板，但与最近备份的内容不同（备份可能是打补丁后的状态）。')
    else:
        report['classification'] = ('未含函数定义的模板（0 个函数；结构与出厂模板不同，可能被改过）')
        report['template_kind'] = 'modified'

    # ---- 与函数库源文件对比 ----
    lib_info: Dict[str, Any] = {}
    if library:
        lib_info = _resolve_library(library)
    else:
        lib_info = find_default_library(require=False)
    if lib_info:
        try:
            lib_validation = validate_library(lib_info['path'])
            if lib_validation.get('ok'):
                lib_funcs = {f['name']: list(f['args'])
                             for f in lib_validation.get('functions') or []}
                cur_funcs = {f['name']: list(f['args'])
                             for f in zh.get('functions') or []}
                added = [n for n in lib_funcs if n not in cur_funcs]
                missing = [n for n in cur_funcs if n not in lib_funcs]
                changed = []
                for name in lib_funcs:
                    if name in cur_funcs and list(lib_funcs[name]) != list(cur_funcs[name]):
                        changed.append({'name': name, 'current_args': cur_funcs[name],
                                        'library_args': lib_funcs[name]})
                lib_vars = set(lib_validation.get('variables') or [])
                cur_vars = set(zh.get('variables') or [])
                # 直接比较“当前模板的 defaultcode”和“函数库应生成的片段”是否逐字符相同，
                # 这比只看函数名更能反映“跑一次同步会不会改变模板”。
                primary_lang = 'zh-hans' if 'zh-hans' in parsed['langs'] else (
                    next(iter(parsed['langs']), ''))
                current_xml = ''
                if primary_lang:
                    current_xml = (parsed['langs'][primary_lang] or {}).get('xml') or ''
                expected_fragment = ''
                try:
                    expected_fragment = build_fragment(lib_info['path'])['fragment']
                except FrameworkError as exc:
                    report['warnings'].append('生成函数库片段失败（无法判断是否一致）：%s' % exc)
                identical = bool(expected_fragment) and current_xml == expected_fragment
                report['compare'] = {
                    'library': lib_info['path'],
                    'library_label': lib_info.get('label', ''),
                    'library_ok': True,
                    'library_function_count': len(lib_funcs),
                    'current_function_count': len(cur_funcs),
                    'to_add': added,
                    'to_remove': missing,
                    'args_changed': changed,
                    'variables_to_add': sorted(lib_vars - cur_vars),
                    'variables_to_remove': sorted(cur_vars - lib_vars),
                    'expected_fragment_chars': len(expected_fragment),
                    'current_template_chars': len(current_xml),
                    'template_identical_to_library': identical,
                    'need_sync': (not identical) if expected_fragment else bool(
                        added or missing or changed or (lib_vars != cur_vars)),
                }
            else:
                report['compare'] = {
                    'library': lib_info['path'],
                    'library_ok': False,
                    'library_errors': list(lib_validation.get('errors') or []),
                }
        except FrameworkError as exc:
            report['warnings'].append('与函数库对比失败：%s' % exc)
    report['ok'] = not report['errors']
    report['exit_code'] = EXIT_OK if report['ok'] else EXIT_FAIL
    return report


# ============================================================================
# 十二、生成新项目文件（不装补丁也能用）
# ============================================================================

def make_new_project(library: Optional[str] = None, out_path: Optional[str] = None,
                     program: str = 'ProgramA', robot: Optional[str] = None,
                     force: bool = False, progress: bool = True) -> Dict[str, Any]:
    """
    把函数库源文件打包成一个可直接「文件→打开」的 .srhs 新项目文件。

    做法：片段（<xml>+<variables>+全部顶层 block，含 1 个 start）+ Info 段
    （RobotType / DownloadProgramName）→ .srh 文本 → zip（唯一条目
    abilixProject.srh，zip 注释 = 机器人枚举数字，默认 111=SKCON9）。

    不依赖 browser_assets / 不装补丁也能用：打开这个文件就是“自带函数库的完整项目”。

    返回 dict：path/bytes/sha256/robot_type/robot_code/program/fragment 摘要/
    verify（读回校验）/errors。
    """
    t, _ = _require_bottom()
    report: Dict[str, Any] = {
        'tool_version': VERSION, 'ok': False, 'exit_code': EXIT_FAIL,
        'library': '', 'path': '', 'bytes': 0, 'sha256': '',
        'robot_type': '', 'robot_code': None, 'program': program,
        'fragment': {}, 'verify': {}, 'errors': [], 'warnings': [],
    }
    started = time.time()
    try:
        resolved = _resolve_library(library)
    except FrameworkError as exc:
        report['errors'].append(str(exc))
        report['exit_code'] = EXIT_NEED
        return report
    report['library'] = resolved['path']
    if resolved.get('fallback'):
        report['warnings'].append('没有找到 我的函数库.srh(.srhs)，使用 %s（演示）'
                                  % resolved['path'])
    try:
        fragment = build_fragment(resolved['path'])
        srh = t.read_project_file(resolved['path'])
    except (FrameworkError, ValueError, OSError) as exc:
        report['errors'].append('读取/抽取函数库失败：%s' % exc)
        report['exit_code'] = EXIT_FAIL
        return report
    report['fragment'] = {
        'chars': fragment['chars'], 'top_blocks': fragment['top_blocks'],
        'start_blocks': fragment['start_blocks'],
        'function_count': fragment['function_count'],
        'variable_count': fragment['variable_count'],
    }
    # 机器人类型：命令行 > 源文件 Info > SKCON9
    robot_value = robot or srh.robot_type or t.DEFAULT_ROBOT_TYPE
    try:
        robot_type = t.normalize_robot_type(robot_value)
    except ValueError as exc:
        report['errors'].append('机器人类型无效：%s' % exc)
        report['exit_code'] = EXIT_NEED
        return report
    version = srh.version or t.DEFAULT_VERSION
    program_name = (program or '').strip() or t.DEFAULT_PROGRAM_NAME
    info_xml = t.make_info_xml(robot_type, version, program_name)
    project_xml = fragment['fragment']
    srh_new = t.SrhFile(info=t.parse_info_xml(info_xml), info_xml=info_xml,
                        project_xml=project_xml)
    if out_path is None:
        stem = os.path.splitext(os.path.basename(resolved['path']))[0]
        out_path = os.path.join(os.path.dirname(resolved['path']),
                                stem + '_新项目.srhs')
    out_abs = os.path.abspath(os.path.expandvars(os.path.expanduser(out_path)))
    if os.path.exists(out_abs) and not force:
        report['errors'].append('输出文件已存在：%s（加 --force 覆盖，或换 --out）' % out_abs)
        report['exit_code'] = EXIT_FAIL
        return report
    os.makedirs(os.path.dirname(out_abs) or '.', exist_ok=True)
    _log(progress, '打包新项目文件：%s（机器人 %s，程序名 %s）...'
         % (out_abs, robot_type, program_name))
    try:
        pack = t.pack_srhs(srh_new, out_abs, robot=robot_type, verify=True)
    except (ValueError, OSError, RuntimeError) as exc:
        report['errors'].append('打包 .srhs 失败：%s' % exc)
        report['exit_code'] = EXIT_FAIL
        return report
    report.update({
        'path': out_abs,
        'bytes': pack.get('zip_bytes', os.path.getsize(out_abs)),
        'sha256': pack.get('zip_sha256', t.sha256_file(out_abs)),
        'robot_type': robot_type,
        'robot_code': t.robot_code_of(robot_type),
    })
    # 读回验证：项目 XML == 片段；函数/变量数量一致
    verify: Dict[str, Any] = {'ok': False, 'errors': [], 'warnings': []}
    try:
        v = t.validate_srhs(out_abs)
        verify['validate_srhs_ok'] = bool(v.get('ok'))
        verify['errors'].extend(v.get('errors') or [])
        readback = t.read_project_file(out_abs)
        verify['project_xml_same_as_fragment'] = (
            readback.project_xml.strip() == project_xml.strip())
        readback_check = t.validate_project_xml(readback.project_xml)
        verify['start_count'] = int(readback_check.get('start_count', 0) or 0)
        verify['defnoreturn_names'] = list(readback_check.get('defnoreturn_names') or [])
        verify['variable_count'] = len(readback_check.get('variable_names') or [])
        verify['comment'] = getattr(readback, 'raw_comment', '')
        if not verify['project_xml_same_as_fragment']:
            verify['errors'].append('读回的项目 XML 与片段不一致')
        if verify['start_count'] != 1:
            verify['errors'].append('读回后 start 块数量不是 1：%s' % verify['start_count'])
        verify['ok'] = (not verify['errors']) and verify['validate_srhs_ok']
    except (ValueError, OSError) as exc:
        verify['errors'].append('读回验证失败：%s' % exc)
    report['verify'] = verify
    report['ok'] = bool(report['verify'].get('ok'))
    report['exit_code'] = EXIT_OK if report['ok'] else EXIT_FAIL
    if not report['ok']:
        report['errors'].extend(verify.get('errors') or [])
    report['elapsed_sec'] = round(time.time() - started, 3)
    return report


# ============================================================================
# 十三、控制台报告（人看的输出）
# ============================================================================

def _print_list(lines: Sequence[str], indent: str = '  ') -> None:
    for line in lines:
        print(indent + line)


def print_validate_report(report: Dict[str, Any]) -> None:
    _title('函数库源文件校验')
    print('文件          : %s' % (report.get('path') or '（无）'))
    print('来源          : %s' % (report.get('label') or ''))
    print('类型          : %s' % ('压缩项目 .srhs' if report.get('kind') == 'srhs'
                                 else '项目 XML .srh'))
    print('机器人/程序名 : %s / %s' % (report.get('robot_type') or '?',
                                      report.get('program_name') or '?'))
    print('顶层块        : %d（函数 %d，start %d，其它 %d）'
          % (report.get('top_block_count', 0), report.get('function_count', 0),
             report.get('start_count', 0),
             max(0, report.get('top_block_count', 0) - report.get('function_count', 0)
                 - report.get('start_count', 0))))
    print('变量声明      : %d 个%s'
          % (report.get('variable_count', 0),
             ('：' + _short_list(report.get('variables') or [])) if report.get('variables') else ''))
    if report.get('fragment_chars'):
        print('defaultcode 片段: %d 字符（顶层块 %d）'
              % (report.get('fragment_chars', 0), report.get('fragment_top_blocks', 0)))
    print('-' * 72)
    funcs = report.get('functions') or []
    if funcs:
        print('函数列表（%d 个）：' % len(funcs))
        for i, f in enumerate(funcs, 1):
            args = ', '.join(f.get('args') or [])
            print('  %2d. %s(%s)%s' % (i, f.get('name') or '?', args,
                                       '' if f.get('type', '').endswith('defnoreturn')
                                       else '   [有返回值]'))
    else:
        print('函数列表：没有函数定义（只有 start 主函数）')
    if report.get('orphan_calls'):
        print('孤立调用（未定义函数）：%s' % _short_list(report['orphan_calls']))
    print('-' * 72)
    warnings = report.get('warnings') or []
    errors = report.get('errors') or []
    for warn in warnings:
        print('[WARN] %s' % warn)
    for err in errors:
        print('[ERROR] %s' % err)
    if not warnings and not errors:
        print('（没有警告，没有错误）')
    print('-' * 72)
    if report.get('ok'):
        print('结论：通过（ERROR=0，WARN=%d）✓  可以运行 同步我的函数库.py' % len(warnings))
    else:
        print('结论：失败（ERROR=%d）✗  请先修正上面的错误再同步' % len(errors))
    _hsep()


def print_sync_report(report: Dict[str, Any]) -> None:
    patch_report = report.get('patch') or {}
    title = '同步我的函数库 → 软件「新建项目」默认模板'
    _title(title)
    if report.get('installed'):
        print('模式          : 【已安装到安装目录】')
    elif report.get('install_requested') and not report.get('dry_run'):
        print('模式          : 【演练：没有权限写安装目录，补丁包已生成】')
    else:
        print('模式          : 【演练：只生成补丁包并自检，不写安装目录】')
    print('函数库源      : %s' % (report.get('library') or '（无）'))
    frag = report.get('fragment') or {}
    if frag:
        print('              函数 %d 个 / 变量 %d 个 / 片段 %d 字符'
              % (frag.get('function_count', 0), frag.get('variable_count', 0),
                 frag.get('chars', 0)))
        names = [f.get('name', '') for f in (frag.get('functions') or []) if f.get('name')]
        if names:
            print('              函数列表：%s' % _short_list(names))
    print('browser_assets: %s' % (report.get('assets') or '（无）'))
    if report.get('assets_source'):
        print('              来源：%s' % report['assets_source'])
    print('语言          : %s' % ','.join(report.get('langs') or []))
    print('-' * 72)
    if report.get('errors') and not report.get('out'):
        for err in report['errors']:
            print('[ERROR] %s' % err)
        for sug in report.get('suggestions') or []:
            print('[建议] %s' % sug)
        _hsep()
        return
    original = patch_report.get('original') or {}
    pure = (patch_report.get('steps') or {}).get('pure_roundtrip') or {}
    cmp_r = (patch_report.get('steps') or {}).get('compare') or {}
    if original:
        print('原资源包      : %d 条目 / %s / sha256 %s'
              % (original.get('count', 0), fmt_bytes(original.get('file_size', 0)),
                 (original.get('sha256') or '')[:16]))
    if pure:
        print('纯 roundtrip  : %s' % ('逐字节一致 ✓' if pure.get('identical') else '不一致 ✗'))
    if cmp_r:
        print('补丁包自检    : %s（仅 %d 个条目变化）'
              % ('通过 ✓' if cmp_r.get('ok') else '失败 ✗',
                 len(cmp_r.get('changed') or [])))
        for c in cmp_r.get('changed') or []:
            print('  变化条目: %s  %d → %d 字节'
                  % (c.get('name'), c.get('old_len', 0), c.get('new_len', 0)))
    if report.get('out'):
        print('补丁包        : %s（%s）'
              % (report['out'], fmt_bytes(os.path.getsize(report['out']))
                 if os.path.isfile(report['out']) else '?'))
        if os.path.isfile(report['out']):
            print('补丁包 sha256 : %s' % sha256_file(report['out']))
    self_check = report.get('self_check') or {}
    if self_check:
        print('框架层独立自检: %s' % ('通过 ✓' if self_check.get('ok') else '失败 ✗'))
        for item in self_check.get('checks') or []:
            if not item.get('ok'):
                print('  [失败] %s %s' % (item.get('name'), item.get('detail') or ''))
    if report.get('installed'):
        print('已安装        : ✓ 写入后 sha256 %s'
              % (report.get('installed_sha256') or '')[:16])
        if report.get('backup'):
            print('原文件备份    : %s' % report['backup'])
        readback = report.get('install_readback') or {}
        if readback:
            print('安装后回读    : ✓ defaultcode 与片段一致')
        print('下一步        : 完全关闭并重启 AbilixScratch3.0，然后 文件→新建项目，'
              '「函数」分类里就能看到这些函数。')
        print('还原方法      : 双击 还原新建模板(管理员).cmd（或 python 还原新建模板.py --yes）')
    else:
        print('下一步        : 本机没有写安装目录的权限（或用了 --dry-run）；'
              '补丁包已准备好，见下方“如何安装”。')
    print('-' * 72)
    for warn in report.get('warnings') or []:
        print('[WARN] %s' % warn)
    for err in report.get('errors') or []:
        print('[ERROR] %s' % err)
    for sug in report.get('suggestions') or []:
        print('[建议] %s' % sug)
    if report.get('needs_admin'):
        print('-' * 72)
        print('需要管理员权限才能写安装目录。以管理员身份运行（任选其一）：')
        print('  1) 双击：%s' % os.path.join(_HERE, '同步我的函数库(管理员).cmd'))
        print('  2) 管理员命令行：python "%s" sync --install --library "%s" --assets "%s"'
              % (os.path.abspath(__file__), report.get('library', ''),
                 report.get('assets', '')))
    _hsep()


def print_restore_report(report: Dict[str, Any]) -> None:
    _title('还原软件「新建项目」默认模板')
    if report.get('list_only'):
        print('browser_assets: %s' % report.get('assets'))
        backups = report.get('backups') or []
        if not backups:
            print('（没有找到任何备份文件 browser_assets.备份-*）')
        else:
            print('找到 %d 份备份（新的在前）：' % len(backups))
            for i, b in enumerate(backups):
                print('  %d) %s  %s  %s%s'
                      % (i + 1, b['name'], b['mtime'], fmt_bytes(b['size']),
                         '   ← 默认还原这一份' if i == 0 else ''))
        _hsep()
        return
    print('browser_assets: %s' % (report.get('assets') or '（无）'))
    if report.get('backup'):
        print('使用备份      : %s' % report['backup'])
        print('              类型：%s' % report.get('backup_kind', ''))
    print('当前包        : %s  sha256 %s'
          % (fmt_bytes(report.get('current_size', 0)),
             (report.get('current_sha256') or '')[:16]))
    print('备份包        : %s  sha256 %s'
          % (fmt_bytes(report.get('backup_size', 0)),
             (report.get('backup_sha256') or '')[:16]))
    print('两者是否相同  : %s' % ('是（无需还原）' if report.get('same') else '否'))
    diff = report.get('diff') or {}
    if diff and not report.get('same'):
        changed = diff.get('changed') or []
        print('差异          : %s'
              % ('仅 maingui_init.js 变化（可安全还原）' if diff.get('ok')
                 else '不止 maingui_init.js，存在风险'))
        for c in changed:
            print('  变化条目: %s  %d → %d 字节'
                  % (c.get('name'), c.get('old_len', 0), c.get('new_len', 0)))
    tmpl = report.get('restored_template') or {}
    if tmpl:
        print('备份里的模板  : %d 个函数 / %d 个变量 / 顶层块 %d%s'
              % (tmpl.get('function_count', 0), tmpl.get('variable_count', 0),
                 tmpl.get('top_block_count', 0),
                 '（原始模板）' if tmpl.get('is_original') else ''))
    print('-' * 72)
    if report.get('apply') and report.get('restored'):
        print('还原结果      : ✓ 已还原')
        print('还原后 sha256 : %s' % (report.get('restored_sha256') or '')[:16])
        if report.get('pre_restore_backup'):
            print('还原前已另存  : %s' % report['pre_restore_backup'])
        print('下一步        : 完全关闭并重启 AbilixScratch3.0，新建项目应恢复原始模板。')
    elif not report.get('apply'):
        print('当前是演练（没有写文件）。确认无误后加 --yes 真正还原：')
        print('  python 还原新建模板.py --yes')
    for warn in report.get('warnings') or []:
        print('[WARN] %s' % warn)
    for err in report.get('errors') or []:
        print('[ERROR] %s' % err)
    for sug in report.get('suggestions') or []:
        print('[建议] %s' % sug)
    _hsep()


def print_inspect_report(report: Dict[str, Any]) -> None:
    _title('当前软件「新建项目」默认模板')
    print('browser_assets: %s' % (report.get('assets') or '（无）'))
    print('              %d 条目 / %s / sha256 %s'
          % (report.get('count', 0), fmt_bytes(report.get('file_size', 0)),
             (report.get('file_sha256') or '')[:16]))
    print('maingui_init.js: %d 字节（%d 行），sha256 %s'
          % (report.get('entry_bytes_len', 0), report.get('js_lines', 0),
             (report.get('entry_sha256') or '')[:16]))
    print('判定          : %s' % (report.get('classification') or '?'))
    for lang, item in (report.get('langs') or {}).items():
        print('-' * 72)
        print('[%s] var %s（第 %d 行，%d 字符）'
              % (lang, item.get('var'), item.get('line', 0), item.get('chars', 0)))
        print('  顶层块 %d / start %d / 函数 %d / 变量 %d'
              % (item.get('top_block_count', 0), item.get('start_count', 0),
                 item.get('function_count', 0), item.get('variable_count', 0)))
        if item.get('start_nested_block_types'):
            print('  start 里预置的块：%s'
                  % _short_list(item['start_nested_block_types']))
        funcs = item.get('functions') or []
        if funcs:
            print('  函数：')
            for f in funcs:
                print('    - %s(%s)' % (f.get('name'), ', '.join(f.get('args') or [])))
        else:
            print('  函数：无（0 个）')
        if item.get('variables'):
            print('  变量：%s' % _short_list(item['variables']))
        if not item.get('xml_ok'):
            print('  [ERROR] defaultcode XML 有问题：%s' % _short_list(item.get('xml_errors') or []))
    cmp_info = report.get('compare') or {}
    if cmp_info:
        print('-' * 72)
        print('与函数库对比：%s（%s）'
              % (cmp_info.get('library'), cmp_info.get('library_label', '')))
        if not cmp_info.get('library_ok'):
            print('  [ERROR] 函数库校验失败：%s'
                  % _short_list(cmp_info.get('library_errors') or []))
        else:
            print('  当前模板函数 %d 个 / 函数库函数 %d 个'
                  % (cmp_info.get('current_function_count', 0),
                     cmp_info.get('library_function_count', 0)))
            print('  同步后会新增函数（%d）：%s'
                  % (len(cmp_info.get('to_add') or []),
                     _short_list(cmp_info.get('to_add') or []) or '（无）'))
            print('  同步后会移除函数（%d）：%s'
                  % (len(cmp_info.get('to_remove') or []),
                     _short_list(cmp_info.get('to_remove') or []) or '（无）'))
            changed = cmp_info.get('args_changed') or []
            print('  参数不同的函数（%d）：%s'
                  % (len(changed),
                     _short_list(['%s %s→%s' % (c['name'], c['current_args'], c['library_args'])
                                  for c in changed]) or '（无）'))
            print('  变量新增 %d / 变量移除 %d'
                  % (len(cmp_info.get('variables_to_add') or []),
                     len(cmp_info.get('variables_to_remove') or [])))
            print('  当前模板与函数库片段是否完全一致：%s'
                  % ('是' if cmp_info.get('template_identical_to_library')
                     else '否（当前模板 %d 字符 / 函数库应生成 %d 字符）'
                     % (cmp_info.get('current_template_chars', 0),
                        cmp_info.get('expected_fragment_chars', 0))))
            print('  是否需要同步：%s'
                  % ('是（运行同步会更新模板）' if cmp_info.get('need_sync')
                     else '否（已一致）'))
    backup = report.get('backup') or {}
    if backup.get('path'):
        print('-' * 72)
        print('最近备份：%s（%s）%s'
              % (backup.get('name'), backup.get('mtime'),
                 '，与当前一致' if backup.get('same_as_current') else '，与当前不同'))
    for warn in report.get('warnings') or []:
        print('[WARN] %s' % warn)
    for err in report.get('errors') or []:
        print('[ERROR] %s' % err)
    _hsep()


def print_gen_report(report: Dict[str, Any]) -> None:
    _title('生成新项目文件（自带函数库的 .srhs）')
    print('函数库源      : %s' % (report.get('library') or '（无）'))
    frag = report.get('fragment') or {}
    if frag:
        print('              函数 %d 个 / 变量 %d 个 / 片段 %d 字符'
              % (frag.get('function_count', 0), frag.get('variable_count', 0),
                 frag.get('chars', 0)))
    print('输出文件      : %s' % (report.get('path') or '（无）'))
    if report.get('path') and os.path.isfile(report['path']):
        print('大小/sha256   : %s / %s'
              % (fmt_bytes(report.get('bytes', 0)), (report.get('sha256') or '')[:16]))
    print('机器人/程序名 : %s (%s) / %s'
          % (report.get('robot_type'), report.get('robot_code'), report.get('program')))
    verify = report.get('verify') or {}
    if verify:
        print('读回校验      : %s（start %d 个，函数 %d 个，变量 %d 个，zip注释 %s）'
              % ('通过 ✓' if verify.get('ok') else '失败 ✗',
                 verify.get('start_count', 0), len(verify.get('defnoreturn_names') or []),
                 verify.get('variable_count', 0), verify.get('comment', '')))
    print('-' * 72)
    if report.get('ok'):
        print('下一步        : 打开 AbilixScratch3.0 → 文件→打开 → 选择上面的 .srhs；')
        print('                工作区会自带函数库，「函数」分类里可直接拖用。')
    for warn in report.get('warnings') or []:
        print('[WARN] %s' % warn)
    for err in report.get('errors') or []:
        print('[ERROR] %s' % err)
    _hsep()


def print_locate_report(loc: Dict[str, Any], candidates: Sequence[Dict[str, Any]]) -> None:
    t, _ = _require_bottom()
    _title('本机 AbilixScratch3.0 资源包定位')
    print('browser_assets: %s' % loc.get('assets'))
    print('来源          : %s' % loc.get('source'))
    try:
        print('大小/sha256   : %s / %s'
              % (fmt_bytes(os.path.getsize(loc['assets'])), t.sha256_file(loc['assets'])[:32] + '…'))
    except OSError:
        pass
    print('-' * 72)
    print('扫描到的候选（%d 个，前 12 个）：' % len(candidates))
    for cand in list(candidates)[:12]:
        flag = '✓' if cand.get('exists') and cand.get('is_zfb') else (
            '存在但不是资源包' if cand.get('exists') else '不存在')
        print('  [%s] %s（%s）' % (flag, cand['path'], cand.get('source', '')))
    _hsep()


# ============================================================================
# 十四、CLI
# ============================================================================

def _common_parent() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument('--json', action='store_true',
                        help='只输出 JSON 结果（便于脚本处理；不打印人类可读报告）')
    parent.add_argument('--json-out', default=None,
                        help='把 JSON 结果写到指定文件（可同时用 --json）')
    return parent


def build_arg_parser(prog: str = '框架核心.py',
                     forced_cmd: Optional[str] = None) -> argparse.ArgumentParser:
    parent = _common_parent()
    p = argparse.ArgumentParser(
        prog=prog,
        description='WER 函数库框架：把「我的函数库」同步进软件新建项目默认模板，'
                    '并提供还原/查看/校验/生成新项目文件。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''常用示例（Windows）:
  python 校验我的函数库.py
  python 同步我的函数库.py --dry-run
  python 同步我的函数库.py --install          # 需要管理员
  python 查看当前新建模板.py
  python 还原新建模板.py --yes                # 需要管理员
  python 生成新项目文件.py --library 我的函数库.srh --out 新项目.srhs

子命令（框架核心.py 直接调用时）:
  locate   自动定位 browser_assets
  validate 校验函数库源文件
  sync     同步到新建项目默认模板（默认演练，--install 才写）
  restore  从备份还原默认模板
  inspect  查看当前软件里的默认模板
  gen      生成可直接打开的新项目 .srhs

退出码: 0=成功  1=校验/自检失败  2=需要管理员或文件缺失
''')
    sub = p.add_subparsers(dest='cmd', metavar='子命令')

    def add(name: str, help_text: str, description: str) -> argparse.ArgumentParser:
        kwargs: Dict[str, Any] = {'help': help_text, 'description': description,
                                  'parents': [parent]}
        if forced_cmd == name:
            kwargs['prog'] = prog
        return sub.add_parser(name, **kwargs)

    sp = add('locate', '自动定位 browser_assets（排错用）', '自动定位 AbilixScratch3.0 的 browser_assets。')
    sp.add_argument('--assets', default=None, help='显式指定 browser_assets 路径（默认自动扫描）')

    sp = add('validate', '校验函数库源文件', '校验函数库源文件（.srh/.srhs），列出函数/参数/变量和问题。')
    sp.add_argument('--library', default=None, help='函数库源文件 .srh/.srhs（默认自动找 我的函数库）')

    sp = add('sync', '同步我的函数库 → 新建项目默认模板',
             '把函数库源文件同步进软件新建项目默认模板（默认演练；--install 才写安装目录，需管理员）。')
    sp.add_argument('--library', default=None, help='函数库源文件 .srh/.srhs（默认自动找 我的函数库）')
    sp.add_argument('--assets', default=None, help='browser_assets 路径（默认自动定位）')
    sp.add_argument('--install', action='store_true',
                    help='写回安装目录（需要管理员；会自动备份原文件）')
    sp.add_argument('--dry-run', action='store_true',
                    help='只生成补丁包并自检，不写安装目录（默认行为；显式写更清楚）')
    sp.add_argument('--langs', default='zh-hans',
                    help='替换哪些语言的 defaultcode：zh-hans / zh-hans,zh-hant,en / all（默认 zh-hans）')
    sp.add_argument('--out', default=None,
                    help='补丁包输出路径（默认 <工作区>/_分析临时/framework_work/browser_assets.patched）')
    sp.add_argument('--keep-work', action='store_true', help='保留临时解包目录（调试用）')

    sp = add('restore', '从备份还原新建项目默认模板',
             '从 browser_assets.备份-<时间戳> 还原默认模板（先备份当前文件再覆盖，可回退）。')
    sp.add_argument('--assets', default=None, help='browser_assets 路径（默认自动定位）')
    sp.add_argument('--backup', default=None,
                    help='指定要还原的备份文件（默认取最新的 browser_assets.备份-*）')
    sp.add_argument('--list', action='store_true', help='只列出备份文件，不做还原')
    sp.add_argument('--yes', action='store_true', help='确认真正还原（不加则只显示计划）')

    sp = add('inspect', '查看当前软件里的新建项目默认模板',
             '查看当前 browser_assets 里的新建项目默认模板内容，可与函数库对比差异。')
    sp.add_argument('--assets', default=None, help='browser_assets 路径（默认自动定位）')
    sp.add_argument('--library', default=None,
                    help='用于对比的函数库源文件（默认自动找 我的函数库；没有则只显示当前模板）')

    sp = add('gen', '生成自带函数库的新项目 .srhs',
             '把函数库源文件打包成可直接「文件→打开」的 .srhs（不依赖安装目录）。')
    sp.add_argument('--library', default=None, help='函数库源文件 .srh/.srhs（默认自动找 我的函数库）')
    sp.add_argument('--out', default=None,
                    help='输出 .srhs 路径（默认 <函数库同目录>/<库名>_新项目.srhs）')
    sp.add_argument('--program', default='ProgramA', help='下载程序名 DownloadProgramName（默认 ProgramA）')
    sp.add_argument('--robot', default=None, help='机器人类型 SKCON2/SKCON5/SKCON9（默认取源文件）')
    sp.add_argument('--force', action='store_true', help='输出文件已存在时覆盖')

    return p


def _emit_json(report: Dict[str, Any], json_out: Optional[str]) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if json_out:
        path = write_json(json_out, report)
        sys.stderr.write('JSON 报告已写入：%s\n' % path)


def _fail_with(exc: FrameworkError) -> int:
    print('[错误] %s' % exc, file=sys.stderr)
    for sug in exc.suggestions:
        print('[建议] %s' % sug, file=sys.stderr)
    return int(exc.exit_code)


def cmd_locate(args: argparse.Namespace) -> int:
    try:
        loc = locate_install(args.assets, verbose=True)
        candidates = loc.get('candidates') or find_install_candidates()
    except FrameworkError as exc:
        if args.json:
            _emit_json({'ok': False, 'readable': str(exc),
                        'suggestions': exc.suggestions}, args.json_out)
        else:
            _fail_with(exc)
        return int(exc.exit_code)
    report = {'ok': True, 'assets': loc['assets'], 'source': loc['source'],
              'size': os.path.getsize(loc['assets']),
              'sha256': sha256_file(loc['assets']),
              'candidates': candidates}
    if args.json:
        _emit_json(report, args.json_out)
    else:
        print_locate_report(loc, candidates)
        if args.json_out:
            print('JSON 报告已写入：%s' % write_json(args.json_out, report))
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    report = validate_library(args.library)
    if args.json:
        _emit_json(report, args.json_out)
    else:
        print_validate_report(report)
        if args.json_out:
            print('JSON 报告已写入：%s' % write_json(args.json_out, report))
    return int(report.get('exit_code', EXIT_OK if report.get('ok') else EXIT_FAIL))


def cmd_sync(args: argparse.Namespace) -> int:
    try:
        report = sync(library=args.library, assets=args.assets, install=args.install,
                      dry_run=args.dry_run, langs=args.langs, out_path=args.out,
                      keep_work=args.keep_work, progress=not args.json,
                      show_patch_progress=not args.json)
    except FrameworkError as exc:
        if args.json:
            _emit_json({'ok': False, 'errors': [str(exc)],
                        'suggestions': exc.suggestions, 'exit_code': exc.exit_code},
                       args.json_out)
        else:
            _fail_with(exc)
        return int(exc.exit_code)
    if args.json:
        _emit_json(report, args.json_out)
    else:
        print_sync_report(report)
        if args.json_out:
            print('JSON 报告已写入：%s' % write_json(args.json_out, report))
    return int(report.get('exit_code', EXIT_OK))


def cmd_restore(args: argparse.Namespace) -> int:
    try:
        report = restore(assets=args.assets, backup=args.backup,
                         apply=bool(args.yes), list_only=bool(args.list),
                         progress=not args.json)
    except FrameworkError as exc:
        if args.json:
            _emit_json({'ok': False, 'errors': [str(exc)],
                        'suggestions': exc.suggestions, 'exit_code': exc.exit_code},
                       args.json_out)
        else:
            _fail_with(exc)
        return int(exc.exit_code)
    if args.json:
        _emit_json(report, args.json_out)
    else:
        print_restore_report(report)
        if args.json_out:
            print('JSON 报告已写入：%s' % write_json(args.json_out, report))
    return int(report.get('exit_code', EXIT_OK))


def cmd_inspect(args: argparse.Namespace) -> int:
    report = inspect_current_template(assets=args.assets, library=args.library)
    if args.json:
        _emit_json(report, args.json_out)
    else:
        print_inspect_report(report)
        if args.json_out:
            print('JSON 报告已写入：%s' % write_json(args.json_out, report))
    return int(report.get('exit_code', EXIT_OK))


def cmd_gen(args: argparse.Namespace) -> int:
    report = make_new_project(library=args.library, out_path=args.out,
                              program=args.program, robot=args.robot,
                              force=args.force, progress=not args.json)
    if args.json:
        _emit_json(report, args.json_out)
    else:
        print_gen_report(report)
        if args.json_out:
            print('JSON 报告已写入：%s' % write_json(args.json_out, report))
    return int(report.get('exit_code', EXIT_OK))


_HANDLERS = {
    'locate': cmd_locate,
    'validate': cmd_validate,
    'sync': cmd_sync,
    'restore': cmd_restore,
    'inspect': cmd_inspect,
    'gen': cmd_gen,
}


def main(argv: Optional[Sequence[str]] = None, prog: Optional[str] = None,
         forced_cmd: Optional[str] = None) -> int:
    """
    CLI 入口。中文封装脚本（同步我的函数库.py 等）调用时传 forced_cmd，
    框架核心.py 直接运行时用子命令（locate/validate/sync/restore/inspect/gen）。
    """
    setup_console()
    args_list = list(sys.argv[1:] if argv is None else argv)
    prog = prog or os.path.basename(sys.argv[0] or '框架核心.py')
    if forced_cmd:
        # 封装脚本：自动补上子命令，用户只需要传自己的参数
        if not args_list or args_list[0] != forced_cmd:
            args_list = [forced_cmd] + args_list
    parser = build_arg_parser(prog=prog, forced_cmd=forced_cmd)
    if not args_list:
        parser.print_help()
        return EXIT_OK
    args = parser.parse_args(args_list)
    cmd = getattr(args, 'cmd', None)
    handler = _HANDLERS.get(cmd)
    if handler is None:
        parser.print_help()
        return EXIT_NEED
    try:
        return int(handler(args))
    except FrameworkError as exc:
        return _fail_with(exc)
    except KeyboardInterrupt:
        print('\n[中断] 用户取消。', file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI 最外层兜底，避免大段 traceback 吓到用户
        print('[错误] 未预期的异常：%s: %s' % (type(exc).__name__, exc), file=sys.stderr)
        print('      如果问题反复出现，可加 --json 输出结果，或把上面的错误信息发给维护者。',
              file=sys.stderr)
        return EXIT_FAIL


if __name__ == '__main__':
    sys.exit(main())
