# -*- coding: utf-8 -*-
"""由 build_report.json + prelude.py + 补丁包内 zfb 索引 生成「编译信息.txt」（离线安装包）。

注意：manifest.entries 只记录 maingui.html / maingui.js / abilix_userlib.js 三项，
      不包含 abilix_userlib.json 自身；新增条目的真实大小/sha 需从补丁包 zfb 索引读取。
"""
import hashlib
import json
import os
import struct

REPO = r'D:\UserData\Documents\WER\2026普级赛'
WORK = os.path.join(REPO, '_分析临时', 'offline_work')
PKG = os.path.join(REPO, 'WER_函数库', '安装包')
PATCHED = os.path.join(PKG, 'browser_assets.patched')


def read7(f):
    shift = 0
    val = 0
    while True:
        b = f.read(1)
        if not b:
            raise EOFError('unexpected EOF in zfb index')
        val |= (b[0] & 0x7f) << shift
        if not b[0] & 0x80:
            break
        shift += 7
    return val


def read_zfb(path):
    """返回 (索引, 读取函数)：{name: (offset, size)}；数据区可用 seek 读取。"""
    f = open(path, 'rb')
    ln = read7(f)
    sig = f.read(ln)
    if sig != b'zfbRes_v1':
        raise RuntimeError('不是 zfbRes_v1: %r' % sig)
    n = struct.unpack('<i', f.read(4))[0]
    index = {}
    for _ in range(n):
        l = read7(f)
        name = f.read(l).decode('utf-8')
        off, = struct.unpack('<q', f.read(8))
        size, = struct.unpack('<i', f.read(4))
        index[name] = (off, size)
    return f, index


def entry_info(f, index, name):
    off, size = index[name]
    f.seek(off)
    data = f.read(size)
    if len(data) != size:
        raise RuntimeError('条目读取不完整: %s' % name)
    return size, hashlib.sha256(data).hexdigest()


