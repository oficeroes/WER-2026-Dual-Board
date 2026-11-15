# -*- coding: utf-8 -*-
"""
卸载.py —— 从 AbilixScratch3.0 项目列表里移除“WER函数库”项目并清理临时目录
==========================================================================

对应 `安装到IDE项目列表.py` 的反向操作：
  1. 在 `abilixProjectConfig.txt` 里找到匹配的项目记录（默认按项目显示名 `WER函数库`）；
  2. 备份 config（`abilixProjectConfig.backup-<时间>.txt`）；
  3. 从 config 删除这些 `<TempProjectInfoList>` 记录；
  4. 删除对应的临时项目目录 `<AbilixProjects>/<机器人数字>/<时间戳>/`。

安全设计
--------
* **默认 dry-run（只打印将删除什么，不动任何文件）**；确认后加 `--apply`。
* 删除前自动备份 config；删除目录前校验目标确实是 `<机器人目录>/<时间戳>` 形式，防止误删。
* 默认不删除 `savedProjectPath` 指向的 .srhs 文件（那是用户的项目文件）；
  只有显式 `--delete-saved` 且路径在桌面/文档目录下时才尝试删除。
* 支持 `--projects-root` 指向副本目录做测试；不指定时自动扫描 110/111/112 三个机器人目录。

用法示例
--------
    # 1) 先看会卸载什么（默认按名字 WER函数库）
    python 卸载.py --dry-run

    # 2) 真正卸载
    python 卸载.py --apply

    # 3) 指定临时目录名/机器人类型/副本目录
    python 卸载.py --folder 1789804807659 --robot SKCON9 --apply
    python 卸载.py --name WER函数库 --projects-root _分析临时\\integration_work\\appdata_test --apply

作者：集成工具工程师（integration）。依赖：仅 Python 标准库 + `安装到IDE项目列表.py`。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_install_tool():
    path = os.path.join(_HERE, '安装到IDE项目列表.py')
    if not os.path.isfile(path):
        raise RuntimeError('找不到同目录的 安装到IDE项目列表.py：%s' % path)
    spec = importlib.util.spec_from_file_location('install_ide', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


install_tool = _load_install_tool()
srhs_tool = install_tool.srhs_tool

DEFAULT_TARGET_NAME = install_tool.DEFAULT_PROJECT_NAME


# ============================================================================
# 一、发现待卸载项目
# ============================================================================

def list_target_robot_dirs(projects_root: Optional[str],
                           robot_type: Optional[Any] = None) -> List[str]:
    """
    列出要检查的机器人目录：
      * 指定 --robot 时只检查该机器人目录；
      * 否则扫描 <products_root>/AbilixProjects 下所有数字目录（110/111/112/...）。
    """
    if robot_type is not None:
        robot_dir, _root = install_tool.resolve_robot_dir(projects_root, robot_type)
        return [robot_dir]
    if projects_root:
        root = os.path.abspath(projects_root)
    else:
        product = install_tool.find_product_dir()
        if not product:
            raise RuntimeError('找不到 IDE 数据目录；请用 --projects-root 指定 AbilixProjects 目录')
        root = os.path.join(product, install_tool.PROJECTS_DIR_NAME)
    if os.path.basename(root.rstrip('\\/')).isdigit():
        return [root]
    if os.path.basename(root.rstrip('\\/')) != install_tool.PROJECTS_DIR_NAME:
        root = os.path.join(root, install_tool.PROJECTS_DIR_NAME)
    if not os.path.isdir(root):
        raise RuntimeError('目录不存在：%s' % root)
    dirs: List[str] = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if os.path.isdir(p) and name.isdigit():
            dirs.append(p)
    return dirs


def find_matches(robot_dirs: Sequence[str],
                 name: Optional[str] = DEFAULT_TARGET_NAME,
                 folder: Optional[str] = None,
                 saved_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    在每个机器人目录里找匹配的项目记录，返回：
        [{'robot_dir','config_path','config','entry'} ...]
    """
    matches: List[Dict[str, Any]] = []
    name_key = (name or '').strip().lower()
    folder_key = (folder or '').strip()
    saved_key = install_tool.normalize_path_key(saved_path) if saved_path else ''

    for robot_dir in robot_dirs:
        config_path = install_tool.config_path_of(robot_dir)
        if not os.path.isfile(config_path):
            continue
        cfg = install_tool.read_config(config_path)
        if cfg['errors']:
            matches.append({'robot_dir': robot_dir, 'config_path': config_path,
                            'config': cfg, 'entry': None,
                            'error': '配置文件读取失败：%s' % '; '.join(cfg['errors'])})
            continue
        for entry in cfg['entries']:
            hit = False
            if folder_key and entry.get('folder') == folder_key:
                hit = True
            if saved_key and install_tool.normalize_path_key(entry.get('saved_path', '')) == saved_key:
                hit = True
            if name_key:
                display = install_tool.project_display_name(entry.get('saved_path', '')).lower()
                # 精确匹配，或“WER函数库”匹配“WER函数库5”这类带后缀的显示名（dry-run 会列出供确认）
                if display == name_key or display.startswith(name_key):
                    hit = True
            if hit:
                matches.append({'robot_dir': robot_dir, 'config_path': config_path,
                                'config': cfg, 'entry': entry, 'error': None})
    return matches


