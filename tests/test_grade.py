# -*- coding: utf-8 -*-
"""grade.py 的单元测试（TDD RED 先行）。

计分表（v2 间隔验证，必须与 skills/exam-tutor/references/掌握度规则v2.md 一致）：
    首对 45 / 同日再对 +3（封顶 50）/ 跨 1 日对 +10 / 跨 3 日对 +15
    首错 30 / 之后再错 -15（下限 0）/ 上限 100
"""
import datetime
import unittest

import grade


D = datetime.date


def rec(score=0, n=0, wrong=0, last=None, cross=0):
    return {"掌握度": score, "答题数": n, "错题数": wrong,
            "最近复习": last, "跨日对次": cross}


class TestCorrectScoring(unittest.TestCase):
    def test_first_correct_is_45(self):
        r, _ = grade.update(rec(), True, D(2026, 11, 5))
        self.assertEqual(r["掌握度"], 45)
        self.assertEqual(r["答题数"], 1)
        self.assertEqual(r["错题数"], 0)
        self.assertEqual(r["最近复习"], "2026-11-05")

    def test_first_wrong_is_30(self):
        r, _ = grade.update(rec(), False, D(2026, 11, 5))
        self.assertEqual(r["掌握度"], 30)
        self.assertEqual(r["错题数"], 1)

    def test_same_day_correct_adds_3_and_caps_50(self):
        r, _ = grade.update(rec(45, 1, 0, "2026-11-05"), True, D(2026, 11, 5))
        self.assertEqual(r["掌握度"], 48)
        r, _ = grade.update(rec(49, 2, 0, "2026-11-05"), True, D(2026, 11, 5))
        self.assertEqual(r["掌握度"], 50)          # 同日封顶 50

    def test_same_day_correct_does_not_lower_high_score(self):
        r, _ = grade.update(rec(84, 5, 0, "2026-11-04", 3), True, D(2026, 11, 5))
        self.assertGreaterEqual(r["掌握度"], 84)   # 跨日 +10 封顶 100

    def test_cross_one_day_adds_10(self):
        r, _ = grade.update(rec(45, 1, 0, "2026-11-04"), True, D(2026, 11, 5))
        self.assertEqual(r["掌握度"], 55)
        self.assertEqual(r["跨日对次"], 1)

    def test_cross_three_days_adds_15(self):
        r, _ = grade.update(rec(45, 1, 0, "2026-11-02"), True, D(2026, 11, 5))
        self.assertEqual(r["掌握度"], 60)

    def test_wrong_minus_15_floor_zero(self):
        r, _ = grade.update(rec(10, 2, 1, "2026-11-04"), False, D(2026, 11, 5))
        self.assertEqual(r["掌握度"], 0)

    def test_cap_84_while_no_cross_day_evidence(self):
        r, _ = grade.update(rec(80, 3, 0, "2026-11-04", 0), True, D(2026, 11, 5))
        self.assertEqual(r["掌握度"], 84)          # 跨日对次 1 -> 仍不可进 85+

    def test_cap_lifted_after_three_cross_day_corrects(self):
        r, _ = grade.update(rec(84, 6, 0, "2026-11-04", 3), True, D(2026, 11, 5))
        self.assertEqual(r["掌握度"], 94)          # 84 + 10，可进 85+


class TestSchedule(unittest.TestCase):
    def test_wrong_schedules_tomorrow(self):
        r, _ = grade.update(rec(60, 3, 1, "2026-11-04"), False, D(2026, 11, 5))
        self.assertEqual(r["next_review"], "2026-11-06")

    def test_unmastered_schedules_tomorrow(self):
        r, _ = grade.update(rec(45, 1, 1, "2026-11-04"), True, D(2026, 11, 5))
        self.assertEqual(r["next_review"], "2026-11-06")   # 45+10=55 < 60

    def test_60_69_schedules_plus_two(self):
        r, _ = grade.update(rec(50, 2, 0, "2026-11-04"), True, D(2026, 11, 5))
        self.assertEqual(r["next_review"], "2026-11-07")   # 50+10=60 -> +2

    def test_70_84_schedules_plus_four(self):
        r, _ = grade.update(rec(60, 3, 0, "2026-11-04"), True, D(2026, 11, 5))
        self.assertEqual(r["next_review"], "2026-11-09")   # 60+10=70 -> +4


class TestJudge(unittest.TestCase):
    def test_multi_choice_order_insensitive(self):
        self.assertTrue(grade.is_correct("ACD", "ADC"))
        self.assertTrue(grade.is_correct("a,c,d", "ACD"))

    def test_multi_choice_missing_option_is_wrong(self):
        self.assertFalse(grade.is_correct("AC", "ACD"))

    def test_single_choice(self):
        self.assertTrue(grade.is_correct("B", "B"))
        self.assertFalse(grade.is_correct("A", "B"))

    def test_question_mark_is_wrong(self):
        self.assertFalse(grade.is_correct("?", "B"))

    def test_uncertain_correct_still_counts(self):
        r, info = grade.update(rec(45, 1, 0, "2026-11-04"), True, D(2026, 11, 5), uncertain=True)
        self.assertEqual(r["掌握度"], 55)
        self.assertTrue(info["uncertain"])
        self.assertEqual(r["档位"], 0)              # 不确定不升档


class TestBatch(unittest.TestCase):
    def test_batch_grades_each_item(self):
        items = [{"no": 1, "id": "a", "answer": "B", "kp": "考点1"},
                 {"no": 2, "id": "b", "answer": "ACD", "kp": "考点2"},
                 {"no": 3, "id": "c", "answer": "C", "kp": "考点3"}]
        out = grade.grade_batch(items, ["B", "AC", "?"], D(2026, 11, 5))
        self.assertEqual([o["correct"] for o in out], [True, False, False])
        self.assertEqual(out[1]["user"], "AC")
        self.assertEqual(out[2]["user"], "?")
