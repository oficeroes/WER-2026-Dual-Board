# -*- coding: utf-8 -*-
"""
安装到IDE项目列表.py —— 把 WER函数库 作为一个项目挂进 AbilixScratch3.0 的“项目列表”
========================================================================================

原理（C# 反编译源码实证，见 `逆向资料/decompiled/Assembly-CSharp.decompiled.cs`）
------------------------------------------------------------------------------------
IDE 启动时会读取：
    %USERPROFILE%\\AppData\\LocalLow\\partnerx\\AbilixScratch3_0\\standalonewindows
        \\AbilixProjects\\<机器人类型数字>\\abilixProjectConfig.txt
其中每个 `<TempProjectInfoList>` 对应项目列表里的一个项目（最多直接显示 7 个）：
    tempProjectFolderName : 该项目的临时目录名（13 位毫秒时间戳）
    isNewProject          : 是否新项目        （装“已有项目”填 false）
    isSaved               : 是否已保存过      （打开过 .srhs 的填 true）
    isChanged             : 是否有改动        （false）
    savedProjectPath      : 项目对应的 .srhs 路径；项目列表显示的名字 = 该路径文件名（去扩展名）

安装做法（与 IDE “文件→打开 .srhs”后行为一致）：
  1. 在 `AbilixProjects\\<数字>\\<时间戳>\\` 下写入 `abilixProject.srh`（项目内容）；
  2. 在 `abilixProjectConfig.txt` 里追加一条 `<TempProjectInfoList>`（先备份 config）。
这样打开 IDE 后项目列表里就会出现一个名为 `WER函数库` 的项目，点开即可看到函数库积木。

安全设计
--------
* **默认 dry-run（只打印计划、不写任何文件）**；确认无误后加 `--apply` 真正安装。
* 修改 `abilixProjectConfig.txt` 前自动备份为 `abilixProjectConfig.backup-<时间>.txt`。
* **幂等**：同一个 savedProjectPath / 同名项目已存在时不会重复添加。
* 支持 `--projects-root` 指向**副本目录**做测试（本机测试推荐，绝不污染真实 AppData）。
* IDE 上限：项目列表直接显示最多 7 个（`MAX_SHOW_PROJ_COUNT = 7`），达到 7 个时会拒绝
  （除非 `--force`，超出部分会进下拉列表）。
* 安装/卸载请先**关闭 IDE**，否则 IDE 退出时可能用内存里的旧配置覆盖文件。

用法示例
--------
    # 1) 先 dry-run 看计划（不写文件）
    python 安装到IDE项目列表.py --dry-run

    # 2) 真正安装（会自动备份 config）
    python 安装到IDE项目列表.py --apply

    # 3) 在副本目录上测试（安全，可随便跑）
    python 安装到IDE项目列表.py --projects-root _分析临时\\integration_work\\appdata_test --apply

    # 4) 指定机器人类型 / 项目在列表里显示的名字（名字由 savedProjectPath 文件名决定）
    python 安装到IDE项目列表.py --robot SKCON9 --saved-path C:\\Users\\me\\Desktop\\WER函数库.srhs --apply

卸载见同目录 `卸载.py`。

作者：集成工具工程师（integration）。依赖：仅 Python 标准库 + 同目录 `srhs工具.py`。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_srhs_tool():
    path = os.path.join(_HERE, 'srhs工具.py')
    if not os.path.isfile(path):
        raise RuntimeError('找不到同目录的 srhs工具.py：%s' % path)
    spec = importlib.util.spec_from_file_location('srhs_tool', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


srhs_tool = _load_srhs_tool()

# ----------------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------------
CONFIG_FILE_NAME = 'abilixProjectConfig.txt'
PROJECT_FILE_NAME = 'abilixProject.srh'
APP_DIR_NAME = 'AbilixScratch3_0'
COMPANY_DIR_NAME = 'partnerx'
PLATFORM_DIR_NAME = 'standalonewindows'
PROJECTS_DIR_NAME = 'AbilixProjects'

#: 项目列表直接显示上限（C# PCScratchProxy.MAX_SHOW_PROJ_COUNT）
MAX_SHOW_PROJ_COUNT = 7

#: 默认项目显示名（= savedProjectPath 的文件名去扩展名）
DEFAULT_PROJECT_NAME = 'WER函数库'

#: 默认机器人类型
DEFAULT_ROBOT_TYPE = 'SKCON9'

#: 项目列表配置文件模板（空配置）
_EMPTY_CONFIG = (
    '<?xml version="1.0" encoding="utf-8"?>\r\n'
    '<TempProjectsInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    ' xmlns:xsd="http://www.w3.org/2001/XMLSchema">\r\n'
    '</TempProjectsInfo>'
)

_TEMP_INFO_BLOCK_RE = re.compile(
    r'[ \t]*<TempProjectInfoList>.*?</TempProjectInfoList>[ \t]*\r?\n?', re.S)
_VALID_PATH_RE = re.compile(r'[<>"|?*\x00-\x1f]')


# ============================================================================
# 一、路径发现
# ============================================================================

def default_library_path() -> str:
    """默认函数库文件：<本脚本上级目录>/WER函数库.srhs（找不到则退回 .srh）。"""
    lib_root = os.path.dirname(_HERE)  # WER_函数库 目录
    for name in ('WER函数库.srhs', 'WER函数库.srh'):
        candidate = os.path.join(lib_root, name)
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(lib_root, 'WER函数库.srhs')


def default_saved_path(project_name: str = DEFAULT_PROJECT_NAME) -> str:
    """默认 savedProjectPath：<桌面>/<项目名>.srhs（与任务书约定一致）。"""
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    return os.path.join(desktop, project_name + '.srhs')


def candidate_product_dirs() -> List[str]:
    """列出可能的 `.../AbilixScratch3_0/standalonewindows` 目录（按可信度排序）。"""
    results: List[str] = []
    user_profile = os.environ.get('USERPROFILE') or os.path.expanduser('~')
    explicit = os.path.join(user_profile, 'AppData', 'LocalLow',
                            COMPANY_DIR_NAME, APP_DIR_NAME, PLATFORM_DIR_NAME)
    if os.path.isdir(explicit):
        results.append(explicit)
    # 兜底：扫描 LocalLow/partnerx 下所有产品目录
    low_root = os.path.join(user_profile, 'AppData', 'LocalLow', COMPANY_DIR_NAME)
    if os.path.isdir(low_root):
        try:
            for name in sorted(os.listdir(low_root)):
                p = os.path.join(low_root, name, PLATFORM_DIR_NAME)
                if os.path.isdir(p) and p not in results:
                    results.append(p)
        except OSError:
            pass
    return results


def find_product_dir() -> Optional[str]:
    """自动发现 IDE 数据根目录（.../AbilixScratch3_0/standalonewindows）。"""
    cands = candidate_product_dirs()
    return cands[0] if cands else None


def resolve_robot_dir(projects_root: Optional[str] = None,
                      robot_type: Any = DEFAULT_ROBOT_TYPE) -> Tuple[str, str]:
    """
    解析出 `<...>/AbilixProjects/<机器人数字>` 目录。

    参数 projects_root 可传：
      * `.../AbilixProjects`（推荐测试用）
      * `.../standalonewindows`
      * `.../AbilixProjects/111`（机器人目录本身）
      * 不传则自动发现真实路径。
    返回 (robot_dir, projects_root)。
    """
    code = srhs_tool.robot_code_of(robot_type)
    if projects_root:
        root = os.path.abspath(projects_root)
    else:
        product = find_product_dir()
        if not product:
            raise RuntimeError(
                '找不到 IDE 数据目录（%s）。请用 --projects-root 显式指定 AbilixProjects 目录。'
                % os.path.join('%USERPROFILE%', 'AppData', 'LocalLow',
                               COMPANY_DIR_NAME, APP_DIR_NAME, PLATFORM_DIR_NAME))
        root = os.path.join(product, PROJECTS_DIR_NAME)

    base = os.path.basename(root.rstrip('\\/'))
    if base == PROJECTS_DIR_NAME:
        return os.path.join(root, str(code)), root
    if base.isdigit():
        # 传的是机器人目录本身；同时反推 projects_root
        return root, os.path.dirname(root)
    # 传的是 standalonewindows / 其它目录
    return os.path.join(root, PROJECTS_DIR_NAME, str(code)), os.path.join(root, PROJECTS_DIR_NAME)


def config_path_of(robot_dir: str) -> str:
    return os.path.join(robot_dir, CONFIG_FILE_NAME)


def project_dir_of(robot_dir: str, folder_name: str) -> str:
    return os.path.join(robot_dir, folder_name)


# ============================================================================
# 二、项目列表配置（abilixProjectConfig.txt）读写
# ============================================================================

def _localname(tag: str) -> str:
    return tag.split('}', 1)[1] if tag.startswith('{') else tag


def read_config(config_path: str) -> Dict[str, Any]:
    """
    读取项目列表配置。返回：
        {'path','exists','bom','newline','text','entries','errors'}
    每个 entry：{'folder','is_new_project','is_saved','is_changed','saved_path','raw'}
    """
    result: Dict[str, Any] = {
        'path': config_path,
        'exists': os.path.isfile(config_path),
        'bom': False,
        'newline': '\r\n',
        'text': '',
        'entries': [],
        'errors': [],
    }
    if not result['exists']:
        result['text'] = _EMPTY_CONFIG
        return result
    with open(config_path, 'rb') as f:
        raw = f.read()
    result['bom'] = raw.startswith(b'\xef\xbb\xbf')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        result['errors'].append('配置文件不是 UTF-8：%s' % exc)
        text = raw.decode('utf-8', 'replace')
    result['newline'] = '\r\n' if '\r\n' in text else '\n'
    result['text'] = text

    # 用 ET 校验并把每个 TempProjectInfoList 解析成 dict
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        result['errors'].append('配置文件 XML 解析失败：%s' % exc)
        return result
    if _localname(root.tag) != 'TempProjectsInfo':
        result['errors'].append('配置文件根节点应为 TempProjectsInfo，实际为 %r' % root.tag)
        return result
    for node in root:
        if _localname(node.tag) != 'TempProjectInfoList':
            continue
        entry = {'folder': '', 'is_new_project': True, 'is_saved': False,
                 'is_changed': False, 'saved_path': '', 'raw': ''}
        for child in node:
            name = _localname(child.tag)
            value = (child.text or '').strip()
            if name == 'tempProjectFolderName':
                entry['folder'] = value
            elif name == 'isNewProject':
                entry['is_new_project'] = value.lower() == 'true'
            elif name == 'isSaved':
                entry['is_saved'] = value.lower() == 'true'
            elif name == 'isChanged':
                entry['is_changed'] = value.lower() == 'true'
            elif name == 'savedProjectPath':
                entry['saved_path'] = value
        result['entries'].append(entry)

    # 文本层面找每个块的原文（用于精确删除）
    spans = list(_TEMP_INFO_BLOCK_RE.finditer(text))
    if len(spans) == len(result['entries']):
        for span, entry in zip(spans, result['entries']):
            entry['raw'] = span.group(0)
            entry['span'] = (span.start(), span.end())
    return result


def make_entry_xml(entry: Dict[str, Any], newline: str = '\r\n') -> str:
    """生成一条 `<TempProjectInfoList>` 配置块文本（缩进与 XmlSerializer 输出一致）。"""
    e = srhs_tool.xml_attr_escape

    def _esc(value: str) -> str:
        return srhs_tool._xml_escape(value)

    lines = [
        '  <TempProjectInfoList>',
        '    <tempProjectFolderName>%s</tempProjectFolderName>' % _esc(entry['folder']),
        '    <isNewProject>%s</isNewProject>' % ('true' if entry.get('is_new_project') else 'false'),
        '    <isSaved>%s</isSaved>' % ('true' if entry.get('is_saved') else 'false'),
        '    <isChanged>%s</isChanged>' % ('true' if entry.get('is_changed') else 'false'),
        '    <savedProjectPath>%s</savedProjectPath>' % _esc(entry['saved_path']),
        '  </TempProjectInfoList>',
    ]
    return newline.join(lines) + newline


def config_to_bytes(text: str, bom: bool = True) -> bytes:
    data = text.encode('utf-8')
    if bom:
        data = b'\xef\xbb\xbf' + data
    return data


def append_entry_to_config(config: Dict[str, Any], entry: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    在配置文本里追加一条项目记录（不改动其它条目/换行/BOM）。
    返回 (新配置 bytes, 新配置文本)。
    """
    text: str = config['text']
    nl: str = config['newline']
    entry_xml = make_entry_xml(entry, nl)
    close_tag = '</TempProjectsInfo>'
    close_idx = text.rfind(close_tag)
    if close_idx < 0:
        raise ValueError('配置文本缺少 %r，无法追加' % close_tag)
    # 处理空配置的自闭合根节点 <TempProjectsInfo ... />
    self_closing = re.search(r'<TempProjectsInfo\b[^>]*/>', text)
    if self_closing and not config['entries']:
        head = text[:self_closing.start()]
        new_text = (head + '<TempProjectsInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
                    ' xmlns:xsd="http://www.w3.org/2001/XMLSchema">' + nl
                    + entry_xml + close_tag)
    else:
        prefix = text[:close_idx]
        if prefix and not prefix.endswith('\n'):
            prefix += nl
        new_text = prefix + entry_xml + text[close_idx:]
    check = _validate_config_text(new_text)
    if check:
        raise ValueError('追加后配置 XML 校验失败：%s' % check)
    return config_to_bytes(new_text, config['bom']), new_text


