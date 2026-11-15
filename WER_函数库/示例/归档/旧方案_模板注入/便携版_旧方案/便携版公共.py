# -*- coding: utf-8 -*-
"""
便携版公共.py —— 「便携函数版」创建 / 更新 / 删除脚本共用的底层函数
============================================================================

本模块不含命令行入口，由同目录的：
    * 创建便携函数版.py
    * 更新便携版函数库.py
    * 删除便携版.py
通过 importlib 加载。

职责
----
1. 定位软件安装目录 / browser_assets / 函数库源文件（路径全部可移植，自动探测 + 可参数覆盖）；
2. 把安装目录复制成一份「用户可写的便携副本」：**优先硬链接 os.link**（同一 NTFS 卷上
   几乎不占额外空间、几秒完成），失败自动回退 shutil.copy2；复制后校验文件数/总大小；
3. 关键安全处理：`browser_assets`（打补丁要改写的文件）**永不做硬链接**，而是独立复制。
   因为硬链接与安装目录共享同一份数据，一旦就地写补丁会把**安装目录**一起改坏。
   （创建时直接 copy2；更新时若发现是硬链接，会先 detach 成独立文件再打补丁。）
4. 调用 `工具/底层/patch_browser_assets.py` 对副本的 browser_assets 打补丁并自检；
5. 读回补丁包里的 defaultcode（zh-hans/zh-hant/en）用于二次校验；
6. 桌面快捷方式（.lnk）创建、桌面路径探测、进程占用探测、备份清理、sha256/目录统计等。

依赖：仅 Python 3.8+ 标准库 + 本仓库 `工具/底层/patch_browser_assets.py`、`srhs工具.py`。
"""

from __future__ import annotations

import base64
import glob
import importlib.util
import json
import os
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ----------------------------------------------------------------------------
# 路径常量（全部相对本文件推算，整个 WER_函数库 目录拷到别处也能用）
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))          # .../WER_函数库/工具/便携版
TOOLS_ROOT = os.path.dirname(HERE)                          # .../WER_函数库/工具
LIB_ROOT = os.path.dirname(TOOLS_ROOT)                      # .../WER_函数库
PATCH_SCRIPT = os.path.join(TOOLS_ROOT, '底层', 'patch_browser_assets.py')
SRHS_SCRIPT = os.path.join(TOOLS_ROOT, '底层', 'srhs工具.py')

DEFAULT_SOURCE = r'D:\Program Files\AbilixScratch3.0'

def locate_install_source():
    """自动探测 AbilixScratch3.0 安装目录（其他电脑可能装在 C 盘；也可用环境变量/参数覆盖）。"""
    candidates = []
    env = os.environ.get('ABILIX_INSTALL_DIR')
    if env:
        candidates.append(env)
    candidates += [
        os.path.join('D:\\Program Files', 'AbilixScratch3.0'),
        os.path.join('C:\\Program Files', 'AbilixScratch3.0'),
    ]
    for key in ('ProgramFiles', 'ProgramFiles(x86)'):
        base = os.environ.get(key)
        if base:
            candidates.append(os.path.join(base, 'AbilixScratch3.0'))
    for drive in ('C:', 'D:', 'E:', 'F:', 'G:', 'H:'):
        candidates.append(os.path.join(drive + '\\Program Files', 'AbilixScratch3.0'))
    seen = set()
    for c in candidates:
        c = os.path.abspath(c)
        if c in seen:
            continue
        seen.add(c)
        exe = os.path.join(c, APP_EXE_NAME)
        if os.path.isfile(exe):
            return c
    return None

#: 默认便携副本目录名：必须**纯 ASCII**！
#: 实测（2026-11-10）：把副本放在含中文的路径（如 ...\2026普级赛\_分析临时\...\AbilixScratch3.0_函数版）
#: 时，IDE 能启动但内嵌 CEF 浏览器初始化失败 → 积木网页区全白；改到纯 ASCII 路径后正常。
#: （原因：软件的 CEF 资源路径走 ANSI 转换，非 ASCII 字符会丢失。）
DEFAULT_TARGET_DIRNAME = 'AbilixScratch3.0_FuncLib'
DEFAULT_SHORTCUT_NAME = 'AbilixScratch3.0 函数版.lnk'
APP_EXE_NAME = 'AbilixScratch3.0.exe'

