# -*- coding: utf-8 -*-
"""阶段2收尾：从备份恢复 AppData 项目列表，校验 config sha。"""
import os, sys, shutil, hashlib, time, json

BACKUP_ROOT = r'D:\UserData\Documents\WER\2026普级赛\WER_函数库\证据\原生积木_便携版\AppData备份\AbilixProjects.备份-20261111-134507\AbilixProjects'
CUR = os.path.join(os.environ['USERPROFILE'], r'AppData\LocalLow\partnerx\AbilixScratch3_0\standalonewindows\AbilixProjects')
EXPECTED_CONFIG_SHA = '5A52DD18D8DE191648C1EB87F847183A3D1C8372DCB2FFDC5E05510EEFACE310'


def stats(root):
    n = size = 0
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            n += 1
            size += os.path.getsize(p)
    return n, size


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest().upper()


print('备份目录存在:', os.path.isdir(BACKUP_ROOT))
print('备份:', stats(BACKUP_ROOT))
print('当前:', stats(CUR))
ts = time.strftime('%Y%m%d-%H%M%S')
moved = CUR + '.测试后-' + ts
if os.path.isdir(CUR):
    os.rename(CUR, moved)
    print('当前已改名备份到:', moved)
shutil.copytree(BACKUP_ROOT, CUR)
print('已恢复:', stats(CUR))
cfg = os.path.join(CUR, r'111\abilixProjectConfig.txt')
print('config exist:', os.path.exists(cfg))
if os.path.exists(cfg):
    h = sha(cfg)
    print('config sha256:', h)
    print('与测试前基线一致:', h == EXPECTED_CONFIG_SHA)
# 清理改动前的备份（保留，记录路径）
print('旧目录备份保留在:', moved)
print('RESTORE_DONE')
