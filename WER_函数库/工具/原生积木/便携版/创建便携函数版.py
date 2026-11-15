# -*- coding: utf-8 -*-
"""
创建便携函数版.py —— 生成「原生函数积木」的 AbilixScratch3.0 免管理员便携副本
============================================================================

方案说明（与上一轮「模板注入」不同）
------------------------------------
把本机安装的 AbilixScratch3.0 **复制**到用户可写目录，然后调用核心工具
`工具/原生积木/原生积木核心.py build`，用「我的函数库」把副本里的
`AbilixScratch3.0_Data\\Resources\\browser_assets` 编译成 **原生积木版**：
之后启动的 IDE 左侧会出现紫色 **「我的函数」** 分类，里面的函数块是 IDE
原生积木（可拖进任何项目，生成的 Python 里自动带 `def func_xxx()` 定义与调用）。

免管理员原理
------------
* 安装目录 `D:\\Program Files\\...` 普通用户只读；便携副本完全在用户目录，
  **不需要管理员权限**，也不写安装目录，随时可删；
* 普通文件优先 `os.link` 硬链接（同卷 NTFS 几乎不占空间），失败自动回退复制；
* `browser_assets` **强制独立复制**（绝不能用硬链接：就地构建会经硬链接改坏安装目录）。

安全设计
--------
* 复制后校验：文件数/总大小/exe/资源包独立性；
* 副本内原始资源先备份为 `_原始资源\\browser_assets.orig`，再构建原生积木版；
  构建产物先写临时文件，**校验通过才原子替换**，失败自动回滚；
* 处理软件内置「清空数据」一次性开关（clear_app_data_switch）：为 1 时先备份
  AbilixProjects 再置 0，保证已有项目列表不被清掉；
* 目标路径**必须纯 ASCII**（实测非 ASCII 路径会让 IDE 积木区全白）。

用法示例
--------
    :: 最常用（双击 .cmd 或命令行）
    python 创建便携函数版.py

    :: 指定安装目录 / 目标目录 / 函数库
    python 创建便携函数版.py --source "D:\\Program Files\\AbilixScratch3.0" ^
        --target "D:\\AbilixScratch3.0_FuncLib" --library "WER_函数库\\我的函数库.srhs"

    :: 只复制不构建（调试用）
    python 创建便携函数版.py --no-build

退出码：0 成功；1 失败；2 参数/预检查失败。
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
        prog='创建便携函数版.py',
        description='创建一份「原生函数积木」的 AbilixScratch3.0 便携副本'
                    '（复制到用户目录 + 核心工具 build 原生积木版资源 + 桌面快捷方式）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python 创建便携函数版.py\n'
               '  python 创建便携函数版.py --source "D:\\Program Files\\AbilixScratch3.0" '
               '--target "D:\\AbilixScratch3.0_FuncLib"\n'
               '  python 创建便携函数版.py --library "WER_函数库\\我的函数库.srhs"\n'
               '  python 创建便携函数版.py --no-build --no-shortcut\n')
    p.add_argument('--source', default=None,
                   help='软件安装目录（默认自动探测，通常 %s）' % common.DEFAULT_SOURCE)
    p.add_argument('--target', default=None,
                   help='便携副本输出目录（默认：%s；必须纯 ASCII）'
                        % common.default_target())
    p.add_argument('--library', default=None,
                   help='函数库源文件 .srh/.srhs（默认 我的函数库.srh/.srhs；'
                        '不存在时回退 示例/WER函数库.srhs）')
    p.add_argument('--core', default=None,
                   help='核心工具路径（默认 %s）' % common.core_path())
    p.add_argument('--shortcut-name', default=common.DEFAULT_SHORTCUT_NAME,
                   help='桌面快捷方式文件名（默认 %s）' % common.DEFAULT_SHORTCUT_NAME)
    p.add_argument('--desktop', default=None, help='桌面目录（默认自动探测）')
    p.add_argument('--no-shortcut', action='store_true', help='不创建桌面快捷方式')
    p.add_argument('--no-build', action='store_true',
                   help='只复制，不构建原生积木版资源（调试用；副本仍是原版软件）')
    p.add_argument('--allow-non-ascii', action='store_true',
                   help='允许目标路径含中文/非 ASCII（默认拒绝：实测会导致积木区全白）')
    p.add_argument('--no-fix-registry', action='store_true',
                   help='不处理「清空数据」注册表开关（默认会备份 AppData 并置 0）')
    p.add_argument('--no-appdata-backup', action='store_true',
                   help='不备份 IDE 的 AppData 项目列表（不建议：开关为 1 时首启会清空）')
    p.add_argument('--force', action='store_true',
                   help='目标目录已存在时，删除后重建（默认报错退出）')
    p.add_argument('--keep-work', action='store_true',
                   help='保留核心工具构建临时目录（调试用）')
    p.add_argument('--allow-existing-assets', action='store_true',
                   help='允许覆盖目标目录里已存在的 browser_assets（默认报错保护）')
    p.add_argument('--report', default=None, help='把完整 JSON 报告写到该路径（留证据用）')
    p.add_argument('--verbose', action='store_true',
                   help='打印每个文件的复制方式（硬链接/独立复制/回退）')
    return p


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    common.setup_console()
    if args.core:
        common.CORE_SCRIPT = os.path.abspath(args.core)
        common._HELP_CACHE.clear()

    report = {'tool': '创建便携函数版.py', 'scheme': '原生函数积木',
              'started_at': common.timestamp(), 'ok': False,
              'errors': [], 'warnings': [], 'steps': {}}
    pending_delete = None

    def fail(msg: str, code: int = 1) -> int:
        report['errors'].append(msg)
        print('[错误] %s' % msg)
        # 失败时也要清掉 --force 改名留下的旧目录，避免 C 盘残留两份副本
        if pending_delete and os.path.isdir(pending_delete):
            try:
                shutil.rmtree(pending_delete)
                print('[清理] 已删除改名后的旧目录：%s' % pending_delete)
            except OSError as exc:
                report['warnings'].append('旧目录清理失败（可手工删）：%s（%s）'
                                          % (pending_delete, exc))
        if args.report:
            common.write_json(args.report, report)
        return code

    common.print_header('AbilixScratch3.0 函数版 —— 便携副本创建（原生函数积木方案）')
    print('本工具会：复制软件到用户目录（硬链接优先，资源包独立复制）')
    print('          → 用核心工具把「我的函数库」编译成 IDE 原生积木资源')
    print('          → 创建桌面快捷方式。不修改安装目录，不需要管理员权限。')
    print()
    common.core_banner(print)

    # ---- 1) 核心工具可用性（build 必需；--no-build 时可缺）----
    if not args.no_build:
        missing = common.require_core('创建便携函数版.py')
        if missing:
            return fail(missing, code=2)

    # ---- 2) 定位安装目录 ----
    _detected = common.locate_install_source()
    source = os.path.abspath(args.source or _detected or common.DEFAULT_SOURCE)
    common.print_kv('安装目录', source)
    src_info = common.validate_install_dir(source)
    report['steps']['source'] = {k: v for k, v in src_info.items()
                                 if k not in ('errors', 'warnings')}
    if not src_info['ok']:
        return fail('安装目录校验失败：\n  - ' + '\n  - '.join(src_info['errors']), code=2)
    common.print_kv('版本 exe', src_info['exe'])
    common.print_kv('资源包', '%s（%s）'
                    % (src_info['assets'], common.fmt_bytes(src_info['assets_size'])))
    common.print_kv('安装体积', '%s / %d 个文件'
                    % (common.fmt_bytes(src_info['bytes']), src_info['files']))
    report['install_assets_baseline'] = {
        'path': src_info['assets'], 'bytes': src_info['assets_size'],
        'sha256': src_info.get('assets_sha256')}
    print()

    # ---- 3) 定位函数库源 ----
    try:
        lib = common.find_library(args.library)
        lib_info = common.describe_library(lib['path'])
    except (FileNotFoundError, ValueError) as exc:
        return fail(str(exc), code=2)
    report['steps']['library'] = lib_info
    report['steps']['library'].update({'origin': lib['origin'], 'kind': lib['kind']})
    common.print_kv('函数库源', '%s（%s）' % (lib['path'], lib['origin']))
    common.print_kv('函数库内容', '顶层块 %d（函数 %d / start %d）  变量 %d  sha256 %s…'
                    % (lib_info['top_blocks'], lib_info['defnoreturn'],
                       lib_info['start_blocks'], lib_info['variables'],
                       lib_info['sha256'][:12]))
    if lib_info['kind'] == 'example':
        report['warnings'].append('当前用的是「示例」函数库（我的函数库.srh/.srhs 还不存在）')
        print('[提示] 当前用示例函数库；之后把自己的函数存成 '
              'WER_函数库\\我的函数库.srhs，再运行 更新便携函数版.py 即可替换。')
    if lib_info['defnoreturn'] == 0:
        msg = ('函数库源里还没有任何函数（0 个 procedures_defnoreturn），'
               '建出来的「我的函数」分类会是空的。请先在 IDE 里建好函数并保存为 '
               '我的函数库.srhs 后再创建/更新。')
        report['warnings'].append(msg)
        print('[警告] ' + msg)
    print()

    # ---- 4) 目标目录与 ASCII 检查 ----
    target = os.path.abspath(args.target or common.default_target())
    report['steps']['target'] = {'path': target}
    common.print_kv('目标目录', target)
    ascii_check = common.check_target_ascii(target)
    report['steps']['target']['non_ascii_chars'] = ascii_check['non_ascii_chars']
    if not ascii_check['ok']:
        msg = (
            '目标路径含非 ASCII 字符：%s\n'
            '  ⚠ 实测（上一轮真实 IDE 端到端验证）：便携副本路径含中文时，IDE 能启动'
            '但积木网页区全白（内嵌 CEF 浏览器初始化失败）。\n'
            '  请改用纯 ASCII 路径，例如：%s\n'
            '  确实要强制继续可加 --allow-non-ascii（不推荐，需要自行承担白屏风险）。'
            % (''.join(ascii_check['non_ascii_chars']), common.default_target()))
        if not args.allow_non_ascii:
            return fail(msg, code=2)
        report['warnings'].append(msg)
        print('[警告] ' + msg)

    pending_delete = None
    if os.path.exists(target):
        if not args.force:
            return fail('目标目录已存在：%s\n'
                        '  更新函数库请用：python 更新便携函数版.py --target "%s"\n'
                        '  删除请用：python 删除便携版.py --target "%s" --yes\n'
                        '  确实要重建请加 --force。' % (target, target, target), code=2)
        old = target + '.旧-' + common.timestamp()
        print('[提示] --force：现有目录先改名为 %s，成功后删除' % os.path.basename(old))
        if os.path.exists(old):
            shutil.rmtree(old)
        try:
            os.rename(target, old)
        except OSError as exc:
            return fail('无法改名现有目录（可能 IDE 正在运行）：%s\n  %s' % (target, exc))
        report['steps']['target']['旧目录'] = old
        pending_delete = old
    else:
        pending_delete = None

    # ---- 5) 空间检查 ----
    space = common.check_disk_space(target, src_info['assets_size'])
    report['steps']['target'].update(space)
    if space['free'] is not None:
        print('[检查] 目标盘剩余空间 %s，预计额外占用约 %s'
              % (common.fmt_bytes(space['free']), common.fmt_bytes(space['needed'])))
        if not space['ok']:
            return fail('目标盘剩余空间不足：需要约 %s，实际 %s'
                        % (common.fmt_bytes(space['needed']),
                           common.fmt_bytes(space['free'])), code=2)
    print()

    # ---- 6) AppData 安全（清空数据一次性开关）----
    print('[安全检查] 软件内置「清空数据」开关（clear_app_data_switch）…')
    backup_root = os.path.dirname(target) or target
    safety = common.ensure_appdata_safe(
        backup_root, fix_registry=not args.no_fix_registry,
        backup=not args.no_appdata_backup, log=print)
    report['steps']['appdata_safety'] = safety
    print()

    # ---- 7) 复制（硬链接优先；browser_assets 独立复制）----
    print('[1/5] 复制安装目录到便携副本（硬链接优先，资源包独立复制）…')
    try:
        copy_stats = common.copy_tree_prefer_hardlink(
            source, target, log=print if args.verbose else None)
    except (OSError, FileExistsError) as exc:
        return fail('复制失败：%s' % exc)
    report['steps']['copy'] = copy_stats
    print('      完成：%d 个文件 / %s，用时 %ss（硬链接 %d、独立复制 %d、回退复制 %d）'
          % (copy_stats['files'], common.fmt_bytes(copy_stats['bytes']),
             copy_stats['seconds'], copy_stats['linked'], copy_stats['copied'],
             copy_stats['fallback']))

    # ---- 8) 校验复制 ----
    print('[2/5] 校验复制结果（文件数/总大小/exe/资源包独立性）…')
    copy_verify = common.verify_copy(source, target)
    report['steps']['copy_verify'] = copy_verify
    if not copy_verify['ok']:
        return fail('复制校验失败：\n  - ' + '\n  - '.join(copy_verify['errors']))
    print('      通过：文件数 %d / %s 一致；exe 存在；资源包已独立（不会被硬链接改坏）'
          % (copy_verify['dst']['files'], common.fmt_bytes(copy_verify['dst']['bytes'])))

    if args.no_build:
        print()
        print('[3/5] 已按要求 --no-build 跳过原生构建（副本是原版软件）')
        report['ok'] = True
    else:
        print()
        print('[3/5] 备份副本内原始资源 → %s\\%s'
              % (common.ORIG_DIRNAME, common.ORIG_ASSETS_NAME))
        backup = common.backup_orig_assets(
            target, expected_sha256=src_info.get('assets_sha256'), log=print)
        report['steps']['orig_backup'] = backup
        if not backup['ok']:
            return fail('备份副本原始资源失败：%s' % (backup.get('error') or '未知错误'))
        print('      原始资源已备份：%s（%s / sha256 %s…）'
              % (backup['orig'], common.fmt_bytes(backup['bytes']),
                 (backup['sha256'] or '')[:16]))

        print('[4/5] 调用核心工具 build 生成原生积木版资源（可能要 1~3 分钟）…')
        build = common.build_portable_assets(
            target, lib['path'], keep_prev=False, log=print)
        report['steps']['native_build'] = build
        if not build['ok']:
            return fail('原生积木构建失败：%s\n  副本已保留在 %s（可用 更新便携函数版.py 重试）'
                        % (build.get('error'), target))
        print('      完成：%s → %s（sha256 %s…）'
              % (common.fmt_bytes(build['before_bytes']),
                 common.fmt_bytes(build['after_bytes']),
                 (build['after_sha256'] or '')[:16]))
        if build.get('verify'):
            print('      核心工具 verify：%s'
                  % ('通过' if build['verify'].get('ok') else '未通过（见报告）'))

        print('[5/5] 复核：副本资源已独立、真实安装目录未被改动…')
        inst_check = common.verify_install_untouched(
            common.INSTALL_ASSETS_SHA256, common.INSTALL_ASSETS_SIZE,
            install_dir=source)
        report['steps']['install_untouched'] = inst_check
        if not inst_check['ok']:
            return fail('真实安装目录校验失败（本工具不会写安装目录，请立即排查）：\n  %s'
                        % inst_check.get('error'))
        report['ok'] = True

    # ---- 9) 桌面快捷方式 ----
    print()
    print('[收尾] 创建桌面快捷方式…')
    shortcut = None
    if args.no_shortcut:
        print('      已按要求 --no-shortcut 跳过')
    else:
        desktop = args.desktop or common.get_desktop_dir()
        lnk = os.path.join(desktop, args.shortcut_name)
        try:
            shortcut = common.create_shortcut(
                os.path.join(target, common.APP_EXE_NAME), lnk, target)
        except Exception as exc:  # noqa: BLE001
            report['warnings'].append('快捷方式创建失败：%s' % exc)
            print('      [警告] 快捷方式创建失败：%s（可直接双击 %s 启动）'
                  % (exc, os.path.join(target, common.APP_EXE_NAME)))
        if shortcut and shortcut.get('ok'):
            print('      已创建：%s' % shortcut['lnk'])
        elif shortcut:
            print('      [警告] 快捷方式未创建成功：%s'
                  % (shortcut.get('stderr') or '未知原因'))
    report['steps']['shortcut'] = shortcut

    # ---- 10) 收尾 ----
    if pending_delete:
        try:
            shutil.rmtree(pending_delete)
            report['steps']['target']['已删除旧目录'] = pending_delete
        except OSError as exc:
            report['warnings'].append('旧目录删除失败（可手工删）：%s（%s）'
                                      % (pending_delete, exc))
    report['finished_at'] = common.timestamp()
    if args.report:
        common.write_json(args.report, report)

    print()
    common.print_header('创建完成 ✓')
    common.print_kv('便携副本', target)
    if shortcut and shortcut.get('ok'):
        common.print_kv('桌面快捷方式', shortcut['lnk'])
    common.print_kv('函数库', '%s（%d 个函数）' % (lib['path'], lib_info['defnoreturn']))
    if report['steps'].get('native_build'):
        nb = report['steps']['native_build']
        common.print_kv('原生资源包', '%s（sha256 %s…）'
                        % (common.fmt_bytes(nb.get('after_bytes', 0)),
                           (nb.get('after_sha256') or '')[:16]))
    print('-' * 76)
    print('怎么用：')
    print('  1. 双击桌面「%s」（或 %s）启动函数版；'
          % (args.shortcut_name, os.path.join(target, common.APP_EXE_NAME)))
    print('  2. 左侧点「我的函数」分类 → 把紫色函数块拖进工作区（新项目里直接可用）；')
    print('  3. 改了「我的函数库」之后，运行：python 更新便携函数版.py；')
    print('  4. 不想用了/要清空间，运行：python 删除便携版.py --yes。')
    print('注意：便携版与安装版共用同一份 AppData 项目列表，不要同时启动两个版本。')
    common.print_footer()
    return 0


if __name__ == '__main__':
    sys.exit(main())
