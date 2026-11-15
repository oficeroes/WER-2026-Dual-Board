# -*- coding: utf-8 -*-
"""
srhs工具.py —— AbilixScratch3.0 项目文件 (.srh / .srhs) 读写工具库
====================================================================

本文件既是**可 import 的工具库**，也是**命令行工具**。

格式来源（均已用 C# 反编译源码 + 真实样本核实，见 `逆向资料/decompiled/Assembly-CSharp.decompiled.cs`）：
  * `.srh`（项目 XML 包装格式），C# 类 `PartnerX.Abilix.PCScratch.Model.ScratchProject`：
        <Abilix.ScratchProject.Info>
        {XmlSerializer 序列化出的 ScratchProjectInfo XML（含 <?xml?> 声明、CRLF）}
        </Abilix.ScratchProject.Info>
        <空行>
        <Abilix.ScratchProject.ProjectString>
        {Blockly 项目 XML：<xml xmlns="http://www.w3.org/1999/xhtml">...}
        </Abilix.ScratchProject.ProjectString>
    - 文件编码 UTF-8（**无 BOM**，C# 用 `Encoding.UTF8.GetBytes` 写出）；
    - 读取时按首对标记截取并 Trim()，因此**结束标记之后的任何内容都会被忽略**（真实样本尾部确有垃圾字节）；
    - 两段标记之间为 "\n\n"（单个 LF 空行）；Info 内部换行为 CRLF（XmlSerializer 默认）。
  * `.srhs`（项目压缩包，C# 类 `ZipHelper`，SharpZipLib 实现）：
    - zip 格式；条目名 = `abilixProject.srh`；条目内容 = 上面的 .srh 文本；
    - **zip 注释 = 机器人类型枚举数字**：SKCON2=112、SKCON5=110、SKCON9=111（`ZipHelper.CreateZip` 的 zipCommnent 参数）；
    - 压缩方式 deflate（SetLevel(6)），真实样本 create_system=0、external_attr=0；
    - 打开项目时用注释里的数字判断机器人类型（`TryOpenProject`），不匹配会弹窗提示切换。

`browser_assets`（zfbRes_v1 二进制打包格式）相关代码在 `新建默认模板_可选/patch_browser_assets.py`，不在本文件。

命令示例
--------
    # 查看项目信息 / 校验
    python srhs工具.py info WER函数库.srhs
    python srhs工具.py validate WER函数库.srhs _分析临时/PI/abilixProject.srh

    # 解包 / 打包（.srhs <-> .srh）
    python srhs工具.py unpack WER函数库.srhs out.srh
    python srhs工具.py pack out.srh out.srhs --robot SKCON9 --program WER函数库

    # 打包再解包自检（读取 .srhs -> 解析 -> 重新打包 -> 再读取，逐项比对）
    python srhs工具.py roundtrip WER函数库.srhs

    # 从项目文件抽取“新建默认模板 defaultcode 片段”（去掉 <variables>，保留全部顶层 block）
    python srhs工具.py extract-defaultcode WER函数库.srh out_defaultcode.xml

在其它脚本中 import
-------------------
本文件文件名含中文，推荐用下面的通用写法加载：

    import importlib.util, os
    def load_srhs_tool():
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, 'srhs工具.py')
        spec = importlib.util.spec_from_file_location('srhs_tool', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    srhs_tool = load_srhs_tool()
    srh = srhs_tool.read_project_file('WER函数库.srhs')   # -> SrhFile
    print(srh.robot_type, srh.download_program_name)

作者：集成工具工程师（integration）。依赖：仅 Python 标准库。文件编码 UTF-8。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape as _xml_escape


# ============================================================================
# 一、常量
# ============================================================================

#: .srh 包装格式的四个标记（C# ScratchProject 常量，顺序与大小写完全一致）
INFO_START = '<Abilix.ScratchProject.Info>'
INFO_END = '</Abilix.ScratchProject.Info>'
PROJ_START = '<Abilix.ScratchProject.ProjectString>'
PROJ_END = '</Abilix.ScratchProject.ProjectString>'

#: .srhs zip 里的唯一项目文件名
PROJECT_ENTRY_NAME = 'abilixProject.srh'

#: 机器人类型 <-> zip 注释数字（C# RobotType 枚举）
ROBOT_CODE_BY_TYPE: Dict[str, int] = {'SKCON2': 112, 'SKCON5': 110, 'SKCON9': 111}
ROBOT_TYPE_BY_CODE: Dict[int, str] = {v: k for k, v in ROBOT_CODE_BY_TYPE.items()}

#: 默认值（与 IDE 新建项目一致）
DEFAULT_VERSION = '1.0.3.4'
DEFAULT_ROBOT_TYPE = 'SKCON9'
DEFAULT_PROGRAM_NAME = 'ProgramA'

#: Blockly 项目 XML 命名空间
BLOCKLY_XMLNS = 'http://www.w3.org/1999/xhtml'
_XSI = 'http://www.w3.org/2001/XMLSchema-instance'
_XSD = 'http://www.w3.org/2001/XMLSchema'

#: 项目 XML 里的空工作区（用于新建项目）
EMPTY_PROJECT_XML = '<xml xmlns="%s"></xml>' % BLOCKLY_XMLNS

#: 函数定义块类型
DEF_BLOCK_TYPES = ('procedures_defnoreturn', 'procedures_defreturn')
DEFNORETURN = 'procedures_defnoreturn'
DEFRETURN = 'procedures_defreturn'
START_BLOCK = 'start'

_TAG_RE = re.compile(r'<([A-Za-z_][A-Za-z0-9_.\-]*)')
_ANY_TAG_RE = re.compile(r'<(/)?([A-Za-z_][A-Za-z0-9_.\-]*)([^>]*?)(/?)>')
_BLOCK_TYPE_RE = re.compile(r'<block\b[^>]*?\btype="([^"]*)"')
_FIELD_NAME_RE = re.compile(r'<field\s+name="NAME">([^<]*)</field>')
_MUTATION_RE = re.compile(r'<mutation\b([^>]*)>(.*?)</mutation>', re.S)
_ARG_RE = re.compile(r'<arg\s+name="([^"]*)"')
_VAR_DECL_RE = re.compile(r'<variable\b([^>]*)>([^<]*)</variable>')
_VAR_FIELD_RE = re.compile(r'<field\s+name="VAR"([^>]*?)>([^<]*)</field>')
_ATTR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_.:\-]*)\s*=\s*"([^"]*)"')


# ============================================================================
# 二、小工具
# ============================================================================

def setup_console() -> None:
    """让 Windows 控制台用 UTF-8 输出中文（避免 GBK 编码报错）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]
        except Exception:
            pass


def now_timestamp_ms() -> str:
    """与 C# `TimeUtil.GetNowTimestamp()` 一致：Unix 毫秒时间戳（13 位字符串）。"""
    return str(int(time.time() * 1000))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_text_utf8(path: str) -> str:
    """读 UTF-8 文本（自动去掉可能存在的 BOM）。"""
    with open(path, 'rb') as f:
        raw = f.read()
    return decode_utf8(raw)


def decode_utf8(raw: bytes) -> str:
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    return raw.decode('utf-8')


def write_text_utf8(path: str, text: str, bom: bool = False) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    data = text.encode('utf-8')
    if bom:
        data = b'\xef\xbb\xbf' + data
    with open(path, 'wb') as f:
        f.write(data)


def xml_unescape(text: str) -> str:
    return (text.replace('&lt;', '<').replace('&gt;', '>')
            .replace('&quot;', '"').replace('&apos;', "'")
            .replace('&amp;', '&'))


def xml_attr_escape(value: str) -> str:
    return _xml_escape(value, {'"': '&quot;'})


def _localname(tag: str) -> str:
    """去掉 ElementTree 命名空间前缀（{ns}tag -> tag）。"""
    if tag.startswith('{'):
        return tag.split('}', 1)[1]
    return tag


