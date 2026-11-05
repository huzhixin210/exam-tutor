# -*- coding: utf-8 -*-
"""把人读的部分渲染成 Markdown —— 给 Obsidian / 手机 / 聊天窗口看的视图。

机器数据（掌握度.json、题库）留在服务器；这里只产出**只读视图**，写进 workspace/导出/。
单向导出 = 本地永远不会把 JSON 改坏，也不会有同步冲突。

纯函数，不读盘。
"""
import datetime
import json
import os
import re
import sys

import decay

STATUS_ORDER = {"红色": 0, "未掌握": 1, "欠账": 2, "松动": 3, "稳固": 4}


def _fmt(v, default="-"):
    return default if v in (None, "") else v


def render_mastery(mastery, today=None, top=None):
    """掌握度看板：按保持率升序（最该复习的排最前）。"""
    today = today or datetime.date.today()
    rows = []
    for sec, kps in (mastery.get("章节") or {}).items():
        for key, rec in (kps or {}).items():
            if not isinstance(rec, dict):
                continue
            r, st, days = decay.record_r(rec, today)
            rows.append({
                "sec": sec, "kp": re.sub(r"^考点\d+_", "", key),
                "score": rec.get("掌握度"), "r": r, "status": st, "days": days,
                "tier": rec.get("档位"), "next": rec.get("next_review"),
                "n": rec.get("答题数"), "wrong": rec.get("错题数"),
            })
    rows.sort(key=lambda x: (x["r"], STATUS_ORDER.get(x["status"], 9)))
    if top:
        rows = rows[:top]

    lines = [f"# 掌握度看板（{today.isoformat()}）", "",
             f"共 {len(rows)} 个考点。按**保持率**升序，越靠前越该复习。", "",
             "| 考点 | 掌握度 | 保持率 | 状态 | 档位 | 已过天数 | 下次复习 | 答题/错 |",
             "|---|---|---|---|---|---|---|---|"]
    for x in rows:
        lines.append(
            f'| {x["kp"]} | {_fmt(x["score"])} | {x["r"]:.0f} | {x["status"]} | '
            f'{_fmt(x["tier"])} | {_fmt(x["days"])} | {_fmt(x["next"])} | '
            f'{_fmt(x["n"], 0)}/{_fmt(x["wrong"], 0)} |')
    red = [x for x in rows if x["status"] in ("红色", "未掌握")]
    if red:
        lines += ["", "## 优先处理", ""]
        for x in red[:8]:
            lines.append(f'- **{x["kp"]}**（{x["status"]}，保持率 {x["r"]:.0f}）— {x["sec"]}')
    return "\n".join(lines) + "\n"


ENTRY = re.compile(r"^###\s*错题\s*(\d+)（([^）]*)）", re.M)


def _parse_entries(text):
    if not text:
        return []
    marks = list(ENTRY.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        block = text[m.end():end]
        def grab(label):
            mm = re.search(r"\*\*" + label + r"\*\*[：:]?\s*(.+)", block)
            return mm.group(1).strip() if mm else ""
        kp = re.sub(r"^[^·]*·", "", grab("【考点标记】")).strip() or grab("【考点标记】")
        out.append({"no": int(m.group(1)), "time": m.group(2).strip(),
                    "kp": kp or "未标注考点", "cause": grab("错因"),
                    "grip": grab("抓手"), "user": grab("你的答案")})
    return out


def render_errors(text, limit=15):
    """错题本速览：按考点合并计数 + 最近明细。"""
    entries = _parse_entries(text)
    lines = [f"# 错题速览（共 {len(entries)} 条）", ""]
    if not entries:
        lines.append("错题本是空的。")
        return "\n".join(lines) + "\n"

    cnt = {}
    for e in entries:
        cnt[e["kp"]] = cnt.get(e["kp"], 0) + 1
    lines += ["## 按考点累计", "", "| 考点 | 错次 |", "|---|---|"]
    for kp, n in sorted(cnt.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {kp} | {n} |")

    lines += ["", f"## 最近错题（最新 {min(limit, len(entries))} 条）", ""]
    for e in entries[-limit:][::-1]:
        lines.append(f'### 错题{e["no"]}（{e["time"]}）')
        lines.append(f'- 考点：{e["kp"]}')
        if e["user"]:
            lines.append(f'- 你的答案：{e["user"]}')
        if e["cause"] and e["cause"] != "待补（AI 批改时填）":
            lines.append(f'- 错因：{e["cause"]}')
        if e["grip"] and e["grip"] != "待补（AI 批改时填，≤120 字）":
            lines.append(f'- 抓手：{e["grip"]}')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_pending(mastery, progress=None, today=None, limit=12):
    """今天该做什么：待复习队列 + 进度一行。"""
    today = today or datetime.date.today()
    flat = {}
    for sec, kps in (mastery.get("章节") or {}).items():
        for key, rec in (kps or {}).items():
            flat[f"{sec}|{key}"] = rec
    queue = decay.build_queue(flat, today=today,
                              only=("红色", "未掌握", "欠账"))[:limit]
    lines = [f"# 今日待复习（{today.isoformat()}）", ""]
    stage = (progress or {}).get("当前阶段")
    if stage:
        lines += [f"**当前阶段**：{stage}", ""]
    if not queue:
        lines.append("队列是空的 —— 条件允许就开新考点。")
        return "\n".join(lines) + "\n"
    lines += ["| 考点 | 保持率 | 状态 | 已过天数 |", "|---|---|---|---|"]
    for key, r, st, d in queue:
        lines.append(f'| {re.sub(r"^考点\d+_", "", key.split("|", 1)[1])} | {r:.0f} | {st} | {_fmt(d)} |')
    return "\n".join(lines) + "\n"


def main():
    """python src/export.py [--root DIR] [kind]   kind: all|看板|错题|待复习"""
    import config
    kind = "all"
    for a in sys.argv[1:]:
        if a in ("all", "看板", "错题", "待复习"):
            kind = a
    root = config.root()
    sysd = os.path.join(root, "做题系统")
    def _load(name, default):
        try:
            return json.load(open(os.path.join(sysd, name), encoding="utf-8"))
        except Exception:
            return default
    mastery = _load("掌握度.json", {"章节": {}})
    progress = _load("进度.json", {})
    errp = os.path.join(sysd, "错题本.md")
    err = open(errp, encoding="utf-8").read() if os.path.exists(errp) else ""
    today = datetime.date.today()
    files = {}
    if kind in ("all", "看板"):
        files["掌握度看板.md"] = render_mastery(mastery, today)
    if kind in ("all", "错题"):
        files["错题速览.md"] = render_errors(err)
    if kind in ("all", "待复习"):
        files["今日待复习.md"] = render_pending(mastery, progress, today)
    out = os.path.join(root, "导出")
    os.makedirs(out, exist_ok=True)
    for fn, md in files.items():
        with open(os.path.join(out, fn), "w", encoding="utf-8") as f:
            f.write(md)
        print(md)
    print(f"[已写] {out}（{len(files)} 个文件）")


if __name__ == "__main__":
    main()