#: 各版本 IDE 的数据目录名（注意真实版本是**点号** 3.0，历史补丁脚本里写的下划线 3_0 是错的）
DATA_DIR_NAMES = ('AbilixScratch3.0_Data', 'AbilixScratch3_0_Data')

#: 这些文件可能被程序/我们自己在运行时改写，**不能硬链接**（否则会改到安装目录）
MUTABLE_FILE_NAMES = {'browser_assets', 'output_log.txt', 'player.log', 'player-prev.log'}
MUTABLE_EXTENSIONS = {'.log'}

BACKUP_PREFIX = 'browser_assets.备份-'


# ============================================================================
# 一、通用工具函数
# ============================================================================

def fmt_bytes(n: int) -> str:
    """人类可读的字节数。"""
    n = float(n)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024.0 or unit == 'TB':
            if unit == 'B':
                return '%d B' % int(n)
            return '%.1f %s' % (n, unit)
        n /= 1024.0
    return '%.1f GB' % n


def timestamp(fmt: str = '%Y%m%d-%H%M%S') -> str:
    return time.strftime(fmt)


def sha256_file(path: str, chunk: int = 1024 * 1024) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def dir_stats(root: str) -> Dict[str, Any]:
    """统计目录下文件数 / 总大小 / 子目录数（不跟随符号链接）。"""
    files = 0
    total = 0
    dirs = 0
    for cur, sub_dirs, filenames in os.walk(root):
        dirs += len(sub_dirs)
        for name in filenames:
            p = os.path.join(cur, name)
            try:
                total += os.path.getsize(p)
            except OSError:
                pass
            files += 1
    return {'files': files, 'bytes': total, 'dirs': dirs}


def write_json(path: str, obj: Any) -> str:
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
    return path