def _fmt_bytes(n: int) -> str:
    if n >= 1024 * 1024:
        return '%.2f MB' % (n / 1024 / 1024)
    if n >= 1024:
        return '%.1f KB' % (n / 1024)
    return '%d B' % n


def _new_id() -> str:
    """生成一个 Blockly 风格的随机 id（字母数字混合）。"""
    import random
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(random.choice(alphabet) for _ in range(20))


# ============================================================================
# 三、机器人类型
# ============================================================================

def normalize_robot_type(value: Any) -> str:
    """接受 'SKCON9' / 'skcon9' / 111 / '111'，返回规范类型名。未知时抛 ValueError。"""
    if isinstance(value, int):
        if value in ROBOT_TYPE_BY_CODE:
            return ROBOT_TYPE_BY_CODE[value]
        raise ValueError('未知的机器人类型编号: %r（应为 110/111/112）' % (value,))
    text = str(value).strip()
    if not text:
        raise ValueError('机器人类型为空')
    if text.isdigit():
        return normalize_robot_type(int(text))
    upper = text.upper()
    if upper in ROBOT_CODE_BY_TYPE:
        return upper
    raise ValueError('未知的机器人类型: %r（可写 SKCON2/SKCON5/SKCON9 或 112/110/111）' % (value,))


def robot_code_of(value: Any) -> int:
    """返回机器人类型的枚举数字（112/110/111）。"""
    return ROBOT_CODE_BY_TYPE[normalize_robot_type(value)]


# ============================================================================
# 四、Info 段（ScratchProjectInfo）
# ============================================================================

_INFO_XML_TEMPLATE = (
    '<?xml version="1.0" encoding="utf-8"?>\r\n'
    '<ScratchProjectInfo xmlns:xsi="{xsi}" xmlns:xsd="{xsd}">\r\n'
    '  <Version>{version}</Version>\r\n'
    '  <RobotType>{robot_type}</RobotType>\r\n'
    '  <DownloadProgramName>{program_name}</DownloadProgramName>\r\n'
    '{ai_pairs}'
    '</ScratchProjectInfo>'
)


def make_info_xml(robot_type: Any = DEFAULT_ROBOT_TYPE,
                  version: str = DEFAULT_VERSION,
                  download_program_name: str = DEFAULT_PROGRAM_NAME,
                  ai_pairs: Optional[Sequence[Tuple[str, str]]] = None) -> str:
    """
    生成 Info 段 XML 文本（复刻 C# XmlSerializer 的输出：CRLF、两空格缩进、无 BOM、无结尾换行）。

    ai_pairs: 可选 [(blockID, aiFileName), ...]，对应 ScratchProjectInfo.AIBlockIDAIFileNamePairList
              （普通项目为空，不输出该节点，与真实样本一致）。
    """
    rt = normalize_robot_type(robot_type)
    ai_xml = ''
    if ai_pairs:
        lines = ['  <AIBlockIDAIFileNamePairList>\r\n']
        for block_id, file_name in ai_pairs:
            lines.append('    <AIBlockIDAIFileNamePair>\r\n')
            lines.append('      <blockID>%s</blockID>\r\n' % _xml_escape(str(block_id)))
            lines.append('      <aiFileName>%s</aiFileName>\r\n' % _xml_escape(str(file_name)))
            lines.append('    </AIBlockIDAIFileNamePair>\r\n')
        lines.append('  </AIBlockIDAIFileNamePairList>\r\n')
        ai_xml = ''.join(lines)
    return _INFO_XML_TEMPLATE.format(
        xsi=_XSI, xsd=_XSD,
        version=_xml_escape(version),
        robot_type=rt,
        program_name=_xml_escape(download_program_name),
        ai_pairs=ai_xml,
    )


def parse_info_xml(info_xml: str) -> Dict[str, Any]:
    """
    解析 Info 段 XML，返回 dict：
        {'version': str, 'robot_type': str, 'download_program_name': str,
         'ai_pairs': [(blockID, aiFileName), ...]}
    解析失败抛 ValueError（含中文说明）。
    """
    text = (info_xml or '').strip()
    if not text:
        raise ValueError('Info 段为空')
    # 去掉 <?xml ...?> 声明后再交给 ElementTree（ET 也能直接解析带声明的字符串，这里统一处理更稳）
    if text.startswith('<?xml'):
        k = text.find('?>')
        if k >= 0:
            text = text[k + 2:].strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError('Info 段 XML 解析失败: %s\n内容片段: %r' % (exc, text[:300]))
    if _localname(root.tag) != 'ScratchProjectInfo':
        raise ValueError('Info 段根节点应为 ScratchProjectInfo，实际为 %r' % root.tag)

    def _child_text(name: str) -> str:
        for node in root:
            if _localname(node.tag) == name:
                return (node.text or '').strip()
        return ''

    robot_type_raw = _child_text('RobotType')
    try:
        robot_type = normalize_robot_type(robot_type_raw) if robot_type_raw else ''
    except ValueError:
        robot_type = robot_type_raw  # 保留原始值，交给校验报告

    ai_pairs: List[Tuple[str, str]] = []
    for node in root:
        if _localname(node.tag) != 'AIBlockIDAIFileNamePairList':
            continue
        for pair in node:
            block_id = file_name = ''
            for f in pair:
                if _localname(f.tag) == 'blockID':
                    block_id = (f.text or '').strip()
                elif _localname(f.tag) == 'aiFileName':
                    file_name = (f.text or '').strip()
            ai_pairs.append((block_id, file_name))

    return {
        'version': _child_text('Version'),
        'robot_type': robot_type,
        'download_program_name': _child_text('DownloadProgramName'),
        'ai_pairs': ai_pairs,
    }


# ============================================================================
# 五、.srh 文本解析 / 生成
# ============================================================================

class SrhFile(object):
    """一个 .srh 项目（Info 段 + ProjectString 段）。"""

    __slots__ = ('info', 'info_xml', 'project_xml', 'source_path', 'kind', 'raw_comment')

    def __init__(self, info: Dict[str, Any], info_xml: str, project_xml: str,
                 source_path: str = '', kind: str = 'srh', raw_comment: Optional[str] = None):
        self.info = info
        self.info_xml = info_xml
        self.project_xml = project_xml
        self.source_path = source_path
        self.kind = kind
        self.raw_comment = raw_comment  # .srhs 的 zip 注释（字符串），.srh 为 None

    # -- 便捷属性 -----------------------------------------------------------
    @property
    def version(self) -> str:
        return self.info.get('version', '')

    @property
    def robot_type(self) -> str:
        return self.info.get('robot_type', '')

    @property
    def download_program_name(self) -> str:
        return self.info.get('download_program_name', '')

    @property
    def robot_code(self) -> Optional[int]:
        try:
            return robot_code_of(self.robot_type)
        except ValueError:
            return None

    # -- 序列化 -------------------------------------------------------------
    def to_text(self) -> str:
        """生成完整 .srh 文本（与 C# GetSaveString() 逐字符一致）。"""
        return build_srh_text(self.info_xml, self.project_xml)

    def to_bytes(self) -> bytes:
        return self.to_text().encode('utf-8')

    def save(self, path: str) -> str:
        write_text_utf8(path, self.to_text())
        return path

    # -- 展示 ---------------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        info = validate_project_xml(self.project_xml)
        return {
            'source': self.source_path,
            'kind': self.kind,
            'version': self.version,
            'robot_type': self.robot_type,
            'robot_code': self.robot_code,
            'download_program_name': self.download_program_name,
            'srhs_comment': self.raw_comment,
            'project_xml_chars': len(self.project_xml),
            'top_blocks': info.get('top_block_count', 0),
            'start_blocks': info.get('start_count', 0),
            'procedures_defnoreturn': info.get('defnoreturn_names', []),
            'procedures_defreturn': info.get('defreturn_names', []),
            'variables': info.get('variable_names', []),
            'project_xml_ok': info.get('ok', False),
            'project_xml_errors': info.get('errors', []),
        }

    def __repr__(self) -> str:  # pragma: no cover
        return '<SrhFile robot=%s program=%r blocks=%d>' % (
            self.robot_type, self.download_program_name, self.project_xml.count('<block '))


