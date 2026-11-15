# -*- coding: utf-8 -*-
"""
删除便携版.py —— 安全删除「原生函数积木」便携副本与桌面快捷方式
================================================================

作用
----
删除 创建便携函数版.py 生成的便携副本（整个目录，含 `_原始资源` 备份）和
桌面快捷方式 `AbilixScratch3.0 函数版.lnk`。**不会**动：
* 真实安装目录（D:\\Program Files\\AbilixScratch3.0）；
* IDE 的 AppData 项目列表（C:\\Users\\<用户>\\AppData\\LocalLow\\partnerx\\...）；
* 函数库源文件（我的函数库.srhs）和工具本身。

安全设计
--------
* 默认 **dry-run**：只列出将被删除的内容，不真删，要加 --yes 才执行；
* 删除前校验：目录里必须有 AbilixScratch3.0.exe（确认是副本）、不能是安装目录、
  不能在 Program Files 下、不能是盘符根/用户目录/桌面/工作目录本身；
* 便携副本正在运行时拒绝删除（先关 IDE）；
* 先改名成 `<目标>.删除中-<时间戳>` 再递归删除，避免删一半留下“看着像副本”的残骸；
* 目录名不像便携副本时拒绝（可加 --force）。

用法示例
--------
    python 删除便携版.py                       :: 只看会被删什么
    python 删除便携版.py --yes                 :: 真删
    python 删除便携版.py --target "D:\\AbilixScratch3.0_FuncLib" --yes
    python 删除便携版.py --keep-shortcut       :: 保留桌面快捷方式

退出码：0 成功/无需删除；1 失败；2 参数/预检查失败。
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_common():
    path = os.path.join(_HERE, '原生便携版公共.py')
    spec = importlib.util.spec_from_file_location('native_portable_common', path)
    if spec is None or spec.loader is None:
        raise ImportError('找不到同目录的 原生便携版公共.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


common = _load_common()


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='删除便携版.py',
        description='安全删除「AbilixScratch3.0 函数版」便携副本与桌面快捷方式。'
                    '默认只预览（dry-run），加 --yes 才真删。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python 删除便携版.py\n'
               '  python 删除便携版.py --yes\n'
               '  python 删除便携版.py --target "D:\\AbilixScratch3.0_FuncLib" --yes\n')
    p.add_argument('--target', default=None,
                   help='便携副本目录（默认：%s）' % common.default_target())
    p.add_argument('--shortcut-name', default=common.DEFAULT_SHORTCUT_NAME,
                   help='桌面快捷方式文件名（默认 %s）' % common.DEFAULT_SHORTCUT_NAME)
    p.add_argument('--desktop', default=None, help='桌面目录（默认自动探测）')
    p.add_argument('--yes', action='store_true', help='真的执行删除（默认只预览）')
    p.add_argument('--keep-shortcut', action='store_true', help='保留桌面快捷方式不删')
    p.add_argument('--force', action='store_true',
                   help='目录名不像便携副本/不是本工具创建时也允许删除')
    p.add_argument('--report', default=None, help='把完整 JSON 报告写到该路径（留证据用）')
    return p


def _shortcut_path(args) -> str:
    desktop = args.desktop or common.get_desktop_dir()
    return os.path.join(desktop, args.shortcut_name)


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    common.setup_console()

    target = os.path.abspath(args.target or common.default_target())
    lnk = _shortcut_path(args)
    report = {'tool': '删除便携版.py', 'scheme': '原生函数积木',
              'started_at': common.timestamp(), 'ok': False, 'dry_run': not args.yes,
              'target': target, 'shortcut': lnk,
              'errors': [], 'warnings': [], 'steps': {}}

    def fail(msg: str, code: int = 1) -> int:
        report['errors'].append(msg)
        print('[错误] %s' % msg)
        if args.report:
            common.write_json(args.report, report)
        return code

    common.print_header('AbilixScratch3.0 函数版 —— 删除便携副本')
    common.print_kv('便携副本', target)
    common.print_kv('桌面快捷方式', lnk)
    print()

    # ---- 1) 目标存在性 ----
    if not os.path.isdir(target):
        print('[提示] 便携副本不存在，无需删除：%s' % target)
        if not args.keep_shortcut and os.path.exists(lnk):
            print('[提示] 桌面快捷方式仍存在：%s' % lnk)
        report['ok'] = True
        report['note'] = '目标不存在'
        if args.report:
            common.write_json(args.report, report)
        return 0

    # ---- 2) 运行中检查 ----
    procs = common.processes_under(target)
    report['steps']['processes'] = procs
    if procs:
        print('[错误] 便携副本正在运行，请先关闭 IDE 再删除：')
        for proc in procs:
            print('  PID %s  %s' % (proc.get('pid'), proc.get('name')))
        return fail('便携副本正在运行（见上面进程列表）', code=1)

    # ---- 3) 路径安全校验（必须在真正删除之前）----
    install_dirs = []
    try:
        detected = common.locate_install_source()
        if detected:
            install_dirs.append(detected)
    except Exception:  # noqa: BLE001
        pass
    install_dirs.append(common.DEFAULT_SOURCE)
    safety = common.safe_delete_target_check(target, install_dirs,
                                             allow_any=args.force)
    report['steps']['safety'] = safety
    if not safety['ok']:
        return fail('路径安全校验未通过，拒绝删除：\n  - ' + '\n  - '.join(safety['errors']),
                    code=2)
    for warn in safety.get('warnings') or []:
        report['warnings'].append(warn)
        print('[警告] ' + warn)

    port = common.is_portable_copy(target)
    report['steps']['portable_copy'] = port
    if not port['ok'] and not args.force:
        return fail('目标目录不像本工具的便携副本，拒绝删除：\n  - '
                    + '\n  - '.join(port.get('errors') or [])
                    + '\n  确认要删可加 --force。', code=2)

    # ---- 4) 统计将被删除的内容 ----
    stats = common.dir_stats(target)
    orig = common.orig_assets_path(target)
    has_orig = os.path.isfile(orig)
    report['steps']['stats'] = stats
    report['steps']['has_orig'] = has_orig
    print('将删除：')
    print('  %s' % target)
    print('    %d 个文件 / %s%s'
          % (stats['files'], common.fmt_bytes(stats['bytes']),
             '（含 _原始资源 原始资源包备份）' if has_orig else ''))
    if not args.keep_shortcut and os.path.exists(lnk):
        print('  %s' % lnk)
    else:
        print('  （保留桌面快捷方式）')
    print('不会动：真实安装目录、AppData 项目列表、函数库源文件、工具本身。')
    print()

    if not args.yes:
        if args.report:
            common.write_json(args.report, report)
        print('[dry-run] 未删除任何内容。确认删除请重新运行并加 --yes：')
        print('  python 删除便携版.py --target "%s" --yes' % target)
        print()
        print('（建议先双击桌面快捷方式确认不再需要；' \
              '删除后要恢复只需重新运行 创建便携函数版.py。）')
        report['ok'] = True
        return 0

    # ---- 5) 先改名再删（避免删一半留下副本残骸）----
    trash = target + '.删除中-' + common.timestamp()
    print('[1/3] 改名到临时名…')
    try:
        if os.path.exists(trash):
            shutil.rmtree(trash)
        os.rename(target, trash)
        report['steps']['renamed_to'] = trash
        print('      %s → %s' % (target, os.path.basename(trash)))
    except OSError as exc:
        return fail('无法改名（文件被占用？请确认 IDE 已退出）：%s' % exc, code=1)

    print('[2/3] 递归删除副本…')
    try:
        shutil.rmtree(trash)
        report['steps']['removed'] = True
        print('      已删除：%s（%s / %d 个文件）'
              % (trash, common.fmt_bytes(stats['bytes']), stats['files']))
    except OSError as exc:
        report['warnings'].append('部分文件删除失败：%s' % exc)
        return fail('删除未完成，残留目录：%s\n  %s\n  可稍后手工删除。' % (trash, exc), code=1)

    print('[3/3] 删除桌面快捷方式…')
    shortcut_removed = False
    shortcut_note = ''
    if args.keep_shortcut:
        shortcut_note = '已按要求保留'
        print('      已按要求保留：%s' % lnk)
    elif os.path.exists(lnk):
        try:
            os.remove(lnk)
            shortcut_removed = True
            print('      已删除：%s' % lnk)
        except OSError as exc:
            shortcut_note = '删除失败：%s' % exc
            report['warnings'].append(shortcut_note)
            print('      [警告] 快捷方式删除失败：%s（可手工删除）' % exc)
    else:
        shortcut_note = '不存在'
        print('      快捷方式不存在，无需删除：%s' % lnk)
    report['steps']['shortcut_removed'] = shortcut_removed
    report['steps']['shortcut_note'] = shortcut_note

    # ---- 6) 只读校验：安装目录与函数库安然无恙 ----
    print()
    inst = common.verify_install_untouched(
        common.INSTALL_ASSETS_SHA256, common.INSTALL_ASSETS_SIZE,
        install_dir=common.locate_install_source() or common.DEFAULT_SOURCE)
    report['steps']['install_untouched'] = inst
    libs = os.path.join(common.LIB_ROOT, '我的函数库.srhs')
    report['steps']['library_intact'] = os.path.isfile(libs)
    if not inst['ok']:
        report['warnings'].append('真实安装目录校验异常：%s' % inst.get('error'))
        print('[警告] ' + str(inst.get('error')))
    print('函数库源文件仍在：%s（%s）'
          % (libs, '是' if os.path.isfile(libs) else '否'))

    report['finished_at'] = common.timestamp()
    report['ok'] = True
    if args.report:
        common.write_json(args.report, report)
    print()
    common.print_header('删除完成 ✓')
    print('便携副本已删除。真实安装目录、AppData 项目列表、函数库源文件均未受影响。')
    print('需要再用时，重新运行：python 创建便携函数版.py')
    common.print_footer()
    return 0


if __name__ == '__main__':
    sys.exit(main())
