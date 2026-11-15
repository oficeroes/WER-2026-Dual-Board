# -*- coding: utf-8 -*-
"""Final artifact sanity check."""
import hashlib, json, os, zipfile

W = r'D:\UserData\Documents\WER\2026普级赛'
LIB = os.path.join(W, r'WER_函数库\WER函数库.srhs')
DESK = r'D:\UserData\Desktop\WER函数库.srhs'
CFG = r'C:\Users\s1325\AppData\LocalLow\partnerx\AbilixScratch3_0\standalonewindows\AbilixProjects\111\abilixProjectConfig.txt'
BACKUP = os.path.join(W, r'_分析临时\appdata_backup_20261110_132905')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


print('LIB  :', os.path.getsize(LIB), sha(LIB))
print('DESK :', os.path.getsize(DESK), sha(DESK))
print('same :', sha(LIB) == sha(DESK))
with zipfile.ZipFile(LIB) as z:
    print('zip entries:', z.namelist(), 'comment:', z.comment)
print('cfg exists:', os.path.exists(CFG), 'backup exists:', os.path.isdir(BACKUP),
      'backup files:', sum(len(fs) for _, _, fs in os.walk(BACKUP)))
text = open(CFG, encoding='utf-8-sig').read()
print('cfg has WERFuncLib entry:', 'WER函数库.srhs' in text)
print('cfg project count:', text.count('<TempProjectInfoList>'))
print('evidence screenshots:')
for f in sorted(os.listdir(os.path.join(W, r'WER_函数库\证据\真实IDE验证'))):
    print('  ', f)