# ============================================================================
# 二、卸载
# ============================================================================

def _safe_temp_dir(robot_dir: str, folder: str) -> Optional[str]:
    """校验 `<机器人目录>/<folder>` 是一个安全可删的临时项目目录，返回绝对路径或 None。"""
    folder = (folder or '').strip()
    if not folder or not folder.isdigit():
        return None
    target = os.path.abspath(os.path.join(robot_dir, folder))
    robot_abs = os.path.abspath(robot_dir).rstrip('\\/')
    if os.path.dirname(target).rstrip('\\/').lower() != robot_abs.lower():
        return None
    return target


def uninstall(name: Optional[str] = DEFAULT_TARGET_NAME,
              folder: Optional[str] = None,
              saved_path: Optional[str] = None,
              projects_root: Optional[str] = None,
              robot_type: Optional[Any] = None,
              apply: bool = False,
              delete_saved: bool = False,
              force: bool = False,
              check_ide: bool = True) -> Dict[str, Any]:
    """卸载入口。apply=False 时只列计划（dry-run）。返回报告 dict。"""
    report: Dict[str, Any] = {
        'ok': False,
        'dry_run': not apply,
        'applied': False,
        'matched': [],
        'removed_entries': [],
        'deleted_dirs': [],
        'deleted_saved': [],
        'backups': [],
        'warnings': [],
        'errors': [],
    }
    try:
        robot_dirs = list_target_robot_dirs(projects_root, robot_type)
    except (RuntimeError, ValueError) as exc:
        report['errors'].append(str(exc))
        return report
    report['robot_dirs'] = robot_dirs

    if not (name or folder or saved_path):
        report['errors'].append('请至少指定 --name / --folder / --saved-path 之一')
        return report

    if check_ide:
        running, hits = install_tool.is_ide_running()
        if running:
            msg = '检测到 IDE 正在运行（%s）。请先关闭 IDE 再卸载。' % ', '.join(hits)
            if apply and not force:
                report['errors'].append(msg + '（确认无妨可加 --force）')
                return report
            report['warnings'].append(msg)

    matches = find_matches(robot_dirs, name=name, folder=folder, saved_path=saved_path)
    for m in matches:
        item = {
            'robot_dir': m['robot_dir'],
            'config_path': m['config_path'],
            'folder': (m['entry'] or {}).get('folder'),
            'saved_path': (m['entry'] or {}).get('saved_path'),
            'display_name': install_tool.project_display_name((m['entry'] or {}).get('saved_path', '')),
            'temp_dir': _safe_temp_dir(m['robot_dir'], (m['entry'] or {}).get('folder')),
            'error': m.get('error'),
        }
        report['matched'].append(item)

    real_matches = [m for m in matches if m.get('entry') is not None]
    if not real_matches:
        report['ok'] = True
        report['warnings'].append('没有找到匹配的项目记录（可能已经卸载过了）')
        return report

    if not apply:
        report['ok'] = True
        return report

    # 按 config 分组处理
    by_config: Dict[str, List[Dict[str, Any]]] = {}
    for m in real_matches:
        by_config.setdefault(m['config_path'], []).append(m)

    for config_path, group in by_config.items():
        robot_dir = group[0]['robot_dir']
        cfg = group[0]['config']
        folders = {(m['entry'] or {}).get('folder') for m in group}
        try:
            backup = install_tool.make_backup(config_path)
            if backup:
                report['backups'].append(backup)
            new_bytes, removed = install_tool.remove_entries_from_config(
                cfg, lambda e, _folders=folders: e.get('folder') in _folders)
            if not removed:
                report['warnings'].append('配置 %s 里没有可删除的记录（可能被其它程序改动）'
                                          % config_path)
                continue
            with open(config_path, 'wb') as f:
                f.write(new_bytes)
            # 写后校验
            cfg2 = install_tool.read_config(config_path)
            if cfg2['errors']:
                raise RuntimeError('写入后配置文件校验失败：%s' % cfg2['errors'])
            for entry in removed:
                report['removed_entries'].append({
                    'config_path': config_path,
                    'folder': entry.get('folder'),
                    'saved_path': entry.get('saved_path'),
                    'display_name': install_tool.project_display_name(entry.get('saved_path', '')),
                })
                # 删除临时项目目录
                temp = _safe_temp_dir(robot_dir, entry.get('folder', ''))
                if temp and os.path.isdir(temp):
                    shutil.rmtree(temp)
                    report['deleted_dirs'].append(temp)
                elif temp:
                    report['warnings'].append('临时目录不存在，跳过：%s' % temp)
                # 可选删除 savedProjectPath
                if delete_saved:
                    sp = entry.get('saved_path') or ''
                    if sp and os.path.isfile(sp):
                        if _is_user_document_path(sp):
                            os.remove(sp)
                            report['deleted_saved'].append(sp)
                        else:
                            report['warnings'].append(
                                'savedProjectPath 不在桌面/文档目录下，为安全起见未删除：%s' % sp)
        except (OSError, RuntimeError, ValueError) as exc:
            report['errors'].append('卸载 %s 失败：%s' % (config_path, exc))
            continue

    report['applied'] = not report['errors']
    report['ok'] = not report['errors']
    return report


