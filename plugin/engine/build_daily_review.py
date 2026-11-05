# -*- coding: utf-8 -*-
"""生成/追加当日错题复盘（exam-tutor 技能配套脚本）。

用法：python build_daily_review.py [YYYY-MM-DD]
- 不传日期＝按 datetime.now() 取今天（禁止手写日期常量）
- 目标文件已存在＝追加合并（保留旧知识点，新考点追加，头部计数与速览重算）
- 作废题（标题含「作废」「补充版」）一条都不写入
- 结束时把进度.json 的 last_session_closed 写成「日期 HH:MM」
"""
import os, re, sys, glob, json, datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

BASE = config.root()
SYS = os.path.join(BASE, "做题系统")
OUT_DIR = os.path.join(BASE, "每日错题复盘")

now = datetime.datetime.now()
_args = [a for a in sys.argv[1:]]
if "--root" in _args:
    i = _args.index("--root"); del _args[i:i + 2]
TODAY = _args[0] if _args else now.strftime("%Y-%m-%d")
HHMM = now.strftime("%H:%M")

DROP = ("罚抄", "这是你第", "这题是理解题", "记牢这条", "下次再错")
ORDER = {"第一章第一节": 1, "第一章第二节": 2, "第一章第三节": 3, "第二章第一节": 4, "第二章第二节": 5,
         "第三章第一节": 6, "第三章第二节": 7, "第三章第三节": 8, "第三章第四节": 9,
         "第四章第一节": 10, "第四章第二节": 11, "第四章第三节": 12,
         "第五章第一节": 13, "第五章第二节": 14, "第五章第三节": 15}


def clean(s):
    s = re.sub(r"\*\*", "", s)
    s = re.sub(r"\s*-{2,}\s*$", "", s)
    return re.sub(r"#+", "", s).strip()


BK = {os.path.basename(p).replace("_背诵稿.md", ""): p for p in glob.glob(f"{BASE}/背诵/*_背诵稿.md")}


def chap_file(chap):
    for nm, p in BK.items():
        if nm.startswith(chap):
            return p
    return None


def kp_block(chap, kp_name):
    """返回 (背诵稿考点原名, 骨架, 口诀)。按考点编号优先、名字兜底。"""
    p = chap_file(chap)
    if not p:
        return "", "", ""
    text = open(p, encoding="utf-8").read()
    parts = re.split(r"(?=^#{3,4}\s*[一二三四五六七八九十]*、?\s*考点)", text, flags=re.M)
    best = None
    m = re.match(r"考点\s*(\d+)", kp_name.strip())
    if m:
        for part in parts:
            if re.search(r"考点\s*" + m.group(1) + r"(?!\d)", part.split("\n")[0]):
                best = part
                break
    if best is None:
        key = re.split(r"[（(]", re.sub(r"^考点\s*\d+", "", kp_name))[0].strip()
        for part in parts:
            if key and key[:5] in part.split("\n")[0]:
                best = part
                break
    if best is None:
        return "", "", ""
    head = re.sub(r"^#{3,4}\s*[一二三四五六七八九十]*、?\s*", "", best.split("\n")[0])
    title = re.sub(r"\s*★.*$", "", head).strip()
    bone = re.search(r"▍骨架\s*\n+(.+?)(?=\n#|\Z)", best, re.S)
    kj = re.search(r"▍口诀\s*\n+(.+?)(?=\n#|\Z)", best, re.S)
    return (title,
            clean(bone.group(1).replace("\n", " "))[:240] if bone else "",
            clean(kj.group(1).replace("\n", " "))[:190] if kj else "")


def split_grab(grab):
    """抓手拆两类：事实性列句=知识点要点；其余=做题经验。"""
    facts, meths = [], []
    for s in [x.strip() for x in re.split(r"[。；;]", grab) if x.strip()]:
        if any(d in s for d in DROP):
            continue
        if s.count("＝") >= 2 or "包括" in s or "指的是" in s:
            facts.append(s)
        else:
            meths.append(s)
    return "；".join(facts)[:200], "；".join(meths)[:170]


# ---------- 1. 读错题本（当日有效条目） ----------
rows = []
for b in re.split(r"(?=### 错题\d+（)", open(os.path.join(SYS, "错题本.md"), encoding="utf-8").read()):
    head = b.split("\n")[0]
    mt = re.match(r"### 错题(\d+)（(\d{4}-\d{2}-\d{2})", head)
    if not mt or mt.group(2) != TODAY:
        continue
    if "作废" in head or "补充版" in head:
        continue
    mk = re.search(r"【考点标记】([^·]+)·([^·\n]+)", b)
    chap = mk.group(1).strip() if mk else "其他"
    kpname = mk.group(2).strip() if mk else head.replace("### ", "")
    ans = re.search(r"\*\*我的答案\*\*[:：]\s*([^\n]+)", b)
    gr = re.search(r"\*\*└解\*\*[:：]?\s*(.+)", b)
    title, bone, kj = kp_block(chap, kpname)
    facts, meths = split_grab(gr.group(1).replace("**", "") if gr else "")
    rows.append({"no": mt.group(1), "chap": chap, "title": title or kpname, "bone": bone,
                 "kj": kj, "ans": (ans.group(1).strip() if ans else ""),
                 "facts": facts, "meths": meths})

