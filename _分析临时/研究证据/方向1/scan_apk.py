# -*- coding: utf-8 -*-
"""方向1 证据提取：扫描机器人端 APK (BlocklyC_V103.apk) 的 dex/so/layout，找端口/UART/I2C/EEPROM 相关字符串。
只做只读提取，输出到同目录。"""
import zipfile, re, os, sys

sys.stdout.reconfigure(encoding='utf-8')

APK = r'D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\StreamingAssets\update\BlocklyC_V103.apk'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'BlocklyC_V103_apk')
os.makedirs(OUT, exist_ok=True)

TARGETS = [
    'classes.dex',
    'lib/armeabi-v7a/libserial_port.so',
    'res/layout/activity_eeprom.xml',
    'res/layout/activity_sensor.xml',
    'res/layout/activity_main.xml',
    'res/layout/activity_usb_test.xml',
    'res/layout/activity_javascript.xml',
    'res/xml/device_filter.xml',
]
z = zipfile.ZipFile(APK)
for n in TARGETS:
    data = z.read(n)
    fn = os.path.join(OUT, n.replace('/', '_'))
    with open(fn, 'wb') as f:
        f.write(data)
    print('wrote', fn, len(data))

# 1) dex 字符串扫描
dex = z.read('classes.dex')
strs = [s.decode('ascii', 'ignore') for s in re.findall(rb'[\x20-\x7e]{4,}', dex)]
KEYS = ['uart', 'i2c', '485', 'baud', 'eeprom', 'sendcmd', 'recvcmd', 'libstarpy', 'starpy',
        'gpio', 'serialport', 'serial_port', 'getai', 'setdo', 'getee', 'setee', 'gettouch',
        'jar', 'lua', 'python', 'rhino', 'blockly', 'usbserial', 'ftdi', 'ch34', 'cp21',
        'jni', 'native', 'sensor', 'port1', 'setport', 'portmode', 'port_mode']
print('\n===== dex keyword strings =====')
seen = set()
for s in strs:
    ls = s.lower()
    for k in KEYS:
        if k in ls:
            if s not in seen:
                seen.add(s)
                print(repr(s))
            break
print('total dex strings:', len(strs))

# 2) dex 里的类/方法名（L...; 形式）
print('\n===== dex class refs (abilix/robotrelated) =====')
cls = set(re.findall(r'L[a-zA-Z0-9_/$]+;', dex.decode('latin-1')))
for c in sorted(cls):
    lc = c.lower()
    if any(k in lc for k in ['abilix', 'robot', 'serial', 'eeprom', 'blockly', 'usb', 'sensor', 'native']):
        print(c)

# 3) so 字符串扫描
print('\n===== libserial_port.so strings =====')
so = z.read('lib/armeabi-v7a/libserial_port.so')
for s in re.findall(rb'[\x20-\x7e]{4,}', so):
    print(repr(s.decode('ascii', 'ignore')))
