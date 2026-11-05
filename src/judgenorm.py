# -*- coding: utf-8 -*-
"""判断题规范化（纯函数）。

山香题库里 `qtype: 判断` 的题 options 是空对象、answer 写成 √ / ×。
组卷脚本要求 options 非空，于是整类判断题被静默过滤，一道也出不来。
这里在读取题库时把它们转成标准选择题形态：options={"A":"正确","B":"错误"}、answer="A"/"B"。
原始文件不动，只在内存里规范化。
"""

QTRUE = "A"
QFALSE = "B"

TRUE_WORDS = ("√", "对", "正确", "是", "T", "TRUE", "True", "A", "1")
FALSE_WORDS = ("×", "x", "X", "错", "错误", "否", "F", "FALSE", "False", "B", "0")

DEFAULT_OPTIONS = {"A": "正确", "B": "错误"}


def is_judge(q):
    return str((q or {}).get("qtype") or "").strip() == "判断"


def norm(q):
    """返回规范化后的副本；非判断题原样返回（不改入参）。"""
    if not isinstance(q, dict) or not is_judge(q):
        return q
    out = dict(q)
    if not out.get("options"):
        out["options"] = dict(DEFAULT_OPTIONS)
    a = str(out.get("answer") or "").strip()
    if a in TRUE_WORDS:
        out["answer"] = QTRUE
    elif a in FALSE_WORDS:
        out["answer"] = QFALSE
    return out


def norm_all(qs):
    return [norm(q) for q in (qs or [])]
