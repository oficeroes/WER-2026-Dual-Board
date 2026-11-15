# -*- coding: utf-8 -*-
"""方向1 证据提取 3：dex 中文字符串 + 方法名关键词。只读。"""
import re, os, sys, zipfile

sys.stdout.reconfigure(encoding='utf-8')
APK = r'D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\StreamingAssets\update\BlocklyC_V103.apk'
z = zipfile.ZipFile(APK)
dex = z.read('classes.dex')

# dex 字符串是 MUTF-8；中文为 UTF-8 三字节。提取含 CJK 的片段。
txt = dex.decode('utf-8', 'ignore')
cjk = re.findall(r'[\u4e00-\u9fff][\u4e00-\u9fff\uff00-\uffef0-9A-Za-z ：:，,。.、%（）()\-]{1,40}', txt)
print('===== dex 中文串 =====')
seen = set()
for s in cjk:
    if s not in seen:
        seen.add(s)
        print(s)
print('cjk count', len(seen))

print('\n===== 类名/方法名关键词 =====')
strs = set(s.decode('ascii', 'ignore') for s in re.findall(rb'[\x20-\x7e]{3,}', dex))
KEYS = ['EE', 'DO', 'AI', 'Port', 'port', 'Uart', 'UART', 'I2c', 'I2C', 'Serial', 'Send', 'Recv',
        'Cmd', 'CMD', 'Boot', 'Reset', 'Update', 'Eeprom', 'SensorType', 'Type', 'Open', 'Close',
        'Read', 'Write', 'Native', 'native']
for s in sorted(strs):
    if not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]{2,40}', s):
        continue
    if any(k in s for k in KEYS):
        print(s)