def _validate_config_text(text: str) -> str:
    """返回空字符串表示合法，否则返回错误原因。"""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return 'XML 解析失败：%s' % exc
    if _localname(root.tag) != 'TempProjectsInfo':
        return '根节点不是 TempProjectsInfo'
    return ''


def remove_entries_from_config(config: Dict[str, Any],
                               predicate: Callable[[Dict[str, Any]], bool]
                               ) -> Tuple[bytes, List[Dict[str, Any]]]:
    """
    删除满足 predicate 的项目记录（保留其它内容/换行/BOM）。
    返回 (新配置 bytes, 被删除的 entry 列表)。
    """
    text: str = config['text']
    removed: List[Dict[str, Any]] = []
    spans: List[Tuple[int, int]] = []
    for entry in config['entries']:
        if not predicate(entry):
            continue
        if 'span' not in entry:
            raise ValueError('配置文本与 XML 结构不一致，无法安全删除；请手工检查 %s'
                             % config['path'])
        spans.append(entry['span'])
        removed.append(entry)
    if not spans:
        return config_to_bytes(text, config['bom']), []
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + text[end:]
    check = _validate_config_text(text)
    if check:
        raise ValueError('删除后配置 XML 校验失败：%s' % check)
    return config_to_bytes(text, config['bom']), removed


