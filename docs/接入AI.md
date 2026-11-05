# 接入你的 AI

## Hermes Agent · 插件方式（推荐）

```bash
hermes plugins install huzhixin210/exam-tutor/plugin
hermes plugins enable exam-tutor
```

授权过 GitHub 的机器可直接装；装完重启会话，多出 `exam_quiz` / `exam_grade` / `exam_status` /
`exam_review` 四个工具和只读技能 `exam-tutor:exam-tutor`，还会自动初始化数据目录
（`<hermes-home>/plugin-data/exam-tutor/workspace`）。

**Windows + Clash 用户注意**：`hermes plugins install` 内部用 git 克隆，schannel 偶尔报
`server closed abruptly (missing close_notify)`。设 `GIT_SSL_BACKEND=openssl` 后重试即可。

要把数据放在你自己的目录（比如桌面上的做题系统）：
```bash
hermes config set plugins.entries.exam-tutor.settings.root "D:/你的目录/教编备考"
```
或直接设环境变量 `EXAM_TUTOR_ROOT`。

## Hermes Agent · 纯技能方式

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
