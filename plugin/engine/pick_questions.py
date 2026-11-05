"""挑题器（省 token 版）：只输出题干/选项/答案，不输出解析。

用法（在 Hermes 的 execute_code 里或终端直接跑）：
    python pick_questions.py --prefix 第五章 --n 10
    python pick_questions.py --prefix 第五章 --kw 核心课程,融合课程,广域,隐性课程 --n 8 --qtype 多选
    python pick_questions.py --prefix 第四章 --n 6 --exclude-ids 664t1dx001,664t1dx002

参数：
  --prefix   章节前缀，匹配 题库/<前缀>.json 与 题库/6600_<前缀>.json
  --n        输出条数（默认 10）
  --kw       逗号分隔关键词，命中题干或任一选项即算（留空＝不过滤）
  --qtype    单选 / 多选 / any（默认 any）
  --exclude-ids   逗号分隔的已用题目 id
  --errbook  错题本路径（默认 教编备考/做题系统/错题本.md，用于排除错过题的同题干）

输出格式（每行一题，便于直接组卷，无解析）：
  [id|qtype|tags] 题干
     A.x  B.y  C.z  D.w  | 答:X
"""
import argparse, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

DEFAULT_ROOT = config.root()


def load_bank(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, dict):
        for k in ("questions", "items", "data"):
            if k in d:
                return d[k]
        return list(d.values())[0] if d else []
    return d


def opts_text(q):
    o = q.get("options")
    if isinstance(o, dict):
        return "  ".join(f"{k}.{v}" for k, v in o.items())
    if isinstance(o, list):
        return "  ".join(str(x) for x in o)
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--kw", default="")
    ap.add_argument("--qtype", default="any")
    ap.add_argument("--exclude-ids", default="")
    ap.add_argument("--errbook", default=None)
    ap.add_argument("--root", default=DEFAULT_ROOT, help="workspace 目录（默认取 EXAM_TUTOR_ROOT 或 ./workspace）")
    a = ap.parse_args()

    if a.errbook is None:
        a.errbook = os.path.join(a.root, "做题系统", "错题本.md")
    qb = os.path.join(a.root, "做题系统", "题库")
    files = [f for f in glob.glob(os.path.join(qb, "*.json"))
             if os.path.basename(f) in (f"{a.prefix}.json", f"6600_{a.prefix}.json")]
    if not files:
        print(f"未找到题库文件：{a.prefix}.json / 6600_{a.prefix}.json（目录 {qb}）")
        return

    errbook = ""
    if os.path.exists(a.errbook):
        with open(a.errbook, encoding="utf-8") as f:
            errbook = f.read().replace(" ", "")

    kws = [k.strip() for k in a.kw.split(",") if k.strip()]
    exclude = {x.strip() for x in a.exclude_ids.split(",") if x.strip()}

    picked = []
    for path in files:
        for q in load_bank(path):
            qid = str(q.get("id", ""))
            if not qid or qid in exclude:
                continue
            if q.get("quality") not in (None, "ok"):
                continue
            if not q.get("options"):
                continue
            if isinstance(q.get("options"), list) and any(x is None for x in q["options"]):
                continue
            if a.qtype != "any" and str(q.get("qtype")) != a.qtype:
                continue
            stem = str(q.get("stem") or "")
            if not stem or "None" in stem:
                continue
            if stem[:16].replace(" ", "") in errbook:
                continue
            if kws and not any(k in stem + opts_text(q) for k in kws):
                continue
            picked.append(q)
            if len(picked) >= a.n:
                break
        if len(picked) >= a.n:
            break

    print(f"# {a.prefix} 挑出 {len(picked)} 题（已排除错过题同题干/已用id/无效题）")
    for q in picked:
        tags = q.get("tags") or []
        print(f"[{q['id']}|{q.get('qtype')}|{','.join(map(str, tags)) or '-'}] {str(q['stem']).replace(chr(10), ' ')}")
        print(f"   {opts_text(q)}  | 答:{q.get('answer')}")


if __name__ == "__main__":
    main()