def normalize_path_key(path: str) -> str:
    """路径比较用的规范化键（小写、正斜杠、去尾部分隔符）。"""
    p = (path or '').strip().replace('/', '\\')
    p = re.sub(r'\\+', r'\\', p)
    return p.rstrip('\\').lower()


def project_display_name(saved_path: str) -> str:
    """项目列表显示名 = 路径文件名去扩展名（C# Path.GetFileNameWithoutExtension）。"""
    base = (saved_path or '').replace('/', '\\').rstrip('\\').split('\\')[-1]
    stem = os.path.splitext(base)[0] if base.lower().endswith('.srhs') else base
    return stem or '(未命名)'


# ============================================================================
# 三、IDE 运行检测 / 备份
# ============================================================================

def is_ide_running() -> Tuple[bool, List[str]]:
    """检测 AbilixScratch3.0 是否在运行（通过 tasklist；找不到 tasklist 时返回 False）。"""
    try:
        proc = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'],
                              capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False, []
    raw = (proc.stdout or b'').lower()
    hits: List[str] = []
    for needle in (b'abilixscratch3.0', b'abilixscratch3_0'):
        if needle in raw:
            hits.append(needle.decode('ascii'))
    return bool(hits), hits


def make_backup(config_path: str) -> Optional[str]:
    """备份配置文件为 `abilixProjectConfig.backup-<时间>.txt`；文件不存在返回 None。"""
    if not os.path.isfile(config_path):
        return None
    stamp = time.strftime('%Y%m%d-%H%M%S')
    backup = os.path.join(os.path.dirname(config_path),
                          'abilixProjectConfig.backup-%s.txt' % stamp)
    n = 1
    while os.path.exists(backup):
        backup = os.path.join(os.path.dirname(config_path),
                              'abilixProjectConfig.backup-%s_%d.txt' % (stamp, n))
        n += 1
    shutil.copy2(config_path, backup)
    return backup


