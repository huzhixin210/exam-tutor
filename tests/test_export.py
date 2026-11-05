# -*- coding: utf-8 -*-
"""导出人读视图：把 JSON/MD 数据渲染成 Obsidian 里能看的 Markdown。"""
import datetime
import unittest

import export


MASTERY = {"章节": {
    "第一章第一节_教育及其产生发展": {
        "考点1_教育的词源": {"掌握度": 88, "答题数": 6, "错题数": 1, "最近复习": "2026-10-20",
                          "跨日对次": 4, "档位": 4, "next_review": "2026-11-19"},
        "考点2_教育的本质属性": {"掌握度": 45, "答题数": 3, "错题数": 2, "最近复习": "2026-11-04",
                            "跨日对次": 1, "档位": 1, "next_review": "2026-11-05"},
    },
    "第二章第一节_心理发展": {
        "考点1_注意的品质": {"掌握度": 70, "答题数": 4, "错题数": 0, "最近复习": "2026-10-01",
                         "跨日对次": 2, "档位": 3, "next_review": "2026-10-05"},
    },
}}


class TestMasteryBoard(unittest.TestCase):
    def setUp(self):
        self.md = export.render_mastery(MASTERY, today=datetime.date(2026, 11, 5))

    def test_contains_all_kp_names(self):
        for name in ("教育的词源", "教育的本质属性", "注意的品质"):
            self.assertIn(name, self.md)

    def test_sorted_by_retention_ascending(self):
        # 注意的品质：10-01 起档位3(14天半衰期) -> 35 天后几乎掉光，应排最前
        self.assertLess(self.md.index("注意的品质"), self.md.index("教育的词源"))

    def test_marks_unmastered(self):
        self.assertIn("未掌握", self.md)

    def test_has_table_header(self):
        self.assertIn("| 考点 |", self.md)
        self.assertIn("保持率", self.md)


class TestErrorBoard(unittest.TestCase):
    def setUp(self):
        self.text = """# 错题本

### 错题1（2026-11-04 21:00）
- **题目**：教育区别于其他社会活动的根本特征
- **你的答案**：B ｜ **正确答案**：A
- **【考点标记】** 第一章第一节·考点2_教育的本质属性
- **错因**：概念混淆
- **抓手**：本质属性只有一条

### 错题2（2026-11-05 22:10）
- **题目**：学校教育产生的条件
- **你的答案**：? ｜ **正确答案**：ABCD
- **【考点标记】** 第一章第一节·考点5_学校教育的产生条件
- **错因**：未答
- **抓手**：生产力+文字+国家+体脑分工
"""
        self.md = export.render_errors(self.text)

    def test_lists_kp_with_counts(self):
        self.assertIn("教育的本质属性", self.md)
        self.assertIn("学校教育的产生条件", self.md)

    def test_recent_entries_section(self):
        self.assertIn("最近错题", self.md)
        self.assertIn("未答", self.md)

    def test_empty_book_does_not_crash(self):
        self.assertIn("错题本", export.render_errors(""))
