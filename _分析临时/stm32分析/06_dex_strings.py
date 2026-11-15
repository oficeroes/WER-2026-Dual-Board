# -*- coding: utf-8 -*-
"""Step 6: extract classes.dex strings from the brain APK (read-only)."""
import zipfile, struct, os, re, sys

APK = r"D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\StreamingAssets\standalonewindows\hot_update_dir\extendat datas".replace(" ", "")
APK = r"D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\StreamingAssets\standalonewindows\hot_update_dir\extenddatas\brainApk\6F\Controller_43.apk"
OUT = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\stm32分析"

def uleb(data, off):
    r = 0; s = 0
    while True:
        b = data[off]; off += 1
        r |= (b & 0x7f) << s
        if not (b & 0x80): return r, off
        s += 7

def dex_strings(data, name):
    magic = data[:8]
    if not magic.startswith(b"dex\n"):
        return ["!! bad magic %r" % magic]
    file_size = struct.unpack_from("<I", data, 32)[0]
    string_ids_size, string_ids_off = struct.unpack_from("<II", data, 56)
    out = []
    for i in range(string_ids_size):
        so = struct.unpack_from("<I", data, string_ids_off + 4*i)[0]
        try:
            n, p = uleb(data, so)
            s = data[p:p+n*4]
            # decode MUTF-8 (approximate: replace CESU-8 pairs)
            end = s.find(b"\x00")
            if end >= 0: s = s[:end]
            try: text = s.decode("utf-8")
            except UnicodeDecodeError:
                text = s.decode("utf-8", "replace")
            out.append(text)
        except Exception as ex:
            out.append("!!err@%d:%s" % (so, ex))
    return out

allstr = {}
with zipfile.ZipFile(APK) as z:
    names = [n for n in z.namelist() if re.match(r"classes\d*\.dex$", n)]
    lines = ["=== APK %s ===" % APK, "dex files: %s" % names]
    for n in sorted(names):
        data = z.read(n)
        ss = dex_strings(data, n)
        lines.append("--- %s : %d strings, size=%d ---" % (n, len(ss), len(data)))
        allstr[n] = ss
        for s in ss:
            lines.append(s)
    open(os.path.join(OUT, "06_dex_strings_raw.txt"), "w", encoding="utf-8").write("\n".join(lines))

# stats / filtered output
lines = []
KEYS = ["tty", "serial", "Serial", "uart", "UART", "usb", "Usb", "USB", "baud", "Baud",
        "stm32", "STM32", "Stm32", "protocol", "Protocol", "cmd", "Cmd", "CMD", "frame", "Frame",
        "crc", "CRC", "Crc", "check", "0x", "%02x", "%02X", "hex", "Hex", "EE", "eeprom", "EEPROM",
        "CCJ", "ProgramAndInterface", "abilix", "Abilix", "Robot", "robot"]
for n, ss in allstr.items():
    lines.append("===== %s =====" % n)
    for s in ss:
        if any(k in s for k in KEYS):
            if len(s) < 300:
                lines.append(s.replace("\n", "\\n"))
open(os.path.join(OUT, "06_dex_strings_kept.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("strings total:", {n: len(v) for n, v in allstr.items()})
