#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 掌握度.json 迁移到衰减模型：补 档位/证据数/上次复习/连续错 四个字段（幂等）。

用法：python migrate_decay.py          # 迁移
      python migrate_decay.py --check  # 只报告不写
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decay
import config

BASE = os.path.join(config.root(), "做题系统")
M = os.path.join(BASE, "掌握度.json")


def migrate(m):
    changed = 0
    for sec, kps in (m.get("章节") or {}).items():
        for name, rec in kps.items():
            if "档位" in rec:
                continue
            score = rec.get("掌握度")
            rec["档位"] = decay.tier_from_score(score)
            total = int(rec.get("答题数") or 0)
            wrong = int(rec.get("错题数") or 0)
            rec["证据数"] = max(0, total - wrong)
            rec["上次复习"] = rec.get("最近复习") or rec.get("上次复习")
            rec["连续错"] = 0
            changed += 1
    return changed


def main():
    check = "--check" in sys.argv
    with open(M, encoding="utf-8") as f:
        m = json.load(f)
    n = migrate(m)
    print(f"{'[check] ' if check else ''}待迁移 {n} 个考点")
    if check:
        return
    if n:
        shutil.copy(M, M + ".bak_decay")
        m["更新日期"] = m.get("更新日期")
        m["衰减模型"] = "档位半衰期 v1（decay.py）；掌握度为派生值，见 遗忘衰减机制设计_v1.md"
        with open(M, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
        print("已写入，备份 ", M + ".bak_decay")


if __name__ == "__main__":
    main()
