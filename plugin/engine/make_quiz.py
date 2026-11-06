#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
教编组卷器 v2  用法：python 出题.py 第五章 [题量]
规则：3600×40% + 6600×60%；多选约25%；排除已做.json与错题本题干；同考点≤2；优先tag题
输出：题干+选项（不含答案）；答案写进 做题系统/当前批次.json
省 token：模型只看10道成品题（~800 token），不再看候选题+解析（~4000 token）
"""
import json, os, re, sys, datetime, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judgenorm   # 判断题 options 空 / answer √× 的规范化，漏了它整类判断题会被静默过滤

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config                       # 数据目录：--root / EXAM_TUTOR_ROOT / ./workspace

BASE = os.path.join(config.root(), "做题系统")
QB = os.path.join(BASE, "题库")
DONE = os.path.join(QB, "已做.json")
CUR = os.path.join(BASE, "当前批次.json")
ERRS = os.path.join(BASE, "错题本.md")

def load(fn):
    p = os.path.join(QB, fn)
    if not os.path.exists(p): return []
    with open(p, encoding="utf-8") as f: d = json.load(f)
    if isinstance(d, dict):
        for k in ("questions","items","data"):
            if k in d: d = d[k]; break
    return judgenorm.norm_all(d or [])

def norm(s): return re.sub(r"[\s\W]+", "", str(s or ""))

def opt_text(v):
    """选项原文去重复的字母前缀（题库里少数选项自带 "A."）。"""
    return re.sub(r"^[A-Ga-g][.．、)]\s*", "", str(v or ""))

def err_stems():
    out = set()
    if not os.path.exists(ERRS): return out
    with open(ERRS, encoding="utf-8") as f: txt = f.read()
    for m in re.finditer(r"\*\*题目\*\*[：:]?\s*(?:（[^）]*）)?\s*[：:]?\s*([^\n]{8,})", txt):
        out.add(norm(m.group(1))[:16])
    return out

BAN = os.path.join(QB, "弃用.json")
def banned():
    try:
        with open(BAN, encoding="utf-8") as f: return set(json.load(f))
    except Exception: return set()

def ok(q, done_ids, errs):
    if q.get("id") in banned(): return False
    if not q.get("options") or q.get("quality") not in (None, "ok"): return False
    o = q["options"]
    if isinstance(o, list) and any(x is None for x in o): return False
    if q.get("id") in done_ids: return False
    stem = str(q.get("stem") or "")
    if len(stem) < 8 or "None" in stem: return False
    if norm(stem)[:16] in errs: return False
    return True

def read_progress():
    """从 学习记录.md 读"出题范围：第六章 第一节"，让出题范围跟着用户的真实进度走。
    找不到就回退到"视频：教育学第六章第一节"这行；都没有则返回 (None, None)。"""
    p = os.path.join(os.path.dirname(BASE), "学习记录.md")
    if not os.path.exists(p): return None, None
    with open(p, encoding="utf-8") as f: txt = f.read()
    pat = re.compile(r"(第[一二三四五六七八九十]+章)\s*[·、，,]?\s*(第[一二三四五六七八九十]+节)?")
    for line in txt.splitlines():
        if line.startswith("出题范围"):
            m = pat.search(line)
            if m: return m.group(1), m.group(2)
    for line in txt.splitlines():
        if line.startswith("视频"):
            m = pat.search(line)
            if m: return m.group(1), m.group(2)
    return None, None


def main():
    argv = [a for a in sys.argv[1:]]
    if "--root" in argv:                 # 吃掉 --root <dir>（config 自己会读）
        i = argv.index("--root")
        del argv[i:i + 2]
    special = None
    for flag in ("--专项", "--复习"):
        if flag in argv:
            special = flag
            argv.remove(flag)
    scope = None
    if "--scope" in argv:          # --scope 第一节：按"节"出题，范围用 题库/节关键词.json 定义
        i = argv.index("--scope")
        scope = argv[i+1] if len(argv) > i+1 else None
        del argv[i:i+2]
    chap = argv[0] if argv and not argv[0].isdigit() else None
    auto_chap, auto_sec = read_progress()
    if chap is None:
        chap = auto_chap or "第五章"
    if scope is None and "--全章" not in argv and auto_sec and auto_chap == chap:
        scope = auto_sec
        print(f"[自动范围] 学习记录.md → {chap}·{scope}（想整章出题加 --全章）")
    if "--全章" in argv: argv.remove("--全章")
    n = int(argv[1]) if len(argv) > 1 else (int(argv[0]) if argv and argv[0].isdigit() else 10)
    if special:
        return run_special(special, n)
    n3600 = max(1, round(n * 0.4)); n6600 = n - n3600
    n_multi = max(1, round(n * 0.25))
    n_review = 1 if n >= 10 else 0          # 冲刺档：9 新 + 1 复习（由队列取 R 最低）
    n_new = n - n_review
    n3600 = max(1, round(n_new * 0.4)); n6600 = n_new - n3600
    n_multi = max(2, round(n_new * 0.25))


    with open(DONE, encoding="utf-8") as f: done_ids = set(json.load(f).get("ids", []))
    errs = err_stems()
    if not os.path.exists(os.path.join(QB, f"{chap}.json")) and not os.path.exists(os.path.join(QB, f"6600_{chap}.json")):
        print(f"[缺题库] {chap} 还没有入库的题库文件（需先 OCR 建库），当前只有：" +
              "、".join(sorted(f[:-5] for f in os.listdir(QB) if f.endswith('.json') and f[:2] in ('第一','第二','第三','第四','第五','第六','第七','第八','第九'))))
        return
    b3600 = [(q, f"{chap}.json") for q in load(f"{chap}.json") if ok(q, done_ids, errs)]
    b6600 = [(q, f"6600_{chap}.json") for q in load(f"6600_{chap}.json") if ok(q, done_ids, errs)]

    if scope:                     # 按节收窄：6600 用 topic 前缀，3600 用考点关键词（题库无节字段）
        try:
            with open(os.path.join(QB, "节关键词.json"), encoding="utf-8") as f:
                semap = json.load(f)
        except Exception:
            semap = {}
        rec = (semap.get(chap) or {}).get(scope)
        if not rec:
            print(f"[缺节映射] 题库/节关键词.json 里没有 {chap}·{scope}。请补 {{topic/topics, kw}} 后再跑")
            return
        topics = rec.get("topics") or ([rec["topic"]] if rec.get("topic") else [])
        kws = rec.get("kw") or []
        if topics:
            b6600 = [(q, s) for q, s in b6600 if any(str(q.get("topic") or "").startswith(t) for t in topics)]
        else:
            b6600 = []
        def hit3600(q):
            kp = str(q.get("kp") or "")
            stem = str(q.get("stem") or "")
            base = kp if kp else stem        # kp 优先；题干只在无 kp 时兜底（题干含"教学任务"等泛词会误收别的节）
            return any(k in base for k in kws)
        b3600 = [(q, s) for q, s in b3600 if hit3600(q)]
        print(f"[节范围] {chap}·{scope}｜6600={'、'.join(topics) or '无'}｜候选 3600={len(b3600)} 6600={len(b6600)}")
        if len(b3600) + len(b6600) < n_new:
            print(f"[警告] 该节候选题不足 {n_new} 道，实际只能出 {len(b3600)+len(b6600)} 道")

    def order(pool):
        pool = list(pool)
        random.seed(datetime.date.today().toordinal())
        random.shuffle(pool)
        pool.sort(key=lambda t: 0 if t[0].get("tags") else 1)
        return pool

    picked, kp_cnt, src_of = [], {}, {}
    def add(q, src):
        picked.append(q); src_of[id(q)] = src
        kp = str(q.get("kp") or "")[:12]
        kp_cnt[kp] = kp_cnt.get(kp, 0) + 1

    def take(pool, cnt, want_multi):
        got = 0
        cap_judge = max(1, round(n * 0.2))   # 判断题封顶 20%（曾出现 10 题 4 判断、多选只剩 1 道）
        for q, src in order(pool):
            if got >= cnt: break
            is_multi = str(q.get("qtype")) == "多选"
            if want_multi != is_multi: continue
            if str(q.get("qtype")) == "判断" and len([p for p in picked if str(p.get("qtype")) == "判断"]) >= cap_judge:
                continue
            kp = str(q.get("kp") or "")[:12]
            if kp and kp_cnt.get(kp, 0) >= 2: continue
            if any(q["id"] == p["id"] for p in picked): continue
            add(q, src); got += 1

    m3600 = max(1, n_multi // 2)
    take(b3600, m3600, True); take(b6600, n_multi - m3600, True)
    used3600 = len([p for p in picked if src_of[id(p)] == f"{chap}.json"])
    used6600 = len([p for p in picked if src_of[id(p)] == f"6600_{chap}.json"])
    take(b3600, max(0, n3600 - used3600), False)
    take(b6600, max(0, n6600 - used6600), False)
    if len(picked) < n_new:
        for q, src in order(b6600 + b3600):
            if len(picked) >= n_new: break
            if any(q["id"] == p["id"] for p in picked): continue
            add(q, src)

    if n_review:      # 冲刺档：最后补 1 道衰减队列顶部的复习题
        rv = review_question(done_ids)
        if rv and all(rv[0].get("id") != p.get("id") for p in picked):
            add(rv[0], rv[1])

    lines = [f"# 组卷 · {chap} · {n}题 · {datetime.datetime.now():%Y-%m-%d %H:%M}", ""]
    for i, q in enumerate(picked[:n], 1):
        lines.append(f"{i}.（{q.get('qtype')}）{str(q.get('stem')).replace(chr(10),' ')}")
        o = q["options"]
        if isinstance(o, dict):
            for k, v in o.items(): lines.append(f"   {k}. {opt_text(v)}")
        else:
            for k, v in zip("ABCDEFG", o): lines.append(f"   {k}. {opt_text(v)}")
        lines.append("")
    print("\n".join(lines))

    with open(CUR, "w", encoding="utf-8") as f:
        json.dump({"date": datetime.datetime.now().strftime("%Y-%m-%d"), "chapter": chap,
                   "items": [{"no": i, "id": q.get("id"), "qtype": q.get("qtype"), "answer": q.get("answer"),
                              "kp": q.get("kp"), "src": src_of[id(q)]} for i, q in enumerate(picked[:n], 1)]},
                  f, ensure_ascii=False, indent=2)
    ids = list(done_ids) + [q.get("id") for q in picked[:n]]
    with open(DONE, "w", encoding="utf-8") as f:
        json.dump({"ids": ids, "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}, f, ensure_ascii=False, indent=2)
    multi_n = len([q for q in picked[:n] if str(q.get("qtype")) == "多选"])
    print(f"[已写] 当前批次.json（{len(picked[:n])}题｜多选{multi_n}道｜3600={used3600+m3600 if False else len([p for p in picked[:n] if src_of[id(p)]==f'{chap}.json'])}）｜已做累计 {len(ids)}")

MASTER = os.path.join(BASE, "掌握度.json")


def mastery_recs():
    try:
        with open(MASTER, encoding="utf-8") as f:
            return json.load(f).get("章节", {})
    except Exception:
        return {}


def weak_tokens(top=20, statuses=("红色", "未掌握", "欠账")):
    """按衰减队列取最该复习的考点，转成可在题库里匹配的关键词。"""
    import decay
    recs = {f"{sec}|{k}": v for sec, kps in mastery_recs().items() for k, v in kps.items()}
    out = []
    for key, r, st, d in decay.build_queue(recs, only=statuses)[:top]:
        sec, name = key.split("|", 1)
        out.append({"key": key, "r": r, "status": st,
                    "tok": re.sub(r"^考点\d+_", "", name)})
    return out


def all_pool():
    pool = []
    for fn in sorted(os.listdir(QB)):
        if not fn.endswith(".json") or fn in ("已做.json", "弃用.json"):
            continue
        for q in load(fn):
            if isinstance(q, dict) and q.get("id"):
                pool.append((q, fn))
    return pool


def match_pool(tok, pool, done_ids, limit=2):
    """按考点关键词找题：优先没做过的，不够再用做过的（复习就是要重见）。"""
    hits = [(q, fn) for q, fn in pool
            if tok and tok in str(q.get("kp") or "") + " " + str(q.get("stem") or "")]
    hits.sort(key=lambda t: (t[0].get("id") in done_ids, not t[0].get("tags")))
    return hits[:limit]


def _emit(picked, src_of, chap, done_ids, tag=""):
    n = len(picked)
    lines = [f"# 组卷{tag} · {chap} · {n}题 · {datetime.datetime.now():%Y-%m-%d %H:%M}", ""]
    for i, q in enumerate(picked, 1):
        lines.append(f"{i}.（{q.get('qtype')}）{str(q.get('stem')).replace(chr(10), ' ')}")
        o = q["options"]
        if isinstance(o, dict):
            for k, v in o.items(): lines.append(f"   {k}. {opt_text(v)}")
        else:
            for k, v in zip("ABCDEFG", o): lines.append(f"   {k}. {opt_text(v)}")
        lines.append("")
    print("\n".join(lines))
    with open(CUR, "w", encoding="utf-8") as f:
        json.dump({"date": datetime.datetime.now().strftime("%Y-%m-%d"), "chapter": chap,
                   "items": [{"no": i, "id": q.get("id"), "qtype": q.get("qtype"),
                              "answer": q.get("answer"), "kp": q.get("kp"),
                              "src": src_of[id(q)]} for i, q in enumerate(picked, 1)]},
                  f, ensure_ascii=False, indent=2)
    ids = list(done_ids) + [q.get("id") for q in picked]
    with open(DONE, "w", encoding="utf-8") as f:
        json.dump({"ids": ids, "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")},
                  f, ensure_ascii=False, indent=2)
    print(f"[已写] 当前批次.json（{n}题）｜已做累计 {len(ids)}")


def run_special(mode, n):
    """--专项 20：只出衰减队列里的红色/未掌握/欠账考点；--复习 5：同源、题量小。"""
    with open(DONE, encoding="utf-8") as f:
        done_ids = set(json.load(f).get("ids", []))
    pool = all_pool()
    toks = weak_tokens(top=max(6, n))
    picked, seen, src_of = [], set(), {}
    for t in toks:
        if len(picked) >= n: break
        for q, fn in match_pool(t["tok"], pool, done_ids, limit=2):
            if len(picked) >= n: break
            if q.get("id") in seen or q.get("id") in banned() or not q.get("options"): continue
            seen.add(q.get("id")); picked.append(q); src_of[id(q)] = fn
    if not picked:
        print("[空] 队列考点在题库里匹配不到题")
        return
    _emit(picked, src_of, f"复习·{mode.strip('-')}", done_ids, tag=f"·{mode.strip('-')}")
    print("[队列来源] " + "；".join(f"{t['tok']}(R{t['r']:.0f},{t['status']})" for t in toks[:8]))


def review_question(done_ids):
    """冲刺档常驻的 1 道复习题：取队列最顶部考点。"""
    toks = weak_tokens(top=6)
    pool = all_pool()
    for t in toks:
        for q, fn in match_pool(t["tok"], pool, done_ids, limit=1):
            if q.get("id") in banned() or not q.get("options"): continue
            return q, fn
    return None


if __name__ == "__main__":
    main()
