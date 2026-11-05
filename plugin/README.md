# exam-tutor 插件

把做题系统的机械活（组卷、判分、掌握度、复盘）交给确定性代码，AI 只负责讲解、换壳和补错因。

## 安装

```bash
hermes plugins install huzhixin210/exam-tutor/plugin     # 从仓库子目录安装
# 或本地开发
hermes plugins install G:/github/exam-tutor/plugin
hermes plugins enable exam-tutor
```

装完重启会话，工具出现。

## 四个工具

| 工具 | 干什么 |
|---|---|
| `exam_quiz` | 组卷：主教材 4 : 补充 6、9 新 + 1 复习、多选约 25%、同考点 ≤2（判断题自动转成 A正确/B错误） |
| `exam_grade` | 判分 + 更新掌握度（v2 计分表）+ 错题本 + 批次记录 + 进度 |
| `exam_status` | 进度快照 + 按保持率排序的待复习队列 |
| `exam_review` | 生成/合并当日错题复盘 |

配套技能 `exam-tutor:exam-tutor`（插件自带，只读）写规则：什么时候出题、怎么批改、失分模式怎么归。

斜杠命令：`/exam quiz 第一章 10`、`/exam status`、`/exam grade A,B?,C`、`/exam review`。

## 数据放哪

1. `plugins.entries.exam-tutor.settings.root`（config.yaml）
2. 环境变量 `EXAM_TUTOR_ROOT`
3. 默认 `<hermes-home>/plugin-data/exam-tutor/workspace`

首次调用自动从插件自带 `template/` 初始化，自带 12 道示例题可直接跑通。
题库（你自己的）丢进 `<workspace>/做题系统/题库/`，命名规则见仓库根 `docs/数据格式.md`。

## 判分规则（写死在这里，改就得改文档和测试）

```
首对 45 ｜ 同日再对 +3（同日封顶 50）｜ 跨 1 整天 +10 ｜ 跨 3 整天 +15
首错 30 ｜ 之后再错 -15（下限 0）｜ 上限 100
跨日对次 = 0 时上限 84；跨日对次 ≥ 3 才可进 85+
排期：错 → 次日；<60 → 次日；60-69 → +2；70-84 → +4；85+ → +7/+14/+30
```

考点在掌握度里找不到时：**唯一匹配才写，多匹配一律报错不猜**；一个都没有则新建
`<章>节_未归类考点` 下的 `考点N_<考点名>`，并在返回的 `auto_created_kp` 里列出来，等人工归档。

## 开发

`python tools/sync_plugin.py` 把 `src/` 同步进 `plugin/engine/`（插件不能引用仓库外路径）。
测试：`PYTHONPATH=src python -m unittest discover -s tests`。
