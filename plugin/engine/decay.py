#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遗忘衰减核心（档位半衰期模型 v1，纯函数无副作用）

tier 0-6 对应半衰期 1/3/7/14/30/60/120 天；
当前保持率 R = 100 * 0.5 ** (距离上次复习天数 / 半衰期)；
答对升 1 档但受"证据数"封顶（从严档），答错/不会掉 2 档。

用法：
    import decay
    decay.retain(4, 9)              # 档位4、9天没复习 -> 保持率
    decay.build_queue(考点字典)      # 复习队列（R 最低优先）
"""
import datetime

TIER_HALF_LIFE = (1, 3, 7, 14, 30, 60, 120)
MAX_TIER = len(TIER_HALF_LIFE) - 1
ALPHA = 100.0

# 从严档证据上限：答对1次最多档2；2-3次档3；4-5次档4；6次以上档6
def evidence_cap(n):
    n = max(0, int(n or 0))
    if n <= 0: return 0
    if n == 1: return 2
    if n <= 3: return 3
    if n <= 5: return 4
    return 6


def clamp_tier(tier):
    return max(0, min(MAX_TIER, int(tier or 0)))


def half_life(tier):
    return TIER_HALF_LIFE[clamp_tier(tier)]


def retain(tier, days, base=100.0):
    """距今 days 天的保持率（0-100）。base=上次复习时的掌握度快照。

    days=0 -> base；days=半衰期 -> base 的一半。base 传 0/None 时按 100 处理。
    """
    days = max(0, float(days or 0))
    b = ALPHA if base is None else max(0.0, min(ALPHA, float(base)))
    return b * 0.5 ** (days / half_life(tier))


def _to_date(x):
    if x is None or x == "":
        return None
    if isinstance(x, datetime.datetime):
        return x.date()
    if isinstance(x, datetime.date):
        return x
    s = str(x)[:10]
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def days_since(last, today=None):
    """距上次复习天数；last 为空 -> None（从未复习）。未来日期按 0 算。"""
    d0 = _to_date(last)
    if d0 is None:
        return None
    d1 = _to_date(today) or datetime.date.today()
    return max(0, (d1 - d0).days)


def next_tier(tier, ok, evidence=0, uncertain=False):
    """答题后的新档位。ok=False 视为答错或「?」（掉 2 档）。"""
    t = clamp_tier(tier)
    if not ok:
        return max(0, t - 2)
    if uncertain:
        return t
    return min(t + 1, evidence_cap(evidence))


# 迁移用：由旧"掌握度"反推初始档位
def tier_from_score(score):
    if score is None:
        return 0
    s = float(score)
    if s >= 90: return 4
    if s >= 75: return 3
    if s >= 60: return 2
    if s >= 40: return 1
    return 0


def status_of(r, base=100.0):
    """两类完全不同的问题分开：

    - 没会：上次测得的掌握度 < 60 -> "未掌握"（要重学/背，不是复习）
    - 会了但忘：按相对掉幅判档（掉 <10% 稳固 / 10-25% 松动 / 25-40% 欠账 / >40% 红色）
    """
    b = ALPHA if base is None else float(base or 0)
    if b < 60:
        return "未掌握"
    frac = (float(r) / b) if b else 0.0
    if frac >= 0.90: return "稳固"
    if frac >= 0.75: return "松动"
    if frac >= 0.60: return "欠账"
    return "红色"


def record_r(rec, today=None):
    """单个考点记录 -> (R, 状态, 距上次天数)。兼容缺档位/缺上次复习的旧数据。"""
    if not isinstance(rec, dict):
        return 0.0, "红色", None
    tier = rec.get("档位")
    base = rec.get("掌握度")
    if tier is None:
        tier = tier_from_score(base)
    if base is None:
        base = 100.0 if "答题数" not in rec else 60.0
    last = rec.get("上次复习") or rec.get("最近复习")
    d = days_since(last, today)
    if d is None:   # 不记得上次复习时间 -> 按"松动"提醒，别当成稳固
        return float(base), ("松动" if float(base) >= 60 else "未掌握"), None
    r = retain(tier, d, base)
    return r, status_of(r, base), d


def build_queue(records, today=None, only=None):
    """records: {考点名: 记录} -> [(考点名, R, 状态, 天数)]，R 升序。only 可传状态集合过滤。"""
    out = []
    for k, rec in (records or {}).items():
        r, st, d = record_r(rec, today)
        if only and st not in only:
            continue
        out.append((k, round(r, 1), st, d))
    out.sort(key=lambda x: x[1])
    return out


if __name__ == "__main__":
    print("档位 半衰期   7天   30天   90天   (基准100)")
    for t in range(MAX_TIER + 1):
        print(f"  {t}  {TIER_HALF_LIFE[t]:>4}天 {retain(t, 7):6.1f} {retain(t, 30):6.1f} {retain(t, 90):6.1f}")