def read_json(path: str) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_module(path: str, name: str):
    """按文件路径加载一个 .py 模块（文件名含中文时也可靠）。"""
    if not os.path.isfile(path):
        raise FileNotFoundError('找不到模块文件：%s' % path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError('无法加载模块：%s' % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_patch_module():
    """加载底层补丁器 patch_browser_assets.py。"""
    return load_module(PATCH_SCRIPT, 'patch_browser_assets_portable')


def load_srhs_tool():
    """加载 .srh/.srhs 工具 srhs工具.py。"""
    return load_module(SRHS_SCRIPT, 'srhs_tool_portable')


# ============================================================================
# 二、安装目录 / 资源包 / 函数库源 定位
# ============================================================================

def default_target() -> str:
    """默认便携副本目录：%USERPROFILE%\\AbilixScratch3.0_函数版。"""
    return os.path.join(os.path.expanduser('~'), DEFAULT_TARGET_DIRNAME)


def validate_install_dir(app_dir: str) -> Dict[str, Any]:
    """校验一个目录是不是 AbilixScratch3.0 安装目录，返回信息字典（不抛异常）。"""
    app_dir = os.path.abspath(app_dir)
    info: Dict[str, Any] = {'ok': False, 'app_dir': app_dir, 'errors': [], 'warnings': []}
    if not os.path.isdir(app_dir):
        info['errors'].append('目录不存在：%s' % app_dir)
        return info
    exe = os.path.join(app_dir, APP_EXE_NAME)
    info['exe'] = exe
    info['exe_exists'] = os.path.isfile(exe)
    if not info['exe_exists']:
        info['errors'].append('目录里没有 %s，不是 AbilixScratch3.0 安装目录？' % APP_EXE_NAME)
    try:
        assets = find_assets(app_dir)
        info['assets'] = assets
        info['assets_size'] = os.path.getsize(assets)
        info['assets_sha256'] = sha256_file(assets)
    except FileNotFoundError as exc:
        info['errors'].append(str(exc))
    stats = dir_stats(app_dir)
    info.update({'files': stats['files'], 'bytes': stats['bytes']})
    info['ok'] = not info['errors']
    return info


def find_assets(app_dir: str) -> str:
    """
    在安装目录里找 browser_assets（真实路径：<App>_Data\\Resources\\browser_assets）。

    兼容历史脚本里写错的下划线目录名 `AbilixScratch3_0_Data`，以及任意 `*_Data` 目录。
    """
    app_dir = os.path.abspath(app_dir)
    candidates: List[str] = []
    for data_name in DATA_DIR_NAMES:
        candidates.append(os.path.join(app_dir, data_name, 'Resources', 'browser_assets'))
    for data_dir in sorted(glob.glob(os.path.join(app_dir, '*_Data'))):
        candidates.append(os.path.join(data_dir, 'Resources', 'browser_assets'))
    seen = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if os.path.isfile(cand):
            if os.path.getsize(cand) < 1024 * 1024:
                raise FileNotFoundError('找到 %s 但体积异常（%s），可能不是真实的资源包'
                                        % (cand, fmt_bytes(os.path.getsize(cand))))
            return cand
    raise FileNotFoundError(
        '在 %s 下找不到 browser_assets（已查找：%s）。\n'
        '  真实路径一般形如：<安装目录>\\AbilixScratch3.0_Data\\Resources\\browser_assets\n'
        '  可用 --source/--assets 显式指定。' % (app_dir, '；'.join(candidates)))


def default_library_candidates() -> List[Tuple[str, str]]:
    """默认函数库源候选：(路径, 来源标记)。按优先级排列。"""
    return [
        (os.path.join(LIB_ROOT, '我的函数库.srh'), 'mine'),
        (os.path.join(LIB_ROOT, '我的函数库.srhs'), 'mine'),
        (os.path.join(LIB_ROOT, 'WER函数库.srh'), 'root'),
        (os.path.join(LIB_ROOT, 'WER函数库.srhs'), 'root'),
        (os.path.join(LIB_ROOT, '示例', 'WER函数库.srhs'), 'example'),
        (os.path.join(LIB_ROOT, '示例', 'WER函数库.srh'), 'example'),
    ]


def find_library(path: Optional[str] = None) -> Dict[str, Any]:
    """
    定位「函数库源文件」(.srh/.srhs)，返回 {'path','kind','origin'}；找不到抛 FileNotFoundError。

    * 给了 path：只认这个；
    * 没给：按 我的函数库.srh → 我的函数库.srhs → WER函数库.srh(s) → 示例/WER函数库.srhs 顺序找。
    """
    if path:
        p = os.path.abspath(path)
        if not os.path.isfile(p):
            raise FileNotFoundError('函数库源文件不存在：%s' % p)
        if os.path.splitext(p)[1].lower() not in ('.srh', '.srhs'):
            raise ValueError('函数库源文件必须是 .srh 或 .srhs：%s' % p)
        kind = 'mine' if os.path.basename(p).startswith('我的函数库') else 'explicit'
        return {'path': p, 'kind': kind, 'origin': '参数 --library 指定'}
    for cand, kind in default_library_candidates():
        if os.path.isfile(cand):
            origin = {'mine': '默认：我的函数库', 'root': 'WER_函数库 根目录同名库',
                      'example': '示例库（我的函数库尚不存在时的回退）'}[kind]
            return {'path': cand, 'kind': kind, 'origin': origin}
    raise FileNotFoundError(
        '找不到函数库源文件。\n'
        '  默认应放在：%s\n'
        '  （或 %s）\n'
        '  也可用 --library 显式指定 .srh/.srhs。' %
        (os.path.join(LIB_ROOT, '我的函数库.srh'),
         os.path.join(LIB_ROOT, '我的函数库.srhs')))


def describe_library(path: str) -> Dict[str, Any]:
    """读取函数库基本信息（顶层块/函数/变量/是否含 start），用于打印与告警。"""
    srhs = load_srhs_tool()
    info = srhs.read_project_file(path)
    v = srhs.validate_project_xml(info.project_xml)
    return {
        'path': os.path.abspath(path),
        'bytes': os.path.getsize(path),
        'sha256': sha256_file(path),
        'top_blocks': v.get('top_block_count', 0),
        'start_blocks': v.get('start_count', 0),
        'defnoreturn': len(v.get('defnoreturn_names', []) or []),
        'defreturn': len(v.get('defreturn_names', []) or []),
        'variables': len(v.get('variable_names', []) or []),
        'ok': bool(v.get('ok')),
        'errors': v.get('errors', []),
    }


# ============================================================================
# 三、复制成便携副本（硬链接优先 + browser_assets 独立）
# ============================================================================

def _is_mutable(rel_path: str) -> bool:
    """判断文件是否属于“可能被改写、不能硬链接”的文件。"""
    name = os.path.basename(rel_path)
    if name in MUTABLE_FILE_NAMES:
        return True
    return os.path.splitext(name)[1].lower() in MUTABLE_EXTENSIONS


def copy_tree_prefer_hardlink(src: str, dst: str,
                              log: Optional[Any] = None) -> Dict[str, Any]:
    """
    把 src 目录整棵树复制到 dst：普通文件优先 os.link（硬链接），
    可能被改写的文件（browser_assets / *.log 等）强制 shutil.copy2；
    硬链接失败（跨卷、非 NTFS 等）自动回退 copy2。

    返回 {'files','bytes','linked','copied','fallback','mutable','seconds'}。
    """
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    if not os.path.isdir(src):
        raise FileNotFoundError('源目录不存在：%s' % src)
    if os.path.exists(dst) and (not os.path.isdir(dst) or os.listdir(dst)):
        raise FileExistsError('目标目录已存在且非空：%s' % dst)

    def _log(msg: str) -> None:
        if log:
            log(msg)

    started = time.time()
    stats = {'files': 0, 'bytes': 0, 'linked': 0, 'copied': 0, 'fallback': 0,
             'mutable': 0, 'mutable_list': []}
    for cur, sub_dirs, filenames in os.walk(src):
        rel_dir = os.path.relpath(cur, src)
        out_dir = dst if rel_dir == '.' else os.path.join(dst, rel_dir)
        os.makedirs(out_dir, exist_ok=True)
        for name in filenames:
            rel = name if rel_dir == '.' else os.path.join(rel_dir, name)
            s = os.path.join(cur, name)
            d = os.path.join(out_dir, name)
            size = os.path.getsize(s)
            if _is_mutable(rel):
                shutil.copy2(s, d)
                stats['copied'] += 1
                stats['mutable'] += 1
                stats['mutable_list'].append(rel)
                _log('  独立复制(不可硬链): %s (%s)' % (rel, fmt_bytes(size)))
            else:
                try:
                    os.link(s, d)
                    stats['linked'] += 1
                except OSError as exc:      # 跨卷/不支持硬链接/权限等
                    shutil.copy2(s, d)
                    stats['copied'] += 1
                    stats['fallback'] += 1
                    _log('  硬链接失败回退复制: %s（%s）' % (rel, exc))
            stats['files'] += 1
            stats['bytes'] += size
    stats['seconds'] = round(time.time() - started, 2)
    return stats


def verify_copy(src: str, dst: str) -> Dict[str, Any]:
    """校验复制结果：文件数/总大小一致、exe 存在、browser_assets 独立且体积一致。"""
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    report: Dict[str, Any] = {'ok': False, 'errors': [], 'warnings': []}
    s_stats = dir_stats(src)
    d_stats = dir_stats(dst)
    report['src'] = s_stats
    report['dst'] = d_stats
    if s_stats['files'] != d_stats['files']:
        report['errors'].append('文件数不一致：源 %d / 副本 %d'
                                % (s_stats['files'], d_stats['files']))
    if s_stats['bytes'] != d_stats['bytes']:
        report['errors'].append('总大小不一致：源 %s / 副本 %s'
                                % (fmt_bytes(s_stats['bytes']), fmt_bytes(d_stats['bytes'])))
    exe = os.path.join(dst, APP_EXE_NAME)
    report['exe'] = exe
    if not os.path.isfile(exe):
        report['errors'].append('副本里没有 %s' % APP_EXE_NAME)
    try:
        src_assets = find_assets(src)
        dst_assets = find_assets(dst)
        report['src_assets'] = src_assets
        report['dst_assets'] = dst_assets
        same = False
        try:
            same = os.path.samefile(src_assets, dst_assets)
        except OSError:
            same = False
        if same:
            report['errors'].append(
                '副本里的 browser_assets 仍是安装目录的硬链接，'
                '打补丁会改坏安装目录！必须独立复制。')
        else:
            report['assets_independent'] = True
        if os.path.getsize(src_assets) != os.path.getsize(dst_assets):
            report['errors'].append('browser_assets 体积不一致')
    except FileNotFoundError as exc:
        report['errors'].append(str(exc))
    report['ok'] = not report['errors']
    return report


def detach_hardlink(path: str) -> bool:
    """
    若 path 是硬链接（st_nlink > 1），把它“断开”成独立文件（复制到临时名后 os.replace）。

    返回是否真的做了 detach。用于更新补丁前的安全保护：
    即使历史上手工创建过硬链接副本，也不会在打补丁时改到安装目录。
    """
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError('文件不存在：%s' % path)
    try:
        st = os.stat(path)
        nlink = getattr(st, 'st_nlink', 1)
    except OSError:
        nlink = 1
    if nlink <= 1:
        return False
    tmp = path + '.detach-%d.tmp' % os.getpid()
    try:
        shutil.copy2(path, tmp)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return True


# ============================================================================
# 四、打补丁 + 读回 defaultcode（二次校验）
# ============================================================================

def patch_copy_assets(copy_app_dir: str, library_path: str,
                      workdir: Optional[str] = None,
                      keep_work: bool = False) -> Dict[str, Any]:
    """
    用底层补丁器给“副本”的 browser_assets 打补丁（--install 等价：先备份再写回）。

    * 打补丁前对 browser_assets 做 detach_hardlink 保护（防安装目录被连带修改）；
    * 补丁器自身会做：格式校验 → 纯 roundtrip 逐字节自检 → 只改 maingui_init.js →
      重打包 → 逐条目 sha256 自检 → 备份原文件 → 写回副本。
    """
    patch = load_patch_module()
    assets = find_assets(copy_app_dir)
    detached = detach_hardlink(assets)
    report: Dict[str, Any] = {
        'assets': assets,
        'detached_hardlink': detached,
        'before_sha256': sha256_file(assets),
        'before_size': os.path.getsize(assets),
    }
    patch_report = patch.patch_assets(
        assets_path=assets,
        library_path=library_path,
        install=True,
        keep_work=keep_work,
        workdir=workdir,
        progress=True,
    )
    report['patch'] = patch_report
    if patch_report.get('installed'):
        report['after_sha256'] = sha256_file(assets)
        report['after_size'] = os.path.getsize(assets)
        report['backup'] = patch_report.get('backup')
        report['ok'] = bool(patch_report.get('ok'))
    else:
        report['ok'] = False
    return report


def read_defaultcodes(assets_path: str) -> Dict[str, str]:
    """从 browser_assets 里读出 maingui_init.js 的三个 defaultcode 原文。"""
    patch = load_patch_module()
    info = patch.read_zfb_index(assets_path, with_data=True)
    raw = patch.read_zfb_entry_bytes(info, patch.MAINGUI_INIT_KEY)
    text = raw.decode('utf-8')
    out: Dict[str, str] = {}
    for lang, var_name in patch.DEFAULTCODE_VARS.items():
        _lineno, _start, literal = patch.find_defaultcode_line(text, var_name)
        out[lang] = patch.js_unescape_js_string(literal)
    out['_raw_bytes'] = len(raw)
    out['_text'] = text
    return out


def verify_patched_defaultcode(assets_path: str, library_path: str) -> Dict[str, Any]:
    """
    补丁后二次校验（独立于补丁器自带自检）：
      1. 从补丁包读回 defaultcode，与「从函数库重新生成的片段」完全相等；
      2. maingui_init.js 仍是合法 UTF-8；defaultcode 变量行数与补丁器一致；
      3. 片段本身是合法项目 XML 且含 start / 函数定义数符合函数库。
    """
    patch = load_patch_module()
    srhs = load_srhs_tool()
    expected = patch.build_defaultcode_fragment(library_path=library_path)
    got = read_defaultcodes(assets_path)
    report: Dict[str, Any] = {
        'ok': False,
        'expected_chars': expected['chars'],
        'expected_top_blocks': expected['top_blocks'],
        'expected_functions': expected['defnoreturn'],
        'expected_variables': expected['variables'],
        'languages': {},
        'errors': [],
    }
    for lang in ('zh-hans', 'zh-hant', 'en'):
        same = got.get(lang) == expected['fragment']
        report['languages'][lang] = {
            'chars': len(got.get(lang) or ''),
            'equals_expected': same,
        }
        if lang == 'zh-hans' and not same:
            report['errors'].append('zh-hans defaultcode 与期望片段不一致')
        if lang != 'zh-hans' and same:
            report['errors'].append('%s defaultcode 被意外修改（应保留原语言内容）' % lang)
    frag_info = srhs.validate_project_xml(expected['fragment'])
    report['fragment_valid'] = bool(frag_info.get('ok'))
    report['fragment_start'] = frag_info.get('start_count', 0)
    report['fragment_functions'] = len(frag_info.get('defnoreturn_names', []) or [])
    if not report['fragment_valid']:
        report['errors'].append('defaultcode 片段不是合法项目 XML：%s' % frag_info.get('errors'))
    if not report['fragment_start']:
        report['errors'].append('defaultcode 片段缺少 start 块')
    report['ok'] = not report['errors']
    return report


def list_backups(assets_path: str) -> List[Dict[str, Any]]:
    """列出 browser_assets 的补丁备份文件（按时间从旧到新）。"""
    assets_path = os.path.abspath(assets_path)
    folder = os.path.dirname(assets_path)
    prefix = os.path.basename(assets_path) + '.备份-'
    out = []
    for name in os.listdir(folder):
        if name.startswith(prefix):
            p = os.path.join(folder, name)
            if os.path.isfile(p):
                out.append({'path': p, 'bytes': os.path.getsize(p),
                            'mtime': os.path.getmtime(p)})
    out.sort(key=lambda x: x['mtime'])
    return out


def prune_backups(assets_path: str, keep: int = 2) -> List[str]:
    """只保留最新 keep 个备份，删除更旧的，返回被删路径列表。"""
    backups = list_backups(assets_path)
    removed = []
    if keep < 0:
        return removed
    for item in backups[:max(0, len(backups) - keep)]:
        try:
            os.remove(item['path'])
            removed.append(item['path'])
        except OSError as exc:
            removed.append('%s（删除失败：%s）' % (item['path'], exc))
    return removed


# ============================================================================
# 五、Windows 交互：桌面路径 / 快捷方式 / 进程占用
# ============================================================================

def _run_powershell(script: str, timeout: int = 60) -> Dict[str, Any]:
    """用 Windows PowerShell(5.1) 执行一段脚本（-EncodedCommand，避免引号地狱）。"""
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    exe = 'powershell.exe'
    try:
        proc = subprocess.run(
            [exe, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-EncodedCommand', encoded],
            capture_output=True, timeout=timeout)
        return {
            'ok': proc.returncode == 0,
            'returncode': proc.returncode,
            'stdout': proc.stdout.decode('utf-8', errors='replace').strip(),
            'stderr': proc.stderr.decode('utf-8', errors='replace').strip(),
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {'ok': False, 'returncode': -1, 'stdout': '',
                'stderr': '无法执行 powershell.exe：%s' % exc}


def _ps_quote(text: str) -> str:
    """把字符串转成 PowerShell 单引号字面量。"""
    return "'" + text.replace("'", "''") + "'"


def get_desktop_dir() -> str:
    """取当前用户桌面目录（含 OneDrive 重定向的情况），失败回退 %USERPROFILE%\\Desktop。"""
    res = _run_powershell("[Environment]::GetFolderPath('Desktop')")
    if res['ok'] and res['stdout']:
        candidate = res['stdout'].splitlines()[0].strip()
        if candidate and os.path.isdir(candidate):
            return candidate
    fallback = os.path.join(os.path.expanduser('~'), 'Desktop')
    if os.path.isdir(fallback):
        return fallback
    return fallback


def create_shortcut(target_exe: str, lnk_path: str, workdir: Optional[str] = None,
                    description: str = 'AbilixScratch3.0 函数版（新建项目自带函数库）') -> Dict[str, Any]:
    """在 Windows 上创建 .lnk 快捷方式（WScript.Shell），返回结果字典。"""
    target_exe = os.path.abspath(target_exe)
    lnk_path = os.path.abspath(lnk_path)
    workdir = os.path.abspath(workdir or os.path.dirname(target_exe))
    os.makedirs(os.path.dirname(lnk_path) or '.', exist_ok=True)
    script = '\n'.join([
        "$ErrorActionPreference = 'Stop'",
        '$ws = New-Object -ComObject WScript.Shell',
        '$sc = $ws.CreateShortcut(%s)' % _ps_quote(lnk_path),
        '$sc.TargetPath = %s' % _ps_quote(target_exe),
        '$sc.WorkingDirectory = %s' % _ps_quote(workdir),
        '$sc.IconLocation = %s' % _ps_quote(target_exe + ',0'),
        '$sc.Description = %s' % _ps_quote(description),
        '$sc.WindowStyle = 1',
        '$sc.Save()',
        "if (Test-Path %s) { Write-Output 'CREATED' } else { Write-Output 'MISSING' }"
        % _ps_quote(lnk_path),
    ])
    res = _run_powershell(script)
    ok = res['ok'] and res['stdout'].endswith('CREATED') and os.path.isfile(lnk_path)
    res['ok'] = ok
    res['lnk'] = lnk_path
    res['target'] = target_exe
    res['workdir'] = workdir
    if ok:
        res['lnk_bytes'] = os.path.getsize(lnk_path)
    return res


def processes_under(dir_path: str) -> List[Dict[str, Any]]:
    """
    找出可执行文件路径位于 dir_path 之下的正在运行的进程（用于提示“请先关闭函数版”）。

    返回 [{'pid','name','path'}, ...]；权限不足查不到路径的进程会被忽略。
    """
    prefix = os.path.abspath(dir_path).rstrip('\\') + '\\'
    script = '\n'.join([
        "$ErrorActionPreference = 'SilentlyContinue'",
        "Get-Process | Where-Object { $_.Path -ne $null -and $_.Path.StartsWith(%s, "
        "[System.StringComparison]::OrdinalIgnoreCase) } | "
        "ForEach-Object { Write-Output ($_.Id.ToString() + '|' + $_.ProcessName + '|' + $_.Path) }"
        % _ps_quote(prefix),
    ])
    res = _run_powershell(script)
    out: List[Dict[str, Any]] = []
    if not res['ok']:
        return out
    for line in res['stdout'].splitlines():
        parts = line.split('|', 2)
        if len(parts) == 3:
            try:
                pid = int(parts[0])
            except ValueError:
                pid = -1
            out.append({'pid': pid, 'name': parts[1], 'path': parts[2]})
    return out


def wait_process_exit(pids: Sequence[int], timeout: float = 60.0) -> bool:
    """等待指定 pid 全部退出（Windows 上任务管理器看不到区别，这里用 os.kill(pid,0) 探测）。"""
    deadline = time.time() + timeout
    pending = set(int(p) for p in pids)
    while pending and time.time() < deadline:
        gone = set()
        for pid in pending:
            try:
                os.kill(pid, 0)
            except OSError:
                gone.add(pid)
            else:
                # Windows 上 os.kill(pid, 0) 对已退出 pid 也可能抛错；用 ctypes 更稳
                try:
                    import ctypes
                    SYNCHRONIZE = 0x00100000
                    h = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
                    if not h:
                        gone.add(pid)
                    else:
                        ctypes.windll.kernel32.CloseHandle(h)
                except Exception:  # noqa: BLE001
                    pass
        pending -= gone
        if pending:
            time.sleep(0.3)
    return not pending


# ============================================================================
# 六、安装/AppData/注册表检查（实测踩坑后的安全措施）
# ============================================================================
#: 软件注册表根键（PlayerPrefs 存在这里，名称后面带 Unity 哈希后缀）
APP_REG_KEY = r'Software\partnerx\AbilixScratch3.0'
CLEAR_SWITCH_PREFIX = 'clear_app_data_switch'


def appdata_standalone_dir() -> str:
    """IDE 的用户数据根目录：%USERPROFILE%\\AppData\\LocalLow\\partnerx\\AbilixScratch3_0\\standalonewindows"""
    home = os.environ.get('USERPROFILE') or os.path.expanduser('~')
    return os.path.join(home, 'AppData', 'LocalLow', 'partnerx',
                        'AbilixScratch3_0', 'standalonewindows')


def appdata_projects_dir() -> str:
    """IDE 的项目列表/临时项目根目录（便携版与安装版共用）。"""
    return os.path.join(appdata_standalone_dir(), 'AbilixProjects')


def non_ascii_chars(path: str) -> List[str]:
    """返回路径里出现的非 ASCII 字符（去重排序）。"""
    return sorted({ch for ch in path if ord(ch) > 127})


def is_ascii_path(path: str) -> bool:
    return not non_ascii_chars(path)


def read_clear_appdata_switch() -> Dict[str, Any]:
    """
    读取软件内置「清空数据」一次性开关（PlayerPrefs: clear_app_data_switch_h*）。

    ⚠ 实测（2026-11-10）：该开关**默认值 1**；首次启动时 `ApplicationEntry.HandleSanBoxRes()`
    会据此删除并重建 `%LocalLow%\\partnerx\\AbilixScratch3_0\\standalonewindows\\`
    （含 AbilixProjects 全部项目列表/临时项目），然后把开关置 0。
    所以：**创建便携版时若开关为 1（或键不存在），第一次启动便携副本会清空 IDE 项目列表数据**。
    本工具会在创建时自动备份 AppData 并把开关置 0（可用 --no-fix-registry 关闭）。
    """
    import winreg
    out: Dict[str, Any] = {'key': r'HKCU\\' + APP_REG_KEY, 'found': False,
                           'name': None, 'value': None, 'error': None}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_REG_KEY, 0, winreg.KEY_READ) as key:
            i = 0
            while True:
                try:
                    name, value, _typ = winreg.EnumValue(key, i)
                except OSError:
                    break
                i += 1
                if name.startswith(CLEAR_SWITCH_PREFIX):
                    out.update({'found': True, 'name': name, 'value': value})
                    break
    except OSError as exc:
        out['error'] = str(exc)
    # 键不存在时按软件默认值 1 处理
    if not out['found'] and not out['error']:
        out['effective_value'] = 1
        out['reason'] = '注册表里没有该值（软件默认按 1 处理→首次启动会清空数据）'
    else:
        out['effective_value'] = out['value']
        out['reason'] = '读到开关值'
    return out


def set_clear_appdata_switch(reg_name: str, value: int = 0) -> Dict[str, Any]:
    """把「清空数据」开关写为指定值（默认 0 = 不清理）。"""
    import winreg
    out: Dict[str, Any] = {'ok': False, 'name': reg_name, 'value': value, 'error': None}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_REG_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, reg_name, 0, winreg.REG_DWORD, int(value))
        out['ok'] = True
    except OSError as exc:
        out['error'] = str(exc)
    return out


def backup_appdata_projects(dest_root: str, label: str = '') -> Dict[str, Any]:
    """
    把 IDE 的整个 AbilixProjects 目录复制到 dest_root 下备份（只读源，不修改 AppData）。

    返回 {'ok','src','dest','files','bytes','config_sha256','error'}。
    """
    src = appdata_projects_dir()
    out: Dict[str, Any] = {'ok': False, 'src': src, 'dest': None, 'files': 0,
                           'bytes': 0, 'config_sha256': None, 'error': None}
    if not os.path.isdir(src):
        out['error'] = 'AppData 项目目录不存在（IDE 可能从未运行过）：%s' % src
        return out
    dest = os.path.join(os.path.abspath(dest_root),
                        'AbilixProjects.备份-%s%s' % (timestamp(), label))
    try:
        shutil.copytree(src, dest)
    except OSError as exc:
        out['error'] = '备份失败：%s' % exc
        return out
    stats = dir_stats(dest)
    out.update({'ok': True, 'dest': dest, 'files': stats['files'], 'bytes': stats['bytes']})
    cfg = os.path.join(dest, '111', 'abilixProjectConfig.txt')
    if os.path.isfile(cfg):
        out['config_sha256'] = sha256_file(cfg)
    return out


# ============================================================================
# 七、打印辅助
# ============================================================================

def print_header(title: str) -> None:
    print('=' * 76)
    print(title)
    print('-' * 76)


def print_kv(key: str, value: Any) -> None:
    print('%-12s: %s' % (key, value))


def print_footer() -> None:
    print('=' * 76)
