# AGENTS.md — 给 AI 的入口

任何 agent（Claude Code、Codex、Cursor、Hermes、自建 agent）读到这里，按下面顺序做。

## 1. 先读规则

**必读**：`skills/exam-tutor/SKILL.md`（教学规则主文件）
**按需读**（不要一次读全部，省 token）：
- `skills/exam-tutor/references/出题规则详细.md` — 批次配比、题型比例、换壳方法
- `skills/exam-tutor/references/掌握度规则v2.md` — 掌握度升降、next_review 计算
- `skills/exam-tutor/references/失分模式.md` — 用户失分归类与对策
- `skills/exam-tutor/references/题库与质量纪律.md` — 题库维护、弃用题登记

## 2. 数据在哪

数据目录（workspace）由 `src/config.py` 解析，优先级：
`--root` 参数 > 环境变量 `EXAM_TUTOR_ROOT` > `./workspace` > 仓库内 `workspace/`。

所有脚本都支持 `--root <目录>`。**不要硬编码绝对路径。**

workspace 结构：

```
workspace/
├── 做题系统/
│   ├── 进度.json        进度快照（换会话先读这个恢复上下文）
│   ├── 掌握度.json      各考点掌握度 + 衰减字段
│   ├── 错题本.md        错题追加记录（只追加不覆盖）
│   ├── 当前批次.json    本次卷子的答案（批改时读它取答案）
│   ├── 批次记录.jsonl   每批一行，永不覆盖
│   └── 题库/            你的题库 JSON
├── 每日错题复盘/
└── 背诵/                可选的背诵稿（复盘时引用原文）
```

不是第一次用：先跑 `python src/init_workspace.py` 生成 workspace。

## 3. 会话开场（每次都要）

1. `date` 核实今天日期（**禁止凭记忆写日期**）
2. 读 `workspace/做题系统/进度.json`
3. 读 `workspace/做题系统/批次记录.jsonl` **最后 3–5 行**
4. 需要时再按章节读 `掌握度.json` 的对应键，不要整份读

## 4. 出题：先跑脚本，别手动筛题库

```bash
python src/make_quiz.py <章节> 10        # 标准卷：9 新 + 1 复习，4:6 配比
python src/make_quiz.py --专项 20        # 专项：只出红色/未掌握/欠账考点
```

脚本输出题目（无答案），答案写进 `当前批次.json`。你负责：把题目贴给用户 → 等回答 → 批改 → 更新掌握度和错题本。

## 5. 批改与落库（一次调用写完）

同一批里完成：
- 掌握度：答对 +10 / 答错或「?」−15（下限 0），同时写 `档位`/`证据数`/`上次复习`/`连续错`
- 错题本：编号取已有最大值 +1，条目带 `【考点标记】章节·考点名`
- 进度.json：更新 `当前阶段`、累计题量、`last_session_closed`

## 6. 硬纪律（违反会污染数据）

- 题库解析与背诵稿冲突 → **以背诵稿为准**；判定异版题后必须把 id 写进 `题库/弃用.json`
- 作废题不进复盘文件
- 不要凭印象判分：批改前先打印 `当前批次.json` 的 answer 列核对
- 掌握度键找不到精确匹配时新建 `考点N_<考点名>`，绝不塞进"最相近"的旧键
