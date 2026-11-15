# -*- coding: utf-8 -*-
"""
更新便携函数版.py —— 把最新「我的函数库」重新编译进便携副本的原生积木资源
=======================================================================

原理
----
便携副本里保留着 **原始资源包** `_原始资源\\browser_assets.orig`（创建时备份的
未打补丁原版）。本工具不依赖当前已打补丁的资源，而是：

    用「我的函数库」+ 原始资源包 → 核心工具 build → 临时产物 → 校验 → 原子替换
    副本的 AbilixScratch3.0_Data\\Resources\\browser_assets

因此：改了函数库后运行一次即可，多次运行不会累积副作用；构建失败时副本原样保留，
可用同一命令无限重试。

用法示例
--------
    :: 最常用：更新默认便携副本
    python 更新便携函数版.py

    :: 指定副本/函数库/核心工具
    python 更新便携函数版.py --target "D:\\AbilixScratch3.0_FuncLib" ^
        --library "WER_函数库\\我的函数库.srhs"

    :: 只看状态不构建
    python 更新便携函数版.py --dry-run

    :: 只校验现有资源、不重新构建
    python 更新便携函数版.py --verify-only

退出码：0 成功/无需更新；1 失败；2 参数/预检查失败。
"""

from __future__ import annotations

import argparse
import importlib.util
import os
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
        prog='更新便携函数版.py',
        description='用最新「我的函数库」重新生成便携副本里的原生积木资源包。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python 更新便携函数版.py\n'
               '  python 更新便携函数版.py --dry-run\n'
               '  python 更新便携函数版.py --target "D:\\AbilixScratch3.0_FuncLib"\n'
               '  python 更新便携函数版.py --verify-only\n')
    p.add_argument('--target', default=None,
                   help='便携副本目录（默认：%s）' % common.default_target())
    p.add_argument('--library', default=None,
                   help='函数库源文件 .srh/.srhs（默认 我的函数库.srh/.srhs）')
    p.add_argument('--core', default=None,
                   help='核心工具路径（默认 %s）' % common.core_path())
    p.add_argument('--install', default=None,
                   help='软件安装目录（用于找回原始资源包，默认自动探测）')
    p.add_argument('--dry-run', action='store_true',
                   help='只检查状态、不构建（打印将执行的操作）')
    p.add_argument('--verify-only', action='store_true',
                   help='只校验证书当前副本资源，不重新构建')
    p.add_argument('--adopt-orig', action='store_true',
                   help='副本缺 _原始资源\\browser_assets.orig 时，若当前资源仍是原包则自动采纳')
    p.add_argument('--no-keep-prev', action='store_true',
                   help='不保留上一版已打补丁的资源包（默认保留为 browser_assets.上一版）')
    p.add_argument('--keep-work', action='store_true', help='保留核心工具构建临时目录（调试用）')
    p.add_argument('--report', default=None, help='把完整 JSON 报告写到该路径（留证据用）')
    p.add_argument('--verbose', action='store_true', help='打印核心工具完整输出')
    return p


