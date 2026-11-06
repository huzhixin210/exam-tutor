# -*- coding: utf-8 -*-
"""exam-tutor 插件 —— 把做题系统的机械活交给确定性代码，AI 只负责讲解与换壳。

四个工具：
    exam_quiz(chapter, n, mode)  组卷（4:6 配比、9 新 + 1 复习、同考点 ≤2）
    exam_grade(answers)          判分 → 更新掌握度/错题本/批次记录/进度
    exam_status()                进度快照 + 该复习的考点队列
    exam_review(date)            生成/合并当日错题复盘

数据目录解析优先级：ctx.get_config("root") > EXAM_TUTOR_ROOT > <plugin-data>/workspace
首次调用若目录不存在，自动从插件自带的 template/ 初始化。
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ENGINE = _HERE / "engine"
_TEMPLATE = _HERE / "template"

# 引擎模块（config/decay/grade 是通用名，加载后常驻 sys.modules）
sys.path.insert(0, str(_ENGINE))
try:
    import config as _config          # noqa: F401
    import decay as _decay
    import export as _export
    import grade as _grade
    import sync_bank as _sync_bank
finally:
    try:
        sys.path.remove(str(_ENGINE))
    except ValueError:
        pass


# --------------------------------------------------------------- 数据目录 ----
def _plugin_data_root() -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir
        return Path(plugin_data_dir("exam-tutor"))
    except Exception:
        return Path.home() / ".hermes" / "plugin-data" / "exam-tutor"


def _root(ctx) -> Path:
    r = None
    try:
        r = ctx.get_config("root", default=None)
    except Exception:
        r = None
    r = r or os.environ.get("EXAM_TUTOR_ROOT")
    root = Path(r).expanduser() if r else (_plugin_data_root() / "workspace")
    if not (root / "做题系统").is_dir():
        _init_workspace(root)
    return root


def _init_workspace(root: Path):
    """从插件自带模板复制一份数据目录（已存在的文件不覆盖）。"""
    if not _TEMPLATE.is_dir():
        raise FileNotFoundError(f"插件模板丢失：{_TEMPLATE}")
    for dirpath, _d, files in os.walk(_TEMPLATE):
        rel = os.path.relpath(dirpath, _TEMPLATE)
        target = root / rel
        target.mkdir(parents=True, exist_ok=True)
        for fn in files:
            dst = target / fn
            if not dst.exists():
                shutil.copy2(os.path.join(dirpath, fn), dst)


def _sysd(root: Path) -> Path:
    return root / "做题系统"


def _load_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _quiz_bank_index(root: Path) -> dict:
    """id -> 题目 dict（写错题本时取题干用）。"""
    idx = {}
    qb = _sysd(root) / "题库"
    if not qb.is_dir():
        return idx
    for f in qb.glob("*.json"):
        if f.name in ("已做.json", "弃用.json"):
            continue
        d = _load_json(f, None)
        if isinstance(d, dict):
            d = d.get("questions") or d.get("items") or []
        for q in d or []:
            if isinstance(q, dict) and q.get("id"):
                idx[q["id"]] = q
    return idx


NEW_REC = {"掌握度": 0, "答题数": 0, "错题数": 0, "最近复习": None, "跨日对次": 0,
           "档位": 0, "证据数": 0, "连续错": 0, "next_review": None}


def _find_kp(章节: dict, kp: str, chapter: str = "", create: bool = True):
    """在掌握度里按考点名找唯一键，返回 ((节名, 键名), 错误说明, 是否新建)。

    命中多个键 -> 报错让人来定（绝不塞进"最相近"的旧键）；
    一个都没有 -> 按技能规则新建 `考点N_<考点名>`，节名用 `<章>节_未归类考点`，
    既不会污染已有考点，也一眼能看出待归档。
    """
    if not kp:
        return None, "题目没有 kp 字段", False
    hits = [(sec, key) for sec, kps in (章节 or {}).items()
            for key in kps if key == kp or key.endswith("_" + kp) or kp in key]
    if len(hits) == 1:
        return hits[0], None, False
    if hits:
        return None, f"考点「{kp}」匹配到多个键：{hits}，需人工指定", False
    if not create:
        return None, f"掌握度里没有考点「{kp}」", False
    sec = f"{chapter or '未分章'}节_未归类考点"
    bucket = 章节.setdefault(sec, {})
    nums = [int(k[2:].split("_")[0]) for k in bucket
            if k.startswith("考点") and k[2:].split("_")[0].isdigit()]
    key = f"考点{(max(nums) + 1) if nums else 1}_{kp}"
    bucket[key] = dict(NEW_REC)
    return (sec, key), None, True


# ------------------------------------------------------------------ 工具 ----
def exam_quiz(args: dict, **kwargs) -> str:
    root = _root(kwargs.get("ctx"))
    chapter = str(args.get("chapter") or "").strip()
    n = int(args.get("n") or 10)
    mode = str(args.get("mode") or "standard")
    if not chapter:
        return json.dumps({"ok": False, "error": "缺 chapter（如 第一章）"}, ensure_ascii=False)
    cmd = [sys.executable, str(_ENGINE / "make_quiz.py"), chapter, str(n), "--root", str(root)]
    if mode in ("专项", "special", "review"):
        cmd = [sys.executable, str(_ENGINE / "make_quiz.py"), "--专项", str(n), "--root", str(root)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"组卷失败：{e}"}, ensure_ascii=False)
    if out.returncode != 0:
        return json.dumps({"ok": False, "error": (out.stderr or out.stdout)[-800:]}, ensure_ascii=False)
    return json.dumps({"ok": True, "questions": out.stdout.strip(),
                       "hint": "把 questions 原样发给用户；用户答完调用 exam_grade"},
                      ensure_ascii=False)


def exam_search(args: dict, **kwargs) -> str:
    """按章节/关键词检索候选题目（只出题干+选项+答案，不含解析）。出题范围由模型决定，这是检索器。"""
    root = _root(kwargs.get("ctx"))
    chapter = str(args.get("chapter") or "").strip()
    if not chapter:
        return json.dumps({"ok": False, "error": "缺 chapter（如 第六章）"}, ensure_ascii=False)
    cmd = [sys.executable, str(_ENGINE / "pick_questions.py"),
           "--prefix", chapter, "--n", str(int(args.get("n") or 20)),
           "--root", str(root)]
    if args.get("kw"):
        cmd += ["--kw", str(args["kw"])]
    if args.get("qtype"):
        cmd += ["--qtype", str(args["qtype"])]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"检索失败：{e}"}, ensure_ascii=False)
    if out.returncode != 0:
        return json.dumps({"ok": False, "error": (out.stderr or out.stdout)[-800:]}, ensure_ascii=False)
    return json.dumps({"ok": True, "candidates": out.stdout.strip(),
                       "hint": "模型自行按考点挑 9 新 + 1 复习（单选为主、多选≥2、判断≤20%、同考点≤2、不标考点），"
                               "挑完自己写 当前批次.json，再交给用户"},
                      ensure_ascii=False)


def exam_grade(args: dict, **kwargs) -> str:
    ctx = kwargs.get("ctx")
    root = _root(ctx)
    sysd = _sysd(root)
    batch = _load_json(sysd / "当前批次.json", None)
    if not batch or not batch.get("items"):
        return json.dumps({"ok": False, "error": "没有 当前批次.json，先 exam_quiz"}, ensure_ascii=False)

    today = _grade._as_date(args.get("date")) or datetime.date.today()
    results = _grade.grade_batch(batch["items"], args.get("answers"), today)
    summary = _grade.summarize(results)
    if any(r["answer_missing"] for r in results):
        return json.dumps({"ok": False, "error": "题库里有题缺 answer，无法判分", "results": results},
                          ensure_ascii=False)

    mpath = sysd / "掌握度.json"
    mastery = _load_json(mpath, {"章节": {}})
    sections = mastery.setdefault("章节", {})
    bank = _quiz_bank_index(root)
    transitions, problems, created = [], [], []

    # 1) 掌握度
    for r in results:
        loc, err, is_new = _find_kp(sections, r["kp"], batch.get("chapter") or "")
        if err:
            problems.append({"no": r["no"], "kp": r["kp"], "problem": err})
            continue
        sec, key = loc
        if is_new:
            created.append({"no": r["no"], "section": sec, "key": key})
        old_rec = sections[sec][key]
        new_rec, info = _grade.update(old_rec, r["correct"], today, uncertain=r["uncertain"])
        sections[sec][key] = new_rec
        r["transition"] = info
        transitions.append({"no": r["no"], "kp": key, "old": info["old"], "new": info["new"],
                            "tier": f'{info["tier_old"]}->{info["tier_new"]}',
                            "next_review": new_rec["next_review"]})
    mastery["更新日期"] = today.isoformat()
    _write_json(mpath, mastery)

    # 2) 错题本（只追加）
    wrong = [r for r in results if not r["correct"]]
    if wrong:
        path = sysd / "错题本.md"
        text = path.read_text(encoding="utf-8") if path.exists() else "# 错题本\n"
        mx = 0
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("### 错题"):
                try:
                    mx = max(mx, int(line.split("错题")[1].split("（")[0].split("(")[0]))
                except Exception:
                    pass
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        block = []
        for r in wrong:
            mx += 1
            q = bank.get(r["id"]) or {}
            stem = str(q.get("stem") or "").replace("\n", " ")[:60] or r["id"]
            block.append(
                f"\n### 错题{mx}（{stamp}）\n"
                f"- **题目**：{stem}\n"
                f"- **你的答案**：{r['user']} ｜ **正确答案**：{r['answer']}\n"
                f"- **【考点标记】** {r['kp'] or '未标注考点'}\n"
                f"- **错因**：待补（AI 批改时填）\n"
                f"- **抓手**：待补（AI 批改时填，≤120 字）\n")
        path.write_text(text.rstrip() + "\n" + "".join(block), encoding="utf-8")

    # 3) 批次记录（追加一行）
    rec = {"date": today.isoformat(), "chapter": batch.get("chapter"),
           "section": batch.get("section"),
           "items": [{k: it.get(k) for k in ("no", "id", "answer", "kp")} for it in batch["items"]],
           "answers": ",".join(str(r["user"]) for r in results),
           "score": summary["score"]}
    with open(sysd / "批次记录.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 4) 进度
    prog_path = sysd / "进度.json"
    prog = _load_json(prog_path, {})
    done = prog.get("已完成") or {}
    done["累计题量"] = int(done.get("累计题量") or 0) + summary["total"]
    done["累计批次数"] = int(done.get("累计批次数") or 0) + 1
    prog["已完成"] = done
    prog["更新日期"] = today.isoformat()
    prog["last_session_closed"] = f"{today.isoformat()} {datetime.datetime.now():%H:%M}"
    _write_json(prog_path, prog)

    return json.dumps({"ok": True, "summary": summary, "results": results,
                       "transitions": transitions, "problems": problems,
                       "auto_created_kp": created,
                       "wrong_ids": [r["id"] for r in wrong],
                       "note": "错题本的错因/抓手留空，由 AI 补；掌握度已按 v2 规则落盘"},
                      ensure_ascii=False)


def exam_status(args: dict, **kwargs) -> str:
    root = _root(kwargs.get("ctx"))
    sysd = _sysd(root)
    prog = _load_json(sysd / "进度.json", {})
    mastery = _load_json(sysd / "掌握度.json", {"章节": {}})
    flat = {}
    for sec, kps in (mastery.get("章节") or {}).items():
        for key, rec in kps.items():
            flat[f"{sec}|{key}"] = rec
    queue = _decay.build_queue(flat, only=("红色", "未掌握", "欠账"))
    backlog = [{"kp": k.split("|", 1)[1], "retain": r, "status": st, "days": d}
               for k, r, st, d in queue[:12]]
    n_kp = len(flat)
    avg = round(sum(float(r.get("掌握度") or 0) for r in flat.values()) / n_kp, 1) if n_kp else 0
    return json.dumps({"ok": True,
                       "进度": prog.get("当前阶段"),
                       "累计": prog.get("已完成"),
                       "考点数": n_kp, "平均掌握度": avg,
                       "待复习队列": backlog,
                       "题库": sorted(p.stem for p in (sysd / "题库").glob("*.json")) if (sysd / "题库").is_dir() else []},
                      ensure_ascii=False)


def exam_review(args: dict, **kwargs) -> str:
    root = _root(kwargs.get("ctx"))
    cmd = [sys.executable, str(_ENGINE / "build_daily_review.py"), "--root", str(root)]
    if args.get("date"):
        cmd.insert(-2, str(args["date"]))
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"复盘生成失败：{e}"}, ensure_ascii=False)
    ok = out.returncode == 0
    return json.dumps({"ok": ok, "output": (out.stdout or out.stderr).strip()[-1500:]},
                      ensure_ascii=False)


def exam_bank_sync(args: dict, **kwargs) -> str:
    """从题库服务器拉取题库（单向，只传 sha256 变了的文件）。"""
    ctx = kwargs.get("ctx")
    url = args.get("url") or (ctx.get_config("bank_url", default=None) if ctx else None) \
        or os.environ.get("EXAM_BANK_URL")
    token = args.get("token") or os.environ.get("EXAM_BANK_TOKEN")
    if not url or not token:
        return json.dumps({"ok": False,
                           "error": "缺服务器地址或令牌：设 bank_url 配置 + EXAM_BANK_TOKEN 环境变量，"
                                    "或直接传 url/token 参数"}, ensure_ascii=False)
    try:
        r = _sync_bank.sync(url, token, root=str(_root(ctx)),
                            dry_run=bool(args.get("dry_run")), prune=bool(args.get("prune")))
    except Exception as e:
        return json.dumps({"ok": False, "error": f"同步失败：{e}"}, ensure_ascii=False)
    return json.dumps({"ok": not r["failed"], **r}, ensure_ascii=False)


EXPORT_KINDS = {"all": ("掌握度看板.md", "错题速览.md", "今日待复习.md"),
                "看板": ("掌握度看板.md",), "错题": ("错题速览.md",), "待复习": ("今日待复习.md",)}


def exam_export(args: dict, **kwargs) -> str:
    """导出人读 Markdown 视图（给 Obsidian / 手机 / 聊天窗口看）。"""
    root = _root(kwargs.get("ctx"))
    sysd = _sysd(root)
    kind = str(args.get("kind") or "all")
    if kind not in EXPORT_KINDS:
        return json.dumps({"ok": False, "error": f"kind 只能是 {list(EXPORT_KINDS)}"}, ensure_ascii=False)
    today = _grade._as_date(args.get("date")) or datetime.date.today()
    mastery = _load_json(sysd / "掌握度.json", {"章节": {}})
    progress = _load_json(sysd / "进度.json", {})
    err_path = sysd / "错题本.md"
    err_text = err_path.read_text(encoding="utf-8") if err_path.exists() else ""

    rendered = {}
    for fn in EXPORT_KINDS[kind]:
        if fn.startswith("掌握度"):
            rendered[fn] = _export.render_mastery(mastery, today=today)
        elif fn.startswith("错题"):
            rendered[fn] = _export.render_errors(err_text)
        else:
            rendered[fn] = _export.render_pending(mastery, progress, today=today)

    out_dir = root / "导出"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for fn, md in rendered.items():
        (out_dir / fn).write_text(md, encoding="utf-8")
        written.append(str(out_dir / fn))

    return json.dumps({"ok": True, "files": written,
                       "markdown": "\n\n---\n\n".join(rendered.values()),
                       "note": f"已写入 {out_dir}（同步目录指到这里，Obsidian 就能看）"},
                      ensure_ascii=False)


# --------------------------------------------------------------- 注册 ------
QUIZ_SCHEMA = {
    "name": "exam_quiz",
    "description": "机械组卷（备用）。按章/标签抽题，默认 9 新 + 1 复习、主教材 4 : 补充 6、多选≥2、判断≤20%。"
                   "注意：出题范围默认应由模型自己定（读学习记录→按节→exam_search 取候选→手挑），"
                   "本工具只在用户明确要求脚本卷时使用，否则会把未学到的节混进来。",
    "parameters": {
        "type": "object",
        "properties": {
            "chapter": {"type": "string", "description": "章节名，与题库文件名一致，如 第一章"},
            "n": {"type": "integer", "description": "题量，默认 10", "default": 10},
            "mode": {"type": "string", "enum": ["standard", "专项"], "description": "standard=常规卷；专项=只出红色/未掌握/欠账考点", "default": "standard"},
        },
        "required": ["chapter"],
    },
}

GRADE_SCHEMA = {
    "name": "exam_grade",
    "description": "批改当前批次：按 v2 规则更新掌握度（首对45/同日+3/跨日+10/跨三日+15/错-15）、追加错题本、写批次记录、更新进度。answers 形如 'A,B?,C,?'（? = 不会，B? = 答了但不确定）。",
    "parameters": {
        "type": "object",
        "properties": {
            "answers": {"type": "string", "description": "按题号顺序、逗号分隔的用户答案"},
            "date": {"type": "string", "description": "判分基准日 YYYY-MM-DD，默认今天"},
        },
        "required": ["answers"],
    },
}

STATUS_SCHEMA = {
    "name": "exam_status",
    "description": "查看做题进度：当前阶段、累计题量、考点数与平均掌握度、最该复习的考点队列（按保持率排序）。",
    "parameters": {"type": "object", "properties": {}},
}

EXPORT_SCHEMA = {
    "name": "exam_export",
    "description": "把掌握度/错题本/待复习队列渲染成人读 Markdown（写进 <workspace>/导出/ 并直接返回全文）。服务器版 Hermes 用它把结果带回聊天窗口或同步进 Obsidian。",
    "parameters": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["all", "看板", "错题", "待复习"],
                     "description": "导出哪一种，默认 all", "default": "all"},
            "date": {"type": "string", "description": "基准日 YYYY-MM-DD，默认今天"},
        },
    },
}

SEARCH_SCHEMA = {
    "name": "exam_search",
    "description": "按章节/关键词检索候选题（只返回题干+选项+答案，不含解析）。这是出题流程的检索器：模型自己决定范围（读学习记录定到节），再用它取候选，然后手挑 10 题。",
    "parameters": {
        "type": "object",
        "properties": {
            "chapter": {"type": "string", "description": "章节名，与题库文件名一致，如 第六章"},
            "kw": {"type": "string", "description": "逗号分隔的考点关键词，命中题干或选项即算"},
            "n": {"type": "integer", "description": "候选条数，默认 20", "default": 20},
            "qtype": {"type": "string", "enum": ["单选", "多选", "判断", "any"], "description": "只取某题型，默认 any"},
        },
        "required": ["chapter"],
    },
}

BANK_SYNC_SCHEMA = {
    "name": "exam_bank_sync",
    "description": "从题库服务器拉取题库到本地 workspace（只下载 sha256 变更的文件，校验后原子替换）。服务器地址取参数 url 或配置 bank_url，令牌取参数 token 或环境变量 EXAM_BANK_TOKEN。",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "如 http://1.2.3.4:9120，默认用配置 bank_url"},
            "dry_run": {"type": "boolean", "description": "只报告要下什么，不写盘", "default": False},
            "prune": {"type": "boolean", "description": "删除本地有、服务器没有的题库文件", "default": False},
        },
    },
}

REVIEW_SCHEMA = {
    "name": "exam_review",
    "description": "生成或合并当日错题复盘文件（<workspace>/每日错题复盘/YYYY-MM-DD.md），并写 last_session_closed。",
    "parameters": {
        "type": "object",
        "properties": {"date": {"type": "string", "description": "日期 YYYY-MM-DD，默认今天"}},
    },
}


def _slash_exam(ctx, raw_args: str) -> str:
    parts = (raw_args or "").strip().split()
    if parts and parts[0] in ("quiz", "grade", "review", "status", "export", "sync", "search"):
        fn = {"quiz": exam_quiz, "grade": exam_grade, "review": exam_review, "status": exam_status,
              "export": exam_export, "sync": exam_bank_sync, "search": exam_search}[parts[0]]
        rest = parts[1:]
        if parts[0] == "quiz":
            return fn({"chapter": rest[0] if rest else "第一章",
                       "n": int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else 10})
        if parts[0] == "grade":
            return fn({"answers": " ".join(rest)})
        if parts[0] == "search":
            return fn({"chapter": rest[0] if rest else "第一章",
                       "kw": " ".join(rest[1:]) or None})
        if parts[0] == "sync":
            return fn({"dry_run": "dry" in rest})
        if parts[0] == "export":
            return fn({"kind": rest[0] if rest else "all"})
        return fn({})
    return exam_status({})


def register(ctx):
    for child in sorted((_HERE / "skills").iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.exists():
            ctx.register_skill(child.name, skill_md)
    ctx.register_tool(name="exam_search", toolset="exam_tutor",
                      schema=SEARCH_SCHEMA, handler=lambda args, **kw: exam_search(args, ctx=ctx, **kw))
    ctx.register_tool(name="exam_quiz", toolset="exam_tutor",
                      schema=QUIZ_SCHEMA, handler=lambda args, **kw: exam_quiz(args, ctx=ctx, **kw))
    ctx.register_tool(name="exam_grade", toolset="exam_tutor",
                      schema=GRADE_SCHEMA, handler=lambda args, **kw: exam_grade(args, ctx=ctx, **kw))
    ctx.register_tool(name="exam_status", toolset="exam_tutor",
                      schema=STATUS_SCHEMA, handler=lambda args, **kw: exam_status(args, ctx=ctx, **kw))
    ctx.register_tool(name="exam_review", toolset="exam_tutor",
                      schema=REVIEW_SCHEMA, handler=lambda args, **kw: exam_review(args, ctx=ctx, **kw))
    ctx.register_tool(name="exam_bank_sync", toolset="exam_tutor",
                      schema=BANK_SYNC_SCHEMA, handler=lambda args, **kw: exam_bank_sync(args, ctx=ctx, **kw))
    ctx.register_tool(name="exam_export", toolset="exam_tutor",
                      schema=EXPORT_SCHEMA, handler=lambda args, **kw: exam_export(args, ctx=ctx, **kw))
    try:
        ctx.register_command("exam", lambda raw: _slash_exam(ctx, raw),
                             description="做题系统：/exam quiz|status|grade <答案>|review|export|sync|search")
    except Exception:
        pass
