# -*- coding: utf-8 -*-
"""
合并到现有项目.py —— 把「函数库项目」里的函数定义块合并进一个现有 WER/Abilix 项目
================================================================================

用途
----
把 `WER函数库.srh` / `WER函数库.srhs` 里的 **函数定义块**（`procedures_defnoreturn`，
可选 `procedures_defreturn`）以及它们用到的 **变量声明**，安全地合并进你自己已经做好的
项目（`.srh` / `.srhs`），这样项目里就多出这些函数，在 IDE「函数」分类里能直接拖动调用。

合并规则（与任务要求一致）
--------------------------
1. **同名函数已存在 → 跳过并报告**（目标项目里的同名函数保持原样，不覆盖）；
2. **变量按名字对齐**：目标里已有同名变量则复用它的 id（把合并块里的 VAR 引用重定向过去）；
   名字不存在则新增声明；若库里的变量 id 与目标里任何 id 冲突则重新生成 id；
3. **不修改**目标项目的 start 积木和其它已有块（只做“追加函数定义 + 追加变量声明”）；
4. 默认**输出新文件、不覆盖**；`--in-place` 时先自动备份；
5. 合并结果重新校验（XML 结构、函数数、变量数、块 id 唯一性），并给出差异摘要。

用法示例
--------
    # 1) 先 dry-run 看计划（不写文件）
    python 合并到现有项目.py --library WER函数库.srh --target 我的项目.srhs --dry-run

    # 2) 输出为新文件（推荐；默认输出到目标同目录的 xxx_已合并函数库.srhs）
    python 合并到现有项目.py --library WER函数库.srhs --target 我的项目.srhs

    # 3) 直接合并回原文件（会先备份为 xxx.srhs.备份-<时间>）
    python 合并到现有项目.py --library WER函数库.srhs --target 我的项目.srhs --in-place

    # 4) 只合并部分函数，并输出 JSON 报告
    python 合并到现有项目.py --library WER函数库.srhs --target 我的项目.srhs \
        --funcs func_MoveForward,func_TurnLeft --json

注意
----
* 合并后请用 IDE 打开确认「函数」分类里能看到这些函数（本工具只保证 XML 结构合法）。
* 若目标项目里已有同名函数导致跳过，而库里的其它函数又调用了被跳过的函数，
  合并后这些调用会绑定到目标项目里的同名函数（报告里会给出警告）。

作者：集成工具工程师（integration）。依赖：仅 Python 标准库 + 同目录 `srhs工具.py`。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# ----------------------------------------------------------------------------
# 加载同目录的 srhs工具.py（文件名含中文，用 importlib 显式加载最稳）
# ----------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_srhs_tool():
    path = os.path.join(_HERE, 'srhs工具.py')
    if not os.path.isfile(path):
        raise RuntimeError('找不到同目录的 srhs工具.py：%s' % path)
    spec = importlib.util.spec_from_file_location('srhs_tool', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


srhs_tool = _load_srhs_tool()

DEFNORETURN = srhs_tool.DEFNORETURN
DEFRETURN = srhs_tool.DEFRETURN
DEF_BLOCK_TYPES = srhs_tool.DEF_BLOCK_TYPES

_BLOCK_TAG_RE = re.compile(r'<(block|shadow)\b([^>]*)>')
_TAG_ID_RE = re.compile(r'\bid="([^"]*)"')
_CALL_MUTATION_RE = re.compile(r'<mutation\b[^>]*\bname="([^"]*)"')
_NAME_FIELD_RE = re.compile(r'<field\s+name="NAME">([^<]*)</field>')


# ============================================================================
# 一、通用小工具
# ============================================================================

def _backup_path(path: str) -> str:
    """生成备份路径：<path>.备份-<yyyyMMdd-HHmmss>（保留扩展名）。"""
    root, ext = os.path.splitext(path)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    candidate = '%s.备份-%s%s' % (root, stamp, ext)
    n = 1
    while os.path.exists(candidate):
        candidate = '%s.备份-%s_%d%s' % (root, stamp, n, ext)
        n += 1
    return candidate


def _collect_tag_ids(project_xml: str) -> List[str]:
    """收集 XML 中所有 id 属性值（block / shadow / field / 变量声明等，保守全集）。"""
    return _TAG_ID_RE.findall(project_xml)


def _collect_block_ids(raw: str) -> List[str]:
    """只收集 <block>/<shadow> 标签上的 id（这些才是 Blockly 的块 id）。"""
    ids = []
    for m in _BLOCK_TAG_RE.finditer(raw):
        idm = _TAG_ID_RE.search(m.group(2))
        if idm:
            ids.append(idm.group(1))
    return ids


def _make_id(reserved: Set[str]) -> str:
    while True:
        new_id = srhs_tool._new_id()
        if new_id not in reserved:
            reserved.add(new_id)
            return new_id


def rewrite_var_fields(raw: str, resolver) -> Tuple[str, int]:
    """
    重写 XML 片段里所有 `<field name="VAR" ...>` 的 id/variabletype。

    resolver(name, old_id, old_variabletype) -> (new_id, new_variabletype)
    返回 (新片段, 被改写的字段数)。
    """
    changed = 0

    def repl(match: 're.Match[str]') -> str:
        nonlocal changed
        attrs = dict(srhs_tool._ATTR_RE.findall(match.group(1)))
        name = srhs_tool.xml_unescape(match.group(2))
        old_id = attrs.get('id', '')
        old_type = attrs.get('variabletype', '')
        new_id, new_type = resolver(name, old_id, old_type)
        if new_id != old_id or new_type != old_type:
            changed += 1
        return ('<field name="VAR" id="%s" variabletype="%s">%s</field>'
                % (srhs_tool.xml_attr_escape(new_id),
                   srhs_tool.xml_attr_escape(new_type),
                   srhs_tool._xml_escape(name)))

    return srhs_tool._VAR_FIELD_RE.sub(repl, raw), changed


def rewrite_colliding_block_ids(raw: str,
                                collisions: Set[str]) -> Tuple[str, int, List[str]]:
    """
    把与 `collisions` 冲突的 <block>/<shadow> id 换成新 id。

    说明：真实 IDE 保存的项目 XML 里，**同一个 shadow 块 id 可能重复出现**
    （用户复制粘贴积木后遗留，IDE 自己能正常加载）。为了忠实保留函数库内容，
    这里只修复“与目标项目已有 id 冲突”的块；函数库内部已有的重复 id 原样保留。

    collisions : 目标项目全部 id + 之前已合并函数块用到的 id。
    返回 (新片段, 改写数, 新片段里出现的所有块 id 列表)。
    """
    changed = 0
    taken: Set[str] = set(collisions)

    def repl(match: 're.Match[str]') -> str:
        nonlocal changed
        tag = match.group(1)
        attrs = match.group(2)
        idm = _TAG_ID_RE.search(attrs)
        if not idm:
            return match.group(0)
        block_id = idm.group(1)
        if block_id not in collisions:
            taken.add(block_id)
            return match.group(0)
        new_id = _make_id(taken)
        changed += 1
        new_attrs = attrs[:idm.start(1)] + new_id + attrs[idm.end(1):]
        return '<%s%s>' % (tag, new_attrs)

    out = _BLOCK_TAG_RE.sub(repl, raw)
    return out, changed, _collect_block_ids(out)


def _extract_called_names(raw: str) -> List[str]:
    """
    提取 XML 片段里 procedures_call* 块调用的函数名。

    说明：函数调用块的 mutation 形如 <mutation name="func_xxx"></mutation>（无参数时）
    或 <mutation name="func_xxx"><arg name="cm"></arg></mutation>；函数定义块自身的
    mutation 没有 name 属性。因此直接收集所有带 name 属性的 mutation 即可。
    """
    return [srhs_tool.xml_unescape(x) for x in _CALL_MUTATION_RE.findall(raw)]


def _variable_decl_xml(decl: Dict[str, str]) -> str:
    return ('<variable type="%s" id="%s">%s</variable>'
            % (srhs_tool.xml_attr_escape(decl.get('type', '')),
               srhs_tool.xml_attr_escape(decl.get('id', '')),
               srhs_tool._xml_escape(decl.get('name', ''))))


# ============================================================================
# 二、合并核心
# ============================================================================

def merge_project_xml(target_xml: str, library_xml: str,
                      func_filter: Optional[Sequence[str]] = None,
                      include_defreturn: bool = False,
                      verbose: bool = False) -> Dict[str, Any]:
    """
    把函数库项目 XML 里的函数定义合并进目标项目 XML（纯函数，不做 IO）。

    返回 dict：
        ok, project_xml（合并后的 XML 文本）, errors, warnings, report{...}
    """
    errors: List[str] = []
    warnings: List[str] = []
    report: Dict[str, Any] = {
        'library_defs_total': 0,
        'candidate_defs': 0,
        'merged': [],
        'skipped_same_name': [],
        'filtered_out': [],
        'missing_requested': [],
        'variables_added': [],
        'variables_reused': [],
        'variables_id_remapped': [],
        'block_ids_regenerated': 0,
        'call_warnings': [],
        'target_defs_before': [],
        'target_defs_after': [],
        'target_top_blocks_before': 0,
        'target_top_blocks_after': 0,
        'target_variables_before': 0,
        'target_variables_after': 0,
    }

    # ---- 1) 解析两边的结构 ----
    try:
        lib_split = srhs_tool.split_top_level(library_xml)
        tgt_split = srhs_tool.split_top_level(target_xml)
    except ValueError as exc:
        return {'ok': False, 'project_xml': target_xml, 'errors': [str(exc)],
                'warnings': warnings, 'report': report}

    lib_types = list(DEF_BLOCK_TYPES) if include_defreturn else [DEFNORETURN]
    lib_defs = srhs_tool.find_def_blocks(library_xml, types=lib_types)
    report['library_defs_total'] = len(lib_defs)

    tgt_types = list(DEF_BLOCK_TYPES)
    tgt_defs = srhs_tool.find_def_blocks(target_xml, types=tgt_types)
    tgt_def_names = {d['name'] for d in tgt_defs}
    report['target_defs_before'] = [d['name'] for d in tgt_defs]
    report['target_top_blocks_before'] = len(tgt_split['blocks'])

    lib_decls = srhs_tool.parse_variable_decls(library_xml)
    tgt_decls = srhs_tool.parse_variable_decls(target_xml)
    report['target_variables_before'] = len(tgt_decls)

    # 目标项目里所有 id（保守全集，用于避免新 id 冲突）
    reserved_ids: Set[str] = set(_collect_tag_ids(target_xml))
    # 变量：name -> decl（同名取第一个）、id -> decl
    var_by_name: Dict[str, Dict[str, str]] = {}
    var_by_id: Dict[str, Dict[str, str]] = {}
    for decl in tgt_decls:
        if decl['name'] not in var_by_name:
            var_by_name[decl['name']] = decl
        if decl['id']:
            var_by_id[decl['id']] = decl
    lib_decl_by_id: Dict[str, Dict[str, str]] = {d['id']: d for d in lib_decls if d['id']}

    # ---- 2) 过滤候选函数 ----
    requested = list(func_filter) if func_filter else None
    candidates = []
    for d in lib_defs:
        name = d['name']
        if requested is not None and name not in requested:
            report['filtered_out'].append(name)
            continue
        if name in tgt_def_names:
            report['skipped_same_name'].append(name)
            continue
        candidates.append(d)
    if requested is not None:
        known = {d['name'] for d in lib_defs}
        report['missing_requested'] = [n for n in requested if n not in known]
        if report['missing_requested']:
            warnings.append('函数库里找不到这些指定函数（已忽略）：%r'
                            % report['missing_requested'])
    report['candidate_defs'] = len(candidates)

    # 额外提示：函数库里有返回值函数但本次未合并、有 start 块但不合并
    if not include_defreturn:
        lib_defreturn = srhs_tool.find_def_blocks(library_xml, types=[DEFRETURN])
        if lib_defreturn:
            warnings.append('函数库里有 %d 个有返回值函数（procedures_defreturn）未合并：%r；'
                            '如需合并请加 --include-defreturn'
                            % (len(lib_defreturn), [d['name'] for d in lib_defreturn]))
    if any(seg.get('type') == srhs_tool.START_BLOCK for seg in lib_split['blocks']):
        warnings.append('函数库的 start 块不参与合并（目标项目的 start 积木保持原样）')

    # ---- 3) 处理每个候选函数的变量引用 ----
    initial_var_names: Set[str] = set(var_by_name)   # 目标项目**原有**变量名
    added_var_names: Set[str] = set()
    variables_to_add: List[Dict[str, str]] = []
    merged_blocks: List[Dict[str, Any]] = []
    merged_block_ids: Set[str] = set()               # 之前已合并函数块用到的 id
    reused_recorded: Set[str] = set()
    remapped_recorded: Set[str] = set()

    for d in candidates:
        raw = d['raw']

        def resolve(name: str, old_id: str, old_vtype: str,
                    _d=d) -> Tuple[str, str]:
            """决定函数块内某个 VAR 字段最终使用的 (变量id, variabletype)。"""
            decl = var_by_name.get(name)
            if decl is not None:
                # 目标已有同名变量（或本次合并中更早加入的）：复用它的 id
                new_id = decl['id']
                new_type = decl.get('type') or old_vtype
                if name in initial_var_names and name not in reused_recorded:
                    reused_recorded.add(name)
                    report['variables_reused'].append(name)
                if old_id and old_id != new_id and name not in remapped_recorded:
                    remapped_recorded.add(name)
                    report['variables_id_remapped'].append({'name': name, 'new_id': new_id})
                return new_id, new_type
            # 目标里没有这个变量：新增声明
            lib_decl = lib_decl_by_id.get(old_id) if old_id else None
            vtype = old_vtype or (lib_decl.get('type', '') if lib_decl else '')
            if old_id and old_id not in reserved_ids and old_id not in var_by_id:
                new_id = old_id
                reserved_ids.add(new_id)
            else:
                # id 与目标项目里别的 id 冲突：重新生成（任务要求“变量 id 冲突时重建”）
                new_id = _make_id(reserved_ids)
                if old_id and name not in remapped_recorded:
                    remapped_recorded.add(name)
                    report['variables_id_remapped'].append({'name': name, 'new_id': new_id})
            decl_new = {'type': vtype, 'id': new_id, 'name': name}
            var_by_name[name] = decl_new
            var_by_id[new_id] = decl_new
            if name not in added_var_names:
                added_var_names.add(name)
                variables_to_add.append(decl_new)
                report['variables_added'].append(name)
            return new_id, vtype

        raw, _n_var_changed = rewrite_var_fields(raw, resolve)

        # 块 id 冲突处理（只修复与目标项目已有 id / 已合并函数块 id 冲突的块；
        # 函数库自身重复的 shadow id 原样保留，IDE 能正常加载）
        collisions = set(reserved_ids) | merged_block_ids
        raw, n_block_ids, ids_in_this_def = rewrite_colliding_block_ids(raw, collisions)
        report['block_ids_regenerated'] += n_block_ids
        for bid in ids_in_this_def:
            merged_block_ids.add(bid)
            reserved_ids.add(bid)

        merged_blocks.append({'name': d['name'], 'type': d['type'], 'raw': raw,
                              'args': d['args']})
        report['merged'].append({'name': d['name'], 'type': d['type'],
                                 'args': d['args']})

    # ---- 4) 调用关系警告：合并的函数调用了被跳过的函数 ----
    skipped = set(report['skipped_same_name'])
    if skipped:
        for mb in merged_blocks:
            for called in _extract_called_names(mb['raw']):
                if called in skipped:
                    msg = ('函数 %r 调用了 %r，但目标项目已有同名函数（已跳过合并）；'
                           '合并后该调用将绑定到目标项目的版本' % (mb['name'], called))
                    if msg not in report['call_warnings']:
                        report['call_warnings'].append(msg)
                        warnings.append(msg)

    # ---- 5) 重建目标项目 XML ----
    try:
        new_project_xml = _rebuild_project_xml(tgt_split, variables_to_add, merged_blocks)
    except ValueError as exc:
        errors.append('重建项目 XML 失败：%s' % exc)
        return {'ok': False, 'project_xml': target_xml, 'errors': errors,
                'warnings': warnings, 'report': report}

    # ---- 6) 重建结果校验 ----
    try:
        check = srhs_tool.validate_project_xml(new_project_xml)
    except Exception as exc:  # noqa: BLE001
        errors.append('合并结果校验异常：%s' % exc)
        check = {'ok': False, 'errors': ['校验异常'], 'top_block_count': 0}
    if not check.get('ok'):
        errors.extend(['合并结果不是合法项目 XML：%s' % e for e in check.get('errors', [])])
        return {'ok': False, 'project_xml': target_xml, 'errors': errors,
                'warnings': warnings, 'report': report}

    # 期望：目标原函数全保留 + 新增函数；原 top block 全保留
    new_def_names = set(check.get('defnoreturn_names', [])) | set(check.get('defreturn_names', []))
    expected_def_names = tgt_def_names | {mb['name'] for mb in merged_blocks}
    if new_def_names != expected_def_names:
        errors.append('合并结果函数集合不符：期望 %r，实际 %r'
                      % (sorted(expected_def_names), sorted(new_def_names)))
    expected_top = report['target_top_blocks_before'] + len(merged_blocks)
    report['target_defs_after'] = sorted(new_def_names)
    report['target_top_blocks_after'] = check.get('top_block_count', 0)
    report['target_variables_after'] = len(check.get('variable_names', []))
    expected_vars = report['target_variables_before'] + len(variables_to_add)
    if report['target_variables_after'] != expected_vars:
        errors.append('合并结果变量数不符：期望 %d，实际 %d'
                      % (expected_vars, report['target_variables_after']))
    if report['target_top_blocks_after'] != expected_top:
        errors.append('合并结果顶层块数不符：期望 %d，实际 %d'
                      % (expected_top, report['target_top_blocks_after']))
    # 目标项目原有块的原文必须全部保留（不含 variables）
    tgt_block_raws = [seg['raw'] for seg in tgt_split['blocks']]
    for raw in tgt_block_raws:
        if raw not in new_project_xml:
            errors.append('合并结果丢失/修改了目标项目原有顶层块（片段开头: %r）' % raw[:120])
            break

    if verbose and report['merged']:
        pass
    return {
        'ok': not errors,
        'project_xml': new_project_xml,
        'errors': errors,
        'warnings': warnings,
        'report': report,
    }


def _rebuild_project_xml(split: Dict[str, Any],
                         variables_to_add: List[Dict[str, str]],
                         merged_blocks: List[Dict[str, Any]]) -> str:
    """把新增变量声明与函数块“追加”进目标项目 XML，其余原文保持不变。"""
    parts: List[str] = [split['root_open']]
    variables_inserted = False
    for seg in split['segments']:
        if seg['kind'] == 'variables':
            raw = seg['raw']
            if variables_to_add:
                extra = ''.join(_variable_decl_xml(d) for d in variables_to_add)
                close_lt = raw.rfind('</variables>')
                raw = raw[:close_lt] + extra + raw[close_lt:]
            parts.append(raw)
            variables_inserted = True
        else:
            parts.append(seg['raw'])
    if variables_to_add and not variables_inserted:
        # 目标原本没有 <variables>：按 Blockly 要求插到根节点之后、所有 block 之前
        parts.insert(1, '<variables>' + ''.join(_variable_decl_xml(d) for d in variables_to_add)
                     + '</variables>')
    # 追加函数定义块（放最后，不移动/修改原有块）
    for mb in merged_blocks:
        parts.append(mb['raw'])
    parts.append(split['root_close'])
    return ''.join(parts)


# ============================================================================
# 三、文件级合并
# ============================================================================

def merge_files(library_path: str, target_path: str, out_path: Optional[str] = None,
                in_place: bool = False, func_filter: Optional[Sequence[str]] = None,
                include_defreturn: bool = False, dry_run: bool = False,
                force: bool = False, verbose: bool = False,
                program_name: Optional[str] = None) -> Dict[str, Any]:
    """
    文件级合并入口。返回报告 dict（含 ok / out_path / report / errors / warnings）。
    """
    result: Dict[str, Any] = {
        'ok': False,
        'library': os.path.abspath(library_path),
        'target': os.path.abspath(target_path),
        'out': None,
        'in_place': in_place,
        'dry_run': dry_run,
        'written': False,
        'backup': None,
        'errors': [],
        'warnings': [],
        'report': {},
    }
    try:
        library = srhs_tool.load_any_project(library_path)
        target = srhs_tool.load_any_project(target_path)
    except (ValueError, OSError) as exc:
        result['errors'].append(str(exc))
        return result

    # 源文件本身有问题时直接拒绝合并
    for label, loaded in (('函数库', library), ('目标项目', target)):
        bad = list(loaded.get('errors') or [])
        if bad:
            result['errors'].extend(['%s文件有问题：%s' % (label, e) for e in bad])
    if result['errors']:
        return result

    lib_srh = library['srh']
    tgt_srh = target['srh']
    if not lib_srh or not tgt_srh:
        result['errors'].append('函数库或目标项目解析失败（srh 为空）')
        return result

    merge_result = merge_project_xml(
        target_xml=tgt_srh.project_xml,
        library_xml=lib_srh.project_xml,
        func_filter=func_filter,
        include_defreturn=include_defreturn,
        verbose=verbose,
    )
    result['report'] = merge_result['report']
    result['errors'].extend(merge_result['errors'])
    result['warnings'].extend(merge_result['warnings'])
    if merge_result['errors']:
        return result

    report = merge_result['report']
    nothing_to_do = len(report['merged']) == 0

    # 决定输出路径
    if in_place:
        dst = os.path.abspath(target_path)
    elif out_path:
        dst = os.path.abspath(out_path)
        # 若只给了目录，自动命名
        if os.path.isdir(dst):
            stem, ext = os.path.splitext(os.path.basename(target_path))
            dst = os.path.join(dst, stem + '_已合并函数库' + ext)
    else:
        stem, ext = os.path.splitext(os.path.abspath(target_path))
        dst = stem + '_已合并函数库' + ext
    result['out'] = dst

    if nothing_to_do and not force:
        result['ok'] = True
        result['warnings'].append('没有需要合并的函数（同名已存在或全部被过滤），未写文件。'
                                  '加 --force 可强制生成规范化副本。')
        return result

    # 构造输出 SrhFile（Info 段沿用目标项目；程序名可覆盖）
    merged_info_xml = tgt_srh.info_xml
    merged_info = dict(tgt_srh.info)
    if program_name:
        merged_info['download_program_name'] = program_name
        merged_info_xml = srhs_tool.make_info_xml(
            robot_type=tgt_srh.robot_type,
            version=tgt_srh.version,
            download_program_name=program_name,
            ai_pairs=tgt_srh.info.get('ai_pairs') or None,
        )
    merged_srh = srhs_tool.SrhFile(info=merged_info, info_xml=merged_info_xml,
                                   project_xml=merge_result['project_xml'])

    if dry_run:
        result['ok'] = True
        result['warnings'].append('dry-run：未写任何文件')
        return result

    # 真正写文件
    try:
        if in_place:
            backup = _backup_path(target_path)
            shutil.copy2(target_path, backup)
            result['backup'] = backup
        elif os.path.exists(dst) and not force:
            result['errors'].append(
                '输出文件已存在，未覆盖：%s\n  如需覆盖请加 --force；或改用 --out 指定其它路径。'
                % dst)
            return result
        os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
        if dst.lower().endswith('.srhs'):
            robot = target.get('comment_robot_type') or tgt_srh.robot_type
            pack_report = srhs_tool.pack_srhs(
                merged_srh, dst, robot=robot,
                extra_files=target.get('extra_files') or None, verify=True)
            result['out_sha256'] = pack_report.get('zip_sha256')
            result['out_bytes'] = pack_report.get('zip_bytes')
        else:
            merged_srh.save(dst)
            result['out_sha256'] = srhs_tool.sha256_file(dst)
            result['out_bytes'] = os.path.getsize(dst)
            validation = srhs_tool.validate_srh(dst)
            if not validation.get('ok'):
                raise RuntimeError('输出 .srh 校验失败：%s' % validation.get('errors'))
        result['written'] = True
        result['ok'] = True
    except (OSError, RuntimeError, ValueError) as exc:
        result['errors'].append('写输出失败：%s' % exc)
        return result
    return result


# ============================================================================
# 四、CLI
# ============================================================================

def _print_report(result: Dict[str, Any], show_json: bool) -> None:
    if show_json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return
    report = result.get('report') or {}
    print('=' * 72)
    print('函数库      : %s' % result.get('library'))
    print('目标项目    : %s' % result.get('target'))
    print('输出        : %s%s' % (result.get('out') or '(不写)',
                                 '  [in-place]' if result.get('in_place') else ''))
    if result.get('backup'):
        print('备份        : %s' % result['backup'])
    print('-' * 72)
    print('函数库函数数: %d    候选: %d'
          % (report.get('library_defs_total', 0), report.get('candidate_defs', 0)))
    merged = report.get('merged') or []
    print('本次合并    : %d 个' % len(merged))
    for item in merged:
        args = item.get('args') or []
        print('   + %-28s 参数=%s' % (item.get('name'), args if args else '无'))
    skipped = report.get('skipped_same_name') or []
    if skipped:
        print('同名跳过    : %d 个 %s' % (len(skipped), skipped))
    filtered = report.get('filtered_out') or []
    if filtered:
        print('过滤掉      : %d 个 %s' % (len(filtered), filtered))
    added_vars = report.get('variables_added') or []
    print('新增变量    : %d 个 %s' % (len(added_vars), added_vars))
    reused = report.get('variables_reused') or []
    if reused:
        print('复用变量    : %d 个 %s' % (len(reused), reused))
    remapped = report.get('variables_id_remapped') or []
    if remapped:
        print('变量id重定向: %d 个 %s' % (len(remapped), remapped))
    print('块id重生成  : %d 个' % report.get('block_ids_regenerated', 0))
    print('顶层块数    : %s -> %s'
          % (report.get('target_top_blocks_before'), report.get('target_top_blocks_after')))
    print('函数数      : %d -> %d'
          % (len(report.get('target_defs_before') or []),
             len(report.get('target_defs_after') or [])))
    print('变量数      : %s -> %s'
          % (report.get('target_variables_before'), report.get('target_variables_after')))
    if result.get('written'):
        print('已写出      : %s (%s, sha256=%s)'
              % (result.get('out'),
                 srhs_tool._fmt_bytes(result.get('out_bytes') or 0),
                 (result.get('out_sha256') or '')[:16]))
    for w in result.get('warnings') or []:
        print('[警告] %s' % w)
    for e in result.get('errors') or []:
        print('[错误] %s' % e)
    print('=' * 72)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='合并到现有项目.py',
        description='把函数库项目里的函数定义合并进现有 .srh/.srhs 项目（同名跳过、变量自动对齐、默认输出新文件）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python 合并到现有项目.py --library WER函数库.srh --target 我的项目.srhs --dry-run\n'
               '  python 合并到现有项目.py --library WER函数库.srhs --target 我的项目.srhs\n'
               '  python 合并到现有项目.py --library WER函数库.srhs --target 我的项目.srhs --in-place\n')
    p.add_argument('--library', required=True,
                   help='函数库项目文件（.srh 或 .srhs），一般是 WER函数库.srh/.srhs')
    p.add_argument('--target', required=True,
                   help='要合并进的现有项目（.srh 或 .srhs）')
    p.add_argument('--out', default=None,
                   help='输出文件路径（默认：目标同目录 <名字>_已合并函数库.<原扩展名>；也可给目录）')
    p.add_argument('--in-place', action='store_true',
                   help='直接写回目标文件（会先备份 <文件名>.备份-<时间>）')
    p.add_argument('--force', action='store_true',
                   help='即使没有新函数也强制写出规范化副本；覆盖已存在输出文件')
    p.add_argument('--dry-run', action='store_true', help='只分析并打印计划，不写文件')
    p.add_argument('--funcs', default=None,
                   help='只合并这些函数（逗号分隔，如 func_A,func_B）')
    p.add_argument('--include-defreturn', action='store_true',
                   help='同时合并有返回值的函数（procedures_defreturn；默认只合并无返回值）')
    p.add_argument('--program', default=None,
                   help='可选：输出项目的 DownloadProgramName（默认沿用目标项目）')
    p.add_argument('--json', action='store_true', help='输出 JSON 报告')
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    srhs_tool.setup_console()
    args = build_arg_parser().parse_args(argv)
    func_filter = None
    if args.funcs:
        func_filter = [x.strip() for x in args.funcs.split(',') if x.strip()]

    # 输出已存在且非 in-place 且未 --force 时，先给出明确提示（不覆盖）
    result = merge_files(
        library_path=args.library,
        target_path=args.target,
        out_path=args.out,
        in_place=args.in_place,
        func_filter=func_filter,
        include_defreturn=args.include_defreturn,
        dry_run=args.dry_run,
        force=args.force,
        program_name=args.program,
    )
    _print_report(result, args.json)
    return 0 if result.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
