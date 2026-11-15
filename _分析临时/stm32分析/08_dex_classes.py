# -*- coding: utf-8 -*-
"""Step 7: use androguard to list classes/methods of interest in the brain APK."""
import os, sys, time
from androguard.core.dex import DEX

OUT = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\stm32分析"
APK = r"D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\StreamingAssets\standalonewindows\hot_update_dir\extenddatas\brainApk\6F\Controller_43.apk"
import zipfile
t0 = time.time()
dexes = []
with zipfile.ZipFile(APK) as z:
    for n in ("classes.dex", "classes2.dex"):
        if n in z.namelist():
            data = z.read(n)
            d = DEX(data)
            dexes.append((n, d))
            print(n, "parsed", len(d.get_classes()), "classes", "%.1fs" % (time.time()-t0))

lines = []
WANT = ["com.abilix.controller.api", "com.abilix.controller.service", "com.abilix.utils", "com.abilix.controller.api.serial"]
for n, d in dexes:
    lines.append("===== %s =====" % n)
    for c in d.get_classes():
        cname = c.get_name()
        if any(cname.startswith(w) for w in WANT):
            lines.append("CLASS %s  super=%s  src=%s" % (cname, c.get_superclassname(), c.get_source_file_name()))
            for f in c.get_fields():
                lines.append("   FIELD %s %s access=0x%x" % (f.get_descriptor(), f.get_name(), f.get_access_flags()))
            for m in c.get_methods():
                lines.append("   METHOD %s %s access=0x%x code_off=0x%x" % (
                    m.get_descriptor(), m.get_name(), m.get_access_flags(), m.get_code_offset() or 0))
open(os.path.join(OUT, "08_dex_classes.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("wrote 08_dex_classes.txt lines=", len(lines), "time %.1fs" % (time.time()-t0))
