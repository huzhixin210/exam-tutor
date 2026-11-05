# -*- coding: utf-8 -*-
"""把 src/、skills/exam-tutor/、template/ 同步到 plugin/（插件必须自带一份，不能引用仓库路径）。

用法：python tools/sync_plugin.py           # 同步
      python tools/sync_plugin.py --check   # 只报告差异，不写
"""
import filecmp
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugin"

PAIRS = [
    (REPO / "src", PLUGIN / "engine", "*.py"),
    (REPO / "skills" / "exam-tutor", PLUGIN / "skills" / "exam-tutor", "**/*"),
    (REPO / "template", PLUGIN / "template", "**/*"),
]


def diff():
    out = []
    for src, dst, _pat in PAIRS:
        for f in src.rglob("*"):
            if not f.is_file() or "__pycache__" in f.parts:
                continue
            target = dst / f.relative_to(src)
            if not target.exists() or not filecmp.cmp(f, target, shallow=False):
                out.append((f, target))
    return out


def main():
    check = "--check" in sys.argv
    changed = diff()
    print(f"{'[check] ' if check else ''}待同步 {len(changed)} 个文件")
    for f, t in changed:
        print("  ", f.relative_to(REPO), "->", t.relative_to(REPO))
        if not check:
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
