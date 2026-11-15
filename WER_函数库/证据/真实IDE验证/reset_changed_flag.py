# -*- coding: utf-8 -*-
"""最后收尾：把配置里 WER函数库 条目的 isChanged 复位为 false（IDE 启动会置 true，仅为避免切换项目时弹保存提示）。"""
import re

CFG = r'C:\Users\s1325\AppData\LocalLow\partnerx\AbilixScratch3_0\standalonewindows\AbilixProjects\111\abilixProjectConfig.txt'
TEMP_FOLDER = '1794288549236'

text = open(CFG, encoding='utf-8-sig').read()
pat = re.compile(r'(<tempProjectFolderName>' + TEMP_FOLDER +
                 r'</tempProjectFolderName>\s*<isNewProject>\w+</isNewProject>\s*'
                 r'<isSaved>\w+</isSaved>\s*<isChanged>)true(</isChanged>)')
text, n = pat.subn(r'\1false\2', text)
open(CFG, 'w', encoding='utf-8', newline='\n').write(text)
print('reset isChanged:', n)
for line in open(CFG, encoding='utf-8'):
    if 'savedProjectPath' in line or 'isChanged' in line:
        print(line.rstrip())
