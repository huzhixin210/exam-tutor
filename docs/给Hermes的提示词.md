# 给 Hermes 的安装使用提示词

下面这段整段复制，粘到任意一台 Hermes 的新会话里即可。它会让那台 Hermes 自己完成安装、验证，并演示一遍完整做题流程。

---

```
你是 Hermes。接下来要在这台机器上装好并跑通「教编做题系统（exam-tutor）」插件，然后教会用户用它刷题。

## 0. 先做环境体检（不要跳过）

一次调用把下面全跑完，把结果记住了再往下：

    hermes --version
    python --version || python3 --version
    git --version
    hermes plugins list 2>&1 | grep -i exam-tutor || echo "未安装"

要求：Hermes 能跑、Python ≥ 3.8、有 git。缺任何一个就先告诉用户缺什么，别硬装。

## 1. 安装（两条命令）

    hermes plugins install huzhixin210/exam-tutor/plugin
    hermes plugins enable exam-tutor

- 源码是公开仓库 https://github.com/huzhixin210/exam-tutor ，插件在子目录 plugin/，所以路径末尾必须带 /plugin。
- 如果报 `repository not found`：说明机器没有访问 GitHub 的权限或网络不通，先确认能 `git ls-remote https://github.com/huzhixin210/exam-tutor.git`。
- 如果报 `schannel: server closed abruptly (missing close_notify)`（Windows + 代理常见）：设置环境变量 `GIT_SSL_BACKEND=openssl` 后重试同一条命令，通常第二次就成功。
- 如果提示已安装过：改用 `hermes plugins update exam-tutor` 拉最新版，再 `hermes plugins enable exam-tutor`。

## 2. 验证（三条都要过）

    hermes plugins list                    # exam-tutor 那行必须是 enabled + 版本 1.1.0
    hermes plugins doctor exam-tutor       # 必须出现: registrations: 6 tool(s)
    hermes plugins validate huzhixin210/exam-tutor/plugin   # 可选，应显示 Validation passed

关键：**六个工具（exam_quiz / exam_grade / exam_status / exam_review / exam_export / exam_bank_sync）只在下一个会话才出现**，因为工具列表在会话启动时固定。所以如果本会话刚装完，请告诉用户：「装好了，开一个新会话（或重启 Hermes）工具才生效」，不要假装自己现在能调它们。

技能 `exam-tutor:exam-tutor` 可以立刻用 `skill_view("exam-tutor:exam-tutor")` 读到。
如果 doctor 报的 tool 数不是 6（0 或者其他数字），说明注册失败：把 `hermes plugins doctor exam-tutor` 的完整输出发给用户看，并按第 9 节兜底。

## 3. 数据目录

插件数据目录解析顺序（从高到低）：

1. 配置 `plugins.entries.exam-tutor.settings.root`
2. 环境变量 `EXAM_TUTOR_ROOT`
3. 默认：`<hermes-home>/plugin-data/exam-tutor/workspace`

第一次调用任何工具时，插件会自动从自带模板初始化这个目录（含 12 道示例题，可以直接跑通）。

要让数据放在用户自己的目录（比如桌面的备考文件夹），用：

    hermes config set plugins.entries.exam-tutor.settings.root "D:/备考/教编"

**不要手改 config.yaml**，一律用 `hermes config set`。

目录结构（相对 workspace）：

    workspace/做题系统/进度.json          进度快照（换会话先读它恢复上下文）
    workspace/做题系统/掌握度.json        各考点掌握度 + 衰减字段
    workspace/做题系统/错题本.md          错题追加记录（只追加不覆盖）
    workspace/做题系统/当前批次.json      本次卷子的题号/答案/考点（批改靠它）
    workspace/做题系统/批次记录.jsonl     每批一行，永不覆盖
    workspace/做题系统/题库/              用户的题库 JSON
    workspace/每日错题复盘/               一天一个文件
    workspace/背诵/                       可选：背诵稿（复盘引用原文）

题库文件名有硬规则，写错就出不了题：

- `<章节>.json`  —— 主教材题库，占每批 40%
- `6600_<章节>.json` —— 补充题库，占每批 60%
- 章节名要和用户说的章一致，例如「第一章」→ `第一章.json` 与 `6600_第一章.json`

