# -*- coding: utf-8 -*-
"""
校验我的函数库.py —— 校验「我的函数库」源文件（.srh / .srhs）
========================================================================

用途：同步前先体检。检查 XML 合法、恰好 1 个 start 块、函数/参数/变量命名、
重名、孤立调用（调用了没定义的函数）等，列出你的全部函数和变量。

用法
----
    python 校验我的函数库.py
    python 校验我的函数库.py --library 我的函数库.srh
    python 校验我的函数库.py --json --json-out 校验结果.json

退出码：0 = 通过（无 ERROR；WARN 不影响）；1 = 有 ERROR；2 = 文件缺失。
默认函数库：WER_函数库/我的函数库.srh / .srhs（没有时借用 示例/WER函数库.srh 演示）。

本文件只是中文名称的入口，真正实现在同目录 框架核心.py（可 import 复用）。
"""

from __future__ import annotations

import importlib.util
import os
import sys


def _load_core():
    """按文件路径加载同目录的 框架核心.py（文件名含中文，不能直接 import）。"""
    sys.dont_write_bytecode = True  # 不在交付目录里留下 __pycache__
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, '框架核心.py')
    spec = importlib.util.spec_from_file_location('wer_framework_core', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('无法加载框架核心.py：%s' % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    core = _load_core()
    return core.main(sys.argv[1:], prog=os.path.basename(os.path.abspath(__file__)),
                     forced_cmd='validate')


if __name__ == '__main__':
    sys.exit(main())
