# -*- coding: utf-8 -*-
"""
同步状态检查.py —— 一眼看清“函数库到底同步进软件了没有”。

检查内容：
  1) 当前账户是否管理员、软件是否正在运行；
  2) 安装目录 / browser_assets 路径、大小、sha256、最近的备份；
  3) 我的函数库.srh(s) 里有哪些函数（用户自己搭的）；
  4) 软件“新建项目默认模板”当前是什么（原始模板 / 已打补丁 / 被改过）；
  5) 两者对比：还需不需要同步、要新增/移除哪些函数；
  6) 给出明确的下一步建议（管理员同步 / 便携版 / 已可用）。

只读：不会修改任何文件。
运行：双击 同步状态检查.cmd（或 python 同步状态检查.py）
"""
import ctypes
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 控制台编码兼容：cmd 里会先 chcp 65001；直接跑 .py 时也尽量不因 GBK 崩溃
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def _load_core():
    path = os.path.join(HERE, '框架核心.py')
    spec = importlib.util.spec_from_file_location('framework_core_status', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def in_admin_group():
    """当前账户是否属于本机管理员组（用 SID 判断，不受系统语言影响）。"""
    try:
        out = subprocess.run(['whoami', '/groups'], capture_output=True, text=True,
                             timeout=15, encoding='mbcs', errors='replace').stdout
        return 'S-1-5-32-544' in out
    except Exception:
        return None


def ide_running():
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq AbilixScratch3.0.exe'],
                             capture_output=True, text=True, timeout=15,
                             encoding='mbcs', errors='replace').stdout
        return 'AbilixScratch3.0.exe' in out
    except Exception:
        return None


def fmt_bool(v):
    return '是' if v else '否'


