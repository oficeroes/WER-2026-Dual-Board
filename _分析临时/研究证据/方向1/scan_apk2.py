# -*- coding: utf-8 -*-
"""方向1 证据提取 2：从 BlocklyC_V103 dex 中提取协议/EEPROM/端口相关字符串及上下文。
只读提取。"""
import re, os, sys, zipfile, collections

sys.stdout.reconfigure(encoding='utf-8')
APK = r'D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\StreamingAssets\update\BlocklyC_V103.apk'
z = zipfile.ZipFile(APK)
dex = z.read('classes.dex')
strs = [s.decode('ascii', 'ignore') for s in re.findall(rb'[\x20-\x7e]{3,}', dex)]

# 打印带上下文的协议类字符串：按包含关键字过滤
KEYS2 = ['%02x', '%x', 'cmd', 'Cmd', 'protocol', 'Protocol', 'checksum', 'CheckSum', 'crc', 'CRC',
         'frame', 'Frame', 'head', 'Head', 'send', 'Send', 'recv', 'Recv', 'recieve', 'Revice',
         'nCurr', 'nSet', 'getEE', 'setEE', 'setDO', 'getAI', 'getTouch', 'eeprom', 'Eeprom',
         'port', 'Port', 'serial', 'Serial', 'read', 'write', 'baud', 'timeout', 'buffer']
print('===== dex strings (protocol/port/eeprom keywords) =====')
seen = set()
for s in strs:
    if s in seen:
        continue
    low = s.lower()
    if any(k.lower() in low for k in KEYS2):
        # 过滤掉大量无意义的 java class refs / resource names
        if s.startswith('L') and s.endswith(';'):
            continue
        seen.add(s)
        print(repr(s))
print('count', len(seen))

print('\n===== 所有含 0x/%x/aa/55 帧头的短串 =====')
for s in strs:
    if re.fullmatch(r'(?:[0-9a-fA-F]{2}[\s:,-]?){2,}', s) and len(s) >= 5:
        print(repr(s))

print('\n===== XML layouts =====')
for n in z.namelist():
    if n.startswith('res/layout'):
        txt = z.read(n).decode('utf-8', 'ignore')
        print('\n---', n, '---')
        # 只保留 android:id / android:text
        for m in re.finditer(r'android:(id|text)="([^"]+)"', txt):
            print(' ', m.group(1), '=', m.group(2))
