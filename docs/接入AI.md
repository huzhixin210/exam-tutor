# 接入你的 AI

## Hermes Agent

Hermes 的技能目录是 `~/.hermes/skills/`（Windows：`C:\Users\<你>\.hermes\skills\`）。
不同安装方式路径可能是 `AppData/Local/hermes/skills/`，以你本机 `skill_view` 能读到的目录为准。

```bash
# 1) 拷技能
cp -r skills/exam-tutor ~/.hermes/skills/

# 2) 让技能知道数据在哪（写进 shell 配置或系统环境变量）
export EXAM_TUTOR_ROOT=/path/to/workspace
```

然后对 Hermes 说「开始做题」或「出题」，它会加载 `exam-tutor` 技能。

> 数据目录可以用相对路径 `./workspace`，但 Hermes 的工作目录不一定是仓库根，**建议设环境变量**。

## Claude Code / Codex / Cursor

不用装任何东西：在仓库目录启动，它们会自动读 `AGENTS.md`，里面已经写了"先读 SKILL.md、数据在哪、出题跑哪个脚本"。

## 其他对话式 AI（网页版）

1. 把 `skills/exam-tutor/SKILL.md` 全文贴进系统提示词 / 自定义指令
2. 每轮手动把 `进度.json` 和相关章节的掌握度贴给它
3. 出题时本地跑 `python src/make_quiz.py 第一章 10`，把输出贴给它

体验会差一些（要手动搬数据），但规则完全一样。

## 定时任务（可选，仅 Hermes）

原作者的周测 / 月度考试 / 每日复盘是用 Hermes 的 `cronjob` 功能跑的：

```
周测       每周六 20:00   10 题（本周章节 + 欠账 + 滚动）
月考       每月最后一个周六 20:00   20 题 + 成绩单
每日复盘   每天 22:30     跑 src/build_daily_review.py
```

cron 的 prompt 里写：读 `AGENTS.md` → 按 SKILL.md 出题 → 结果推给用户。
