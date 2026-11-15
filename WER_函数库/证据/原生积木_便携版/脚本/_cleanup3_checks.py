# -*- coding: utf-8 -*-
"""阶段3：清理前的最终校验记录。"""
import os, hashlib, json

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest().upper()

install = r'D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets'
lib = r'D:\UserData\Documents\WER\2026普级赛\WER_函数库\我的函数库.srhs'
copy_dir = r'C:\Users\s1325\AbilixScratch3.0_FuncLib'
lnk = r'D:\UserData\Desktop\AbilixScratch3.0 函数版.lnk'
APP = os.path.join(os.environ['USERPROFILE'], r'AppData\LocalLow\partnerx\AbilixScratch3_0\standalonewindows\AbilixProjects')

print('=== 真实安装 browser_assets ===')
st = os.stat(install)
h = sha(install)
print('size:', st.st_size, 'sha256:', h)
print('与基线一致:', h == 'DF6DB241752D42BFF2995FCD24521E070ADF9EB5D96E870148F9DC51690EDC40' and st.st_size == 85271033)
print('=== 我的函数库.srhs ===')
print('size:', os.path.getsize(lib), 'sha256:', sha(lib))
print('=== AppData 已恢复的 config 文件 ===')
for dp, dn, fn in os.walk(APP):
    for f in fn:
        if f.lower().endswith('.txt'):
            p = os.path.join(dp, f)
            print(os.path.relpath(p, APP), os.path.getsize(p), sha(p))
print('=== 便携副本/快捷方式（清理前） ===')
print('copy dir exists:', os.path.isdir(copy_dir))
if os.path.isdir(copy_dir):
    n = size = 0
    for dp, dn, fn in os.walk(copy_dir):
        for f in fn:
            n += 1
            size += os.path.getsize(os.path.join(dp, f))
    print('files:', n, 'bytes:', size)
print('shortcut exists:', os.path.exists(lnk))
print('CHECK_DONE')