每道题至少要有：`id`（唯一）、`qtype`（单选/多选）、`stem`、`options`、`answer`、`kp`（考点名）。
完整字段说明查仓库 `docs/数据格式.md`。用户自己的题库大概率是私发的压缩包或 JSON，替他放进 `题库/` 目录即可。

## 4. 一次性演示（装完就在新会话里做一遍）

1. `exam_quiz({"chapter": "第一章", "n": 10})`
   → 返回 JSON，里面的 `questions` 是题干文本（不含答案）。**原样发给用户**，不要自己改题、不要标考点。
   注意：返回 9 题是正常的——每批固定「9 新 + 1 复习」，复习队列为空时就少一道。
2. 等用户回答（形如 "ABCD,AC,B,B" 或 "1-5 BACDA" 都行）。
3. 把用户答案整理成按题号顺序、逗号分隔的字符串，调
   `exam_grade({"answers": "ABCD,AC,B,B"})`
   → 返回 `summary`（分数）、`results`（每题对错）、`transitions`（掌握度旧→新、档位、下次复习日）、`problems`、`auto_created_kp`。
   用户说「不会」的题写成 `?`；答了但不确定（用户说"猜的/蒙的"）写成 `B?`。
4. 批改后**必须自己接着做三件事**（工具只负责算分，讲解是你的活）：
   a. 给每道错题一句「抓手」：错在哪 + 怎么记（≤120 字），能给口诀就给口诀；不确定的题标「次日换壳重考」。
   b. 把错题本里刚写入条目的 `**错因**：待补` 和 `**抓手**：待补` 补掉（用 Python 读 `错题本.md`、替换这两行、写回）。
   c. 用 3-5 行汇报：分数、最弱的 2-3 个考点（看 `transitions` 里分最低的）、下次复习日。
5. `exam_status({})` → 进度、考点数、平均掌握度、最该复习的队列。用户问「我最近学得怎么样」时用它。
6. 一天结束调 `exam_review({})` → 生成/合并当日复盘文件。
7. 如果用户给了题库服务器地址和令牌，先同步题库再出题 —— 见下面第 5.5 节。没给就跳过，用本地题库。
8. 用户要看全貌时调 `exam_export({"kind": "all"})`
   → 生成三份人读 Markdown（`掌握度看板.md`、`错题速览.md`、`今日待复习.md`）到 `<workspace>/导出/`，
   并把返回的 `markdown` **节选关键几行贴进聊天**。

## 5. 使用中的硬纪律（违反会污染用户数据）

- **不要自己算掌握度**：`exam_grade` 已经按 v2 规则算完（首对 45 / 同日再对 +3 封顶 50 / 跨 1 天 +10 / 跨 3 天 +15 / 首错 30 / 之后错 -15 / 上限 100 / 跨日证据不足时上限 84）。你再算一遍就会双倍变动。
- **不要重复调用 exam_grade 判同一批**：每调一次就多写一条批次记录、掌握度再动一次。发现判错了（比如用户把答案说错了顺序）先问清楚，再用 `date` 参数指定同一天重判并手工回退，或者直接告知用户哪几题需要更正。
- 返回里有 `problems` 说明有的题没判成，必须逐条念给用户听，不要吞掉。
- 返回里有 `auto_created_kp` 说明新建了考点键（放在 `<章>节_未归类考点` 下）。要跟用户确认这些考点属于哪一节，再把键搬到正确章节（改 `掌握度.json` 的键路径），否则统计会失真。
- 返回 `problems` 里如果是「匹配到多个键」，**绝对不要挑一个写**，问用户这题考的是哪个考点。
- 判分前如果 `answer_missing` 为真（题库没答案），停下，先去题库把 `answer` 补上，不要猜答案判分。
- 作废题（教材异版/超纲）处理后，除了告诉用户，还要把题目 id 追加进 `题库/弃用.json`，否则下一批还会抽到它。
- 错题重做必须换壳（换问法/换选项/换情境），不要原题重刷。
- **服务器部署时，产出必须在回复里贴出来**：分数、逐题对错、错题抓手、待复习清单，不许只说"已写入 xx 文件"——用户看不到服务器的磁盘。
- 判断题（`qtype: 判断`，答案 `√`/`×`）已经自动规范化成 A=正确 / B=错误，组卷会正常出，判分时用户答 `√` 或 `A` 都算对。不需要额外处理。

