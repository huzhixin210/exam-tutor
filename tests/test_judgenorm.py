# -*- coding: utf-8 -*-
"""判断题规范化：题库里 判断 题的 options 是空、answer 是 √/×，出题脚本会整类跳过。"""
import unittest

import judgenorm


def jq(answer, options=None):
    return {"id": "x1", "qtype": "判断", "stem": "学校教育是万能的。（）",
            "options": options or {}, "answer": answer}


class TestJudgeNorm(unittest.TestCase):
    def test_empty_options_become_true_false(self):
        q = judgenorm.norm(jq("√"))
        self.assertEqual(q["options"], {"A": "正确", "B": "错误"})

    def test_check_symbol_maps_to_A(self):
        self.assertEqual(judgenorm.norm(jq("√"))["answer"], "A")
        self.assertEqual(judgenorm.norm(jq("对"))["answer"], "A")
        self.assertEqual(judgenorm.norm(jq("正确"))["answer"], "A")

    def test_cross_symbol_maps_to_B(self):
        for raw in ("×", "X", "x", "错", "错误"):
            self.assertEqual(judgenorm.norm(jq(raw))["answer"], "B", raw)

    def test_existing_options_untouched(self):
        q = judgenorm.norm(jq("√", {"A": "真", "B": "假"}))
        self.assertEqual(q["options"], {"A": "真", "B": "假"})
        self.assertEqual(q["answer"], "A")

    def test_choice_questions_untouched(self):
        q = {"id": "y", "qtype": "单选", "options": {"A": "1", "B": "2"}, "answer": "B"}
        self.assertEqual(judgenorm.norm(q), q)

    def test_unknown_answer_left_alone(self):
        self.assertEqual(judgenorm.norm(jq("??"))["answer"], "??")

    def test_does_not_mutate_input(self):
        src = jq("√")
        judgenorm.norm(src)
        self.assertEqual(src["options"], {})
        self.assertEqual(src["answer"], "√")


class TestGradeAcceptsSymbols(unittest.TestCase):
    """用户按 √/× 答题也要判对。"""

    def test_symbol_answers(self):
        import grade
        self.assertTrue(grade.is_correct("√", "√"))
        self.assertTrue(grade.is_correct("×", "×"))
        self.assertTrue(grade.is_correct("√", "A"))     # 题库已规范化成 A
        self.assertTrue(grade.is_correct("A", "√"))
        self.assertFalse(grade.is_correct("√", "×"))
