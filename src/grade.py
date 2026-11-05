# -*- coding: utf-8 -*-
"""判分 + 掌握度更新（v2 间隔验证模型）。

计分表（与 skills/exam-tutor/references/掌握度规则v2.md 一致，改这里必须同时改文档和 tests/test_grade.py）：
    首对 45 ｜ 同日再对 +3（同日封顶 50）｜ 跨 1 整天对 +10 ｜ 跨 3 整天对 +15
    首错 30 ｜ 之后再错 -15（下限 0）｜ 上限 100
封顶：跨日对次 = 0 时掌握度上限 84；跨日对次 >= 3 才可进 85+
排期：答错 -> 次日；<60 -> 次日；60-69 -> +2；70-84 -> +4；85+ -> +7/+14/+30（按证据数递增）

纯函数，不读写文件；落盘由调用方（插件/脚本）负责。
"""
import datetime

import decay

MAX_SCORE = 100
CAP_NO_EVIDENCE = 84


# ---------------------------------------------------------------- 判对错 ----
_TRUE_WORDS = {"√", "对", "正确", "是", "T", "TRUE", "1"}
_FALSE_WORDS = {"×", "x", "X", "错", "错误", "否", "F", "FALSE", "0"}
_TRUE_CHARS = str.maketrans({"√": "A", "对": "A", "×": "B", "错": "B"})


def norm_answer(a):
    """答案规范化：判断题符号(√/×)与 A/B 等价；多选去空格/逗号、转大写、按字母排序。"""
    if a is None:
        return ""
    s = str(a).strip()
    if s.upper() in _TRUE_WORDS:
        return "A"
    if s.upper() in _FALSE_WORDS:
        return "B"
    s = s.translate(_TRUE_CHARS)
    for ch in (" ", "\t", ",", "，", "、", "|", "/"):
        s = s.replace(ch, "")
    s = s.upper()
    return "".join(sorted(set(s)))


def is_correct(user, answer):
    """用户答案是否等于标准答案。'?' / 空 / None 一律算错。"""
    u = norm_answer(user)
    a = norm_answer(answer)
    if not u or u == "?" or not a:
        return False
    return u == a


# ------------------------------------------------------------ 掌握度更新 ----
def _as_date(x):
    if isinstance(x, datetime.date):
        return x
    if not x:
        return None
    try:
        return datetime.date.fromisoformat(str(x)[:10])
    except ValueError:
        return None


def _schedule(score, correct, cross, today):
    """下次复习日期。"""
    if not correct:
        return today + datetime.timedelta(days=1)
    if score < 60:
        return today + datetime.timedelta(days=1)
    if score < 70:
        return today + datetime.timedelta(days=2)
    if score < 85:
        return today + datetime.timedelta(days=4)
    step = 7 if cross < 3 else (14 if cross < 6 else 30)
    return today + datetime.timedelta(days=step)


def update(rec, correct, today=None, uncertain=False):
    """按 v2 规则更新一条考点记录，返回 (新记录, 变动说明)。

    rec 可以缺字段（旧数据），缺什么补什么。today 传 date 或 None（取本机今天）。
    """
    today = _as_date(today) or datetime.date.today()
    r = dict(rec or {})

    old = float(r.get("掌握度") or 0)
    n = int(r.get("答题数") or 0)
    wrong_n = int(r.get("错题数") or 0)
    cross = int(r.get("跨日对次") or 0)
    last = _as_date(r.get("最近复习") or r.get("上次复习"))
    days = (today - last).days if last else None

    if n == 0:                                  # 首答
        score = 45.0 if correct else 30.0
    elif correct:
        if days is None or days <= 0:            # 同日再对
            score = min(old + 3, max(old, 50))
        elif days >= 3:
            score = old + 15
        else:
            score = old + 10
    else:
        score = old - 15

    score = max(0.0, min(float(MAX_SCORE), score))

    new_cross = cross
    if correct and days is not None and days >= 1:
        new_cross = cross + 1
    if new_cross < 3:                            # 证据不足，压住虚高
        score = min(score, float(CAP_NO_EVIDENCE))

    tier = decay.next_tier(r.get("档位") or 0, correct and not uncertain,
                           evidence=new_cross, uncertain=uncertain)

    out = dict(r)
    out.update({
        "掌握度": round(score, 1) if score != int(score) else int(score),
        "答题数": n + 1,
        "错题数": wrong_n + (0 if correct else 1),
        "最近复习": today.isoformat(),
        "上次复习": today.isoformat(),
        "跨日对次": new_cross,
        "证据数": new_cross,
        "档位": tier,
        "连续错": 0 if correct else int(r.get("连续错") or 0) + 1,
        "next_review": _schedule(score, correct, new_cross, today).isoformat(),
    })
    info = {"old": old, "new": out["掌握度"], "correct": bool(correct),
            "uncertain": bool(uncertain), "days": days,
            "tier_old": r.get("档位") or 0, "tier_new": tier}
    return out, info


# ------------------------------------------------------------- 整批判分 ----
def parse_answers(text):
    """'A,B?,C,?' -> ['A','B?','C','?']（也接受空格/换行分隔）。"""
    if text is None:
        return []
    if isinstance(text, (list, tuple)):
        return [str(x).strip() for x in text]
    s = str(text).replace("\n", ",").replace(" ", ",").replace("，", ",")
    return [x.strip() for x in s.split(",") if x.strip() != ""]


def grade_batch(items, answers, today=None):
    """items: 当前批次.json 的 items；answers: 用户答案列表或 'A,B?' 字符串。

    返回每题一条：{no, id, kp, user, answer, correct, uncertain, qtype}
    - '?' = 不会（按错处理）
    - 'B?' = 答了但不确定（按对记分，标记 uncertain）
    """
    ans = parse_answers(answers)
    out = []
    for i, it in enumerate(items or []):
        user = ans[i] if i < len(ans) else ""
        uncertain = user.endswith("?") and norm_answer(user) not in ("", "?")
        raw = user[:-1] if uncertain else user
        answer = it.get("answer")
        out.append({
            "no": it.get("no", i + 1),
            "id": it.get("id"),
            "kp": it.get("kp"),
            "qtype": it.get("qtype"),
            "user": user or "（未答）",
            "answer": answer,
            "correct": is_correct(raw, answer),
            "uncertain": uncertain,
            "answer_missing": answer in (None, ""),
        })
    return out


def summarize(results):
    total = len(results or [])
    right = len([r for r in results if r.get("correct")])
    return {"total": total, "correct": right,
            "score": f"{right}/{total}",
            "rate": round(right / total * 100, 1) if total else 0.0}
