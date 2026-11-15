# -*- coding: utf-8 -*-
"""
生成新项目文件.py —— 把函数库打包成可直接「文件→打开」的新项目 .srhs
========================================================================

用途：**不装补丁也能用**。把「我的函数库」里的函数定义 + 变量 + start 主函数
      包装成一个标准项目文件（.srhs，SKCON9 默认），在 IDE 里 文件→打开 它，
      工作区就自带你的函数库，「函数」分类里可以直接拖用。

区别：这是“打开一个现成项目”；而 同步我的函数库.py 是改软件，让“新建项目”都自带函数库。

用法
----
    python 生成新项目文件.py
    python 生成新项目文件.py --library 我的函数库.srh --out 我的新项目.srhs
    python 生成新项目文件.py --program ProgramA --robot SKCON9
    python 生成新项目文件.py --force          （输出文件已存在时覆盖）

参数：
    --library  函数库源文件（默认自动找 我的函数库.srh/.srhs）
    --out      输出 .srhs 路径（默认 <函数库同目录>/<库名>_新项目.srhs）
    --program  下载程序名（默认 ProgramA）
    --robot    机器人类型 SKCON2/SKCON5/SKCON9（默认取函数库源文件里的；再不行用 SKCON9）
    --force    覆盖已存在的输出文件

退出码：0 = 成功；1 = 校验/打包/回读失败；2 = 函数库文件缺失或机器人类型无效。

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
                     forced_cmd='gen')


if __name__ == '__main__':
    sys.exit(main())
