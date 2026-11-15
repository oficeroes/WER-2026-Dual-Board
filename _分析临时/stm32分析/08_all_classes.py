# -*- coding: utf-8 -*-
"""Step 8 (v2): dump com.abilix classes with methods/fields/instruction listings."""
import sys, zipfile, os, traceback

# kill androguard loguru noise
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

lines = []
for n, d in dexes:
    lines.append("##### %s #####" % n)
    for c in d.get_classes():
        cname = c.get_name()[1:-1]
        if not cname.startswith("com/abilix/"):
            continue
        lines.append("")
        lines.append("CLASS %s  super=%s src=%s access=0x%x" % (
            cname, c.get_superclassname(), c.get_source_file_idx(), c.get_access_flags()))
        for f in c.get_fields():
            lines.append("  FIELD %-30s %s (0x%x)" % (f.get_name(), f.get_descriptor(), f.get_access_flags()))
        for m in c.get_methods():
            lines.append("  METHOD %-28s %s access=0x%x" % (m.get_name(), m.get_descriptor(), m.get_access_flags()))
open(os.path.join(OUT, "08_all_abilix_classes.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("classes dump lines", len(lines))

TARGETS = [
    "com/abilix/controller/api/Protocol",
    "com/abilix/controller/api/Protocol$MasterUART",
    "com/abilix/controller/api/Protocol$TransUART",
    "com/abilix/controller/api/ProtocolDatagramHandler",
    "com/abilix/controller/service/ProtocolService",
    "com/abilix/controller/api/serial/BaseSerial",
    "com/abilix/controller/api/serial/MasterSerial",
    "com/abilix/controller/api/serial/TransSerial",
    "com/abilix/utils/ProgramAndInterfaceC",
    "com/abilix/utils/SerialPort",
]
bymap = {}
for n, d in dexes:
    for c in d.get_classes():
        bymap[c.get_name()[1:-1]] = c
allnames = sorted(bymap)
lines = ["=== classes matching Protocol/Serial/serial/sensor ==="]
for cn in allnames:
    if "Protocol" in cn or "Serial" in cn or "serial" in cn or "Sensor" in cn:
        lines.append(cn)
open(os.path.join(OUT, "08_match_names.txt"), "w", encoding="utf-8").write("\n".join(lines))

lines = []
for t in TARGETS:
    c = bymap.get(t)
    if c is None:
        lines.append("!! class not found: %s" % t); continue
    lines.append("")
    lines.append("=" * 100)
    lines.append("CLASS %s" % t)
    lines.append("=" * 100)
    for m in c.get_methods():
        lines.append("")
        lines.append("---- METHOD %s %s access=0x%x ----" % (m.get_name(), m.get_descriptor(), m.get_access_flags()))
        try:
            for ins in m.get_bc().get_instructions():
                lines.append("  " + ins.get_name() + " " + str(ins.get_output()))
        except Exception as ex:
            lines.append("  !! disasm error: %r" % (ex,))
open(os.path.join(OUT, "09_keyclass_bytecode.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("bytecode dump lines", len(lines))
