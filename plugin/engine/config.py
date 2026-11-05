# -*- coding: utf-8 -*-
"""数据目录解析（所有脚本共用）。

优先级：
  1. 命令行 --root <目录>
  2. 环境变量 EXAM_TUTOR_ROOT
  3. 当前目录/workspace
  4. 仓库根/workspace

workspace 目录结构（由 init_workspace.py 生成）：
    workspace/
      ├─ 做题系统/        进度.json 掌握度.json 错题本.md 当前批次.json 题库/
      ├─ 每日错题复盘/
      └─ 背诵/            你自己的背诵稿（可选）
"""
import os
import sys

ENV = "EXAM_TUTOR_ROOT"


def _from_argv(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if "--root" in argv:
        i = argv.index("--root")
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def root(cli=None, argv=None):
    """返回 workspace 绝对路径（不保证已存在）。"""
    p = cli or _from_argv(argv) or os.environ.get(ENV)
    if p:
        return os.path.abspath(os.path.expanduser(p))
    cand = os.path.join(os.getcwd(), "workspace")
    if os.path.isdir(os.path.join(cand, "做题系统")):
        return cand
    cand = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace")
    return os.path.abspath(cand)


def sysdir(r=None):
    return os.path.join(r or root(), "做题系统")