# ============================================================================
# 四、安装
# ============================================================================

def _unique_folder_name(robot_dir: str, config: Dict[str, Any]) -> str:
    """生成一个不与现有目录/配置冲突的 13 位毫秒时间戳目录名。"""
    used = {e.get('folder') for e in config['entries']}
    ts = srhs_tool.now_timestamp_ms()
    while ts in used or os.path.exists(project_dir_of(robot_dir, ts)):
        ts = str(int(ts) + 1)
    return ts


def install(library_path: Optional[str] = None,
            robot_type: Any = None,
            projects_root: Optional[str] = None,
            saved_path: Optional[str] = None,
            project_name: str = DEFAULT_PROJECT_NAME,
            apply: bool = False,
            force: bool = False,
            copy_saved: bool = False,
            check_ide: bool = True) -> Dict[str, Any]:
    """
    安装函数库到 IDE 项目列表。返回报告 dict（也供 `卸载.py` 复用内部函数）。

    apply=False 时只做校验与计划输出（dry-run），不写任何文件。
    """
    report: Dict[str, Any] = {
        'ok': False,
        'dry_run': not apply,
        'applied': False,
        'library': None,
        'robot': None,
        'robot_code': None,
        'robot_dir': None,
        'config_path': None,
        'backup': None,
        'folder': None,
        'saved_path': None,
        'display_name': None,
        'entries_before': [],
        'entries_after': [],
        'warnings': [],
        'errors': [],
    }
    # ---- 1) 函数库 ----
    lib = library_path or default_library_path()
    lib = os.path.abspath(lib)
    report['library'] = lib
    if not os.path.isfile(lib):
        report['errors'].append(
            '函数库文件不存在：%s\n  请先构建 WER函数库.srhs（或用 --library 指定路径）。' % lib)
        return report
    try:
        loaded = srhs_tool.load_any_project(lib)
    except (ValueError, OSError) as exc:
        report['errors'].append('函数库读取失败：%s' % exc)
        return report
    if loaded.get('errors'):
        report['errors'].extend('函数库校验失败：%s' % e for e in loaded['errors'])
        return report
    v = srhs_tool.validate_any(lib)
    if not v.get('ok'):
        report['errors'].extend('函数库校验失败：%s' % e for e in v.get('errors', []))
        return report
    srh = loaded['srh']

    # ---- 2) 机器人类型 ----
    robot_from_lib = loaded.get('comment_robot_type') or srh.robot_type
    try:
        if robot_type is None:
            robot_type = robot_from_lib
        robot = srhs_tool.normalize_robot_type(robot_type)
    except ValueError as exc:
        report['errors'].append('机器人类型无效：%s' % exc)
        return report
    report['robot'] = robot
    report['robot_code'] = srhs_tool.robot_code_of(robot)
    if lib.lower().endswith('.srhs') and loaded.get('comment_robot_type') \
            and robot != loaded.get('comment_robot_type'):
        report['warnings'].append(
            '函数库 .srhs 的 zip 注释机器人类型是 %s，本次安装按 %s 处理（项目会出现在 %s 目录）'
            % (loaded.get('comment_robot_type'), robot, report['robot_code']))

    # ---- 3) 目标目录 ----
    try:
        robot_dir, projects_root_resolved = resolve_robot_dir(projects_root, robot)
    except (RuntimeError, ValueError) as exc:
        report['errors'].append(str(exc))
        return report
    report['robot_dir'] = robot_dir
    report['projects_root'] = projects_root_resolved
    report['config_path'] = config_path_of(robot_dir)
    if not os.path.isdir(robot_dir):
        report['errors'].append(
            '机器人项目目录不存在：%s\n  （请先运行一次 IDE 并选择该机器人类型，或用 --projects-root 指定副本）'
            % robot_dir)
        return report

    # ---- 4) savedProjectPath（决定项目在列表里显示的名字） ----
    if not saved_path:
        saved_path = default_saved_path(project_name)
    saved_path = os.path.abspath(os.path.expanduser(saved_path))
    if _VALID_PATH_RE.search(saved_path):
        report['errors'].append('savedProjectPath 含非法字符：%r' % saved_path)
        return report
    if not saved_path.lower().endswith('.srhs'):
        saved_path += '.srhs'
    report['saved_path'] = saved_path
    report['display_name'] = project_display_name(saved_path)

    # ---- 5) IDE 是否在运行 ----
    if check_ide:
        running, hits = is_ide_running()
        if running:
            msg = '检测到 IDE 正在运行（%s）。请先关闭 IDE 再安装/卸载，否则退出时可能覆盖配置。' % ', '.join(hits)
            if apply and not force:
                report['errors'].append(msg + '（确认无妨可加 --force）')
                return report
            report['warnings'].append(msg)

    # ---- 6) 读取 config，幂等检查 ----
    cfg = read_config(report['config_path'])
    if cfg['errors']:
        report['errors'].extend('读取项目列表配置失败：%s' % e for e in cfg['errors'])
        return report
    report['entries_before'] = [dict(e) for e in cfg['entries']]
    before_count = len(cfg['entries'])

    saved_key = normalize_path_key(saved_path)
    for entry in cfg['entries']:
        same_path = normalize_path_key(entry.get('saved_path', '')) == saved_key
        same_name = project_display_name(entry.get('saved_path', '')) == report['display_name']
        if same_path:
            report['ok'] = True
            report['already_installed'] = True
            report['warnings'].append(
                '已安装（幂等跳过）：项目列表里已存在指向 %s 的记录（临时目录 %s）'
                % (saved_path, entry.get('folder')))
            report['entries_after'] = report['entries_before']
            return report
        if same_name:
            report['warnings'].append(
                '项目列表里已有同名项目 %r（临时目录 %s，路径 %r）；'
                '本次仍会安装，但列表里会出现两个同名项目'
                % (report['display_name'], entry.get('folder'), entry.get('saved_path')))

    if before_count >= MAX_SHOW_PROJ_COUNT:
        msg = ('项目列表已有 %d 个项目（IDE 直接显示上限 %d 个）。请先关闭/卸载一个项目，'
               '或加 --force 继续（多出的项目会进下拉列表）。' % (before_count, MAX_SHOW_PROJ_COUNT))
        if not force:
            report['errors'].append(msg)
            return report
        report['warnings'].append(msg + '（已用 --force 继续）')

    # ---- 7) 计划 ----
    folder = _unique_folder_name(robot_dir, cfg)
    report['folder'] = folder
    report['project_dir'] = project_dir_of(robot_dir, folder)
    entry = {
        'folder': folder,
        'is_new_project': False,
        'is_saved': True,
        'is_changed': False,
        'saved_path': saved_path,
    }
    report['new_entry'] = entry
    report['entries_after'] = report['entries_before'] + [entry]

    if not apply:
        report['ok'] = True
        return report

    # ---- 8) 真正写文件 ----
    try:
        # 8.1 备份 config
        backup = make_backup(report['config_path'])
        report['backup'] = backup
        # 8.2 临时项目目录 + abilixProject.srh
        pdir = report['project_dir']
        if os.path.isdir(pdir):
            raise RuntimeError('临时项目目录已存在（不应发生）：%s' % pdir)
        os.makedirs(pdir, exist_ok=True)
        srh_bytes = srh.project_xml.encode('utf-8')  # 占位，下面用规范文本覆盖
        srh_text = srh.to_text()
        with open(os.path.join(pdir, PROJECT_FILE_NAME), 'wb') as f:
            f.write(srh_text.encode('utf-8'))
        # 8.3 追加 config 记录
        new_bytes, _new_text = append_entry_to_config(cfg, entry)
        with open(report['config_path'], 'wb') as f:
            f.write(new_bytes)
        # 8.4 写后校验（重新读取）
        cfg2 = read_config(report['config_path'])
        if cfg2['errors']:
            raise RuntimeError('写入后配置文件校验失败：%s' % cfg2['errors'])
        if len(cfg2['entries']) != before_count + 1:
            raise RuntimeError('写入后项目数量异常：期望 %d，实际 %d'
                               % (before_count + 1, len(cfg2['entries'])))
        # 8.5 可选：把函数库 .srhs 复制到 savedProjectPath（这样项目“另存为/保存”有实际文件）
        if copy_saved:
            if os.path.abspath(lib).lower() != saved_path.lower():
                os.makedirs(os.path.dirname(saved_path) or '.', exist_ok=True)
                shutil.copy2(lib, saved_path)
                report['copied_saved'] = saved_path
        report['ok'] = True
        report['applied'] = True
    except (OSError, RuntimeError, ValueError) as exc:
        report['errors'].append('安装失败：%s' % exc)
    return report