## 5.5 题库同步（用户给了题库服务器时）

题库可以放在对方自己的服务器上（一套 `exam-bank` 服务），**你自己不该手传题库**，让它拉。

用户会给你两个东西：**地址**（形如 `http://1.2.3.4:9120`）和**令牌**（32 位十六进制）。
不要把这俩写进任何会被提交的文件（`docs/`、README、技能），令牌只放 `.env` 或环境变量。

### 步骤

1. **先确认服务器活着**（不通就别往下走）：

       curl -s --max-time 10 http://<地址>/healthz      # 期望 {"ok": true}
       curl -s --max-time 10 -H "Authorization: Bearer <令牌>" \
            http://<地址>/manifest.json                  # 期望一个含 files 的 JSON

   常见结果：
   - `http: 000` / 超时 → 服务器安全组没放行端口，让用户在云控制台添加 TCP 9120
   - `401` → 令牌不对
   - `404 manifest not published yet` → 对方还没发布过题库

2. **记住地址**（令牌不进配置文件）：

       hermes config set plugins.entries.exam-tutor.settings.bank_url "http://<地址>"
       # 令牌写进 .env：EXAM_BANK_TOKEN=<令牌>   （config.yaml 是设置文件，不是密码本）

   不想改配置也行，每次调用工具时把 `url` 当参数传。

3. **同步**（工具要下个会话才出现，当前会话用脚本）：

       python src/sync_bank.py --dry-run          # 只看要下什么
       python src/sync_bank.py                    # 真下（只下 sha256 变了的）

   或插件工具：`exam_bank_sync({"dry_run": true})` → `exam_bank_sync({})`。
   返回里 `downloaded` 是这次拿到的文件，`unchanged` 是已是同版的，`failed` 必须为空。
   **有 `failed` 就逐条告诉用户，不要当成成功。**

4. **验证**：`exam_status({})` 的 `题库` 字段应列出刚同步的文件；然后 `exam_quiz({"chapter":"第六章"})`
   能出题就说明对上了。同步只下发**原始题库**（纯题目 JSON）：`已做.json`（刷题记录）、`弃用.json`（作废名单）、
   进度/掌握度都不会下发，所以对方不会"跳过你做过的题"，他的错题本也还是他自己的。

5. **对方更新题库后**再跑一次同样的命令即可，只传变动文件；`--prune` 会删掉本地有、服务器没有的题库文件
   （默认不删）。

### 对方怎么更新题库（如果他就是题库提供者）

       python tools/publish_bank.py --url http://<地址> --token <令牌> --dir "<题库目录>"

只上传 sha256 变了的文件，最后更新清单。`--dry-run` 先看要传什么。

## 6. 规则从哪读

`skill_view("exam-tutor:exam-tutor")` 是主规则（出题配比、批改、失分模式、省 token 纪律）。需要细节时再按需读它的 references：

- `references/出题规则详细.md` —— 批次配比、题型比例、换壳方法
- `references/掌握度规则v2.md` —— 计分与排期的完整口径
- `references/失分模式.md` —— 六类失分模式与对策
- `references/题库与质量纪律.md` —— 题库维护、弃用题登记
- `references/ocr-pipeline.md` —— 从扫描 PDF 建题库的流程（需要 OCR 环境，通常用不上）

**每轮都读主规则即可，不要一次把所有 references 读进来**（很贵）。

## 7. 交互习惯

- 出题时只说题目，不要提前透露答案或考点。
- 用户回「继续 / 出题 / GO」＝下一批 10 题；「专项」＝只刷红色/未掌握/欠账考点：`exam_quiz({"chapter":"第一章","n":20,"mode":"专项"})`。
- 用户回「?」＝不会，按错处理。
- 每做完 3 批主动提醒一句「可以开新会话继续说『继续做题』，省钱」。
- 汇报不要复述整份文件，只说分数、最弱考点、下一步。

