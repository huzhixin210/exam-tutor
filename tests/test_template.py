# -*- coding: utf-8 -*-
"""模板完整性：别人 clone 下来 init→出题 必须能直接跑通，所以模板本身要合法。"""
import json
import os
import unittest

import judgenorm

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(REPO, "template", "做题系统")
QB = os.path.join(TPL, "题库")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class TestTemplate(unittest.TestCase):
    def test_all_template_json_parses(self):
        for dirpath, _d, files in os.walk(os.path.join(REPO, "template")):
            for fn in files:
                if fn.endswith(".json"):
                    p = os.path.join(dirpath, fn)
                    with self.subTest(file=fn):
                        self.assertIsInstance(load(p), (dict, list))

    def test_sample_questions_have_required_fields(self):
        for fn in ("第一章.json", "6600_第一章.json"):
            d = load(os.path.join(QB, fn))
            qs = d["questions"] if isinstance(d, dict) else d
            self.assertTrue(qs, fn)
            for q in qs:
                q = judgenorm.norm(q)
                with self.subTest(q=q.get("id")):
                    for k in ("id", "qtype", "stem", "options", "answer", "kp"):
                        self.assertTrue(q.get(k) not in (None, ""), f"{fn} {q.get('id')} 缺 {k}")
                    self.assertTrue(str(q["stem"]).strip())
                    self.assertGreaterEqual(len(q["options"]), 2)

    def test_section_map_is_well_formed(self):
        m = load(os.path.join(QB, "节关键词.json"))
        self.assertIsInstance(m, dict)
        for chap, secs in m.items():
            self.assertTrue(chap.startswith("第"), chap)
            for sec, rec in secs.items():
                with self.subTest(chap=chap, sec=sec):
                    self.assertRegex(sec, r"^第[一二三四五六七八九十]+节$")
                    self.assertIsInstance(rec, dict)
                    has_topic = bool(rec.get("topic") or rec.get("topics"))
                    has_kw = bool(rec.get("kw"))
                    self.assertTrue(has_topic or has_kw, "节映射至少要给 topic(s) 或 kw")

    def test_progress_template_has_required_keys(self):
        p = load(os.path.join(TPL, "进度.json"))
        for k in ("当前阶段", "已完成", "last_session_closed"):
            self.assertIn(k, p)