# ============================================================================
# 五、报告输出 / CLI
# ============================================================================

def print_report(report: Dict[str, Any], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return
    print('=' * 72)
    print('安装到 IDE 项目列表 —— %s' % ('【DRY-RUN 只演练，不写文件】' if report['dry_run'] else '【实际安装】'))
    print('-' * 72)
    print('函数库文件      : %s' % report.get('library'))
    print('机器人类型      : %s (%s)' % (report.get('robot'), report.get('robot_code')))
    print('机器人项目目录  : %s' % report.get('robot_dir'))
    print('项目列表配置    : %s' % report.get('config_path'))
    print('临时项目目录名  : %s' % (report.get('folder') or '(未生成)'))
    print('项目显示名      : %s' % report.get('display_name'))
    print('savedProjectPath: %s' % report.get('saved_path'))
    print('项目数量        : %d -> %d'
          % (len(report.get('entries_before') or []), len(report.get('entries_after') or [])))
    if report.get('backup'):
        print('配置备份        : %s' % report['backup'])
    if report.get('copied_saved'):
        print('已复制函数库到  : %s' % report['copied_saved'])
    if report.get('already_installed'):
        print('状态            : 已安装过，无需重复安装')
    for w in report.get('warnings') or []:
        print('[警告] %s' % w)
    for e in report.get('errors') or []:
        print('[错误] %s' % e)
    if report.get('dry_run') and report.get('ok'):
        print('-' * 72)
        print('以上为演练结果。确认无误后加 --apply 真正安装：')
        print('  python 安装到IDE项目列表.py --apply %s'
              % ('--projects-root "%s"' % report['projects_root']
                 if report.get('projects_root') else ''))
    print('=' * 72)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='安装到IDE项目列表.py',
        description='把 WER函数库 作为一个项目挂进 AbilixScratch3.0 的项目列表（默认 dry-run，带备份、幂等）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python 安装到IDE项目列表.py --dry-run\n'
               '  python 安装到IDE项目列表.py --apply\n'
               '  python 安装到IDE项目列表.py --projects-root _分析临时\\integration_work\\appdata_test --apply\n')
    p.add_argument('--library', default=None,
                   help='函数库项目文件（默认：<WER_函数库>/WER函数库.srhs）')
    p.add_argument('--robot', default=None,
                   help='机器人类型 SKCON9/SKCON5/SKCON2 或 111/110/112（默认取函数库里的类型）')
    p.add_argument('--projects-root', default=None,
                   help='AbilixProjects 根目录（测试时指向副本目录；默认自动发现真实 AppData）')
    p.add_argument('--saved-path', default=None,
                   help='写进配置的 savedProjectPath（默认：<桌面>/WER函数库.srhs）')
    p.add_argument('--project-name', default=DEFAULT_PROJECT_NAME,
                   help='项目显示名（默认 WER函数库；只在未指定 --saved-path 时用于生成默认路径）')
    p.add_argument('--apply', action='store_true',
                   help='真正写入（不加则只做 dry-run 演练）')
    p.add_argument('--dry-run', action='store_true', help='显式指定只演练（默认行为）')
    p.add_argument('--force', action='store_true',
                   help='忽略 IDE 运行中 / 项目数已达上限等警告继续')
    p.add_argument('--copy-saved', action='store_true',
                   help='同时把函数库 .srhs 复制到 savedProjectPath（这样 IDE 里保存有实际文件）')
    p.add_argument('--no-ide-check', action='store_true', help='跳过 IDE 是否运行的检测')
    p.add_argument('--json', action='store_true', help='输出 JSON 报告')
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    srhs_tool.setup_console()
    args = build_arg_parser().parse_args(argv)
    apply = bool(args.apply and not args.dry_run)
    report = install(
        library_path=args.library,
        robot_type=args.robot,
        projects_root=args.projects_root,
        saved_path=args.saved_path,
        project_name=args.project_name,
        apply=apply,
        force=args.force,
        copy_saved=args.copy_saved,
        check_ide=not args.no_ide_check,
    )
    print_report(report, args.json)
    return 0 if report.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
