# -*- coding: utf-8 -*-
"""
创建便携函数版.py —— 生成一份「新建项目自带函数库」的 AbilixScratch3.0 便携副本
============================================================================

用途（对应第二轮的真正需求：只改软件内置设定、可复现到其他电脑）
------------------------------------------------------------------
把本机安装的 AbilixScratch3.0 **复制** 到用户可写目录，并对副本里的
`AbilixScratch3.0_Data\\Resources\\browser_assets` 打上「默认模板补丁」：
之后双击副本 exe（或桌面快捷方式）启动的 IDE，**每次"新建项目"工作区都自带
函数库里的全部函数定义 + 变量声明**，左侧「函数」分类里能直接看到这些调用块。

为什么用便携副本
----------------
* 安装目录 `D:\\Program Files\\...` 普通用户只读（写补丁需要管理员）；
* 便携副本完全在用户目录，**不需要管理员权限**，也不碰安装目录，随时可删；
* 复制用**硬链接**（同一 NTFS 卷）：407MB 的软件只额外占实际改写的约 85MB。

安全设计（重要）
----------------
* 普通文件用 os.link 硬链接（不占空间、秒完成），失败自动回退 shutil.copy2；
* `browser_assets` 这类会被改写的文件**强制独立复制**——否则就地写补丁会通过
  硬链接把**安装目录**的文件一起改坏（本工具带校验，绝不允许）；
* 打补丁用 `工具/底层/patch_browser_assets.py`，其自带 7 步自检
  （纯 roundtrip 逐字节一致、只改 1/6645 条目、逐条目 sha256 比对）；
* 原 `browser_assets` 在副本里自动备份为 `browser_assets.备份-<时间戳>`，可还原。

用法示例
--------
    :: 最常用：自动找安装目录，用「我的函数库.srhs」做函数库源
    双击 创建便携函数版.cmd
    或  python 创建便携函数版.py

    :: 指定安装目录 / 目标目录 / 函数库源（其他电脑上照抄这一步即可）
    python 创建便携函数版.py --source "D:\\Program Files\\AbilixScratch3.0" ^
        --target "D:\\AbilixScratch3.0_函数版" ^
        --library "WER_函数库\\我的函数库.srhs"

    :: 只复制不打补丁（调试用）
    python 创建便携函数版.py --no-patch

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
    path = os.path.join(_HERE, '便携版公共.py')
    spec = importlib.util.spec_from_file_location('portable_common', path)
    if spec is None or spec.loader is None:
        raise ImportError('找不到同目录的 便携版公共.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


common = _load_common()


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='创建便携函数版.py',
        description='创建一份「新建项目自带函数库」的 AbilixScratch3.0 便携副本'
                    '（硬链接复制 + 默认模板补丁 + 桌面快捷方式）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python 创建便携函数版.py\n'
               '  python 创建便携函数版.py --source "D:\\Program Files\\AbilixScratch3.0" '
               '--target "D:\\AbilixScratch3.0_函数版"\n'
               '  python 创建便携函数版.py --library WER_函数库\\示例\\WER函数库.srhs\n'
               '  python 创建便携函数版.py --no-patch --no-shortcut\n')
    p.add_argument('--source', default=None,
                   help='软件安装目录（默认 %s）' % common.DEFAULT_SOURCE)
    p.add_argument('--target', default=None,
                   help='便携副本输出目录（默认：用户目录\\%s；必须纯 ASCII）'
                        % common.DEFAULT_TARGET_DIRNAME)
    p.add_argument('--library', default=None,
                   help='函数库源文件 .srh/.srhs（默认 我的函数库.srh/.srhs；'
                        '不存在时回退 示例/WER函数库.srhs）')
    p.add_argument('--assets', default=None,
                   help='直接指定要打补丁的 browser_assets（默认按 --source/--target 自动找）')
    p.add_argument('--shortcut-name', default=common.DEFAULT_SHORTCUT_NAME,
                   help='桌面快捷方式文件名（默认 %s）' % common.DEFAULT_SHORTCUT_NAME)
    p.add_argument('--desktop', default=None,
                   help='桌面目录（默认自动探测；用于指定/测试）')
    p.add_argument('--no-shortcut', action='store_true', help='不创建桌面快捷方式')
    p.add_argument('--no-patch', action='store_true', help='只复制，不打补丁（调试用）')
    p.add_argument('--allow-non-ascii', action='store_true',
                   help='允许目标路径含中文/非 ASCII 字符（默认拒绝：实测非 ASCII 路径会导致'
                        '积木网页区全白，因为软件内嵌 CEF 无法加载中文路径资源）')
    p.add_argument('--no-fix-registry', action='store_true',
                   help='不处理软件注册表里的「清空数据」一次性开关（默认会备份 AppData 并置 0）')
    p.add_argument('--no-appdata-backup', action='store_true',
                   help='不备份 IDE 的 AppData 项目列表（不建议；该开关为 1 时首启会清空项目列表）')
    p.add_argument('--force', action='store_true',
                   help='目标目录已存在时，删除后重建（默认报错退出）')
    p.add_argument('--keep-work', action='store_true',
                   help='保留补丁过程临时目录（含解包文件，约 500MB，调试用）')
    p.add_argument('--report', default=None,
                   help='把完整 JSON 报告写到该路径（留证据用）')
    p.add_argument('--verbose', action='store_true',
                   help='打印每个文件的复制方式（硬链接/独立复制/回退）')
    return p


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    common.load_srhs_tool().setup_console()

    report = {
        'tool': '创建便携函数版.py',
        'started_at': common.timestamp(),
        'ok': False,
        'errors': [],
        'warnings': [],
        'steps': {},
    }

    def fail(msg: str) -> int:
        report['errors'].append(msg)
        print('[错误] %s' % msg)
        if args.report:
            common.write_json(args.report, report)
        return 1

    common.print_header('AbilixScratch3.0 函数版 —— 便携副本创建')
    print('本工具会：复制软件到用户目录（硬链接省空间）→ 给副本打「新建项目自带函数库」补丁')
    print('          → 创建桌面快捷方式。不修改安装目录，不需要管理员权限。')
    print()

    # ---- 1) 定位安装目录 ----
    _detected = common.locate_install_source()
    source = os.path.abspath(args.source or _detected or common.DEFAULT_SOURCE)
    common.print_kv('安装目录', source)
    src_info = common.validate_install_dir(source)
    report['steps']['source'] = {k: v for k, v in src_info.items()
                                 if k not in ('errors', 'warnings')}
    if not src_info['ok']:
        return fail('安装目录校验失败：\n  - ' + '\n  - '.join(src_info['errors']))
    common.print_kv('版本 exe', src_info['exe'])
    common.print_kv('资源包', '%s（%s）'
                    % (src_info['assets'], common.fmt_bytes(src_info['assets_size'])))
    common.print_kv('安装体积', '%s / %d 个文件'
                    % (common.fmt_bytes(src_info['bytes']), src_info['files']))
    print()

    # ---- 2) 定位函数库源 ----
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
    if lib_info['kind'] == 'example':
        report['warnings'].append('当前用的是「示例」函数库（我的函数库.srh/.srhs 还不存在）')
        print('[提示] 当前用的是示例函数库。以后把自己的函数保存为 '
              'WER_函数库\\我的函数库.srhs，再运行 更新便携版函数库.py 即可替换。')
    if lib_info['defnoreturn'] == 0:
        msg = ('函数库源里还没有任何函数（0 个 procedures_defnoreturn）。'
               '新项目只会带 start 主函数模板；请先在 IDE 里建好函数并保存成 '
               '我的函数库.srhs 后再运行 更新便携版函数库.py。')
        report['warnings'].append(msg)
        print('[警告] ' + msg)
    if not lib_info['start_blocks']:
        report['warnings'].append('函数库源里没有 start 块（补丁器会失败）')
    print()

    # ---- 3) 目标目录检查 ----
    target = os.path.abspath(args.target or common.default_target())
    report['steps']['target'] = {'path': target}
    common.print_kv('目标目录', target)

    # ---- 3.1) ASCII 路径检查（实测：非 ASCII 路径会让积木网页区全白）----
    bad_chars = common.non_ascii_chars(target)
    report['steps']['target']['non_ascii_chars'] = bad_chars
    if bad_chars:
        msg = (
            '目标路径含非 ASCII 字符：%s\n'
            '  ⚠ 实测（2026-11-10 真实 IDE 端到端验证）：便携副本路径含中文时，IDE 能启动'
            '但积木网页区全白（内嵌 CEF 浏览器初始化失败）。\n'
            '  请改用纯 ASCII 路径，例如：%s\n'
            '  确实要强制继续可加 --allow-non-ascii（不推荐，需要自行承担白屏风险）。'
            % (''.join(bad_chars), os.path.join(os.path.expanduser('~'),
                                                common.DEFAULT_TARGET_DIRNAME)))
        if not args.allow_non_ascii:
            return fail(msg)
        report['warnings'].append(msg)
        print('[警告] ' + msg)

    if os.path.exists(target):
        if not args.force:
            return fail('目标目录已存在：%s\n'
                        '  更新函数库请用：python 更新便携版函数库.py --target "%s"\n'
                        '  删除请用：python 删除便携版.py --target "%s" --yes\n'
                        '  确实要重建请加 --force。' % (target, target, target))
        # --force：先改名，成功后删除（避免半途删掉用户目录）
        old = target + '.旧-' + common.timestamp()
        print('[提示] --force：现有目录先改名为 %s，稍后删除' % os.path.basename(old))
        if os.path.exists(old):
            shutil.rmtree(old)
        os.rename(target, old)
        report['steps']['target']['旧目录'] = old
        pending_delete = old
    else:
        pending_delete = None

    # ---- 4) 空间检查 ----
    try:
        target_drive = os.path.splitdrive(target)[0] + os.sep
        free = shutil.disk_usage(target_drive).free
    except OSError:
        free = -1
    # 硬链接几乎不占空间；实际额外占用 ≈ browser_assets 独立副本 + 补丁备份 + 补丁后新包
    needed = src_info['assets_size'] * 3 + 64 * 1024 * 1024
    report['steps']['target']['free_bytes'] = free
    report['steps']['target']['needed_bytes_estimate'] = needed
    if free >= 0:
        print('[检查] 目标盘剩余空间 %s，预计额外占用约 %s'
              % (common.fmt_bytes(free), common.fmt_bytes(needed)))
        if free < needed:
            return fail('目标盘剩余空间不足：需要约 %s，实际 %s'
                        % (common.fmt_bytes(needed), common.fmt_bytes(free)))
    print()

    # ---- 4.5) 安全检查：软件内置「清空数据」一次性开关 + 备份 AppData ----
    # 实测（2026-11-10）：该开关默认 1，首次启动便携副本会把
    # %LocalLow%\partnerx\AbilixScratch3_0\standalonewindows\ 整个删除重建（项目列表/临时项目全没）。
    print('[安全检查] 软件内置「清空数据」开关（clear_app_data_switch）…')
    reg = common.read_clear_appdata_switch()
    report['steps']['appdata_safety'] = {'registry': reg}
    fix_registry = not args.no_fix_registry
    print('      %s = %r（存在=%s）%s'
          % (reg.get('name') or 'clear_app_data_switch_h*',
             reg.get('value'), reg['found'],
             '' if not reg.get('error') else ' 读取错误：%s' % reg['error']))
    need_clean = (reg.get('effective_value') == 1)
    if need_clean:
        msg = ('该开关为 1（或缺失，软件默认按 1）→ **第一次启动 IDE 会清空项目列表数据**。'
               '本工具会先备份 AppData，再把开关置 0，保证你的项目列表不被清掉。')
        print('[警告] ' + msg)
        report['warnings'].append(msg)
        backup = None
        if not args.no_appdata_backup:
            backup_root = os.path.dirname(target) or target
            try:
                backup = common.backup_appdata_projects(
                    backup_root, label='-便携版创建')
            except Exception as exc:  # noqa: BLE001
                report['warnings'].append('AppData 备份失败：%s' % exc)
                print('      [警告] AppData 备份失败：%s' % exc)
            if backup and backup.get('ok'):
                report['steps']['appdata_safety']['backup'] = backup
                print('      已备份 IDE 项目目录到：%s（%d 个文件 / %s，config sha256=%s…）'
                      % (backup['dest'], backup['files'], common.fmt_bytes(backup['bytes']),
                         (backup.get('config_sha256') or '')[:12]))
                print('      （如果以后要找回旧项目列表，关掉 IDE 后把这个目录复制回 '
                      '%s）' % common.appdata_projects_dir())
            elif backup and backup.get('error'):
                print('      [警告] ' + backup['error'])
        else:
            print('      已按要求 --no-appdata-backup 跳过 AppData 备份（有清空风险！）')
        if fix_registry and reg.get('name'):
            fix = common.set_clear_appdata_switch(reg['name'], 0)
            report['steps']['appdata_safety']['registry_fix'] = fix
            if fix.get('ok'):
                print('      已把 %s 置 0（下次启动不会再清空数据）' % reg['name'])
            else:
                print('      [警告] 置 0 失败：%s（可手动在注册表 '
                      'HKCU\\%s 把它改成 0）' % (fix.get('error'), common.APP_REG_KEY))
        elif not fix_registry:
            print('      已按要求 --no-fix-registry：请手动把该开关置 0，否则首启会清空数据！')
    else:
        print('      开关为 0（正常），不会清空 AppData。')
    print()

    # ---- 5) 复制（硬链接优先） ----
    print('[1/5] 复制安装目录到便携副本（硬链接优先，browser_assets 独立复制）…')
    try:
        copy_stats = common.copy_tree_prefer_hardlink(source, target,
                                                      log=print if args.verbose else None)
    except (OSError, FileExistsError) as exc:
        return fail('复制失败：%s' % exc)
    report['steps']['copy'] = copy_stats
    print('      完成：%d 个文件 / %s，用时 %ss（硬链接 %d、独立复制 %d、回退复制 %d）'
          % (copy_stats['files'], common.fmt_bytes(copy_stats['bytes']),
             copy_stats['seconds'], copy_stats['linked'], copy_stats['copied'],
             copy_stats['fallback']))

    # ---- 6) 校验复制 ----
    print('[2/5] 校验复制结果（文件数/总大小/exe/browser_assets 独立）…')
    copy_verify = common.verify_copy(source, target)
    report['steps']['copy_verify'] = copy_verify
    if not copy_verify['ok']:
        return fail('复制校验失败：\n  - ' + '\n  - '.join(copy_verify['errors']))
    print('      通过：文件数 %d / %s 一致；exe 存在；browser_assets 已独立（不会被硬链接改坏）'
          % (copy_verify['dst']['files'], common.fmt_bytes(copy_verify['dst']['bytes'])))

    if args.no_patch:
        print()
        print('[3/5] 已按要求 --no-patch 跳过补丁（副本是原版软件）')
        report['ok'] = True
    else:
        # ---- 7) 打补丁 ----
        print()
        print('[3/5] 给副本打默认模板补丁（底层 patch_browser_assets.py，自带 7 步自检）…')
        try:
            patch_result = common.patch_copy_assets(
                target, lib['path'],
                keep_work=args.keep_work,
                workdir=os.path.join(target, '_补丁临时') if args.keep_work else None)
        except Exception as exc:  # noqa: BLE001
            return fail('打补丁失败：%s' % exc)
        report['steps']['patch'] = patch_result
        if not patch_result.get('ok'):
            errs = (patch_result.get('patch') or {}).get('errors') or ['未知错误']
            return fail('打补丁失败（副本已保留在 %s，可运行 更新便携版函数库.py 重试）：\n  - %s'
                        % (target, '\n  - '.join(str(e) for e in errs)))
        print()
        print('[4/5] 读回补丁结果并二次校验 defaultcode…')
        try:
            verify_dc = common.verify_patched_defaultcode(
                common.find_assets(target), lib['path'])
        except Exception as exc:  # noqa: BLE001
            return fail('读回补丁结果失败：%s' % exc)
        report['steps']['defaultcode_verify'] = verify_dc
        if not verify_dc['ok']:
            return fail('补丁后校验失败：\n  - ' + '\n  - '.join(verify_dc['errors']))
        pr = patch_result['patch']
        print('      通过：zh-hans defaultcode 与函数库重新生成的片段完全相等'
              '（%d 字符），zh-hant/en 保持不变' % verify_dc['expected_chars'])
        print('      条目自检：原包 %d 条，仅 %d 条变化（其余 sha256 全部一致）'
              % (pr['original']['count'], len((pr.get('steps', {}).get('compare') or {}).get('changed') or [])))
        print('      原文件备份：%s' % (patch_result.get('backup') or '（未记录）'))
        print('      补丁后版本：%s（sha256 %s…）'
              % (common.fmt_bytes(patch_result.get('after_size', 0)),
                 (patch_result.get('after_sha256') or '')[:12]))
        report['ok'] = True

    # ---- 8) 桌面快捷方式 ----
    print()
    print('[5/5] 创建桌面快捷方式…')
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
            shortcut = None
        if shortcut and shortcut.get('ok'):
            print('      已创建：%s' % shortcut['lnk'])
        elif shortcut:
            report['warnings'].append('快捷方式未创建成功：%s' % shortcut.get('stderr'))
            print('      [警告] 快捷方式未创建成功：%s' % (shortcut.get('stderr') or '未知原因'))
    report['steps']['shortcut'] = shortcut

    # ---- 9) 收尾 ----
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
    if patch_result := report['steps'].get('patch'):
        common.print_kv('补丁备份', patch_result.get('backup') or '-')
    print('-' * 76)
    print('怎么用：')
    print('  1. 双击桌面「%s」（或 %s）启动函数版；' % (args.shortcut_name,
                                                    os.path.join(target, common.APP_EXE_NAME)))
    print('  2. 菜单「文件 → 新建」（或工具栏新建按钮）：新项目工作区自带函数库，')
    print('     左侧「函数」分类里直接拖用；')
    print('  3. 改了「我的函数库」之后，运行：python 更新便携版函数库.py')
    print('  4. 不想用了/要清空间，运行：python 删除便携版.py --yes')
    print('注意：便携版与安装版共用同一份 AppData 项目列表（%USERPROFILE%\\AppData\\LocalLow\\'
          'partnerx\\AbilixScratch3_0\\standalonewindows\\AbilixProjects）。')
    common.print_footer()
    return 0


if __name__ == '__main__':
    sys.exit(main())
