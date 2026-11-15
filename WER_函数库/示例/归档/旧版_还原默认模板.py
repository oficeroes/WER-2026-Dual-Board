# -*- coding: utf-8 -*-
"""
还原默认模板.py —— 从备份恢复 browser_assets（撤销新建项目默认模板补丁）
========================================================================

`patch_browser_assets.py --install` 在写回安装目录前，会把原文件备份成：
    <安装目录>\\browser_assets.备份-<yyyyMMdd-HHmmss>
本脚本用来把 install 目录里的 browser_assets 还原到某个备份。

功能
----
* `--list`：列出安装目录里所有可用备份（含大小/时间/sha256 前缀）；
* 默认（不带 --apply）：dry-run，只打印“会用哪个备份、当前文件与备份的差异”；
* `--apply`：把当前文件先备份为 `browser_assets.还原前-<时间>`，再用选定备份覆盖
  （需要管理员权限；会自动校验备份格式与写入后 sha256）。

用法
----
    # 0) 先看看有哪些备份
    python 还原默认模板.py --list

    # 1) 演练（默认行为）
    python 还原默认模板.py

    # 2) 真正还原（管理员）
    python 还原默认模板.py --apply
    # 或指定某个备份
    python 还原默认模板.py --backup "D:/Program Files/.../browser_assets.备份-20261110-140000" --apply

    # 3) 从任意一个“原始/补丁版”资源包文件恢复
    python 还原默认模板.py --backup 某个browser_assets文件 --apply

作者：集成工具工程师（integration）。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_patch_module():
    path = os.path.join(_HERE, 'patch_browser_assets.py')
    if not os.path.isfile(path):
        raise RuntimeError('找不到同目录的 patch_browser_assets.py：%s' % path)
    spec = importlib.util.spec_from_file_location('patch_browser_assets', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


patch = _load_patch_module()
srhs_tool = patch.srhs_tool

RESTORE_PREFIX = 'browser_assets.还原前-'
#: 可能的安装目录（按顺序找）
CANDIDATE_ASSETS = [
    r'D:\Program Files\AbilixScratch3.0\AbilixScratch3_0_Data\Resources\browser_assets',
    r'C:\Program Files\AbilixScratch3.0\AbilixScratch3_0_Data\Resources\browser_assets',
    r'C:\Program Files (x86)\AbilixScratch3.0\AbilixScratch3_0_Data\Resources\browser_assets',
]


def find_assets_path(explicit: Optional[str] = None) -> str:
    """定位 browser_assets 文件；explicit 可以是文件或目录。"""
    if explicit:
        p = os.path.abspath(explicit)
        if os.path.isdir(p):
            p = os.path.join(p, 'browser_assets')
        return p
    for cand in CANDIDATE_ASSETS:
        if os.path.isfile(cand):
            return cand
    if os.path.isfile(patch.DEFAULT_ASSETS):
        return patch.DEFAULT_ASSETS
    raise RuntimeError('找不到 browser_assets 安装文件，请用 --assets 指定（可传文件或所在目录）')


def list_backups(assets_path: str) -> List[Dict[str, Any]]:
    """列出同目录下所有 `browser_assets.备份-*` 文件（按修改时间从新到旧）。"""
    assets_dir = os.path.dirname(os.path.abspath(assets_path))
    items: List[Dict[str, Any]] = []
    if not os.path.isdir(assets_dir):
        return items
    for name in os.listdir(assets_dir):
        if not name.startswith(patch.BACKUP_PREFIX):
            continue
        p = os.path.join(assets_dir, name)
        if not os.path.isfile(p):
            continue
        item = {'path': p, 'name': name, 'size': os.path.getsize(p),
                'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.localtime(os.path.getmtime(p))),
                'sha256': srhs_tool.sha256_file(p), 'valid': False, 'count': None}
        try:
            info = patch.read_zfb_index(p)
            item['valid'] = True
            item['count'] = info['count']
        except (ValueError, OSError) as exc:
            item['invalid_reason'] = str(exc)
        items.append(item)
    items.sort(key=lambda x: os.path.getmtime(x['path']), reverse=True)
    return items


def restore(assets_path: str, backup_path: Optional[str] = None,
            apply: bool = False) -> Dict[str, Any]:
    """还原入口。apply=False 时只打印计划。返回报告 dict。"""
    report: Dict[str, Any] = {
        'ok': False,
        'dry_run': not apply,
        'assets': os.path.abspath(assets_path),
        'backup': None,
        'backups_found': [],
        'pre_restore_backup': None,
        'errors': [],
        'warnings': [],
    }
    if not os.path.isfile(assets_path):
        report['errors'].append('安装目录里的 browser_assets 不存在：%s' % assets_path)
        return report
    backups = list_backups(assets_path)
    report['backups_found'] = [{'path': b['path'], 'valid': b['valid'], 'count': b['count'],
                                'sha256': b['sha256'][:16], 'mtime': b['mtime']}
                               for b in backups]

    if backup_path:
        chosen = os.path.abspath(backup_path)
        if not os.path.isfile(chosen):
            report['errors'].append('指定的备份文件不存在：%s' % chosen)
            return report
    else:
        valid = [b for b in backups if b['valid']]
        if not valid:
            report['errors'].append(
                '没有找到可用的备份（%s%s*）。\n'
                '  请确认之前用 patch_browser_assets.py --install 打过补丁；'
                '或用 --backup 指定一个原始 browser_assets 文件。'
                % (os.path.dirname(assets_path), os.sep + patch.BACKUP_PREFIX))
            return report
        chosen = valid[0]['path']

    report['backup'] = chosen
    # 校验备份格式
    try:
        b_info = patch.read_zfb_index(chosen)
        b_validate = patch.validate_zfb(chosen)
    except (ValueError, OSError) as exc:
        report['errors'].append('备份文件不是合法的 zfbRes_v1 资源包：%s' % exc)
        return report
    report['backup_count'] = b_info['count']
    if not b_validate.get('ok'):
        report['errors'].extend('备份文件校验失败：%s' % e for e in b_validate.get('errors', []))
        return report
    cur_sha = srhs_tool.sha256_file(assets_path)
    bak_sha = srhs_tool.sha256_file(chosen)
    report['current_sha256'] = cur_sha
    report['backup_sha256'] = bak_sha
    report['already_restored'] = (cur_sha == bak_sha)
    if cur_sha == bak_sha:
        report['warnings'].append('当前 browser_assets 已经与备份完全一致（无需还原）')
        report['ok'] = True
        return report
    if not apply:
        report['ok'] = True
        return report

    # ---- 真正还原 ----
    target_dir = os.path.dirname(assets_path)
    if not patch._can_write_dir(target_dir):
        report['errors'].append(
            '没有写入权限：%s\n'
            '  请以“管理员身份运行”本脚本（推荐用同目录的 还原默认模板(管理员).cmd），'
            '当前是否管理员：%s' % (target_dir, patch._is_admin()))
        return report
    try:
        # 先备份当前文件（万一还原错了还能回来）
        pre = os.path.join(target_dir, RESTORE_PREFIX + patch._timestamp())
        n = 1
        while os.path.exists(pre):
            pre = os.path.join(target_dir, RESTORE_PREFIX + patch._timestamp() + '_%d' % n)
            n += 1
        shutil.copy2(assets_path, pre)
        if srhs_tool.sha256_file(pre) != cur_sha:
            report['errors'].append('还原前的当前文件备份校验失败，已中止（未改动 browser_assets）')
            return report
        report['pre_restore_backup'] = pre
        # 覆盖
        shutil.copy2(chosen, assets_path)
        final_sha = srhs_tool.sha256_file(assets_path)
        if final_sha != bak_sha:
            report['errors'].append('还原后 sha256 与备份不一致！请手工从 %s 复制恢复' % chosen)
            return report
        # 最终格式校验
        final_validate = patch.validate_zfb(assets_path)
        if not final_validate.get('ok'):
            report['errors'].append('还原后的 browser_assets 校验失败：%s'
                                    % final_validate.get('errors'))
            return report
        report['ok'] = True
        report['restored'] = True
        report['final_sha256'] = final_sha
        return report
    except (OSError, RuntimeError, ValueError) as exc:
        report['errors'].append('还原失败：%s' % exc)
        return report


def print_report(report: Dict[str, Any], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return
    print('=' * 72)
    print('还原 browser_assets —— %s' % ('【DRY-RUN 只演练】' if report.get('dry_run') else '【实际还原】'))
    print('-' * 72)
    print('安装文件    : %s' % report.get('assets'))
    if report.get('current_sha256'):
        print('当前 sha256 : %s' % report['current_sha256'])
    found = report.get('backups_found') or []
    if found:
        print('可用备份    : %d 个' % len(found))
        for b in found[:10]:
            print('   - %s  %s 条 %s %s'
                  % (b['path'], b['count'], '合法' if b['valid'] else '非法', b['mtime']))
    print('选用备份    : %s' % report.get('backup'))
    if report.get('backup_sha256'):
        print('备份 sha256 : %s' % report['backup_sha256'])
    if report.get('pre_restore_backup'):
        print('还原前备份  : %s' % report['pre_restore_backup'])
    if report.get('restored'):
        print('状态        : ✓ 已还原（重启 IDE 后生效）')
    if report.get('already_restored'):
        print('状态        : 当前文件已与备份一致，无需还原')
    for w in report.get('warnings') or []:
        print('[警告] %s' % w)
    for e in report.get('errors') or []:
        print('[错误] %s' % e)
    if report.get('dry_run') and report.get('ok') and not report.get('already_restored'):
        print('-' * 72)
        print('以上为演练结果。确认后加 --apply 真正还原（需管理员权限）。')
    print('=' * 72)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='还原默认模板.py',
        description='从 browser_assets.备份-<时间> 恢复 AbilixScratch3.0 的浏览器资源包（撤销默认模板补丁）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python 还原默认模板.py --list\n'
               '  python 还原默认模板.py            # 演练\n'
               '  python 还原默认模板.py --apply    # 真正还原（管理员）\n')
    p.add_argument('--assets', default=None,
                   help='browser_assets 路径（文件或所在目录；默认自动找安装目录）')
    p.add_argument('--backup', default=None,
                   help='指定要恢复的备份文件（默认用最新一个 备份-*）')
    p.add_argument('--list', action='store_true', help='只列出可用备份')
    p.add_argument('--apply', action='store_true', help='真正执行还原（不加则只是 dry-run）')
    p.add_argument('--dry-run', action='store_true', help='显式指定只演练（默认行为）')
    p.add_argument('--json', action='store_true', help='输出 JSON')
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    srhs_tool.setup_console()
    args = build_arg_parser().parse_args(argv)
    try:
        assets = find_assets_path(args.assets)
    except RuntimeError as exc:
        sys.stderr.write('[错误] %s\n' % exc)
        return 2
    if args.list:
        backups = list_backups(assets)
        print('安装文件：%s' % assets)
        if not backups:
            print('没有找到备份（%s*）' % patch.BACKUP_PREFIX)
            return 1
        print('共 %d 个备份：' % len(backups))
        for b in backups:
            print('  %s  %s 条 %s sha256=%s  %s'
                  % (b['path'], b['count'], '合法' if b['valid'] else '非法',
                     b['sha256'][:16], b['mtime']))
        return 0
    report = restore(assets, backup_path=args.backup, apply=bool(args.apply and not args.dry_run))
    print_report(report, args.json)
    return 0 if report.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