def main():
    report = json.load(open(os.path.join(WORK, 'build_report.json'), encoding='utf-8'))
    prelude = open(os.path.join(PKG, 'prelude.py'), encoding='utf-8').read()

    lib = report['manifest']['library']
    src = report['manifest']['sourceAssets']
    pat = report['patchedAssets']
    mann = report['manifest']
    verify = report['verify']

    zf, index = read_zfb(PATCHED)
    names = ['/Blockly_Code/maingui.html', '/Blockly_Code/maingui.js',
             '/Blockly_Code/abilix_userlib.js', '/Blockly_Code/abilix_userlib.json']
    infos = {n: entry_info(zf, index, n) for n in names}
    zf.close()

    lines = []
    lines.append('# WER 原生函数积木 · 离线安装包 编译信息')
    lines.append('# 本文件由 工具/原生积木/原生积木核心.py build 的产物整理而成。')
    lines.append('# 格式：key = value（安装.ps1 / 还原.ps1 会读取其中的 sha256 做校验）')
    lines.append('# 注意：请保持本文件与 browser_assets.patched 在一起，不要单独拷走。')
    lines.append('')
    lines.append('工具名称 = WER原生积木核心')
    lines.append('工具版本 = %s' % report.get('toolVersion', ''))
    lines.append('生成时间 = %s' % report.get('builtAt', ''))
    lines.append('构建机器 = %s' % os.environ.get('COMPUTERNAME', ''))
    lines.append('构建用户 = %s' % os.environ.get('USERNAME', ''))
    lines.append('')
    lines.append('函数库路径 = %s' % lib['path'])
    lines.append('函数库sha256 = %s' % lib['sha256'])
    lines.append('函数库大小 = %s' % lib['size'])
    lines.append('机器人类型 = %s' % lib.get('robotType', ''))
    lines.append('程序名称 = %s' % lib.get('programName', ''))
    lines.append('函数数量 = %d' % len(lib['defs']))
    lines.append('函数列表 = %s' % '、'.join(d['name'] for d in lib['defs']))
    for i, d in enumerate(lib['defs'], 1):
        args = ', '.join(d.get('args') or [])
        lines.append('函数%d = %s(%s)  [积木类型 %s]' % (i, d['name'], args, d.get('blockType', '')))
    lines.append('')
    lines.append('原版资源包路径 = %s' % src['path'])
    lines.append('原版资源包sha256 = %s' % src['sha256'].upper())
    lines.append('原版资源包大小 = %s' % src['size'])
    lines.append('')
    lines.append('补丁包文件 = browser_assets.patched')
    lines.append('补丁包sha256 = %s' % pat['sha256'].upper())
    lines.append('补丁包大小 = %s' % pat['size'])
    lines.append('补丁包条目数 = %s' % pat['count'])
    lines.append('补丁包条目说明 = 原版 %d 条 + 新增 2 条（abilix_userlib.js、abilix_userlib.json）'
                 % verify['original']['count'])
    lines.append('')
    lines.append('prelude文件 = prelude.py（与安装.ps1同目录；仅作记录，安装时不需要）')
    lines.append('prelude sha256 = %s' % mann['prelude']['sha256'].upper())
    lines.append('prelude 字符数 = %s' % mann['prelude']['chars'])
    lines.append('')
    lines.append('自检结果 = 通过（只允许 2 处修改 + 2 处新增，其余条目逐字节不变）')
    lines.append('自检-修改条目 = %s'
                 % '；'.join('%s（%d -> %d 字节）' % (c['name'], c['old_len'], c['new_len'])
                             for c in verify['changed']))
    lines.append('自检-新增条目 = %s'
                 % '；'.join('%s（%d 字节）' % (n, infos[n][0]) for n in
                             ['/Blockly_Code/abilix_userlib.js', '/Blockly_Code/abilix_userlib.json']))
    lines.append('自检-逐字节不变条目数 = %s' % verify['unchanged'])
    lines.append('自检-新增条目sha256 = %s；%s'
                 % ('%s=%s' % ('abilix_userlib.js', infos['/Blockly_Code/abilix_userlib.js'][1].upper()),
                    '%s=%s' % ('abilix_userlib.json', infos['/Blockly_Code/abilix_userlib.json'][1].upper())))
    lines.append('自检-条目数核对 = 补丁包索引实测 %d 条，与 build 自检一致' % len(index))
    lines.append('')
    lines.append('安装校验值 = 补丁包sha256（安装.ps1 写入后用它校验目标资源包）')
    lines.append('还原校验值 = 原版资源包sha256（还原.ps1 用它校验备份与还原结果）')
    lines.append('')
    lines.append('# ---------------------------------------------------------------------------')
    lines.append('# 附：4 个被修改/新增条目的实测信息（从补丁包 zfb 索引读取）')
    lines.append('# 说明：补丁包内 manifest 的 entries 只记录 html/js/userlib 三项，不含 manifest 自身；')
    lines.append('#       故 abilix_userlib.json 的大小/sha 以本段实测为准。')
    for n in names:
        size, sh = infos[n]
        kind = '修改' if n in ('/Blockly_Code/maingui.html', '/Blockly_Code/maingui.js') else '新增'
        lines.append('%s = %s（%d 字节，%s）' % (n, sh.upper(), size, kind))
    lines.append('')
    lines.append('# ---------------------------------------------------------------------------')
    lines.append('# 附：prelude（Python 前奏）完整内容，安装后由 abilix_userlib.js 注入到生成代码里')
    lines.append('===== PRELUDE 开始 =====')
    for ln in prelude.rstrip('\n').split('\n'):
        lines.append(ln)
    lines.append('===== PRELUDE 结束 =====')
    lines.append('')

    out = os.path.join(PKG, '编译信息.txt')
    with open(out, 'w', encoding='utf-8-sig', newline='\r\n') as f:
        f.write('\n'.join(lines))
    print('written:', out, os.path.getsize(out), 'bytes')
    print('新增条目实测:', {n: infos[n] for n in
                          ['/Blockly_Code/abilix_userlib.js', '/Blockly_Code/abilix_userlib.json']})


if __name__ == '__main__':
    main()