def _stop_if_running(target: str) -> int:
    procs = common.processes_under(target)
    if procs:
        print('[错误] 便携副本正在运行，请先关闭 IDE 再更新：')
        for proc in procs:
            print('  PID %s  %s' % (proc.get('pid'), proc.get('name')))
        return 1
    return 0


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    common.setup_console()
    if args.core:
        common.CORE_SCRIPT = os.path.abspath(args.core)
        common._HELP_CACHE.clear()

    report = {'tool': '更新便携函数版.py', 'scheme': '原生函数积木',
              'started_at': common.timestamp(), 'ok': False,
              'errors': [], 'warnings': [], 'steps': {}}

    def fail(msg: str, code: int = 1) -> int:
        report['errors'].append(msg)
        print('[错误] %s' % msg)
        if args.report:
            common.write_json(args.report, report)
        return code

    common.print_header('AbilixScratch3.0 函数版 —— 更新原生积木资源')
    common.core_banner(print)

    # ---- 1) 目标副本检查 ----
    target = os.path.abspath(args.target or common.default_target())
    report['steps']['target'] = {'path': target}
    common.print_kv('便携副本', target)
    if not os.path.isdir(target):
        return fail('便携副本不存在：%s\n  请先运行 创建便携函数版.py' % target, code=2)
    chk = common.is_portable_copy(target)
    report['steps']['target']['check'] = chk
    if not chk['ok']:
        return fail('目标目录不是本工具的便携副本：%s\n  %s'
                    % (target, '\n  '.join(chk.get('errors') or [])), code=2)
    exe = os.path.join(target, common.APP_EXE_NAME)
    assets = common.assets_path(target)
    orig = common.orig_assets_path(target)
    print('  资源包：%s（%s）'
          % (assets, common.fmt_bytes(os.path.getsize(assets))
             if os.path.isfile(assets) else '缺失（更新时重新生成）'))
    print('  原始备份：%s（%s）'
          % (orig, common.fmt_bytes(os.path.getsize(orig)) if os.path.isfile(orig) else '缺失'))
    print()

    # ---- 2) IDE 未运行 ----
    rc = _stop_if_running(target)
    if rc:
        return fail('便携副本正在运行（见上面进程列表），请先退出 IDE', code=1)

    # ---- 3) 核心工具 ----
    missing = common.require_core('更新便携函数版.py')
    if missing:
        return fail(missing, code=2)

    # ---- 4) 函数库 ----
    try:
        lib = common.find_library(args.library)
        lib_info = common.describe_library(lib['path'])
    except (FileNotFoundError, ValueError) as exc:
        return fail(str(exc), code=2)
    report['steps']['library'] = lib_info
    report['steps']['library'].update({'origin': lib['origin'], 'kind': lib['kind']})
    common.print_kv('函数库', '%s（%s）' % (lib['path'], lib['origin']))
    common.print_kv('函数库内容', '函数 %d / 顶层块 %d / 变量 %d  sha256 %s…'
                    % (lib_info['defnoreturn'], lib_info['top_blocks'],
                       lib_info['variables'], lib_info['sha256'][:12]))
    if lib_info['defnoreturn'] == 0:
        msg = '函数库源里没有任何函数（0 个 procedures_defnoreturn），构建出来的「我的函数」会是空的。'
        report['warnings'].append(msg)
        print('[警告] ' + msg)
    print()

    # ---- 5) 确保副本有原始资源包（更新必须从 orig 重新构建）----
    if not os.path.isfile(orig):
        if args.adopt_orig:
            install = args.install
            if not install:
                install = common.locate_install_source()
            install_assets = None
            if install:
                try:
                    install_assets = common.find_assets(install)
                except FileNotFoundError:
                    install_assets = None
            adopt = common.ensure_orig_assets(target, install_assets, log=print)
            report['steps']['adopt_orig'] = adopt
            if not adopt['ok']:
                return fail('无法找回原始资源包：%s\n  （请用 创建便携函数版.py --force 重建副本）'
                            % adopt.get('error'))
        else:
            return fail('副本缺少原始资源备份：%s\n'
                        '  更新必须从原始资源包重新构建。请加 --adopt-orig 尝试自动找回'
                        '（当前资源仍为原包时可行），或运行 创建便携函数版.py --force 重建。'
                        % orig, code=2)

    # ---- 6) 状态/校验 ----
    if args.verify_only:
        print('[校验] 只校验当前副本资源（不构建）…')
        ver = common.verify_assets(assets, orig, log=print if args.verbose else None)
        report['steps']['verify'] = {'ok': ver.get('ok'), 'returncode': ver.get('returncode'),
                                     'stdout': (ver.get('stdout') or '')[-6000:],
                                     'stderr': (ver.get('stderr') or '')[-6000:]}
        if args.report:
            common.write_json(args.report, report)
        if ver.get('ok'):
            common.print_header('校验通过 ✓')
            print('  副本资源包与原始资源包的关系符合预期（见核心工具 verify 输出）。')
            report['ok'] = True
            return 0
        return fail('校验未通过：%s' % ((ver.get('stdout') or '') + (ver.get('stderr') or '')).strip()[-1500:])

    print('[1/3] 检查当前副本状态…')
    st = common.status_assets(assets, lib['path'], log=print if args.verbose else None)
    report['steps']['status'] = {'ok': st.get('ok'), 'returncode': st.get('returncode'),
                                 'stdout': (st.get('stdout') or '')[-6000:],
                                 'stderr': (st.get('stderr') or '')[-6000:]}
    if st.get('stdout'):
        for line in st['stdout'].splitlines()[:40]:
            print('  ' + line)
    if args.dry_run:
        print()
        print('[dry-run] 将执行：核心工具 build %s → 临时 → 校验 → 原子替换 %s'
              % (orig, assets))
        if args.report:
            common.write_json(args.report, report)
        report['ok'] = True
        print('[dry-run] 未做任何修改。')
        return 0

    # ---- 7) 重新构建 ----
    print()
    print('[2/3] 从原始资源重新构建原生积木资源（可能要 1~3 分钟）…')
    build = common.build_portable_assets(
        target, lib['path'], keep_prev=not args.no_keep_prev,
        log=print, timeout=3600)
    report['steps']['native_build'] = build
    if not build['ok']:
        return fail('更新失败：%s\n  副本资源未被改动，可重试。' % build.get('error'))
    print('  完成：%s → %s（sha256 %s…）'
          % (common.fmt_bytes(build.get('before_bytes', 0)),
             common.fmt_bytes(build['after_bytes']),
             (build['after_sha256'] or '')[:16]))
    if build.get('prev_backup'):
        print('  上一版已备份：%s' % build['prev_backup'])
    if build.get('verify') is not None:
        print('  核心工具 verify：%s' % ('通过' if build['verify'].get('ok') else '未通过（见报告）'))
        if not build['verify'].get('ok'):
            report['warnings'].append('核心工具 verify 未通过，请复核构建产物')

    # ---- 8) 二次校验 ----
    print('[3/3] 二次校验（资源包已更新且安装目录未受影响）…')
    final = common.verify_assets(assets, orig, log=None)
    report['steps']['final_verify'] = {'ok': final.get('ok'),
                                       'returncode': final.get('returncode')}
    if not final.get('ok'):
        report['warnings'].append('更新后校验 verify 未通过（副本已更新，请人工复核）')
    inst = common.verify_install_untouched(
        common.INSTALL_ASSETS_SHA256, common.INSTALL_ASSETS_SIZE,
        install_dir=args.install or common.locate_install_source())
    report['steps']['install_untouched'] = inst
    if not inst['ok']:
        return fail('真实安装目录校验失败（本工具不写安装目录，请立即排查）：%s'
                    % inst.get('error'))

    report['finished_at'] = common.timestamp()
    report['ok'] = True
    if args.report:
        common.write_json(args.report, report)
    print()
    common.print_header('更新完成 ✓')
    common.print_kv('便携副本', target)
    common.print_kv('原生资源包', '%s（sha256 %s…）'
                    % (common.fmt_bytes(build['after_bytes']),
                       (build['after_sha256'] or '')[:16]))
    print('-' * 76)
    print('接下来：关闭并重新打开「%s」即可看到新的「我的函数」积木。' % common.DEFAULT_SHORTCUT_NAME)
    common.print_footer()
    return 0


if __name__ == '__main__':
    sys.exit(main())