def main():
    core = _load_core()
    print('=' * 78)
    print(' AbilixScratch3.0 「我的函数库」同步状态检查')
    print('=' * 78)

    admin = is_admin()
    admin_group = in_admin_group()
    run = ide_running()
    print('[环境] 当前进程已提升    : %s' % fmt_bool(admin))
    print('[环境] 账户在管理员组    : %s' % ('是' if admin_group else ('否' if admin_group is False else '未知')))
    if not admin:
        if admin_group:
            print('       -> 你的账户可以提权：运行“同步我的函数库(管理员).cmd”时会出现 UAC，点“是”。')
        elif admin_group is False:
            print('       -> 你的账户不在管理员组：需要管理员账户密码，或改用便携版（不需要管理员）。')
    print('[环境] 软件正在运行       : %s' % ('是（同步前请关闭软件）' if run else '否'))

    # 1) 安装目录/资源包
    try:
        loc = core.locate_install()
        assets = loc['assets']
    except Exception as exc:  # noqa: BLE001
        print('\n[错误] 找不到软件安装目录：%s' % exc)
        print('     可用 --assets 指定，或确认 AbilixScratch3.0 已安装。')
        return 2
    print('\n[安装] browser_assets : %s' % assets)

    # 2) 函数库
    lib = core.find_default_library(require=False)
    lib_funcs = []
    if not lib or not lib.get('path'):
        print('\n[函数库] 没有找到 我的函数库.srh / 我的函数库.srhs')
        print('       请先按 README 第 1 步在 IDE 里搭函数并保存到 WER_函数库\\我的函数库.srhs')
        lib_path = None
    else:
        lib_path = lib['path']
        print('\n[函数库] %s%s' % (lib_path, '（示例库）' if not lib.get('is_my_library', True) else ''))
        try:
            val = core.validate_library(lib_path)
            lib_funcs = [f.get('name') for f in val.get('functions') or []]
            print('         函数 %d 个：%s' % (len(lib_funcs), ', '.join(lib_funcs) if lib_funcs else '（无）'))
            for w in (val.get('warnings') or [])[:6]:
                print('         [WARN] %s' % w)
            for e in (val.get('errors') or [])[:6]:
                print('         [ERROR] %s' % e)
        except Exception as exc:  # noqa: BLE001
            print('         读取失败：%s' % exc)

    # 3) 当前默认模板
    try:
        rep = core.inspect_current_template(assets=assets)
    except Exception as exc:  # noqa: BLE001
        print('\n[错误] 读取当前默认模板失败：%s' % exc)
        return 2
    if rep.get('errors'):
        for e in rep['errors'][:4]:
            print('         [ERROR] %s' % e)
    print('\n[默认模板] 文件大小 %s B / sha256 %s' % (rep.get('file_size'), (rep.get('file_sha256') or '')[:16] + '…'))
    print('           当前状态：%s' % (rep.get('classification') or '未知'))
    zh = (rep.get('langs') or {}).get('zh-hans') or {}
    cur_funcs = [f.get('name') for f in zh.get('functions') or []]
    print('           简中模板函数 %d 个：%s' % (len(cur_funcs), ', '.join(cur_funcs) if cur_funcs else '（无）'))
    bk = rep.get('backup') or {}
    if bk.get('name'):
        print('           最近备份：%s（与当前%s）' % (bk['name'], '相同' if bk.get('same_as_current') else '不同'))

    # 4) 对比
    cmp_ = rep.get('compare') or {}
    need_sync = cmp_.get('need_sync')
    print('\n[对比] 还需要同步吗：%s' % ('需要' if need_sync else ('不需要（模板已与函数库一致）' if need_sync is False else '无法判断')))
    if cmp_:
        print('       当前模板函数 %s 个 / 函数库 %s 个' % (cmp_.get('current_function_count'), cmp_.get('library_function_count')))
        if cmp_.get('to_add'):
            print('       同步后会新增函数：%s' % ', '.join(cmp_['to_add']))
        if cmp_.get('to_remove'):
            print('       同步后会移除函数：%s' % ', '.join(cmp_['to_remove']))
        if cmp_.get('args_changed'):
            print('       参数有变化的函数：%s' % ', '.join(x['name'] for x in cmp_['args_changed']))

    # 5) 结论/下一步
    print('\n' + '-' * 78)
    kind = rep.get('template_kind')
    if run:
        print('结论：软件正在运行，请先完全关闭 AbilixScratch3.0，再执行同步/验证。')
    if kind == 'patched' and need_sync is False:
        print('结论：[OK] 已同步。打开软件 -> 文件->新建项目，左侧「函数」分类里应能看到：')
        print('      ' + (', '.join(cur_funcs) if cur_funcs else '（无）'))
    elif kind == 'original':
        print('结论：[X] 软件当前还是“原始模板”，你的函数库【没有】同步进去。')
        print('      这一步才是关键：')
        if admin:
            print('      -> 当前进程已是管理员：直接双击“同步我的函数库(管理员).cmd”即可；完成后重启软件再新建项目。')
        elif admin_group:
            print('      -> 你的账户在管理员组：先完全关闭 AbilixScratch3.0，再双击本目录')
            print('        “同步我的函数库(管理员).cmd”，UAC 弹窗里点“是”（不需要输密码）。')
            print('        窗口结束后看最终提示；上次没生效通常是 UAC 被取消/没点“是”。')
        else:
            print('      -> 当前 Windows 账户不在管理员组：需要管理员账户密码（在 UAC 里输入），')
            print('        或改用 ..\\便携版\\创建便携函数版.cmd 生成“函数版”（不需要管理员），')
            print('        用桌面“AbilixScratch3.0 函数版”快捷方式新建项目。')
    elif need_sync:
        print('结论：[!] 模板与函数库不一致，需要重新同步（运行同步 cmd，完成后重启软件）。')
    else:
        print('结论：模板被改过/状态无法完全确认；先运行同步再验证。')

    if lib_funcs and not cur_funcs:
        print('\n提示：同步成功后，新建项目里应出现这些函数：%s' % ', '.join(lib_funcs))
    print('-' * 78)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
