# 教编做题系统 · Exam Tutor

一套**让 AI 陪你刷题**的备考系统：AI 负责出卷、批改、讲解和复盘，脚本负责机械活（按比例组卷、算遗忘曲线、生成复盘），所有状态都存在**纯文本文件**里，换个 AI、换台电脑都能接着做。

> 最初为「教师招聘 / 特岗教师」考试设计（教育学、心理学），但学科和教材都能替换 —— 只要你的题库符合 `docs/数据格式.md`。

> 👉 **完全不懂电脑？先看 [`docs/新手使用说明.md`](docs/新手使用说明.md)** —— 里面只有"你要说什么话"，没有命令。
> 给别人的 AI 看的是 [`docs/给Hermes的提示词.md`](docs/给Hermes的提示词.md)；已经按旧版装过的用 [`docs/提示词补丁_旧版已发.md`](docs/提示词补丁_旧版已发.md)。

## 它解决什么问题

| 普通刷题 App | 这套系统 |
|---|---|
| 你刷完就忘，不知道哪个考点在漏 | 每个考点有**保持率**，按半衰期衰减，快忘了自动进复习队列 |
| 程序出题，答错只给个答案 | AI 批改时给**口诀 + 抓手 + 错因归类**，错题第二天换壳重考 |
| 错题本是一堆散题 | 每日复盘按考点合并，标注"这个考点今天错了几次" |
| 数据在别人服务器 | 全部是本地 JSON / Markdown，可 diff、可备份、可迁移 |

## 3 分钟跑起来

```bash
git clone <repo> && cd exam-tutor

# 1) 生成数据目录（本仓库自带 12 道示例题，能直接跑通）
python src/init_workspace.py

# 2) 组一份 10 题的卷子
python src/make_quiz.py 第一章 10
```

第 2 步会打印 9～10 道题（不含答案）——每批固定 9 新 + 1 复习，复习队列为空时就是 9 题；答案写进 `workspace/做题系统/当前批次.json`。把题目贴给 AI，让它按 `skills/exam-tutor/SKILL.md` 的规则批改、更新掌握度、写错题本。

换成你自己的题库：把 JSON 放进 `workspace/做题系统/题库/`，命名规则见 `docs/数据格式.md`。

环境：Python 3.8+，**零第三方依赖**（标准库即可）。

## 让别的 Hermes 自己装

把 [`docs/给Hermes的提示词.md`](docs/给Hermes的提示词.md) 整段粘给朋友的 Hermes，它会自己完成体检、安装、验证和演示。

## 方式二：装成 Hermes 插件（一条命令）

```bash
hermes plugins install huzhixin210/exam-tutor/plugin
hermes plugins enable exam-tutor
```

装完会多出四个工具（`exam_quiz` / `exam_grade` / `exam_status` / `exam_review`）和配套技能
`exam-tutor:exam-tutor`。判分、掌握度、错题本、复盘全部由代码完成，AI 只负责讲解和换壳——
比纯技能模式少一半出错机会。详见 `plugin/README.md`。

## 目录结构

```
exam-tutor/
├── AGENTS.md                  通用 AI 入口（Claude Code / Codex / 任意 agent 从这里读）
├── skills/exam-tutor/
│   ├── SKILL.md               教学规则主文件（出题配比、批改、掌握度、纪律）
│   └── references/            细则：出题规则、掌握度算法、失分模式、题库质量
├── src/
│   ├── config.py              数据目录解析（--root / EXAM_TUTOR_ROOT / ./workspace）
│   ├── init_workspace.py      复制模板生成 workspace
│   ├── make_quiz.py           组卷（比例、多选占比、同考点去重、排除已做）
│   ├── decay.py               遗忘衰减核心（纯函数，档位半衰期模型）
│   ├── pick_questions.py      按关键词临时找题（省 token）
│   ├── build_daily_review.py  生成/合并当日错题复盘
│   └── migrate_decay.py       旧掌握度数据迁移到衰减模型
├── plugin/                    Hermes 插件（自带一份 engine/ 与 template/）
├── tools/sync_plugin.py       把 src/ 同步进 plugin/engine/
├── template/                  空模板 + 12 道示例题（MIT）
├── tests/test_decay.py        衰减算法单元测试（27 个用例）
└── docs/                      设计说明、数据格式、AI 接入
```