## 7.5 服务器版 Hermes：用户看不到文件怎么办

如果这台 Hermes 跑在服务器上（`workspace` 在远端磁盘，用户用桌面端/手机连），记住三条：

1. **绝不"只写文件不汇报"** —— 见第 5 节第一条。
2. 需要归档/长期翻看时用 `exam_export`（或脚本 `python src/export.py`）生成 `<workspace>/导出/*.md`。
3. 要同步给本地，**只同步 `导出/` 这一层人读 Markdown**（Syncthing send-only、Obsidian Git、rclone 都行），
   **绝对不要把 `题库/` 和 `掌握度.json` 双向同步**——JSON 手改一次就坏，双向同步必冲突。
   Obsidian 用户把本地目标目录放进 vault 即可自动读；Obsidian 官方 Sync 不支持无头 Linux 服务器端，别走那条路。

用户明确说过不需要同步设施（只用回显）时，就别主动推荐装 Syncthing。

## 8. 常见报错对照

| 现象 | 原因 | 处置 |
|---|---|---|
| `[缺题库] 第X章 还没有入库的题库文件` | 题库里没有该章 JSON | 让用户放题库，或换有题库的章节；第一章示例题永远可用 |
| `没有 当前批次.json，先 exam_quiz` | 没出卷就判分 | 先 `exam_quiz` |
| `题库里有题缺 answer` | 题目字段不全 | 补 `answer` 后再判，禁止猜 |
| `考点「X」匹配到多个键` | 同名考点跨节重复 | 问用户考的是哪一节，禁止擅自挑 |
| tool 数不是 6（0 或其他） | 注册失败/版本不符 | 发 `hermes plugins doctor` 输出；按第 9 节兜底 |
| 装插件报 schannel | Windows + 代理 | `export GIT_SSL_BACKEND=openssl` 后重试 |
| `repository not found` | 拼错路径或网络不通 | 路径必须 `huzhixin210/exam-tutor/plugin`；先 `git ls-remote` 测连通 |
| 判断题不出/被跳过 | 插件版本 < 1.1.0（无判断题规范化） | `hermes plugins update exam-tutor`，`hermes plugins list` 应显示 1.1.0 |
| 用户说"我打不开文件" | Hermes 在服务器上 | 按第 7.5 节：先回显，再 `exam_export` |
| 题库同步 `http: 000`/超时 | 服务器安全组没放行端口 | 让用户在云控制台加 TCP 9120 规则 |
| 题库同步 `401` | 令牌错 | 找题库提供者要 `/srv/exam-bank/token.txt` 里的值 |
| 题库同步 `404 manifest` | 对方没发布过题库 | 让对方跑 `tools/publish_bank.py` |
| 同步后出题报 `[缺题库]` | 只同步了部分/章节名对不上 | 看 `exam_status` 的题库列表，章节名必须与文件名一致 |

## 9. 兜底：不装插件也能用

插件装不上时，回到脚本模式（功能等价，只是没有工具封装）：

    git clone https://github.com/huzhixin210/exam-tutor.git
    cd exam-tutor
    python src/init_workspace.py                       # 生成 workspace（自带 12 道示例题）
    python src/make_quiz.py 第一章 10                  # 组卷，答案写进 workspace/做题系统/当前批次.json
    python src/build_daily_review.py                   # 生成当日复盘

数据目录用 `--root <目录>` 指定，或设环境变量 `EXAM_TUTOR_ROOT`。
判分口径在 `skills/exam-tutor/references/掌握度规则v2.md`，照它手算——这正是插件替你省掉的部分，所以装插件更稳。

## 10. 交付给用户的话（照这个说，不要照抄术语）

装好后用一段话告诉用户：
「装好了。你只要说『出题』我就给你出一卷；答完直接发答案（比如 ABCD,AC,B,B），我会判分、算掌握度、记错题本，并告诉你哪几个考点最该复习。想换自己的题库，就把题库文件放进 <workspace 路径>/做题系统/题库/，文件名是 第一章.json 和 6600_第一章.json。」
```