def build_srh_text(info_xml: str, project_xml: str) -> str:
    """按 C# GetSaveString() 拼装 .srh 文本（两段之间一个 LF 空行，末尾无换行）。"""
    info_xml = (info_xml or '').strip()
    project_xml = (project_xml or '').strip()
    if not info_xml:
        raise ValueError('info_xml 为空')
    if not project_xml:
        raise ValueError('project_xml 为空')
    return (INFO_START + '\n' + info_xml + '\n' + INFO_END + '\n\n'
            + PROJ_START + '\n' + project_xml + '\n' + PROJ_END)


def parse_srh_text(text: str, source_path: str = '') -> SrhFile:
    """
    解析 .srh 文本（或 .srhs 里解出的 abilixProject.srh 内容）。

    与 C# 一致：用**第一对**标记截取，中间内容 Trim()。
    结束标记之后的内容（真实文件里偶尔存在）一律忽略。
    解析失败抛 ValueError（含中文说明）。
    """
    if not isinstance(text, str):
        raise TypeError('parse_srh_text 需要 str，实际 %r' % type(text))
    text = text.lstrip('\ufeff')
    i1 = text.find(INFO_START)
    i2 = text.find(INFO_END)
    if i1 < 0 or i2 < 0 or i2 <= i1:
        raise ValueError(
            '不是合法的 .srh 内容：找不到 Info 段标记 %r / %r。\n'
            '提示：.srhs 请先用 unpack 解包；若是 .srh 文件请确认没有传错路径。'
            % (INFO_START, INFO_END))
    info_xml = text[i1 + len(INFO_START):i2].strip()

    i3 = text.find(PROJ_START)
    i4 = text.find(PROJ_END)
    if i3 < 0 or i4 < 0 or i4 <= i3:
        raise ValueError('不是合法的 .srh 内容：找不到 ProjectString 段标记 %r / %r。'
                         % (PROJ_START, PROJ_END))
    project_xml = text[i3 + len(PROJ_START):i4].strip()

    info = parse_info_xml(info_xml)
    # 项目 XML 至少要是可解析的 XML（具体结构校验交给 validate_project_xml）
    try:
        ET.fromstring(project_xml)
    except ET.ParseError as exc:
        raise ValueError('ProjectString 段不是合法 XML: %s\n内容片段: %r'
                         % (exc, project_xml[:300]))
    return SrhFile(info=info, info_xml=info_xml, project_xml=project_xml,
                   source_path=source_path)


def new_srh(robot_type: Any = DEFAULT_ROBOT_TYPE,
            program_name: str = DEFAULT_PROGRAM_NAME,
            project_xml: str = EMPTY_PROJECT_XML,
            version: str = DEFAULT_VERSION) -> SrhFile:
    """构造一个新的 .srh 对象（空工作区或指定项目 XML）。"""
    rt = normalize_robot_type(robot_type)
    info_xml = make_info_xml(rt, version, program_name)
    return SrhFile(info=parse_info_xml(info_xml), info_xml=info_xml,
                   project_xml=project_xml.strip())


# ============================================================================
# 六、.srhs 打包 / 解包
# ============================================================================

def _zip_entry_info(now: Optional[time.struct_time] = None) -> zipfile.ZipInfo:
    """构造与 SharpZipLib 写出的条目属性一致的 ZipInfo。"""
    lt = now or time.localtime()
    zi = zipfile.ZipInfo(PROJECT_ENTRY_NAME, date_time=tuple(lt[:6]))
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.create_system = 0       # 真实样本 create_system=0
    zi.external_attr = 0       # 真实样本 external_attr=0
    return zi