def _is_user_document_path(path: str) -> bool:
    """粗略判断路径在用户桌面/文档目录下（用于 --delete-saved 的安全保护）。"""
    home = os.path.expanduser('~')
    candidates = [
        os.path.join(home, 'Desktop'),
        os.path.join(home, 'Documents'),
        os.path.join(home, 'OneDrive', 'Desktop'),
        os.path.join(home, 'OneDrive', 'Documents'),
    ]
    p = os.path.abspath(path).lower()
    return any(p.startswith(os.path.abspath(c).lower() + os.sep) for c in candidates)


# ============================================================================
# 三、报告 / CLI
# ============================================================================

def print_report(report: Dict[str, Any], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return
    print('=' * 72)
    print('从 IDE 项目列表卸载 —— %s' % ('【DRY-RUN 只演练，不写文件】' if report['dry_run'] else '【实际卸载】'))
    print('-' * 72)
    print('检查的机器人目录: %s' % (report.get('robot_dirs') or []))
    matched = report.get('matched') or []
    print('匹配到项目      : %d 个' % len(matched))
    for m in matched:
        print('   - 显示名=%r  临时目录=%s  savedProjectPath=%s  [%s]'
              % (m.get('display_name'), m.get('folder'), m.get('saved_path'),
                 m.get('robot_dir')))
        if m.get('error'):
            print('     [错误] %s' % m['error'])
    if report.get('removed_entries'):
        print('已从配置移除    : %d 条' % len(report['removed_entries']))
    for b in report.get('backups') or []:
        print('配置备份        : %s' % b)
    for d in report.get('deleted_dirs') or []:
        print('已删除临时目录  : %s' % d)
    for d in report.get('deleted_saved') or []:
        print('已删除项目文件  : %s' % d)
    for w in report.get('warnings') or []:
        print('[警告] %s' % w)
    for e in report.get('errors') or []:
        print('[错误] %s' % e)
    if report.get('dry_run') and report.get('ok'):
        print('-' * 72)
        print('以上为演练结果。确认无误后加 --apply 真正卸载。')
    print('=' * 72)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='卸载.py',
        description='从 AbilixScratch3.0 项目列表移除 WER函数库 项目并清理临时目录（默认 dry-run，带备份）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python 卸载.py --dry-run\n'
               '  python 卸载.py --apply\n'
               '  python 卸载.py --folder 1789804807659 --robot SKCON9 --apply\n')
    p.add_argument('--name', default=DEFAULT_TARGET_NAME,
                   help='按项目显示名匹配（默认 WER函数库；传空字符串则不用名字匹配）')
    p.add_argument('--folder', default=None, help='按临时项目目录名（13 位时间戳）匹配')
    p.add_argument('--saved-path', default=None, help='按 savedProjectPath 精确匹配')
    p.add_argument('--robot', default=None,
                   help='只处理该机器人类型（默认扫描 110/111/112 所有目录）')
    p.add_argument('--projects-root', default=None,
                   help='AbilixProjects 根目录（测试时指向副本目录；默认自动发现真实 AppData）')
    p.add_argument('--apply', action='store_true', help='真正执行卸载（不加则只是 dry-run）')
    p.add_argument('--dry-run', action='store_true', help='显式指定只演练（默认行为）')
    p.add_argument('--delete-saved', action='store_true',
                   help='同时删除 savedProjectPath 指向的 .srhs（仅限桌面/文档目录下的文件）')
    p.add_argument('--force', action='store_true', help='忽略 IDE 正在运行等警告')
    p.add_argument('--no-ide-check', action='store_true', help='跳过 IDE 是否运行的检测')
    p.add_argument('--json', action='store_true', help='输出 JSON 报告')
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    srhs_tool.setup_console()
    args = build_arg_parser().parse_args(argv)
    name = args.name if args.name else None
    apply = bool(args.apply and not args.dry_run)
    report = uninstall(
        name=name,
        folder=args.folder,
        saved_path=args.saved_path,
        projects_root=args.projects_root,
        robot_type=args.robot,
        apply=apply,
        delete_saved=args.delete_saved,
        force=args.force,
        check_ide=not args.no_ide_check,
    )
    print_report(report, args.json)
    return 0 if report.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
