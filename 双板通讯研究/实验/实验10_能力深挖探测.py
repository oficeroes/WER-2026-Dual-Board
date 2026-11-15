#<SKCON9><USB><ProgramE>
# ============================================================
# 实验10 · 能力深挖探测（只读为主，安全）
# ------------------------------------------------------------
# 目的：实验05 已证明 socket 不可用，但还留下几个关键问题：
#   1) 除了 time/sys/os/threading/struct/json，还能 import 什么？（re/io/binascii/zipfile/hashlib...）
#   2) libstarpy / star 模块里到底有什么（能否借它做网络/系统调用）？
#   3) os.system(os.popen) 能不能执行 shell 命令（→ getprop 看 Android 版本，未来也许能起服务）？
#   4) 文件系统能力：cwd="/" 可写吗？python_dir 在哪？/sdcard 能读吗？/proc/net/tcp 能读吗？
#   5) os.open('/dev/ttyMT1') 这类设备节点是否可访问（不打开串口硬件，只 os.access/os.path.exists 探测，避免干扰）。
#
# 结果：屏幕打印 + 同时写 EEPROM（130 起，掉电不丢；避开 11~20 官方占用、100~115 实验05 已用）。
# 用法：用官方软件下载为任意程序名（记得改第一行文件头），运行，等屏幕出现 done。
# ============================================================

import time
import libstarpy

robot = Robot()

EE = 130          # 结果写 EEPROM 130 起
MODS = ['io', 're', 'collections', 'binascii', 'base64', 'hashlib', 'zipfile',
        'gzip', 'codecs', 'locale', 'glob', 'shutil', 'tempfile', 'pickle',
        'copy', 'datetime', 'itertools', 'functools', 'operator', 'heapq',
        'bisect', 'string', 'traceback', 'warnings', 'gc', 'imp', 'marshal',
        'select', 'errno', 'fcntl', 'termios', 'array', 'mmap', '_thread',
        'libstarpy', 'star', 'starcore']

def say(s):
    robot.print(s + '\n')
    time.sleep(0.05)

def probe_import(name):
    try:
        __import__(name)
        return 1
    except Exception:
        return 0

def main():
    robot.clear()
    say('deep probe...')
    time.sleep(0.3)

    # ---------- 1) 模块导入 ----------
    idx = 0
    mod_ok = []
    for name in MODS:
        ok = probe_import(name)
        mod_ok.append(ok)
        robot.set_ee(EE + idx, ok)
        idx += 1
        if ok:
            say(name + '=1')
    say('mod done')

    # ---------- 2) libstarpy 内容（只打印名字，不调用） ----------
    try:
        names = dir(libstarpy)
        robot.set_ee(EE + 60, len(names))
        buf = ''
        for n in names[:40]:
            buf = buf + n + ','
        say('libstarpy=' + buf)
    except Exception as e:
        robot.set_ee(EE + 60, -1)
        say('libstarpy ERR ' + str(e))

    # ---------- 3) os.system / os.popen ----------
    sys_ok = 0
    try:
        import os
        try:
            rc = os.system('getprop ro.build.version.release')
            robot.set_ee(EE + 61, rc)
            sys_ok = 1
        except Exception as e:
            robot.set_ee(EE + 61, -2)
        say('os.system=' + str(sys_ok))
    except Exception as e:
        say('os ERR ' + str(e))

    # ---------- 4) 文件系统 ----------
    try:
        import os
        fs = []
        try:
            cwd = os.getcwd()
        except Exception:
            cwd = '?'
        fs.append('cwd=' + str(cwd))
        try:
            fs.append('root_ls=' + str(len(os.listdir('/'))))
        except Exception:
            fs.append('root_ls=ERR')
        # 只读判断，不创建文件
        for p in ('/sdcard', '/data/local/tmp', '/proc/net/tcp', '/dev/ttyMT1', '/dev/ttyMT0',
                  '/system/lib/python/libpython3.4m.so'):
            try:
                fs.append(p + ':e' + str(int(os.path.exists(p))) + 'r' + str(int(os.access(p, os.R_OK))))
            except Exception:
                fs.append(p + ':ERR')
        robot.set_ee(EE + 62, len(fs))
        for s in fs:
            say(s)
    except Exception as e:
        say('fs ERR ' + str(e))

    # ---------- 5) 写能力（只试临时目录；cwd="/" 一般不写） ----------
    try:
        import os
        try:
            f = open('/data/local/tmp/wer_probe.txt', 'w')
            f.write('ok')
            f.close()
            writable = 1
        except Exception:
            writable = 0
        robot.set_ee(EE + 63, writable)
        say('tmp_writable=' + str(writable))
    except Exception as e:
        say('write ERR ' + str(e))

    say('done')

main()  # program entry
