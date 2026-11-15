# -*- coding: utf-8 -*-
"""
删除便携版.py —— 删除「AbilixScratch3.0 函数版」便携副本与桌面快捷方式
============================================================================

安全设计
--------
* **默认 dry-run**：只报告将要删除的目录/快捷方式/占用空间，不删任何东西；
* 真正删除要加 `--yes`；
* 删除前检查 IDE 是否正在运行该副本，运行中则拒绝（先关 IDE）；
* 删除用"先改名再删"：改名成功才继续，避免半途删坏；
* 只删便携副本目录和对应快捷方式，**绝不碰**安装目录、AppData 项目列表、桌面其它文件。

用法
----
    python 删除便携版.py                      # 演练：显示会删什么
    python 删除便携版.py --yes                # 真正删除（默认目标）
    python 删除便携版.py --target "D:\\AbilixScratch3.0_FuncLib" --yes
    python 删除便携版.py --yes --keep-shortcut

退出码：0 成功；1 失败。
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
import time

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
        prog='删除便携版.py',
        description='删除 AbilixScratch3.0 便携函数版副本与桌面快捷方式（默认演练，不删）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python 删除便携版.py                  # 演练\n'
               '  python 删除便携版.py --yes            # 真正删除\n')
    p.add_argument('--target', default=None,
                   help='便携副本目录（默认 %s）' % common.default_target())
    p.add_argument('--shortcut-name', default=common.DEFAULT_SHORTCUT_NAME,
                   help='桌面快捷方式文件名（默认 %s）' % common.DEFAULT_SHORTCUT_NAME)
    p.add_argument('--desktop', default=None, help='桌面目录（默认自动探测）')
    p.add_argument('--keep-shortcut', action='store_true', help='只删目录，不删快捷方式')
    p.add_argument('--yes', action='store_true',
                   help='真正执行删除（不加时只演练、不删任何东西）')
    p.add_argument('--report', default=None, help='把 JSON 报告写到该路径（留证据用）')
    return p


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        common.load_srhs_tool().setup_console()   # 控制台中文输出
    except Exception:  # noqa: BLE001
        pass
    report = {'tool': '删除便携版.py', 'started_at': common.timestamp(),
              'dry_run': not args.yes, 'ok': False, 'errors': [], 'steps': {}}

    def fail(msg: str) -> int:
        report['errors'].append(msg)
        print('[错误] %s' % msg)
        if args.report:
            common.write_json(args.report, report)
        return 1

    target = os.path.abspath(args.target or common.default_target())
    desktop = os.path.abspath(args.desktop or common.get_desktop_dir())
    lnk = None if args.keep_shortcut else os.path.join(desktop, args.shortcut_name)

    common.print_header('AbilixScratch3.0 函数版 —— 删除便携副本%s'
                        % ('（演练模式，不会真删）' if not args.yes else ''))
    common.print_kv('便携副本', target)
    report['steps']['target'] = {'path': target, 'exists': os.path.isdir(target)}
    print()

    if not os.path.isdir(target):
        print('便携副本目录不存在，无需删除：%s' % target)
    else:
        stats = common.dir_stats(target)
        common.print_kv('目录内容', '%d 个文件 / %d 个子目录 / %s'
                        % (stats['files'], stats['dirs'], common.fmt_bytes(stats['bytes'])))
        report['steps']['target'].update(stats)
        try:
            drive = os.path.splitdrive(target)[0] + os.sep
            free_before = shutil.disk_usage(drive).free
        except OSError:
            free_before = None
        report['steps']['target']['free_before'] = free_before

        running = common.processes_under(target)
        report['steps']['target']['running'] = running
        if running:
            return fail('函数版 IDE 正在运行，请先关闭再删除：\n'
                        + '\n'.join('  pid=%s %s' % (r['pid'], r['path']) for r in running))

        if not args.yes:
            print('[演练] 将会删除上面的目录（约 %s）%s'
                  % (common.fmt_bytes(stats['bytes']),
                     '' if not lnk else '，以及快捷方式：%s' % lnk))
            print('[演练] 确认无误后加 --yes 真正删除。')
        else:
            trash = target + '.删除中-' + common.timestamp()
            try:
                os.rename(target, trash)
            except OSError as exc:
                return fail('无法重命名目录（可能仍被进程占用）：%s\n  %s' % (target, exc))
            try:
                shutil.rmtree(trash)
            except OSError as exc:
                report['warnings'] = report.get('warnings', [])
                report['warnings'].append('改名成功但删除失败：%s（可手工删 %s）' % (exc, trash))
                return fail('删除失败：%s\n  目录已改名为 %s，可手工删除。' % (exc, trash))
            print('已删除目录：%s' % target)
            report['steps']['target']['deleted'] = True
            try:
                free_after = shutil.disk_usage(drive).free
            except OSError:
                free_after = None
            report['steps']['target']['free_after'] = free_after
            if free_before is not None and free_after is not None:
                print('磁盘空间回收（约）：%s' % common.fmt_bytes(max(0, free_after - free_before)))

    if lnk:
        report['steps']['shortcut'] = {'path': lnk, 'exists': os.path.isfile(lnk)}
        if os.path.isfile(lnk):
            if args.yes:
                try:
                    os.remove(lnk)
                    print('已删除快捷方式：%s' % lnk)
                    report['steps']['shortcut']['deleted'] = True
                except OSError as exc:
                    report['warnings'] = report.get('warnings', [])
                    report['warnings'].append('快捷方式删除失败：%s（%s）' % (lnk, exc))
                    print('[警告] 快捷方式删除失败：%s（%s）' % (lnk, exc))
            else:
                print('[演练] 将会删除快捷方式：%s' % lnk)
        else:
            print('快捷方式不存在（可能本来就没建/已删）：%s' % lnk)
    else:
        print('已按要求 --keep-shortcut：保留快捷方式。')

    # 顺带提示：AppData 与安装目录完全没动
    print()
    print('[说明] 本工具只删便携副本；安装目录 %s 和 IDE 项目列表（AppData）都没有改动。'
          % common.DEFAULT_SOURCE)
    if not args.yes:
        print('[说明] 这是演练。真正删除请加 --yes。')
    report['ok'] = True
    report['finished_at'] = common.timestamp()
    if args.report:
        common.write_json(args.report, report)
    common.print_footer()
    return 0


if __name__ == '__main__':
    sys.exit(main())