## 核心设计（最值得借鉴的部分）

1. **出题范围由模型定，不交给脚本**：脚本只按章/标签抽题，会把还没学的节混进来（真实踩过的坑）。
   默认流程是「读学习记录定到节 → 检索候选 → 模型手挑 10 题」；脚本的机械卷只作为备用。
2. **配比参考 4:6**（主教材 4 题 / 补充 6 题），题源不均时按实际说明，避免单一来源偏差。
3. **每批 10 题 = 9 新 + 1 复习**，复习题从衰减队列顶部自动取，不靠人挑。
4. **掌握度不是分数，是保持率**：`R = 掌握度 × 0.5^(天数/半衰期)`，档位 0–6 对应半衰期 1/3/7/14/30/60/120 天；答对升 1 档但受**证据数封顶**（答对 1 次最多档 2），答错掉 2 档。
5. **"会了但忘" ≠ "没会"**：掌握度 <60 记为「未掌握」（要重学），否则按掉幅分「稳固 / 松动 / 欠账 / 红色」。
6. **错题必须换壳**：重做时换问法、换选项、换情境，禁止原题重刷。
7. **失分模式库**：把个人反复踩的坑归纳成六类（配对串位 / 分类混组 / "最早第一"互换 / 名句归属 / 阵营词混入 / 清单漏选），每类对应固定对策。

详见 `docs/设计说明.md`。

## 题库共享（可选）

题库可以放在自己的服务器上，自己推、朋友拉：

```bash
# 服务器一次性安装（生成令牌 + systemd 服务）
curl -fsSLO https://raw.githubusercontent.com/huzhixin210/exam-tutor/main/deploy/install_server.sh && sudo bash install_server.sh

# 自己发布（只传 sha256 变了的文件）
python tools/publish_bank.py --url http://<IP>:9120 --token <令牌> --dir "<题库目录>"

# 朋友拉取（或用插件工具 exam_bank_sync）
python src/sync_bank.py --url http://<IP>:9120 --token <令牌>
```

单向传输 = 服务器是唯一真源，不会产生冲突。完整说明见 [`docs/题库同步.md`](docs/题库同步.md)。

## 关于题库与版权

仓库**不含任何教材真题**。`template/` 里那 12 道是作者自编的示例题（MIT 授权，随便改）。

真实题库请自己录入或获取授权。`.gitignore` 默认排除 `workspace/`，所以你的题库和个人数据不会误传。

## 接入方式

| 你的 AI | 怎么做 |
|---|---|
| Hermes Agent | 把 `skills/exam-tutor/` 拷进 `~/.hermes/skills/`，详见 `docs/接入AI.md` |
| Claude Code / Codex / Cursor | 打开仓库，它们会自动读 `AGENTS.md` |
| 其他对话式 AI | 把 `skills/exam-tutor/SKILL.md` 全文粘进系统提示词，数据文件手动喂 |

## Roadmap

- [x] 组卷 / 衰减 / 复盘脚本（命令行走通）
- [x] AI 无关的规则层（AGENTS.md + SKILL.md）
- [x] Hermes 插件（工具化：组卷/判分/状态/复盘/导出 + 斜杠命令）
- [x] 服务器部署支持：导出人读视图（`导出/`），只单向同步 Markdown，不碰 JSON
- [ ] 本地网页版（浏览器做题，手机同 WiFi 可用）
- [ ] 题库导入工具（PDF / 图片 → JSON，OCR）

## License

MIT。规则文档和代码随便用，改了欢迎 PR。
