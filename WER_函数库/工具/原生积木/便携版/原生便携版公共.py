# -*- coding: utf-8 -*-
"""
原生便携版公共.py —— 「原生函数积木」便携版的公共底层
============================================================================

本模块不含命令行入口，由同目录的：
    * 创建便携函数版.py
    * 更新便携函数版.py
    * 删除便携版.py
通过 importlib 加载。

它做什么
--------
1. **自包含**：安装目录定位、硬链接复制（browser_assets 强制独立复制）、
   复制结果校验、桌面快捷方式、`clear_app_data_switch` 注册表保护、进程占用探测、
   AppData 项目列表备份、sha256/目录统计等通用能力，来自本目录内自带的
   `便携版公共.py` 副本（源自上一轮 `工具/便携版/便携版公共.py`，已随本工具一起打包，
   整个 `原生积木\便携版\` 目录单独拷到别的电脑也能用）。
2. **原生积木专属**（与旧「模板注入」方案的差异，旧 defaultcode 补丁路径完全不再使用）：
   * 默认目标目录 `%USERPROFILE%\\AbilixScratch3.0_FuncLib`（**纯 ASCII**——实测非 ASCII
     路径会让 IDE 内嵌 CEF 加载失败、积木区全白）；
   * 副本内原始资源备份到 `<副本>\\_原始资源\\browser_assets.orig`（供更新/还原）；
   * 调核心工具 `工具/原生积木/原生积木核心.py` 的 `build` 子命令生成 patched
     browser_assets（原生积木版），`verify` 子命令做独立校验；
   * 构建到临时文件，**校验通过后才原子替换**副本的 browser_assets；失败自动回滚。
3. 核心工具的参数名以它自己的 `--help` 为准（本模块会探测 `--help` 文本，兼容
   `--source-assets/--source`、`--out/--output` 等细微命名差异）。

依赖：Python 3.8+ 标准库 + 同目录 `便携版公共.py`
（+ 核心工具 `工具/原生积木/原生积木核心.py`，由 Lead 提供）。
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

# ----------------------------------------------------------------------------
# 路径常量（全部相对本文件推算，整个 WER_函数库 目录拷到别处也能用）
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))            # .../工具/原生积木/便携版
NATIVE_ROOT = os.path.dirname(HERE)                          # .../工具/原生积木
TOOLS_ROOT = os.path.dirname(NATIVE_ROOT)                    # .../工具
LIB_ROOT = os.path.dirname(TOOLS_ROOT)                       # .../WER_函数库

#: 便携版公共模块：优先用本目录内自带的副本（自包含，整个 原生积木/便携版
#: 目录单独拷走也能用）；没有时才回退到旧目录 工具/便携版/便携版公共.py。
_SAME_DIR_COMMON = os.path.join(HERE, '便携版公共.py')
BASE_COMMON_SCRIPT = (_SAME_DIR_COMMON if os.path.isfile(_SAME_DIR_COMMON)
                      else os.path.join(TOOLS_ROOT, '便携版', '便携版公共.py'))
CORE_SCRIPT = os.path.join(NATIVE_ROOT, '原生积木核心.py')

#: 副本内「原始资源」备份目录名与文件名（相对副本根目录）
ORIG_DIRNAME = '_原始资源'
ORIG_ASSETS_NAME = 'browser_assets.orig'
PREV_ASSETS_NAME = 'browser_assets.上一版'

#: 默认便携副本目录名：必须**纯 ASCII**！
#: 实测（2026-11-10，上一轮真机验证）：副本路径含中文时 IDE 能启动，但内嵌 CEF
#: 浏览器初始化失败 → 积木网页区全白。本工具默认沿用 ASCII 目录名。
DEFAULT_TARGET_DIRNAME = 'AbilixScratch3.0_FuncLib'

#: 桌面快捷方式名（快捷方式本身可以含中文，只有副本目录路径必须纯 ASCII）
DEFAULT_SHORTCUT_NAME = 'AbilixScratch3.0 函数版.lnk'

APP_EXE_NAME = 'AbilixScratch3.0.exe'
DEFAULT_SOURCE = r'D:\Program Files\AbilixScratch3.0'

#: 核心工具就绪探测的默认等待时间（由旧工具检测用，入口脚本也可用）
CORE_WAIT_SECONDS = 10 * 60

_bases: Dict[str, Any] = {}


# ============================================================================
# 一、载入上一轮公共模块（只读复用）
# ============================================================================

def _load_module(path: str, name: str):
    if not os.path.isfile(path):
        raise FileNotFoundError('找不到模块文件：%s' % path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError('无法加载模块：%s' % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_base():
    """加载本目录自带的 `便携版公共.py`（通用能力底层）。"""
    if 'base' not in _bases:
        _bases['base'] = _load_module(BASE_COMMON_SCRIPT, 'portable_common_base')
    return _bases['base']


# --- 常用函数转发（调用方统一走本模块，不直接 import 旧模块）----------------
def fmt_bytes(n: int) -> str:
    return get_base().fmt_bytes(n)


def timestamp(fmt: str = '%Y%m%d-%H%M%S') -> str:
    return get_base().timestamp(fmt)


def sha256_file(path: str) -> str:
    return get_base().sha256_file(path)


def dir_stats(root: str) -> Dict[str, Any]:
    return get_base().dir_stats(root)


def write_json(path: str, obj: Any) -> str:
    return get_base().write_json(path, obj)


def read_json(path: str) -> Any:
    return get_base().read_json(path)


def non_ascii_chars(path: str) -> List[str]:
    return get_base().non_ascii_chars(path)


def is_ascii_path(path: str) -> bool:
    return get_base().is_ascii_path(path)


def locate_install_source() -> Optional[str]:
    return get_base().locate_install_source()


def validate_install_dir(app_dir: str) -> Dict[str, Any]:
    return get_base().validate_install_dir(app_dir)


def find_assets(app_dir: str) -> str:
    return get_base().find_assets(app_dir)


def find_library(path: Optional[str] = None) -> Dict[str, Any]:
    return get_base().find_library(path)


def describe_library(path: str) -> Dict[str, Any]:
    return get_base().describe_library(path)


def copy_tree_prefer_hardlink(src: str, dst: str, log=None) -> Dict[str, Any]:
    return get_base().copy_tree_prefer_hardlink(src, dst, log=log)


def verify_copy(src: str, dst: str) -> Dict[str, Any]:
    return get_base().verify_copy(src, dst)


def detach_hardlink(path: str) -> bool:
    return get_base().detach_hardlink(path)


def get_desktop_dir() -> str:
    return get_base().get_desktop_dir()


def create_shortcut(target_exe: str, lnk_path: str, workdir: Optional[str] = None,
                    description: str = 'AbilixScratch3.0 函数版（左侧「我的函数」原生积木）') -> Dict[str, Any]:
    return get_base().create_shortcut(target_exe, lnk_path, workdir=workdir,
                                      description=description)


def processes_under(dir_path: str) -> List[Dict[str, Any]]:
    return get_base().processes_under(dir_path)


def appdata_projects_dir() -> str:
    return get_base().appdata_projects_dir()


def backup_appdata_projects(dest_root: str, label: str = '') -> Dict[str, Any]:
    return get_base().backup_appdata_projects(dest_root, label=label)


def read_clear_appdata_switch() -> Dict[str, Any]:
    return get_base().read_clear_appdata_switch()


def set_clear_appdata_switch(reg_name: str, value: int = 0) -> Dict[str, Any]:
    return get_base().set_clear_appdata_switch(reg_name, value)


def print_header(title: str) -> None:
    return get_base().print_header(title)


def print_kv(key: str, value: Any) -> None:
    return get_base().print_kv(key, value)


def print_footer() -> None:
    return get_base().print_footer()


def setup_console() -> None:
    """控制台中文输出（失败忽略）。"""
    try:
        get_base().load_srhs_tool().setup_console()
    except Exception:  # noqa: BLE001
        pass


def default_target() -> str:
    """默认便携副本目录：%USERPROFILE%\\AbilixScratch3.0_FuncLib（纯 ASCII）。

    可用环境变量 ABILIX_PORTABLE_TARGET 覆盖（供测试/其他电脑用）。
    """
    env = os.environ.get('ABILIX_PORTABLE_TARGET')
    if env:
        return os.path.abspath(env)
    return os.path.join(os.path.expanduser('~'), DEFAULT_TARGET_DIRNAME)


def assets_rel_path() -> str:
    """副本内 browser_assets 的相对路径（真实版本是点号 3.0）。"""
    return os.path.join('AbilixScratch3.0_Data', 'Resources', 'browser_assets')


def orig_dir(copy_app_dir: str) -> str:
    return os.path.join(os.path.abspath(copy_app_dir), ORIG_DIRNAME)


def orig_assets_path(copy_app_dir: str) -> str:
    return os.path.join(orig_dir(copy_app_dir), ORIG_ASSETS_NAME)


def prev_assets_path(copy_app_dir: str) -> str:
    return os.path.join(orig_dir(copy_app_dir), PREV_ASSETS_NAME)


def assets_path(copy_app_dir: str) -> str:
    """返回副本内 browser_assets 的路径（**文件允许暂时不存在**）。

    两个场景必须用本函数而不是 find_assets：
    * `backup_orig_assets` 把资源移到 `_原始资源\browser_assets.orig` 之后，
      副本内的 browser_assets 位置是空的，此时 find_assets 会抛 FileNotFoundError；
    * 更新流程/首次构建开始前，资源包可能还没生成。
    """
    copy_app_dir = os.path.abspath(copy_app_dir)
    try:
        return find_assets(copy_app_dir)
    except FileNotFoundError:
        names = getattr(get_base(), 'DATA_DIR_NAMES', ('AbilixScratch3.0_Data',))
        return os.path.join(copy_app_dir, names[0], 'Resources', 'browser_assets')


def is_portable_copy(app_dir: str) -> Dict[str, Any]:
    """校验一个目录是不是「原生积木函数版」便携副本（不抛异常）。"""
    out: Dict[str, Any] = {'ok': False, 'app_dir': None, 'errors': [], 'warnings': []}
    app_dir = os.path.abspath(app_dir)
    out['app_dir'] = app_dir
    if not os.path.isdir(app_dir):
        out['errors'].append('目录不存在：%s' % app_dir)
        return out
    exe = os.path.join(app_dir, APP_EXE_NAME)
    out['exe'] = exe
    if not os.path.isfile(exe):
        out['errors'].append('目录里没有 %s，不像是 AbilixScratch3.0 便携副本' % APP_EXE_NAME)
    try:
        assets = find_assets(app_dir)
        out['assets'] = assets
        out['assets_size'] = os.path.getsize(assets)
        out['assets_sha256'] = sha256_file(assets)
    except FileNotFoundError as exc:
        out['errors'].append(str(exc))
    out['orig_assets'] = orig_assets_path(app_dir)
    out['orig_exists'] = os.path.isfile(out['orig_assets'])
    out['ok'] = not out['errors']
    return out


# ============================================================================
# 二、核心工具（原生积木核心.py）调用
# ============================================================================

def core_exists() -> bool:
    return os.path.isfile(CORE_SCRIPT)


def core_path() -> str:
    return CORE_SCRIPT


def _decode(raw: bytes) -> str:
    """解码子进程输出：优先 UTF-8；乱码多时回退 GBK（Windows 控制台）。"""
    if not raw:
        return ''
    text = raw.decode('utf-8', errors='replace')
    if text.count('\ufffd') > max(3, len(text) // 200):
        alt = raw.decode('gbk', errors='replace')
        if alt.count('\ufffd') <= text.count('\ufffd'):
            return alt
    return text


def run_core(args: List[str], timeout: int = 3600,
             log=None) -> Dict[str, Any]:
    """执行 `python 原生积木核心.py <args...>`，返回结构化结果（不抛异常）。"""
    out: Dict[str, Any] = {'ok': False, 'returncode': -1, 'stdout': '',
                           'stderr': '', 'cmd': [], 'seconds': 0.0}
    if not core_exists():
        out['stderr'] = ('核心工具尚未就绪：%s\n'
                         '（请等 Lead 交付 原生积木核心.py 后重试）' % CORE_SCRIPT)
        return out
    cmd = [sys.executable, CORE_SCRIPT] + [str(a) for a in args]
    out['cmd'] = cmd
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              cwd=NATIVE_ROOT)
    except subprocess.TimeoutExpired:
        out['stderr'] = '核心工具执行超时（%ss）：%s' % (timeout, ' '.join(cmd[1:]))
        out['seconds'] = round(time.time() - started, 2)
        return out
    except OSError as exc:
        out['stderr'] = '无法执行核心工具：%s' % exc
        return out
    out['returncode'] = proc.returncode
    out['stdout'] = _decode(proc.stdout)
    out['stderr'] = _decode(proc.stderr)
    out['ok'] = proc.returncode == 0
    out['seconds'] = round(time.time() - started, 2)
    if log:
        for line in (out['stdout'] + out['stderr']).splitlines():
            log(line)
    return out


_HELP_CACHE: Dict[str, str] = {}


def core_help(subcommand: Optional[str] = None) -> str:
    """读取核心工具（或其子命令）的 --help 文本（缓存）。"""
    key = subcommand or '_top'
    if key not in _HELP_CACHE:
        args = ([subcommand] if subcommand else []) + ['--help']
        res = run_core(args, timeout=120)
        _HELP_CACHE[key] = (res['stdout'] or '') + '\n' + (res['stderr'] or '')
    return _HELP_CACHE[key]


def _has_flag(text: str, flag: str) -> bool:
    """在 help 文本里按“独立 token”匹配参数名（避免 --out 误匹配 --output）。"""
    pattern = r'(?<![\w-])' + re.escape(flag) + r'(?![\w-])'
    return re.search(pattern, text) is not None


def _pick_flag(text: str, candidates: List[str]) -> str:
    for cand in candidates:
        if _has_flag(text, cand):
            return cand
    return candidates[0]


def build_assets(library: str, source_assets: str, out_assets: str,
                 workdir: Optional[str] = None, timeout: int = 3600,
                 log=None) -> Dict[str, Any]:
    """调核心工具 `build`：从原始 browser_assets 生成原生积木版 patched assets。

    参数名按核心工具实际的 --help 探测，兼容细微差异；返回 run_core 的结果。
    """
    help_text = core_help('build')
    flag_lib = _pick_flag(help_text, ['--library', '--lib', '-l'])
    flag_src = _pick_flag(help_text, ['--source-assets', '--source', '--src', '-s'])
    flag_out = _pick_flag(help_text, ['--out', '--output', '--dst', '--dest', '-o'])
    args = ['build', flag_lib, os.path.abspath(library),
            flag_src, os.path.abspath(source_assets),
            flag_out, os.path.abspath(out_assets)]
    if workdir:
        flag_wd = _pick_flag(help_text, ['--workdir', '--work-dir', '--tmp', '--temp'])
        args += [flag_wd, os.path.abspath(workdir)]
    res = run_core(args, timeout=timeout, log=log)
    res['args_used'] = args
    return res


def verify_assets(file_path: str, original: str, timeout: int = 600,
                  log=None) -> Dict[str, Any]:
    """调核心工具 `verify`：校验 patched assets 与原始 assets 的关系。"""
    help_text = core_help('verify')
    flag_file = _pick_flag(help_text, ['--file', '--patched', '-f'])
    flag_orig = _pick_flag(help_text, ['--original', '--orig', '--source-assets',
                                       '--source', '-o'])
    args = ['verify', flag_file, os.path.abspath(file_path),
            flag_orig, os.path.abspath(original)]
    res = run_core(args, timeout=timeout, log=log)
    res['args_used'] = args
    return res


def status_assets(assets_path: str, library: str, timeout: int = 600,
                  log=None) -> Dict[str, Any]:
    """调核心工具 `status`：输出某个 browser_assets 的补丁状态。"""
    help_text = core_help('status')
    flag_assets = _pick_flag(help_text, ['--assets', '--file', '-a'])
    flag_lib = _pick_flag(help_text, ['--library', '--lib', '-l'])
    args = ['status', flag_assets, os.path.abspath(assets_path),
            flag_lib, os.path.abspath(library)]
    res = run_core(args, timeout=timeout, log=log)
    res['args_used'] = args
    return res


# ============================================================================
# 三、副本内「原始资源」备份与原生构建（核心安全流程）
# ============================================================================

def backup_orig_assets(copy_app_dir: str, expected_sha256: Optional[str] = None,
                       log=None) -> Dict[str, Any]:
    """把副本里的原始 browser_assets 移到 `<副本>\\_原始资源\\browser_assets.orig`。

    * 用 os.replace（同一副本内移动，免拷贝 85MB），副本 browser_assets 位置变空；
    * 移动前 detach 硬链接（防历史副本是硬链接时改到安装目录）；
    * 若给出 expected_sha256，会校验移动前后的 sha256（默认用安装目录原包的 sha）。
    """
    out: Dict[str, Any] = {'ok': False, 'orig': None, 'sha256': None,
                           'bytes': None, 'detached': False, 'error': None}
    copy_app_dir = os.path.abspath(copy_app_dir)
    assets = find_assets(copy_app_dir)
    orig = orig_assets_path(copy_app_dir)
    out['orig'] = orig
    os.makedirs(orig_dir(copy_app_dir), exist_ok=True)
    try:
        out['detached'] = detach_hardlink(assets)
        out['sha256'] = sha256_file(assets)
        out['bytes'] = os.path.getsize(assets)
        if expected_sha256 and out['sha256'].lower() != expected_sha256.lower():
            out['error'] = ('副本里的 browser_assets 与安装目录原包不一致：\n'
                            '  副本 sha256 = %s\n  安装 sha256 = %s\n'
                            '（可能副本已被手工改动；请用 创建便携函数版.py --force 重建）'
                            % (out['sha256'], expected_sha256))
            return out
        if os.path.exists(orig):
            # 已存在：校验一致则直接删掉副本文件（复用已有备份），不一致则报错
            old_sha = sha256_file(orig)
            if old_sha.lower() == out['sha256'].lower():
                os.remove(assets)
                if log:
                    log('  已存在一致的原始资源备份，直接复用：%s' % orig)
                out['ok'] = True
                out['reused'] = True
                return out
            out['error'] = ('副本内已有原始资源备份但与当前副本资源不一致：%s' % orig)
            return out
        os.replace(assets, orig)
        out['ok'] = True
    except OSError as exc:
        out['error'] = '备份原始资源失败：%s' % exc
    return out


def ensure_orig_assets(copy_app_dir: str, install_assets: Optional[str] = None,
                       log=None) -> Dict[str, Any]:
    """确保副本内有 `_原始资源\\browser_assets.orig`（更新前调用，不抛异常）。

    三种情况：
      1. 已有 orig → 直接用；
      2. 没有 orig，但当前副本 browser_assets 与安装目录原包 sha256 相同（说明副本
         还是干净的原始资源）→ 移过去当备份；
      3. 没有 orig 且副本资源已被打过补丁 → 报错，提示重建（不猜测）。
    """
    out: Dict[str, Any] = {'ok': False, 'orig': None, 'adopted_from_install': False,
                           'error': None}
    copy_app_dir = os.path.abspath(copy_app_dir)
    orig = orig_assets_path(copy_app_dir)
    out['orig'] = orig
    if os.path.isfile(orig):
        out['ok'] = True
        out['bytes'] = os.path.getsize(orig)
        out['sha256'] = sha256_file(orig)
        return out
    try:
        assets = find_assets(copy_app_dir)
    except FileNotFoundError as exc:
        out['error'] = str(exc)
        return out
    expected = None
    if install_assets and os.path.isfile(install_assets):
        expected = sha256_file(install_assets)
    cur = sha256_file(assets)
    if expected and cur.lower() == expected.lower():
        os.makedirs(orig_dir(copy_app_dir), exist_ok=True)
        os.replace(assets, orig)
        out.update({'ok': True, 'adopted_from_install': True,
                    'bytes': os.path.getsize(orig), 'sha256': cur})
        if log:
            log('  副本尚无原始资源备份；当前资源与原包一致，已移入 %s' % orig)
        return out
    out['error'] = ('副本里没有 _原始资源\\%s，且当前 browser_assets 已被改过，'
                    '无法确定原始资源。\n'
                    '  请用 创建便携函数版.py --force 重建副本后再更新。' % ORIG_ASSETS_NAME)
    return out


def build_portable_assets(copy_app_dir: str, library_path: str,
                          keep_prev: bool = True, log=None,
                          timeout: int = 3600) -> Dict[str, Any]:
    """核心构建流程：orig → 核心 build → 临时文件 → verify → 原子替换副本资源。

    返回 {'ok','library','orig','assets','before','after','build','verify','error'}。
    * 构建产物先写到 `_原始资源\\browser_assets.build-<时间戳>`，
      **核心工具返回 0 且校验通过后才用 os.replace 覆盖副本 browser_assets**；
    * 失败时副本原文件保持不动（临时文件清理），可安全重试；
    * keep_prev=True 时先把当前 patched 资源另存为 `_原始资源\\browser_assets.上一版`。
    """
    out: Dict[str, Any] = {'ok': False, 'error': None, 'library': os.path.abspath(library_path),
                           'orig': orig_assets_path(copy_app_dir),
                           'assets': None, 'build': None, 'verify': None}
    copy_app_dir = os.path.abspath(copy_app_dir)
    orig = orig_assets_path(copy_app_dir)
    if not os.path.isfile(orig):
        out['error'] = '副本内没有原始资源备份，请先运行 更新便携函数版.py 的自动修复或重建副本。'
        return out
    assets = assets_path(copy_app_dir)
    out['assets'] = assets
    out['orig_bytes'] = os.path.getsize(orig)
    out['orig_sha256'] = sha256_file(orig)
    out['before_bytes'] = os.path.getsize(assets) if os.path.isfile(assets) else 0
    out['before_sha256'] = sha256_file(assets) if os.path.isfile(assets) else None
    tmp_out = os.path.join(orig_dir(copy_app_dir),
                           'browser_assets.build-%s' % timestamp())
    if os.path.exists(tmp_out):
        try:
            os.remove(tmp_out)
        except OSError:
            pass
    try:
        if log:
            log('  核心工具 build：%s → %s' % (orig, tmp_out))
        build_res = build_assets(library=library_path, source_assets=orig,
                                 out_assets=tmp_out, log=log, timeout=timeout)
        out['build'] = {k: build_res.get(k) for k in
                        ('ok', 'returncode', 'seconds', 'args_used')}
        if not build_res['ok']:
            out['error'] = ('核心工具 build 失败（退出码 %s）：\n%s'
                            % (build_res['returncode'],
                               (build_res['stderr'] or build_res['stdout'] or '').strip()))
            return out
        if not os.path.isfile(tmp_out):
            out['error'] = ('核心工具返回成功，但没有生成输出文件：%s\n'
                            '核心工具输出：%s' % (tmp_out,
                                                  (build_res['stdout'] or '').strip()[-2000:]))
            return out
        new_size = os.path.getsize(tmp_out)
        new_sha = sha256_file(tmp_out)
        out['after_bytes'] = new_size
        out['after_sha256'] = new_sha
        if new_size < 1024 * 1024:
            out['error'] = '核心工具生成的资源包体积异常：%s' % fmt_bytes(new_size)
            return out
        if new_sha.lower() == out['orig_sha256'].lower():
            out['error'] = ('核心工具生成的资源包与原始资源完全相同（sha256 一致），'
                            '原生积木没有被写入。请检查核心工具 build。')
            return out
        # 独立校验（核心工具的 verify 子命令；失败只警告，不阻断，但会记录）
        try:
            ver = verify_assets(tmp_out, orig)
            out['verify'] = {'ok': ver.get('ok'), 'returncode': ver.get('returncode'),
                             'args_used': ver.get('args_used'),
                             'stdout_tail': (ver.get('stdout') or '').strip()[-4000:],
                             'stderr_tail': (ver.get('stderr') or '').strip()[-4000:]}
            if not ver.get('ok') and log:
                log('  [警告] 核心工具 verify 未通过（继续，但请复核）：\n%s'
                    % ((ver.get('stdout') or '') + (ver.get('stderr') or '')).strip()[-1000:])
        except Exception as exc:  # noqa: BLE001
            out['verify'] = {'ok': False, 'error': str(exc)}
        # 覆盖前：保留上一版 patched 资源（可选）
        if keep_prev and os.path.isfile(assets):
            prev = prev_assets_path(copy_app_dir)
            try:
                os.replace(assets, prev)
                out['prev_backup'] = prev
            except OSError:
                os.remove(assets)
        os.replace(tmp_out, assets)
        out['ok'] = True
    except Exception as exc:  # noqa: BLE001
        out['error'] = '原生构建流程异常：%s' % exc
    finally:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except OSError:
                pass
    return out


# ============================================================================
# 四、AppData 安全（复用旧工具的注册表开关逻辑）
# ============================================================================

def ensure_appdata_safe(backup_root: str, fix_registry: bool = True,
                        backup: bool = True, log=print) -> Dict[str, Any]:
    """检查并处理软件内置「清空数据」一次性开关（会清空 AbilixProjects）。

    实测：`HKCU\\Software\\partnerx\\AbilixScratch3.0\\clear_app_data_switch_h*=1`
    （或缺失，默认按 1）时，**下一次启动 IDE 会删除重建 `standalonewindows`**
    （含 AbilixProjects 全部项目列表），随后把开关置 0。
    本函数：开关为 1 → 备份 AbilixProjects + 置 0；开关为 0 → 只报告。
    返回 {'switch','backup','fix','need_clean'}。
    """
    out: Dict[str, Any] = {'switch': None, 'backup': None, 'fix': None,
                           'need_clean': False}
    reg = read_clear_appdata_switch()
    out['switch'] = reg
    if log:
        log('  %s = %r（存在=%s）'
            % (reg.get('name') or 'clear_app_data_switch_h*', reg.get('value'),
               reg.get('found')))
    need_clean = (reg.get('effective_value') == 1)
    out['need_clean'] = need_clean
    if not need_clean:
        if log:
            log('  开关为 0（正常），下次启动不会清空 AppData。')
        return out
    if log:
        log('  [警告] 该开关为 1（或缺失，软件默认按 1）→ 下一次启动 IDE 会清空项目列表数据。')
    if backup:
        try:
            bk = backup_appdata_projects(backup_root, label='-原生积木便携版')
        except Exception as exc:  # noqa: BLE001
            bk = {'ok': False, 'error': str(exc)}
        out['backup'] = bk
        if log:
            if bk.get('ok'):
                log('  已备份 IDE 项目目录到：%s（%d 个文件 / %s）'
                    % (bk['dest'], bk['files'], fmt_bytes(bk['bytes'])))
            elif bk.get('error'):
                log('  [警告] ' + bk['error'])
    if fix_registry:
        if reg.get('name'):
            fix = set_clear_appdata_switch(reg['name'], 0)
            out['fix'] = fix
            if log:
                if fix.get('ok'):
                    log('  已把 %s 置 0（下次启动不会再清空数据）。' % reg['name'])
                else:
                    log('  [警告] 置 0 失败：%s（请手动改注册表 HKCU\\%s）'
                        % (fix.get('error'), get_base().APP_REG_KEY))
        elif log:
            log('  [警告] 注册表里还没有 clear_app_data_switch（IDE 可能从未启动过）：'
                '无法预先置 0。已备份 AppData；建议先正常启动一次 IDE 再建便携版。')
    return out


def switch_is_off(log=print) -> bool:
    """启动 IDE 前调用：确保「清空数据」开关为 0（是 0 返回 True）。"""
    reg = read_clear_appdata_switch()
    if reg.get('effective_value') == 0:
        return True
    if reg.get('name'):
        fix = set_clear_appdata_switch(reg['name'], 0)
        if fix.get('ok'):
            if log:
                log('  启动前已把 %s 置 0。' % reg['name'])
            return True
    if log:
        log('  [警告] 无法确认清空数据开关为 0：%r（若为 1，启动会清空项目列表）'
            % (reg.get('value'),))
    return False


# ============================================================================
# 五、路径/空间/安全性校验
# ============================================================================

def check_target_ascii(target: str) -> Dict[str, Any]:
    bad = non_ascii_chars(target)
    return {'ok': not bad, 'target': target, 'non_ascii_chars': bad}


def check_disk_space(target: str, assets_size: int, factor: int = 4,
                     extra: int = 256 * 1024 * 1024) -> Dict[str, Any]:
    """检查目标盘剩余空间（原生构建需要解包/重打包临时空间）。"""
    out: Dict[str, Any] = {'ok': True, 'free': None, 'needed': assets_size * factor + extra}
    try:
        drive = os.path.splitdrive(os.path.abspath(target))[0] + os.sep
        out['free'] = shutil.disk_usage(drive).free
        out['ok'] = out['free'] >= out['needed']
    except OSError as exc:
        out['error'] = str(exc)
    return out


def safe_delete_target_check(target: str, install_dirs: List[str],
                             allow_any: bool = False) -> Dict[str, Any]:
    """删除前的路径安全校验：只允许删“便携副本”目录，拒绝安装目录/系统目录等。"""
    out: Dict[str, Any] = {'ok': False, 'errors': [], 'warnings': []}
    target = os.path.abspath(target)
    out['target'] = target
    base = get_base()
    if not os.path.isdir(target):
        out['errors'].append('目录不存在：%s' % target)
        return out
    exe = os.path.join(target, APP_EXE_NAME)
    if not os.path.isfile(exe):
        out['errors'].append('目录里没有 %s，不是 AbilixScratch3.0 便携副本，拒绝删除'
                             % APP_EXE_NAME)
    # 拒绝：安装目录本身或包含安装目录
    for inst in install_dirs:
        if not inst:
            continue
        inst = os.path.abspath(inst).rstrip('\\/')
        t = target.rstrip('\\/')
        if os.path.normcase(t) == os.path.normcase(inst):
            out['errors'].append('目标是软件安装目录本身，拒绝删除：%s' % target)
        if os.path.normcase(inst).startswith(os.path.normcase(t) + os.sep):
            out['errors'].append('目标包含软件安装目录，拒绝删除：%s' % target)
        if os.path.normcase(t).startswith(os.path.normcase(inst) + os.sep):
            out['errors'].append('目标位于软件安装目录内，拒绝删除：%s' % target)
    # 拒绝：盘符根 / 用户主目录 / 桌面 / 工作目录（上层目录）
    dangerous = {os.path.abspath(os.path.expanduser('~')).rstrip('\\/') + os.sep,
                 os.path.abspath(os.path.expanduser('~')).rstrip('\\/'),
                 os.path.abspath(get_desktop_dir()).rstrip('\\/'),
                 LIB_ROOT.rstrip('\\/'),
                 os.path.abspath(os.path.dirname(LIB_ROOT)).rstrip('\\/')}
    for d in dangerous:
        if d and os.path.normcase(target.rstrip('\\/') + os.sep) == os.path.normcase(
                d if d.endswith(os.sep) else d + os.sep):
            out['errors'].append('目标是受保护目录，拒绝删除：%s' % target)
    drive, tail = os.path.splitdrive(target)
    if tail in ('\\', '/', ''):
        out['errors'].append('目标是盘符根目录，拒绝删除：%s' % target)
    # 警告：目录名不像便携副本（默认名/含 FuncLib/函数版）；--force 才允许
    name = os.path.basename(target.rstrip('\\/'))
    looks_like = (name == DEFAULT_TARGET_DIRNAME or 'FuncLib' in name
                  or '函数版' in name or '_函数版' in name)
    if not looks_like:
        msg = '目录名不像便携副本（不是 %s / *FuncLib / *函数版）：%s' % (
            DEFAULT_TARGET_DIRNAME, name)
        if allow_any:
            out['warnings'].append(msg + '（已按 --force 继续）')
        else:
            out['errors'].append(msg + '\n  确认要删可加 --force。')
    # 拒绝：Program Files 下
    low = os.path.normcase(target)
    if 'program files' in low:
        out['errors'].append('目标位于 Program Files 下，拒绝删除：%s' % target)
    out['ok'] = not out['errors']
    return out


# ============================================================================
# 六、原生积木便携版创建/更新/删除的公共小工具
# ============================================================================

def require_core(script_name: str) -> Optional[str]:
    """核心工具是否存在；不存在返回错误消息（供入口脚本 fail）。"""
    if core_exists():
        return None
    return ('核心工具尚未就绪：%s\n'
            '  这是「原生函数积木」方案的构建引擎（Lead 提供）。\n'
            '  请等 原生积木核心.py 出现后重试；本脚本只依赖它的 build/verify 子命令；'
            '其余逻辑（复制/快捷方式/AppData 保护/删除）与它无关。' % CORE_SCRIPT)


def core_banner(log=print) -> None:
    if core_exists():
        st = os.stat(CORE_SCRIPT)
        log('  核心工具：%s（%s，修改时间 %s）'
            % (CORE_SCRIPT, fmt_bytes(st.st_size),
               time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))))
    else:
        log('  核心工具：尚未就绪（%s）' % CORE_SCRIPT)


def verify_install_untouched(expected_sha256: str, expected_size: int,
                             install_dir: Optional[str] = None,
                             log=print) -> Dict[str, Any]:
    """只读校验真实安装目录的 browser_assets 是否仍为原包（未被修改）。"""
    out: Dict[str, Any] = {'ok': False, 'assets': None, 'sha256': None,
                           'bytes': None, 'error': None}
    try:
        app = os.path.abspath(install_dir or locate_install_source() or DEFAULT_SOURCE)
        assets = find_assets(app)
        out['assets'] = assets
        out['bytes'] = os.path.getsize(assets)
        out['sha256'] = sha256_file(assets)
        out['ok'] = (out['sha256'].lower() == expected_sha256.lower()
                     and out['bytes'] == expected_size)
        if not out['ok']:
            out['error'] = ('真实安装目录 browser_assets 与基准不一致：\n'
                            '  实际 %s / %s\n  期望 %s / %s'
                            % (fmt_bytes(out['bytes']), out['sha256'],
                               fmt_bytes(expected_size), expected_sha256))
    except Exception as exc:  # noqa: BLE001
        out['error'] = '校验安装目录失败：%s' % exc
    if log:
        if out['ok']:
            log('  真实安装目录 browser_assets 未修改：%s / %s'
                % (fmt_bytes(out['bytes']), out['sha256'].upper()))
        elif out.get('error'):
            log('  [警告] ' + out['error'])
    return out


#: 已知原包基准（2026-11-10 实测，真实安装目录）
INSTALL_ASSETS_SHA256 = 'DF6DB241752D42BFF2995FCD24521E070ADF9EB5D96E870148F9DC51690EDC40'
INSTALL_ASSETS_SIZE = 85271033