# ---------- 2. 按（章节, 背诵稿原名）合并 ----------
groups = {}
for r in rows:
    k = (r["chap"], r["title"])
    if k in groups:
        groups[k]["nos"].append(r["no"])
    else:
        g = dict(r)
        g["nos"] = [r["no"]]
        groups[k] = g

def sort_key(g):
    return (ORDER.get(g["chap"], 99), g["title"])


def block_text(g):
    flag = f"　⚠️今日错{len(g['nos'])}次" if len(g["nos"]) > 1 else ""
    L = [f"#### {g['title']}（错{'、'.join(g['nos'])}）{flag}", ""]
    if g["bone"]:
        L += [f"**📌 知识点：{g['bone']}**", ""]
    if g["kj"]:
        L += [f"**🧠 口诀：{g['kj']}**", ""]
    if g["facts"]:
        L += [f"**📌 要点：{g['facts']}**", ""]
    if g["meths"]:
        L.append(f"- ✍️ 经验：{g['meths']}")
    if g["ans"]:
        L.append(f"- ✗ 今日错点：{g['ans'][:60]}")
    L.append("")
    return "\n".join(L)


os.makedirs(OUT_DIR, exist_ok=True)
path = os.path.join(OUT_DIR, f"{TODAY}.md")

# ---------- 3. 已存在＝保留旧块，只补新考点 ----------
old_blocks, old_titles = "", []
if os.path.exists(path):
    txt = open(path, encoding="utf-8").read()
    body = re.split(r"^## ②", txt, flags=re.M)[1] if re.search(r"^## ②", txt, flags=re.M) else ""
    body = re.split(r"^## ③", body, flags=re.M)[0] if "## ③" in body else body
    old_blocks = body.strip()
    old_titles = re.findall(r"^#### (.+?)（错", old_blocks, flags=re.M)

new_blocks = [block_text(g) for g in sorted(groups.values(), key=sort_key)
              if g["title"] not in old_titles]
all_sec = "\n".join([x for x in [old_blocks, "\n".join(new_blocks)] if x]).strip()

if not rows and not old_blocks:
    all_sec = "（今日无新错题）"

# 从合并后的正文里重算标题与计数
heads = re.findall(r"^#### (.+?)\n", all_sec, flags=re.M)
counts = {}
for line in all_sec.split("\n"):
    m = re.match(r"^#### (.+?)（错([\d、]+)）", line)
    if m:
        counts[m.group(1)] = counts.get(m.group(1), 0) + len(m.group(2).split("、"))

n_total = sum(counts.values())
ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:10]

out = [f"# 每日错题复盘 · {TODAY}", "",
       f"**今日错题 {n_total} 条 → {len(counts)} 个知识点**　|　每天 22:30 自动生成", "",
       "> 用法：**📌 知识点 + 🧠 口诀 = 要背的**（念一遍→合上复述）；**✍️ 经验 = 做题方法**（扫一眼）；背不出的标 △。", "",
       f"> ✅ 今日做题会话已结束（{HHMM} 归档，共 {n_total} 条错题）", "", "---", "",
       "## ① 30秒速览", "", "| # | 知识点 | 今日错 |", "|---|---|---|"]
for i, (t, c) in enumerate(ranked, 1):
    out.append(f"| {i} | {t} | {c}次 |")
out += ["", "---", "", "## ② 知识点清单（按章节）", "", all_sec, "", "---", "", "## ③ 明日自测（合上文件答）", ""]
for i, (t, _) in enumerate(ranked[:8], 1):
    out.append(f"{i}. **{t}** —— 📌知识点和🧠口诀能复述吗？")
out += ["", "> 答不上来的，做题时说重考哪条，我出换壳题。", ""]

open(path, "w", encoding="utf-8").write("\n".join(out))

# ---------- 4. 归档当日会话 ----------
pj = os.path.join(SYS, "进度.json")
if os.path.exists(pj):
    d = json.load(open(pj, encoding="utf-8"))
    d["last_session_closed"] = f"{TODAY} {HHMM}"
    d["更新日期"] = TODAY
    json.dump(d, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# ---------- 5. 自检 ----------
miss = [b.split("\n")[0] for b in all_sec.split("\n\n#### ") if b.startswith("#### ") and "📌" not in b]
print(f"[ok] {path}")
print(f"今日有效错题 {n_total} 条 / {len(counts)} 个知识点；本次新增 {len(new_blocks)} 块")
print("缺📌条目：", miss if miss else "无")
print("last_session_closed =", f"{TODAY} {HHMM}")
