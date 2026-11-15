# -*- coding: utf-8 -*-
"""快速扫描 brainApk Controller APK：条目清单 / AndroidManifest / classes*.dex 字符串。
只做证据提取，不做完整反编译（完整逆向由 apk-dex 同事负责）。
用法: python scan_controller_apk.py [apk路径] [输出目录]
"""
import sys, os, re, struct, zipfile, json

def dex_strings(data):
    """解析 DEX string_ids 返回字符串列表。"""
    if data[:4] != b'dex\n':
        return []
    (string_ids_size,) = struct.unpack_from('<I', data, 56)
    (string_ids_off,) = struct.unpack_from('<I', data, 60)
    out = []
    for i in range(string_ids_size):
        (off,) = struct.unpack_from('<I', data, string_ids_off + 4 * i)
        p = off
        # uleb128 utf16 length
        n = data[p]; p += 1
        if n & 0x80:
            while data[p - 1] & 0x80:
                n = (n & 0x7f) | ((data[p] & 0x7f) << 7); p += 1
        end = data.index(b'\x00', p)
        raw = data[p:end]
        try:
            s = raw.decode('utf-8')
        except Exception:
            s = raw.decode('latin1')
        out.append(s)
    return out

# ---------- AXML ----------
def _uleb(data, p):
    n = 0; shift = 0
    while True:
        b = data[p]; p += 1
        n |= (b & 0x7f) << shift
        if not (b & 0x80):
            return n, p
        shift += 7

def parse_axml(data):
    """返回 [(element_name, [(attr_name, typed_value_str)])]，够用于 manifest 取证。"""
    if len(data) < 8 or struct.unpack_from('<H', data, 0)[0] != 0x0003:
        return None
    p = 8  # skip file header (type,headerSize,size)
    strings = []
    elems = []
    while p + 8 <= len(data):
        ctype, hsize, csize = struct.unpack_from('<HHI', data, p)
        if csize == 0:
            break
        if ctype == 0x0001:  # string pool
            cnt, style_cnt, flags, strings_start, styles_start = struct.unpack_from('<IIIII', data, p + 8)
            offs = [struct.unpack_from('<I', data, p + 28 + 4 * i)[0] for i in range(cnt)]
            utf8 = (flags & (1 << 8)) != 0
            for off in offs:
                q = p + strings_start + off
                if utf8:
                    n = data[q]; q += 1
                    if n & 0x80:
                        q += 1
                    n = data[q]; q += 1
                    if n & 0x80:
                        n = ((n & 0x7f) << 8) | data[q]; q += 1
                    strings.append(data[q:q + n].decode('utf-8', 'replace'))
                else:
                    n = struct.unpack_from('<H', data, q)[0]; q += 2
                    if n & 0x8000:
                        n = ((n & 0x7fff) << 16) | struct.unpack_from('<H', data, q)[0]; q += 2
                    strings.append(data[q:q + 2 * n].decode('utf-16le', 'replace'))
        elif ctype == 0x0102:  # start element
            # chunk: header(8) + lineNumber(4) + comment(4) + ns(4) + name(4) + attrStart(2)+attrSize(2)+attrCount(2)+...
            name_idx = struct.unpack_from('<I', data, p + 20)[0]
            attr_start, attr_size, attr_count = struct.unpack_from('<HHH', data, p + 24)
            attrs = []
            for i in range(attr_count):
                ap = p + 16 + attr_start + i * attr_size
                ns_idx, aname_idx, raw_idx = struct.unpack_from('<III', data, ap)
                dtype = data[ap + 15]
                dval = struct.unpack_from('<I', data, ap + 16)[0]
                aname = strings[aname_idx] if aname_idx < len(strings) else '?%d' % aname_idx
                if raw_idx != 0xFFFFFFFF and raw_idx < len(strings):
                    val = strings[raw_idx]
                elif dtype == 0x12:  # INT_BOOLEAN
                    val = 'true' if dval else 'false'
                elif dtype == 0x10:  # INT_DEC
                    val = str(dval)
                elif dtype == 0x11:  # INT_HEX
                    val = hex(dval)
                elif dtype == 0x03:
                    val = strings[dval] if dval < len(strings) else '?'
                else:
                    val = '<type=0x%02x data=0x%08x>' % (dtype, dval)
                attrs.append((aname, val))
            ename = strings[name_idx] if name_idx < len(strings) else '?%d' % name_idx
            elems.append((ename, attrs))
        p += csize
    return elems

def dump_apk(apk, outdir):
    os.makedirs(outdir, exist_ok=True)
    z = zipfile.ZipFile(apk)
    names = z.namelist()
    lines = ['# APK: ' + apk, '# entries: %d' % len(names), '']
    for n in names:
        i = z.getinfo(n)
        lines.append('%12d  %s' % (i.file_size, n))
    open(os.path.join(outdir, 'apk_entries.txt'), 'w', encoding='utf-8').write('\n'.join(lines))

    # manifest
    mout = ['# AndroidManifest.xml AXML 解析: ' + apk, '']
    try:
        man = z.read('AndroidManifest.xml')
        elems = parse_axml(man)
        if elems is None:
            mout.append('!! 不是 RES_XML 格式')
        else:
            for ename, attrs in elems:
                mout.append('<%s> %s' % (ename, '; '.join('%s=%s' % a for a in attrs)))
    except KeyError:
        mout.append('!! APK 内没有 AndroidManifest.xml')
    open(os.path.join(outdir, 'manifest_parsed.txt'), 'w', encoding='utf-8').write('\n'.join(mout))

    # dex strings
    dex_names = sorted([n for n in names if re.match(r'classes\d*\.dex$', n)])
    allstr = []
    counts = {}
    for dn in dex_names:
        s = dex_strings(z.read(dn))
        counts[dn] = len(s)
        allstr.extend(s)
    open(os.path.join(outdir, 'dex_strings_all.txt'), 'w', encoding='utf-8').write('\n'.join(allstr))

    kws = ['python', 'starpy', 'chaquopy', 'sl4a', '.py', 'py_', 'Py_', 'popen', 'getruntime',
           'exec', 'serversocket', '10086', '8890', '7777', '9999', '/dev/tty', 'ttymt', 'sdcard',
           'programa', '我的程序', 'librobot', 'robot.h', 'program_c', 'debuggable', 'su', 'shell']
    hit = {}
    for s in allstr:
        ls = s.lower()
        for k in kws:
            if k in ls:
                hit.setdefault(k, set()).add(s)
    kout = ['# dex 字符串关键字命中（全小写匹配） 文件: ' + str(counts), '']
    for k in kws:
        hs = sorted(hit.get(k, []))
        kout.append('## %-14s %d 条' % (k, len(hs)))
        kout.extend('   ' + h for h in hs[:120])
        kout.append('')
    open(os.path.join(outdir, 'dex_keyword_hits.txt'), 'w', encoding='utf-8').write('\n'.join(kout))
    return {'entries': len(names), 'dex': counts, 'strings': len(allstr)}

if __name__ == '__main__':
    apk = sys.argv[1]
    outdir = sys.argv[2]
    r = dump_apk(apk, outdir)
    print(json.dumps(r, ensure_ascii=False))