def pack_srhs(srh: Any, out_path: str, robot: Any = None,
              extra_files: Optional[Dict[str, bytes]] = None,
              verify: bool = True) -> Dict[str, Any]:
    """
    把 .srh 文本/对象/路径打包成 .srhs。

    参数
    ----
    srh : SrhFile | str | bytes
        可以是 SrhFile 对象、完整的 .srh 文本、或 .srh 文件路径。
    out_path : 输出 .srhs 路径。
    robot : 机器人类型（SKCON9/111/...），默认取 info 段里的 RobotType。
    extra_files : 可选，额外打包进 zip 的条目 {zip内名称: bytes}。
        说明：IDE 保存项目时会把临时项目目录下所有文件打进 zip（如 AbilixAIFiles/），
        一般留空即可。
    verify : 打包后是否立即读回校验（默认 True，失败抛 RuntimeError）。

    返回：打包报告 dict（含 comment / 条目 / 大小 / sha256）。
    """
    if isinstance(srh, SrhFile):
        obj = srh
        text = srh.to_text()
    elif isinstance(srh, bytes):
        text = decode_utf8(srh)
        obj = parse_srh_text(text)
    elif isinstance(srh, str):
        if ('\n' not in srh) and os.path.isfile(srh):
            # 传入的是文件路径：.srhs 会先解包再重打包
            loaded = load_any_project(srh)
            obj = loaded['srh']
            text = obj.to_text()
        else:
            text = srh
            obj = parse_srh_text(text)
    else:
        raise TypeError('pack_srhs 的 srh 参数类型不支持: %r' % type(srh))

    robot_type = normalize_robot_type(robot if robot is not None else obj.robot_type)
    code = ROBOT_CODE_BY_TYPE[robot_type]

    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    data_bytes = text.encode('utf-8')
    entries: List[Tuple[str, bytes]] = [(PROJECT_ENTRY_NAME, data_bytes)]
    for name, blob in (extra_files or {}).items():
        entries.append((name, blob))

    tmp_path = out_path + '.tmp-%d' % os.getpid()
    try:
        with zipfile.ZipFile(tmp_path, 'w', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as zf:
            for name, blob in entries:
                if name == PROJECT_ENTRY_NAME:
                    zi = _zip_entry_info()
                else:
                    lt = time.localtime()
                    zi = zipfile.ZipInfo(name, date_time=tuple(lt[:6]))
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zi.create_system = 0
                    zi.external_attr = 0
                zf.writestr(zi, blob)
            zf.comment = str(code).encode('ascii')
        os.replace(tmp_path, out_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    report: Dict[str, Any] = {
        'ok': True,
        'path': out_path,
        'robot_type': robot_type,
        'robot_code': code,
        'comment': str(code),
        'entries': [name for name, _ in entries],
        'srh_sha256': sha256_bytes(data_bytes),
        'srh_bytes': len(data_bytes),
        'zip_bytes': os.path.getsize(out_path),
        'zip_sha256': sha256_file(out_path),
    }
    if verify:
        v = validate_srhs(out_path)
        report['verify'] = v
        if not v.get('ok'):
            raise RuntimeError('打包出的 .srhs 自检失败：\n  - ' + '\n  - '.join(v.get('errors', []))
                               + '\n文件：' + out_path)
        # 读回内容必须与写入文本逐字节一致
        rt = read_srhs_file(out_path)
        if rt['srh_bytes'] != data_bytes:
            raise RuntimeError('打包出的 .srhs 读回内容与写入内容不一致：%s' % out_path)
    return report


def read_srhs_file(srhs_path: str) -> Dict[str, Any]:
    """
    读取 .srhs（不落盘），返回 dict：
        {'path','comment_raw','comment_code','comment_robot_type','names','main_name',
         'srh_bytes','srh': SrhFile,'extra_files': {name: bytes},
         'errors': [], 'warnings': []}
    zip 损坏时抛 ValueError。
    """
    srhs_path = os.path.abspath(srhs_path)
    if not os.path.isfile(srhs_path):
        raise ValueError('文件不存在：%s' % srhs_path)
    if not zipfile.is_zipfile(srhs_path):
        raise ValueError('不是有效的 zip / .srhs 文件：%s' % srhs_path)
    try:
        with zipfile.ZipFile(srhs_path) as zf:
            names = zf.namelist()
            comment_raw = zf.comment
            extra: Dict[str, bytes] = {}
            for name in names:
                if name in (PROJECT_ENTRY_NAME,):
                    continue
                extra[name] = zf.read(name)
            if PROJECT_ENTRY_NAME in names:
                main_name = PROJECT_ENTRY_NAME
            elif len(names) == 1:
                main_name = names[0]
            else:
                raise ValueError('.srhs 内找不到 %r 条目（实际条目: %r）'
                                 % (PROJECT_ENTRY_NAME, names[:20]))
            srh_bytes = zf.read(main_name)
    except zipfile.BadZipFile as exc:
        raise ValueError('.srhs 不是有效的 zip：%s（%s）' % (srhs_path, exc))

    errors: List[str] = []
    warnings: List[str] = []
    comment_text = ''
    comment_code: Optional[int] = None
    comment_robot: Optional[str] = None
    if comment_raw:
        comment_text = comment_raw.decode('utf-8', 'replace')
        try:
            comment_code = int(comment_text.strip())
        except ValueError:
            errors.append('zip 注释不是数字：%r（IDE 会解析失败）' % comment_text)
        if comment_code is not None:
            if comment_code in ROBOT_TYPE_BY_CODE:
                comment_robot = ROBOT_TYPE_BY_CODE[comment_code]
            else:
                errors.append('zip 注释 %d 不是已知机器人类型（应为 110/111/112）' % comment_code)
    else:
        errors.append('zip 没有注释；IDE 打开时会因解析机器人类型失败')

    if comment_robot:
        errors_hint = None  # 占位，便于断点调试
    if len(names) != 1:
        warnings.append('zip 内有 %d 个条目（IDE 保存的项目通常只有 1 个，额外条目可能是 AbilixAIFiles）: %r'
                        % (len(names), names[:20]))

    try:
        text = decode_utf8(srh_bytes)
        srh = parse_srh_text(text, source_path=srhs_path)
        srh.kind = 'srhs'
        srh.raw_comment = comment_text
    except ValueError as exc:
        errors.append('abilixProject.srh 内容解析失败：%s' % exc)
        srh = None  # type: ignore[assignment]

    return {
        'path': srhs_path,
        'comment_raw': comment_raw,
        'comment_text': comment_text,
        'comment_code': comment_code,
        'comment_robot_type': comment_robot,
        'names': names,
        'main_name': main_name,
        'srh_bytes': srh_bytes,
        'srh': srh,
        'extra_files': extra,
        'errors': errors,
        'warnings': warnings,
    }


def unpack_srhs(srhs_path: str, out_srh_path: Optional[str] = None,
                extra_dir: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    """
    解包 .srhs。

    参数
    ----
    out_srh_path : 可选，把主条目 abilixProject.srh 写到该路径（.srh）。
    extra_dir : 可选，把其它条目（若有）按原路径写到该目录。
    force : 目标已存在时是否覆盖。

    返回读包报告（同 read_srhs_file，额外含 'written_srh' / 'written_extra'）。
    """
    info = read_srhs_file(srhs_path)
    result = dict(info)
    result['written_srh'] = None
    result['written_extra'] = []
    if out_srh_path:
        out_srh_path = os.path.abspath(out_srh_path)
        if os.path.exists(out_srh_path) and not force:
            raise FileExistsError('目标文件已存在（加 --force 覆盖）：%s' % out_srh_path)
        os.makedirs(os.path.dirname(out_srh_path) or '.', exist_ok=True)
        with open(out_srh_path, 'wb') as f:
            f.write(info['srh_bytes'])
        result['written_srh'] = out_srh_path
    if extra_dir:
        extra_dir = os.path.abspath(extra_dir)
        for name, blob in info['extra_files'].items():
            rel = name.lstrip('/').replace('/', os.sep)
            dest = os.path.join(extra_dir, rel)
            if os.path.exists(dest) and not force:
                raise FileExistsError('目标文件已存在（加 --force 覆盖）：%s' % dest)
            os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
            with open(dest, 'wb') as f:
                f.write(blob)
            result['written_extra'].append(dest)
    return result


def load_any_project(path: str) -> Dict[str, Any]:
    """
    统一读取 .srh / .srhs，返回：
        {'kind': 'srh'|'srhs', 'path', 'srh': SrhFile,
         'comment_code': int|None, 'comment_robot_type': str|None,
         'srh_bytes': bytes, 'extra_files': dict, 'errors': [], 'warnings': []}
    """
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise ValueError('文件不存在：%s' % path)
    ext = os.path.splitext(path)[1].lower()
    if ext == '.srhs' or (ext != '.srh' and zipfile.is_zipfile(path)):
        info = read_srhs_file(path)
        return {
            'kind': 'srhs',
            'path': path,
            'srh': info['srh'],
            'comment_code': info['comment_code'],
            'comment_robot_type': info['comment_robot_type'],
            'srh_bytes': info['srh_bytes'],
            'extra_files': info['extra_files'],
            'errors': info['errors'],
            'warnings': info['warnings'],
        }
    raw = open(path, 'rb').read()
    text = decode_utf8(raw)
    srh = parse_srh_text(text, source_path=path)
    srh.kind = 'srh'
    return {
        'kind': 'srh',
        'path': path,
        'srh': srh,
        'comment_code': None,
        'comment_robot_type': None,
        'srh_bytes': raw,
        'extra_files': {},
        'errors': [],
        'warnings': [],
    }


def read_project_file(path: str) -> SrhFile:
    """读 .srh/.srhs 并返回 SrhFile（最常用的便捷入口）。"""
    return load_any_project(path)['srh']


# ============================================================================
# 七、项目 XML 校验 / 顶层结构拆分
# ============================================================================

def validate_info(info_xml: str) -> Dict[str, Any]:
    """校验 Info 段，返回报告 dict（不会抛异常，errors 列出问题）。"""
    errors: List[str] = []
    warnings: List[str] = []
    data: Dict[str, Any] = {}
    try:
        data = parse_info_xml(info_xml)
    except ValueError as exc:
        errors.append(str(exc))
        return {'ok': False, 'errors': errors, 'warnings': warnings, 'info': data}
    if not data.get('version'):
        warnings.append('Info 段缺少 Version')
    if not data.get('robot_type'):
        errors.append('Info 段缺少 RobotType 或取值未知')
    else:
        try:
            normalize_robot_type(data['robot_type'])
        except ValueError:
            errors.append('Info 段 RobotType 不是已知机器人类型：%r' % data['robot_type'])
    if not data.get('download_program_name'):
        warnings.append('Info 段缺少 DownloadProgramName')
    return {'ok': not errors, 'errors': errors, 'warnings': warnings, 'info': data}


def _find_element_end(text: str, start: int, tag: str) -> int:
    """
    从 text[start] 的 <tag ...> 开始，返回到该元素结束（含结束标签）的位置。

    兼容：同名标签嵌套、**自闭合标签**（如 <block .../>，真实项目里可能出现），
    以及属性值中不含 '>' 的常规 Blockly XML（Blockly 不会在属性里放 '>'）。
    """
    depth = 0
    for m in _ANY_TAG_RE.finditer(text, start):
        name = m.group(2)
        if name.lower() != tag.lower():
            continue
        is_close = m.group(1) == '/'
        is_self_closing = m.group(4) == '/'
        if is_close:
            depth -= 1
            if depth <= 0:
                return m.end()
        elif is_self_closing:
            if depth == 0:
                return m.end()
        else:
            depth += 1
    raise ValueError('XML 元素 <%s> 未闭合 @%d（片段: %r）'
                     % (tag, start, text[start:start + 120]))


def split_top_level(project_xml: str) -> Dict[str, Any]:
    """
    把项目 XML 拆成“根开标签 + 顶层片段序列 + 根闭标签”。

    返回 dict：
        root_open : '<xml xmlns="...">' 原文
        root_close: '</xml>'
        inner     : 根内部原文
        segments  : [ {'kind': 'ws'|'block'|'variables'|'comment'|其它, 'raw': 原文,
                       ('type', 'name') 由 helper 提供} ... ]  —— 保持原始顺序
        variables_segment : variables 片段（或 None）
        blocks    : [ {'raw','type','name','index'} ... ] 顶层 block 列表
        comments  : 顶层 comment 列表
    解析失败抛 ValueError。
    """
    text = (project_xml or '').strip()
    if not text:
        raise ValueError('项目 XML 为空')
    if text.startswith('<?xml'):
        k = text.find('?>')
        if k >= 0:
            text = text[k + 2:].strip()
    m = re.match(r'<xml\b[^>]*>', text)
    if not m:
        raise ValueError('项目 XML 根节点不是 <xml>：%r' % text[:120])
    root_open = m.group(0)
    close_start = text.rfind('</xml>')
    if close_start < m.end():
        raise ValueError('项目 XML 缺少 </xml> 结束标记')
    root_close = text[close_start:]
    inner = text[m.end():close_start]

    segments: List[Dict[str, Any]] = []
    blocks: List[Dict[str, Any]] = []
    comments: List[Dict[str, Any]] = []
    variables_segment: Optional[Dict[str, Any]] = None

    i = 0
    n = len(inner)
    while i < n:
        lt = inner.find('<', i)
        if lt < 0:
            if i < n:
                segments.append({'kind': 'ws', 'raw': inner[i:]})
            break
        if lt > i:
            segments.append({'kind': 'ws', 'raw': inner[i:lt]})
        mm = _TAG_RE.match(inner, lt)
        if not mm:
            raise ValueError('项目 XML 顶层片段解析失败 @%d: %r'
                             % (lt, inner[lt:lt + 80]))
        tag = mm.group(1)
        end = _find_element_end(inner, lt, tag)
        raw = inner[lt:end]
        if tag == 'variables':
            if variables_segment is not None:
                raise ValueError('项目 XML 出现多个 <variables> 根级片段')
            open_gt = raw.find('>')
            close_lt = raw.rfind('</variables>')
            variables_segment = {
                'kind': 'variables',
                'raw': raw,
                'inner': raw[open_gt + 1:close_lt],
                'index': len(segments),
            }
            segments.append(variables_segment)
        elif tag == 'block':
            seg = {
                'kind': 'block',
                'raw': raw,
                'type': parse_block_type(raw),
                'name': parse_block_name(raw),
                'index': len(segments),
            }
            blocks.append(seg)
            segments.append(seg)
        elif tag == 'comment':
            seg = {'kind': 'comment', 'raw': raw, 'index': len(segments)}
            comments.append(seg)
            segments.append(seg)
        else:
            segments.append({'kind': tag, 'raw': raw, 'index': len(segments)})
        i = end

    return {
        'root_open': root_open,
        'root_close': root_close,
        'inner': inner,
        'segments': segments,
        'variables_segment': variables_segment,
        'blocks': blocks,
        'comments': comments,
    }


def parse_block_type(raw_block_xml: str) -> str:
    m = _BLOCK_TYPE_RE.search(raw_block_xml)
    return m.group(1) if m else ''


def parse_block_name(raw_block_xml: str) -> str:
    m = _FIELD_NAME_RE.search(raw_block_xml)
    return xml_unescape(m.group(1)) if m else ''


def parse_var_refs(raw_block_xml: str) -> List[Dict[str, str]]:
    """
    提取 XML 片段里所有 `<field name="VAR" ...>名称</field>` 引用：
        [{'id':..., 'variabletype':..., 'name':...}, ...]
    """
    refs = []
    for m in _VAR_FIELD_RE.finditer(raw_block_xml):
        attrs = dict(_ATTR_RE.findall(m.group(1)))
        refs.append({
            'id': attrs.get('id', ''),
            'variabletype': attrs.get('variabletype', ''),
            'name': xml_unescape(m.group(2)),
        })
    return refs


def parse_def_args(raw_block_xml: str) -> List[str]:
    """提取 procedures_def* 块 mutation 里的参数名列表（<arg name="cm"/>）。"""
    m = _MUTATION_RE.search(raw_block_xml)
    if not m:
        return []
    return [xml_unescape(x) for x in _ARG_RE.findall(m.group(2))]


def parse_variable_decls(project_xml: str) -> List[Dict[str, str]]:
    """
    解析项目 XML 的 <variables> 声明：
        [{'type','id','name'}, ...]
    """
    try:
        split = split_top_level(project_xml)
    except ValueError:
        return []
    seg = split['variables_segment']
    if not seg:
        return []
    decls = []
    for m in _VAR_DECL_RE.finditer(seg['inner']):
        attrs = dict(_ATTR_RE.findall(m.group(1)))
        decls.append({
            'type': attrs.get('type', ''),
            'id': attrs.get('id', ''),
            'name': xml_unescape(m.group(2)),
        })
    return decls


def find_def_blocks(project_xml: str,
                    types: Sequence[str] = (DEFNORETURN,)) -> List[Dict[str, Any]]:
    """
    提取项目 XML 中**顶层**的函数定义块。

    返回 [{'type','name','raw','args','var_refs','index'}, ...]
    """
    split = split_top_level(project_xml)
    result = []
    for seg in split['blocks']:
        if seg.get('type') not in types:
            continue
        raw = seg['raw']
        result.append({
            'type': seg['type'],
            'name': parse_block_name(raw),
            'raw': raw,
            'args': parse_def_args(raw),
            'var_refs': parse_var_refs(raw),
            'index': seg['index'],
        })
    return result


def _top_level_blocks_info(project_xml: str) -> Dict[str, Any]:
    split = split_top_level(project_xml)
    type_counts: Dict[str, int] = {}
    for seg in split['blocks']:
        type_counts[seg['type']] = type_counts.get(seg['type'], 0) + 1
    def_names: List[str] = []
    defreturn_names: List[str] = []
    for seg in split['blocks']:
        if seg['type'] == DEFNORETURN:
            def_names.append(seg['name'])
        elif seg['type'] == DEFRETURN:
            defreturn_names.append(seg['name'])
    start_count = type_counts.get(START_BLOCK, 0)
    decls = parse_variable_decls(project_xml)
    return {
        'split': split,
        'block_type_counts': type_counts,
        'top_block_count': len(split['blocks']),
        'defnoreturn_names': def_names,
        'defreturn_names': defreturn_names,
        'start_count': start_count,
        'variable_decls': decls,
        'variable_names': [d['name'] for d in decls],
    }


def validate_project_xml(project_xml: str) -> Dict[str, Any]:
    """
    校验 Blockly 项目 XML 的结构，返回：
        {'ok','errors','warnings','top_block_count','block_type_counts',
         'defnoreturn_names','defreturn_names','start_count',
         'variable_names','variable_decls'}
    """
    errors: List[str] = []
    warnings: List[str] = []
    base: Dict[str, Any] = {
        'ok': False,
        'errors': errors,
        'warnings': warnings,
        'top_block_count': 0,
        'block_type_counts': {},
        'defnoreturn_names': [],
        'defreturn_names': [],
        'start_count': 0,
        'variable_names': [],
        'variable_decls': [],
    }
    text = (project_xml or '').strip()
    if not text:
        errors.append('项目 XML 为空')
        return base

    # 1) XML 语法
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        errors.append('项目 XML 不是合法 XML：%s' % exc)
        return base
    if _localname(root.tag) != 'xml':
        errors.append('项目 XML 根节点应为 <xml>，实际为 <%s>' % _localname(root.tag))
        return base
    if root.attrib.get('xmlns') not in (None, BLOCKLY_XMLNS):
        warnings.append('根节点 xmlns=%r（通常应为 %r）'
                        % (root.attrib.get('xmlns'), BLOCKLY_XMLNS))
    ns = '{' + BLOCKLY_XMLNS + '}' if root.tag.startswith('{') else ''

    # 2) 顶层结构（用文本扫描，保留原文用于后续合并/抽取）
    try:
        info = _top_level_blocks_info(text)
    except ValueError as exc:
        errors.append('项目 XML 顶层结构解析失败：%s' % exc)
        return base
    base.update({k: info[k] for k in ('top_block_count', 'block_type_counts',
                                      'defnoreturn_names', 'defreturn_names',
                                      'start_count', 'variable_names', 'variable_decls')})

    # 3) <variables> 必须在所有 block 之前（Blockly 的硬性要求）
    split = info['split']
    vars_index = None
    first_block_index = None
    for seg in split['segments']:
        if seg['kind'] == 'variables' and vars_index is None:
            vars_index = seg['index']
        if seg['kind'] == 'block' and first_block_index is None:
            first_block_index = seg['index']
    if vars_index is not None and first_block_index is not None and vars_index > first_block_index:
        errors.append('<variables> 出现在 block 之后；Blockly 加载会报错（variables 必须最先）')

    # 4) 变量 id / 名字重复检查
    seen_ids: Dict[str, str] = {}
    for d in info['variable_decls']:
        if not d['id']:
            warnings.append('存在没有 id 的变量声明：%r' % d['name'])
        elif d['id'] in seen_ids:
            errors.append('变量 id 重复：%r（%r 与 %r）' % (d['id'], seen_ids[d['id']], d['name']))
        else:
            seen_ids[d['id']] = d['name']

    # 5) 函数定义检查
    seen_def_names: Dict[str, int] = {}
    for seg in split['blocks']:
        if seg['type'] not in DEF_BLOCK_TYPES:
            continue
        name = seg['name']
        if not name:
            id_match = re.search(r'\bid="([^"]*)"', seg['raw'])
            errors.append('存在没有 NAME 字段的函数定义块（id=%s）'
                          % (id_match.group(1) if id_match else '?'))
            continue
        seen_def_names[name] = seen_def_names.get(name, 0) + 1
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
            warnings.append('函数名 %r 不是纯 ASCII 标识符；生成为 Python 函数名时可能变形' % name)
        # 参数重复
        try:
            args = parse_def_args(seg['raw'])
        except ValueError:
            args = []
        if len(args) != len(set(args)):
            errors.append('函数 %r 的 mutation 参数名重复：%r' % (name, args))
    for name, cnt in seen_def_names.items():
        if cnt > 1:
            errors.append('同名函数定义出现 %d 次：%r（会导致函数分类里出现多个同名调用块）'
                          % (cnt, name))

    # 6) 顶层块必须有 type
    for seg in split['blocks']:
        if not seg['type']:
            errors.append('存在没有 type 属性的顶层 block（片段: %r）' % seg['raw'][:120])

    base['ok'] = not errors
    return base


# ============================================================================
# 八、校验（.srh / .srhs）
# ============================================================================

def validate_srh(srh: Any) -> Dict[str, Any]:
    """校验 .srh（SrhFile / 文本 / 路径），返回报告 dict。"""
    errors: List[str] = []
    warnings: List[str] = []
    if isinstance(srh, SrhFile):
        obj = srh
    elif isinstance(srh, bytes):
        try:
            obj = parse_srh_text(decode_utf8(srh))
        except ValueError as exc:
            return {'ok': False, 'errors': [str(exc)], 'warnings': warnings}
    elif isinstance(srh, str):
        if '\n' not in srh and os.path.isfile(srh):
            try:
                obj = parse_srh_text(read_text_utf8(srh), source_path=srh)
            except ValueError as exc:
                return {'ok': False, 'errors': [str(exc)], 'warnings': warnings}
        else:
            try:
                obj = parse_srh_text(srh)
            except ValueError as exc:
                return {'ok': False, 'errors': [str(exc)], 'warnings': warnings}
    else:
        return {'ok': False, 'errors': ['不支持的输入类型: %r' % type(srh)], 'warnings': []}

    info_report = validate_info(obj.info_xml)
    errors.extend(info_report['errors'])
    warnings.extend(info_report['warnings'])
    proj_report = validate_project_xml(obj.project_xml)
    errors.extend(proj_report['errors'])
    warnings.extend(proj_report['warnings'])
    return {
        'ok': not errors,
        'errors': errors,
        'warnings': warnings,
        'info': info_report['info'],
        'project': {k: proj_report[k] for k in
                    ('top_block_count', 'block_type_counts', 'defnoreturn_names',
                     'defreturn_names', 'start_count', 'variable_names')},
    }


def validate_srhs(srhs_path: str) -> Dict[str, Any]:
    """
    校验 .srhs：zip 完整性、条目名、zip 注释机器人类型、abilixProject.srh 内容。
    返回 {'ok','errors','warnings','comment_code','comment_robot_type',
          'info','project','srh_sha256','srh_bytes'}（不会抛异常）。
    """
    errors: List[str] = []
    warnings: List[str] = []
    path = os.path.abspath(srhs_path)
    report: Dict[str, Any] = {
        'ok': False, 'errors': errors, 'warnings': warnings, 'path': path,
        'comment_code': None, 'comment_robot_type': None, 'info': {},
        'project': {}, 'srh_sha256': None, 'srh_bytes': 0,
    }
    if not os.path.isfile(path):
        errors.append('文件不存在：%s' % path)
        return report
    if not zipfile.is_zipfile(path):
        errors.append('不是有效的 zip / .srhs 文件（IDE 会打不开）：%s' % path)
        return report
    try:
        info = read_srhs_file(path)
    except ValueError as exc:
        errors.append(str(exc))
        return report
    report.update({
        'comment_code': info['comment_code'],
        'comment_robot_type': info['comment_robot_type'],
        'names': info['names'],
        'extra_files': list(info['extra_files'].keys()),
        'srh_bytes': len(info['srh_bytes']),
        'srh_sha256': sha256_bytes(info['srh_bytes']),
    })
    errors.extend(info['errors'])
    warnings.extend(info['warnings'])
    if info['srh'] is None:
        return report
    srh_report = validate_srh(info['srh'])
    errors.extend(srh_report['errors'])
    warnings.extend(srh_report['warnings'])
    report['info'] = srh_report.get('info', {})
    report['project'] = srh_report.get('project', {})
    # 注释机器人类型 vs Info.RobotType 是否一致
    crt = info.get('comment_robot_type')
    irt = (srh_report.get('info') or {}).get('robot_type', '')
    if crt and irt and crt != irt:
        warnings.append('zip 注释机器人类型 %r 与 Info.RobotType %r 不一致；'
                        'IDE 打开时会提示切换机器人类型' % (crt, irt))
    report['ok'] = not errors
    return report


def validate_any(path: str) -> Dict[str, Any]:
    """按扩展名校验 .srh / .srhs。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.srhs' or (ext != '.srh' and zipfile.is_zipfile(path)):
        return validate_srhs(path)
    return validate_srh(path)


# ============================================================================
# 九、新建默认模板 defaultcode 片段抽取
# ============================================================================

def extract_defaultcode(project_xml: str,
                        keep_variables: bool = False,
                        require_start: bool = True) -> str:
    """
    从项目 XML 抽取“新建项目默认模板 defaultcode”片段。

    规则（任务 D 要求）：
      * 去掉 <variables>（默认；keep_variables=True 时保留）；
      * 所有**顶层 block** 原样序列化；
      * 必须包含 start 块（require_start=True 时缺 start 抛 ValueError）；
      * 全部包进一个 `<xml xmlns="http://www.w3.org/1999/xhtml">` 根。

    返回单行 XML 文本（可直接作为 maingui_init.js 里 defaultcode 字符串的内容）。
    """
    split = split_top_level(project_xml)
    blocks = split['blocks']
    if not blocks:
        raise ValueError('项目 XML 没有任何顶层 block，无法生成 defaultcode 片段')
    if require_start and not any(b.get('type') == START_BLOCK for b in blocks):
        raise ValueError('项目 XML 缺少 start 块（新建项目模板必须带 start）')
    parts = [split['root_open']]
    if keep_variables and split['variables_segment']:
        parts.append(split['variables_segment']['raw'])
    for seg in blocks:
        parts.append(seg['raw'])
    parts.append(split['root_close'])
    fragment = ''.join(parts)
    # 确保片段本身是合法 XML
    try:
        root = ET.fromstring(fragment)
    except ET.ParseError as exc:
        raise ValueError('生成的 defaultcode 片段不是合法 XML：%s' % exc)
    if _localname(root.tag) != 'xml':
        raise ValueError('生成的 defaultcode 片段根节点异常：%r' % root.tag)
    return fragment


# ============================================================================
# 十、roundtrip 自检
# ============================================================================

def roundtrip_srhs(srhs_path: str, workdir: Optional[str] = None,
                   keep_artifacts: bool = False) -> Dict[str, Any]:
    """
    .srhs 读→解析→重新打包→再读 的 roundtrip 自检。

    检查项：
      1. 原包可读、zip 注释为合法机器人类型、abilixProject.srh 可解析；
      2. 原包内 srh 字节 == 解析后再序列化的文本（逐字节）；
      3. 重新打包后：zip 注释一致、条目名一致、srh 字节一致、解析结果一致；
      4. 重新打包后再次校验通过。
    """
    srhs_path = os.path.abspath(srhs_path)
    tmpdir = workdir or tempfile.mkdtemp(prefix='srhs_roundtrip_')
    created_tmp = workdir is None
    try:
        os.makedirs(tmpdir, exist_ok=True)
        info = read_srhs_file(srhs_path)
        srh = info['srh']
        report: Dict[str, Any] = {
            'ok': False,
            'source': srhs_path,
            'workdir': tmpdir,
            'checks': [],
            'errors': [],
            'warnings': list(info['warnings']),
        }
        checks = report['checks']

        def check(name: str, cond: bool, detail: str = '') -> None:
            checks.append({'name': name, 'ok': bool(cond), 'detail': detail})
            if not cond:
                report['errors'].append('%s：%s' % (name, detail))

        check('原包可读取/解析', srh is not None,
              'srh 解析失败' if srh is None else 'robot=%s program=%r' % (srh.robot_type, srh.download_program_name))
        if srh is None:
            return report

        orig_entry_bytes = info['srh_bytes']
        orig_text = decode_utf8(orig_entry_bytes)
        end_idx = orig_text.find(PROJ_END)
        trailing = orig_text[end_idx + len(PROJ_END):] if end_idx >= 0 else ''
        reparsed_text = srh.to_text()
        if orig_entry_bytes == reparsed_text.encode('utf-8'):
            check('原包 srh 字节 == 重新序列化文本', True,
                  '%d 字节' % len(orig_entry_bytes))
        elif trailing.strip():
            # 真实样本里存在“结束标记之后的冗余字节”（C# 读取时用 IndexOf 截取，会忽略）；
            # 重打包会清除这类垃圾，此时比较“标记之前的内容”是否一致。
            canonical_orig = orig_text[:end_idx + len(PROJ_END)]
            check('原包结尾冗余字节可忽略且标记前内容一致',
                  canonical_orig == reparsed_text,
                  '结束标记后有 %d 字节冗余（IDE 读取时会忽略，重打包已清除）'
                  % len(trailing))
            report['warnings'].append(
                '原包结束标记后有 %d 字节冗余内容；IDE 读取时会忽略，重打包后已清除'
                % len(trailing))
        else:
            check('原包 srh 字节 == 重新序列化文本', False,
                  '原 %d 字节 / 重序列化 %d 字节'
                  % (len(orig_entry_bytes), len(reparsed_text.encode('utf-8'))))

        # 重新打包
        repath = os.path.join(tmpdir, 'roundtrip_rebuilt.srhs')
        pack_report = pack_srhs(srh, repath, robot=info['comment_code'] or srh.robot_type,
                                extra_files=info['extra_files'], verify=False)
        report['rebuilt_path'] = repath
        check('重新打包成功', os.path.isfile(repath), pack_report.get('path', ''))
        rebuilt = read_srhs_file(repath)
        expected_srh_bytes = reparsed_text.encode('utf-8')
        check('重新打包后 zip 注释一致',
              rebuilt['comment_code'] == info['comment_code'],
              '原 %r / 新 %r' % (info['comment_code'], rebuilt['comment_code']))
        check('重新打包后条目名一致',
              sorted(rebuilt['names']) == sorted(info['names']),
              '原 %r / 新 %r' % (info['names'], rebuilt['names']))
        check('重新打包后 srh 字节 == 解析后的规范文本',
              rebuilt['srh_bytes'] == expected_srh_bytes,
              '期望 %d / 实际 %d（原始 %d 字节）'
              % (len(expected_srh_bytes), len(rebuilt['srh_bytes']), len(orig_entry_bytes)))
        rebuilt_validate = validate_srhs(repath)
        check('重新打包后再次校验通过',
              rebuilt_validate['ok'],
              '; '.join(rebuilt_validate.get('errors', [])))
        # 项目 XML 结构等价
        try:
            p1 = validate_project_xml(srh.project_xml)
            p2 = validate_project_xml(rebuilt['srh'].project_xml) if rebuilt['srh'] else {}
            check('项目 XML 顶层结构一致',
                  p1.get('top_block_count') == p2.get('top_block_count')
                  and p1.get('defnoreturn_names') == p2.get('defnoreturn_names'),
                  'blocks %r vs %r' % (p1.get('top_block_count'), p2.get('top_block_count')))
        except ValueError as exc:
            check('项目 XML 顶层结构一致', False, str(exc))

        report['ok'] = all(c['ok'] for c in checks)
        return report
    finally:
        if created_tmp and not keep_artifacts:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================================
# 十一、CLI
# ============================================================================

def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _print_human_summary(summary: Dict[str, Any]) -> None:
    print('文件          : %s' % summary.get('source'))
    print('类型          : %s' % ('压缩项目 .srhs' if summary.get('kind') == 'srhs' else '项目 XML .srh'))
    print('版本/程序名   : %s / %s' % (summary.get('version'), summary.get('download_program_name')))
    print('机器人类型    : %s (zip注释=%s)' % (summary.get('robot_type'), summary.get('srhs_comment')))
    print('顶层块数      : %d' % summary.get('top_blocks', 0))
    print('start 块      : %d' % summary.get('start_blocks', 0))
    print('无返回值函数  : %d 个 %s' % (len(summary.get('procedures_defnoreturn', [])),
                                       summary.get('procedures_defnoreturn', [])[:10]))
    print('有返回值函数  : %d 个 %s' % (len(summary.get('procedures_defreturn', [])),
                                       summary.get('procedures_defreturn', [])[:10]))
    print('变量声明      : %d 个 %s' % (len(summary.get('variables', [])),
                                       summary.get('variables', [])[:10]))
    print('项目 XML 合法 : %s' % ('是' if summary.get('project_xml_ok') else '否'))
    for e in summary.get('project_xml_errors', []):
        print('  [错误] %s' % e)


def cmd_info(args: argparse.Namespace) -> int:
    srh = read_project_file(args.file)
    summary = srh.summary()
    if args.json:
        _print_json(summary)
    else:
        _print_human_summary(summary)
    return 0 if summary.get('project_xml_ok') else 1


def cmd_validate(args: argparse.Namespace) -> int:
    reports = []
    bad = 0
    for path in args.files:
        report = validate_any(path)
        report.setdefault('path', os.path.abspath(path))
        reports.append(report)
        if not report.get('ok'):
            bad += 1
    if args.json:
        _print_json({'ok': bad == 0, 'reports': reports})
    else:
        for report in reports:
            print('=' * 70)
            print('文件: %s' % report.get('path', report.get('source', '')))
            print('结论: %s' % ('通过' if report.get('ok') else '不通过'))
            for e in report.get('errors', []):
                print('  [错误] %s' % e)
            for w in report.get('warnings', []):
                print('  [警告] %s' % w)
            proj = report.get('project') or {}
            if proj:
                print('  顶层块=%s start=%s 无返回函数=%d 变量=%d'
                      % (proj.get('top_block_count'), proj.get('start_count'),
                         len(proj.get('defnoreturn_names', [])),
                         len(proj.get('variable_names', []))))
    return 0 if bad == 0 else 1


def cmd_unpack(args: argparse.Namespace) -> int:
    info = unpack_srhs(args.srhs, args.out, extra_dir=args.extra_dir, force=args.force)
    if args.json:
        _print_json({k: v for k, v in info.items() if k != 'extra_files'})
    else:
        print('解包成功：%s' % info['path'])
        print('  zip 注释机器人类型: %s (%s)' % (info['comment_robot_type'], info['comment_code']))
        print('  条目: %r' % info['names'])
        print('  写出 .srh: %s (%s)' % (info['written_srh'], _fmt_bytes(len(info['srh_bytes']))))
        for e in info['errors']:
            print('  [错误] %s' % e)
        for w in info['warnings']:
            print('  [警告] %s' % w)
    return 0 if not info['errors'] else 1


def cmd_pack(args: argparse.Namespace) -> int:
    report = pack_srhs(args.srh, args.out, robot=args.robot, verify=not args.no_verify)
    if args.json:
        _print_json(report)
    else:
        print('打包成功：%s' % report['path'])
        print('  机器人类型: %s (zip 注释 %s)' % (report['robot_type'], report['comment']))
        print('  zip 大小: %s   srh sha256: %s'
              % (_fmt_bytes(report['zip_bytes']), report['srh_sha256']))
        v = report.get('verify') or {}
        print('  自检: %s%s' % ('通过' if v.get('ok') else '失败',
                              '' if not v.get('errors') else (' ' + '; '.join(v['errors']))))
    return 0 if report.get('ok') else 1


def cmd_roundtrip(args: argparse.Namespace) -> int:
    report = roundtrip_srhs(args.srhs, workdir=args.workdir)
    if args.json:
        _print_json(report)
    else:
        print('roundtrip 自检：%s' % ('通过' if report['ok'] else '不通过'))
        print('  源文件: %s' % report['source'])
        for c in report.get('checks', []):
            print('  [%s] %-38s %s' % ('OK' if c['ok'] else 'FAIL', c['name'], c['detail']))
        for e in report.get('errors', []):
            print('  [错误] %s' % e)
        for w in report.get('warnings', []):
            print('  [警告] %s' % w)
    return 0 if report['ok'] else 1


def cmd_extract_defaultcode(args: argparse.Namespace) -> int:
    srh = read_project_file(args.file)
    fragment = extract_defaultcode(srh.project_xml,
                                   keep_variables=args.keep_variables,
                                   require_start=not args.allow_no_start)
    write_text_utf8(args.out, fragment)
    summary = validate_project_xml(fragment)
    if args.json:
        _print_json({'ok': True, 'out': os.path.abspath(args.out),
                     'chars': len(fragment), 'top_blocks': summary.get('top_block_count'),
                     'start_count': summary.get('start_count')})
    else:
        print('已生成 defaultcode 片段：%s' % os.path.abspath(args.out))
        print('  字符数: %d  顶层块: %d  start 块: %d'
              % (len(fragment), summary.get('top_block_count'), summary.get('start_count')))
        print('  片段开头: %s ...' % fragment[:160])
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    project_xml = EMPTY_PROJECT_XML
    if args.project_xml:
        project_xml = read_text_utf8(args.project_xml).strip()
    srh = new_srh(args.robot, args.program, project_xml, args.version)
    srh.save(args.out)
    print('已生成 .srh：%s' % os.path.abspath(args.out))
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='srhs工具.py',
        description='AbilixScratch3.0 项目文件（.srh / .srhs）读写、打包、校验、defaultcode 抽取工具。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python srhs工具.py info WER函数库.srhs\n'
               '  python srhs工具.py unpack WER函数库.srhs out.srh\n'
               '  python srhs工具.py pack out.srh out.srhs --robot SKCON9\n'
               '  python srhs工具.py roundtrip WER函数库.srhs\n'
               '  python srhs工具.py extract-defaultcode WER函数库.srh fragment.xml\n')
    sub = p.add_subparsers(dest='command', required=True)

    sp = sub.add_parser('info', help='查看项目文件信息')
    sp.add_argument('file', help='.srh 或 .srhs 路径')
    sp.add_argument('--json', action='store_true', help='输出 JSON')
    sp.set_defaults(func=cmd_info)

    sp = sub.add_parser('validate', help='校验 .srh/.srhs 是否合法（可多个）')
    sp.add_argument('files', nargs='+', help='.srh / .srhs 路径')
    sp.add_argument('--json', action='store_true', help='输出 JSON')
    sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser('unpack', help='解包 .srhs 为 .srh')
    sp.add_argument('srhs', help='输入 .srhs')
    sp.add_argument('out', help='输出 .srh 路径')
    sp.add_argument('--extra-dir', default=None, help='额外条目（若有）的输出目录')
    sp.add_argument('--force', action='store_true', help='覆盖已存在文件')
    sp.add_argument('--json', action='store_true', help='输出 JSON')
    sp.set_defaults(func=cmd_unpack)

    sp = sub.add_parser('pack', help='把 .srh 打包为 .srhs')
    sp.add_argument('srh', help='输入 .srh（或 .srhs 也可，会先读再重打包）')
    sp.add_argument('out', help='输出 .srhs 路径')
    sp.add_argument('--robot', default=None, help='机器人类型 SKCON2/SKCON5/SKCON9 或 112/110/111')
    sp.add_argument('--no-verify', action='store_true', help='跳过打包后自检（不建议）')
    sp.add_argument('--json', action='store_true', help='输出 JSON')
    sp.set_defaults(func=cmd_pack)

    sp = sub.add_parser('roundtrip', help='读->重新打包->再读 自检')
    sp.add_argument('srhs', help='输入 .srhs')
    sp.add_argument('--workdir', default=None, help='指定临时工作目录（默认自动创建并清理）')
    sp.add_argument('--json', action='store_true', help='输出 JSON')
    sp.set_defaults(func=cmd_roundtrip)

    sp = sub.add_parser('extract-defaultcode', help='抽取新建项目默认模板 defaultcode 片段')
    sp.add_argument('file', help='.srh 或 .srhs')
    sp.add_argument('out', help='输出片段 .xml 路径')
    sp.add_argument('--keep-variables', action='store_true', help='保留 <variables>（默认去掉）')
    sp.add_argument('--allow-no-start', action='store_true', help='允许片段里没有 start 块')
    sp.add_argument('--json', action='store_true', help='输出 JSON')
    sp.set_defaults(func=cmd_extract_defaultcode)

    sp = sub.add_parser('new', help='生成一个新的空项目 .srh')
    sp.add_argument('out', help='输出 .srh 路径')
    sp.add_argument('--robot', default=DEFAULT_ROBOT_TYPE, help='机器人类型（默认 SKCON9）')
    sp.add_argument('--program', default=DEFAULT_PROGRAM_NAME, help='下载程序名（默认 ProgramA）')
    sp.add_argument('--version', default=DEFAULT_VERSION, help='版本号（默认 1.0.3.4）')
    sp.add_argument('--project-xml', default=None, help='可选：用指定 XML 文件作为工作区内容')
    sp.set_defaults(func=cmd_new)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    setup_console()
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError, OSError) as exc:
        sys.stderr.write('[错误] %s\n' % exc)
        return 2


if __name__ == '__main__':
    sys.exit(main())
