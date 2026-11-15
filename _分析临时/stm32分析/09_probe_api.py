# -*- coding: utf-8 -*-
"""Step 9: dump bytecode of key Protocol/Serial classes using correct androguard API."""
import sys, zipfile, os
try:
    from loguru import logger
    logger.remove()
except Exception:
    pass
from androguard.core.dex import DEX

APK = r"D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\StreamingAssets\standalonewindows\hot_update_dir\extenddatas\brainApk\6F\Controller_43.apk"
OUT = os.path.dirname(os.path.abspath(__file__))

with zipfile.ZipFile(APK) as z:
    dexes = [(n, DEX(z.read(n))) for n in ("classes.dex", "classes2.dex")]

bymap = {}
for n, d in dexes:
    for c in d.get_classes():
        bymap[c.get_name()[1:-1]] = c

probe = bymap["com/abilix/controller/api/serial/MasterSerial"]
m = probe.get_methods()[0]
print("EncodedMethod attrs:", [a for a in dir(m) if "code" in a.lower() or "inst" in a.lower()])
try:
    code = m.get_code()
    print("get_code ->", type(code), [a for a in dir(code) if not a.startswith("_")][:25])
except Exception as ex:
    print("get_code fail", ex)
