# -*- coding: utf-8 -*-
"""创建一份可用的 workspace（个人数据目录），从 template/ 复制，已存在的文件不覆盖。

用法：
    python src/init_workspace.py                 # 默认 ./workspace
    python src/init_workspace.py --root D:/mydata
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(REPO, "template")


def main():
    dest = config.root()
    if not os.path.isdir(TPL):
        print(f"[错] 找不到模板目录：{TPL}")
        return 1
    created = skipped = 0
    for dirpath, _dirs, files in os.walk(TPL):
        rel = os.path.relpath(dirpath, TPL)
        target_dir = os.path.normpath(os.path.join(dest, rel))
        os.makedirs(target_dir, exist_ok=True)
        for fn in files:
            dst = os.path.join(target_dir, fn)
            if os.path.exists(dst):
                skipped += 1
                continue
            shutil.copy2(os.path.join(dirpath, fn), dst)
            created += 1
    print(f"[完成] workspace = {dest}")
    print(f"       新建 {created} 个文件，跳过已存在的 {skipped} 个")
    print()
    print("  下一步（按顺序）：")
    print("    1. 题库：把题库 JSON 放进 <workspace>/做题系统/题库/，或配置题库服务器后同步")
    print("    2. 进度：打开 <workspace>/学习记录.md，把\"第?章第?节\"改成你真实学到的地方")
    print("       —— 没有这一步，任何 AI 都不知道该给你出哪一节，只能整章乱抽")
    print("    3. 出题：告诉 AI \"开始做题\"，它会读 学习记录.md 定范围，再检索候选让你挑")
    return 0


if __name__ == "__main__":
    sys.exit(main())
