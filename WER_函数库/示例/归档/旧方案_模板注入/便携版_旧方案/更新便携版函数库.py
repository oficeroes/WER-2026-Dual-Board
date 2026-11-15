# -*- coding: utf-8 -*-
"""
更新便携版函数库.py —— 把「我的函数库」的最新内容重新同步进已有的便携函数版副本
============================================================================

适用场景
--------
你已经用 `创建便携函数版.py` 生成过便携副本（或本工具创建过），之后：
  * 在 IDE 里新建/修改了自己的函数，保存成 `WER_函数库/我的函数库.srhs`；
  * 想把这些函数同步进便携版，让以后「新建项目」继续自带最新函数库。

本工具做的事
------------
1. 检查便携副本存在、IDE 没在运行（打补丁时不能有 IDE 正在用这个副本）；
2. 安全断开 browser_assets 的硬链接（如果历史副本是硬链接的，防止改坏安装目录）；
3. 调 `工具/底层/patch_browser_assets.py` 对副本的 browser_assets 重新打补丁
   （自动把旧 browser_assets 备份为 `browser_assets.备份-<时间戳>`）；
4. 读回 defaultcode 二次校验（与函数库重新生成的片段逐字符相等）；
5. 可选 `--prune`：只保留最新 2 个补丁备份，删掉更旧的（每个约 81MB）。

用法
----
    python 更新便携版函数库.py                     # 默认更新 %USERPROFILE%\\AbilixScratch3.0_FuncLib
    python 更新便携版函数库.py --target "D:\\AbilixScratch3.0_FuncLib"
    python 更新便携版函数库.py --library "WER_函数库\\我的函数库.srhs"
    python 更新便携版函数库.py --prune             # 更新后清理旧备份
    python 更新便携版函数库.py --dry-run           # 只检查不写

退出码：0 成功；1 失败；2 预检查失败。
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_common():
    path = os.path.join(_HERE, '便携版公共.py')
    spec = importlib.util.spec_from_file_location('portable_common', path)
    if spec is None or spec.loader is None:
        raise ImportError('找不到同目录的 便携版公共.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


common = _load_common()


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='更新便携版函数库.py',
        description='把「我的函数库」最新内容重新同步进已有的 AbilixScratch3.0 便携函数版。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python 更新便携版函数库.py\n'
               '  python 更新便携版函数库.py --prune\n'
               '  python 更新便携版函数库.py --target "D:\\AbilixScratch3.0_FuncLib" '
               '--library "WER_函数库\\我的函数库.srhs"\n')
    p.add_argument('--target', default=None,
                   help='便携副本目录（默认 %s）' % common.default_target())
    p.add_argument('--library', default=None,
                   help='函数库源文件 .srh/.srhs（默认 我的函数库.srh/.srhs；'
                        '不存在时回退 示例/WER函数库.srhs）')
    p.add_argument('--prune', action='store_true',
                   help='更新成功后只保留最新 2 个 browser_assets 备份，删除更旧的')
    p.add_argument('--keep-backups', type=int, default=2,
                   help='配合 --prune：保留多少个最新备份（默认 2）')
    p.add_argument('--dry-run', action='store_true', help='只做检查/读当前模板，不写文件')
    p.add_argument('--force', action='store_true',
                   help='即使当前模板已与函数库完全一致，也强制重新打一遍补丁')
    p.add_argument('--report', default=None, help='把完整 JSON 报告写到该路径（留证据用）')
    return p


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    common.load_srhs_tool().setup_console()
    report = {'tool': '更新便携版函数库.py', 'started_at': common.timestamp(),
              'ok': False, 'errors': [], 'warnings': [], 'steps': {}}

    def fail(msg: str) -> int:
        report['errors'].append(msg)
        print('[错误] %s' % msg)
        if args.report:
            common.write_json(args.report, report)
        return 1

    common.print_header('AbilixScratch3.0 函数版 —— 更新副本里的函数库')
    target = os.path.abspath(args.target or common.default_target())
    common.print_kv('便携副本', target)

    # ---- 1) 预检查 ----
    if not os.path.isdir(target):
        return fail('便携副本目录不存在：%s\n  先用 创建便携函数版.py 创建。' % target)
    exe = os.path.join(target, common.APP_EXE_NAME)
    if not os.path.isfile(exe):
        return fail('目录里没有 %s，不像是便携函数版副本：%s' % (common.APP_EXE_NAME, target))
    try:
        assets = common.find_assets(target)
    except FileNotFoundError as exc:
        return fail(str(exc))
    running = common.processes_under(target)
    report['steps']['precheck'] = {'target': target, 'assets': assets, 'running': running}
    if running:
        return fail('函数版 IDE 正在运行，请先关闭再更新：\n'
                    + '\n'.join('  pid=%s %s' % (r['pid'], r['path']) for r in running))
    common.print_kv('资源包', '%s（%s）' % (assets, common.fmt_bytes(os.path.getsize(assets))))

    # ---- 2) 函数库源 ----
    try:
        lib = common.find_library(args.library)
        lib_info = common.describe_library(lib['path'])
    except (FileNotFoundError, ValueError) as exc:
        return fail(str(exc))
    report['steps']['library'] = lib_info
    report['steps']['library'].update({'origin': lib['origin'], 'kind': lib['kind']})
    common.print_kv('函数库源', '%s（%s）' % (lib['path'], lib['origin']))
    common.print_kv('函数库内容', '顶层块 %d（函数 %d / start %d）  变量 %d  sha256 %s…'
                    % (lib_info['top_blocks'], lib_info['defnoreturn'],
                       lib_info['start_blocks'], lib_info['variables'],
                       lib_info['sha256'][:12]))
    if lib_info['defnoreturn'] == 0:
        report['warnings'].append('函数库源里没有任何函数（0 个），更新后新项目将只有 start 模板')
        print('[警告] 函数库源里没有任何函数（0 个），更新后新项目将只有 start 模板')

    # ---- 3) 当前补丁状态 ----
    try:
        current = common.read_defaultcodes(assets)
        cur_chars = len(current.get('zh-hans') or '')
        common.print_kv('当前模板', 'zh-hans defaultcode %d 字符' % cur_chars)
        report['steps']['current'] = {'zh_hans_chars': cur_chars,
                                      'zh_hant_chars': len(current.get('zh-hant') or ''),
                                      'en_chars': len(current.get('en') or '')}
    except Exception as exc:  # noqa: BLE001
        report['warnings'].append('读当前 defaultcode 失败（可能从未打过补丁）：%s' % exc)
        common.print_kv('当前模板', '无法读取（可能从未打过补丁）：%s' % exc)

    if args.dry_run:
        print()
        print('[dry-run] 不写任何文件。要真正更新请去掉 --dry-run。')
        report['ok'] = True
        report['finished_at'] = common.timestamp()
        if args.report:
            common.write_json(args.report, report)
        return 0

    # ---- 3.5) 先判断是否已经是最新（避免重复打补丁时"没有变化"导致报错）----
    try:
        expected_frag = common.load_patch_module().build_defaultcode_fragment(
            library_path=lib['path'])
        up_to_date = (current.get('zh-hans') == expected_frag['fragment'])
    except Exception as exc:  # noqa: BLE001
        expected_frag = None
        up_to_date = False
        report['warnings'].append('无法计算期望片段：%s' % exc)
    report['steps']['up_to_date'] = bool(up_to_date)
    if up_to_date and not args.force:
        print()
        print('当前副本的新建模板已与「%s」完全一致（%d 字符），**无需更新**。'
              % (os.path.basename(lib['path']), len(expected_frag['fragment'])))
        if lib_info['defnoreturn'] == 0:
            print('提示：函数库源里还没有函数，新建项目只会带 start 模板。')
        print('（确实要强制重打一遍可加 --force）')
        report['ok'] = True
        report['up_to_date'] = True
        report['finished_at'] = common.timestamp()
        if args.report:
            common.write_json(args.report, report)
        return 0
    if up_to_date and args.force:
        print()
        print('[--force] 当前模板已一致，仍按要求强制重打补丁。')

    # ---- 4) 打补丁（自动备份旧 browser_assets） ----
    print()
    print('[1/3] 重新打补丁（旧 browser_assets 会自动备份）…')
    try:
        patch_result = common.patch_copy_assets(target, lib['path'])
    except Exception as exc:  # noqa: BLE001
        return fail('打补丁失败：%s' % exc)
    report['steps']['patch'] = patch_result
    if not patch_result.get('ok'):
        errs = (patch_result.get('patch') or {}).get('errors') or ['未知错误']
        return fail('打补丁失败：\n  - ' + '\n  - '.join(str(e) for e in errs))
    print('      完成：%s → %s（%s）'
          % (common.fmt_bytes(patch_result.get('before_size', 0)),
             common.fmt_bytes(patch_result.get('after_size', 0)),
             (patch_result.get('after_sha256') or '')[:16]))
    print('      原文件备份：%s' % (patch_result.get('backup') or '（未记录）'))

    # ---- 5) 二次校验 ----
    print('[2/3] 读回 defaultcode 二次校验…')
    try:
        verify = common.verify_patched_defaultcode(assets, lib['path'])
    except Exception as exc:  # noqa: BLE001
        return fail('读回校验失败：%s' % exc)
    report['steps']['verify'] = verify
    if not verify['ok']:
        return fail('补丁后校验失败：\n  - ' + '\n  - '.join(verify['errors']))
    print('      通过：zh-hans defaultcode = %d 字符，与函数库重新生成的片段完全相等；'
          'zh-hant/en 未改动' % verify['expected_chars'])

    # ---- 6) 清理旧备份（可选） ----
    print('[3/3] 备份/清理…')
    backups = common.list_backups(assets)
    report['steps']['backups'] = backups
    print('      当前备份 %d 个：' % len(backups))
    for item in backups:
        print('        %s（%s）' % (os.path.basename(item['path']),
                                   common.fmt_bytes(item['bytes'])))
    if args.prune:
        removed = common.prune_backups(assets, keep=max(0, args.keep_backups))
        report['steps']['pruned'] = removed
        if removed:
            print('      已按 --prune 删除 %d 个旧备份（保留最新 %d 个）'
                  % (len(removed), args.keep_backups))
            for item in removed:
                print('        删除：%s' % item)
        else:
            print('      无需清理（备份数 ≤ %d）' % args.keep_backups)
    else:
        print('      未清理旧备份（可加 --prune 只保留最新 %d 个，每个约 81MB）'
              % args.keep_backups)

    report['ok'] = True
    report['finished_at'] = common.timestamp()
    if args.report:
        common.write_json(args.report, report)
    print()
    common.print_header('更新完成 ✓')
    common.print_kv('便携副本', target)
    common.print_kv('函数库', '%s（%d 个函数）' % (lib['path'], lib_info['defnoreturn']))
    print('现在双击函数版（或桌面快捷方式）→「文件 → 新建」，新项目就会带上最新函数库。')
    common.print_footer()
    return 0


if __name__ == '__main__':
    sys.exit(main())
