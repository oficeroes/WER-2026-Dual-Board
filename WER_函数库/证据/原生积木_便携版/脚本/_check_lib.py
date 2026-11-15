# -*- coding: utf-8 -*-
"""检查 我的函数库.srhs 是否被改动。"""
import os, zipfile, hashlib, time

lib = r'D:\UserData\Documents\WER\2026普级赛\WER_函数库\我的函数库.srhs'
st = os.stat(lib)
print('mtime:', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)), 'size:', st.st_size)
z = zipfile.ZipFile(lib)
print('zip entries:', z.namelist())
for n in z.namelist():
    data = z.read(n)
    print(' ', n, len(data), hashlib.sha256(data).hexdigest().upper()[:16])
txt = z.read(z.namelist()[0]).decode('utf-8', 'replace')
print('--- content head 1200 ---')
print(txt[:1200])
print('--- contains func_Hello:', 'func_Hello' in txt, '; contains func_ count:', txt.count('func_'))
# 目录内其他文件
d = os.path.dirname(lib)
for f in sorted(os.listdir(d)):
    p = os.path.join(d, f)
    if os.path.isfile(p):
        s = os.stat(p)
        print('FILE', f, s.st_size, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(s.st_mtime)))
