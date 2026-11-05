# -*- coding: utf-8 -*-
"""decay.py 的单元测试（TDD RED 先行）。运行：python -m unittest test_decay -v"""
import datetime
import unittest

import decay


class TestRetain(unittest.TestCase):
    def test_days_zero_is_full_score(self):
        for tier in range(7):
            self.assertAlmostEqual(decay.retain(tier, 0), 100.0, places=6)

    def test_one_half_life_is_half(self):
        for tier in range(7):
            hl = decay.TIER_HALF_LIFE[tier]
            self.assertAlmostEqual(decay.retain(tier, hl), 50.0, places=6)

    def test_tier0_drops_fastest(self):
        self.assertLess(decay.retain(0, 3), decay.retain(6, 3))

    def test_two_half_lives_is_quarter(self):
        self.assertAlmostEqual(decay.retain(3, 28), 25.0, places=6)

    def test_no_negative_and_floor(self):
        self.assertGreaterEqual(decay.retain(0, 9999), 0.0)
        self.assertAlmostEqual(decay.retain(0, 9999), 0.0, places=2)

    def test_tier_out_of_range_clamped(self):
        self.assertEqual(decay.retain(-3, 0), 100.0)
        self.assertEqual(decay.retain(99, 0), 100.0)


class TestDaysSince(unittest.TestCase):
    def test_same_day(self):
        d = datetime.date(2026, 11, 5)
        self.assertEqual(decay.days_since(d, d), 0)

    def test_cross_month(self):
        self.assertEqual(decay.days_since(datetime.date(2026, 10, 31), datetime.date(2026, 11, 2)), 2)

    def test_cross_year(self):
        self.assertEqual(decay.days_since(datetime.date(2025, 12, 31), datetime.date(2026, 1, 1)), 1)

    def test_string_input(self):
        self.assertEqual(decay.days_since("2026-11-01", "2026-11-05"), 4)

    def test_future_date(self):
        self.assertEqual(decay.days_since("2026-11-09", "2026-11-05"), 0)

    def test_none_means_never_reviewed(self):
        self.assertIsNone(decay.days_since(None, "2026-11-05"))


class TestEvidenceCap(unittest.TestCase):
    """从严档：答对1次最多档2，2-3次档3，4-5次档4，6次以上档6。"""

    def test_cap_table(self):
        self.assertEqual(decay.evidence_cap(0), 0)
        self.assertEqual(decay.evidence_cap(1), 2)
        self.assertEqual(decay.evidence_cap(2), 3)
        self.assertEqual(decay.evidence_cap(3), 3)
        self.assertEqual(decay.evidence_cap(4), 4)
        self.assertEqual(decay.evidence_cap(5), 4)
        self.assertEqual(decay.evidence_cap(6), 6)
        self.assertEqual(decay.evidence_cap(99), 6)


class TestNextTier(unittest.TestCase):
    def test_correct_rises_one(self):
        self.assertEqual(decay.next_tier(1, ok=True, evidence=4), 2)

    def test_correct_capped_by_evidence(self):
        # 规则：答对升 1 档，但不超过证据上限（证据1次 -> 上限档2）
        self.assertEqual(decay.next_tier(0, ok=True, evidence=1), 1)
        self.assertEqual(decay.next_tier(2, ok=True, evidence=1), 2)
        self.assertEqual(decay.next_tier(3, ok=True, evidence=1), 2)

    def test_wrong_drops_two_floor_zero(self):
        self.assertEqual(decay.next_tier(4, ok=False, evidence=9), 2)
        self.assertEqual(decay.next_tier(1, ok=False, evidence=9), 0)
        self.assertEqual(decay.next_tier(0, ok=False, evidence=9), 0)

    def test_uncertain_does_not_rise(self):
        self.assertEqual(decay.next_tier(3, ok=True, evidence=9, uncertain=True), 3)

    def test_uncertain_like_wrong_when_not_ok(self):
        self.assertEqual(decay.next_tier(3, ok=False, evidence=9, uncertain=True), 1)

    def test_top_tier_stays(self):
        self.assertEqual(decay.next_tier(6, ok=True, evidence=99), 6)


class TestTierFromScore(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(decay.tier_from_score(100), 4)
        self.assertEqual(decay.tier_from_score(90), 4)
        self.assertEqual(decay.tier_from_score(85), 3)
        self.assertEqual(decay.tier_from_score(70), 2)
        self.assertEqual(decay.tier_from_score(50), 1)
        self.assertEqual(decay.tier_from_score(30), 0)
        self.assertEqual(decay.tier_from_score(None), 0)


class TestStatus(unittest.TestCase):
    def test_bands_relative_to_base(self):
        self.assertEqual(decay.status_of(95, 100), "稳固")
        self.assertEqual(decay.status_of(90, 100), "稳固")
        self.assertEqual(decay.status_of(80, 100), "松动")
        self.assertEqual(decay.status_of(65, 100), "欠账")
        self.assertEqual(decay.status_of(59.9, 100), "红色")

    def test_not_mastered_is_its_own_band(self):
        # 上次测得 55 分：是"没会"，不是"忘了"
        self.assertEqual(decay.status_of(55, 55), "未掌握")
        self.assertEqual(decay.status_of(0, 30), "未掌握")

    def test_base_scales_retention(self):
        self.assertAlmostEqual(decay.retain(2, 0, 70), 70.0, places=6)
        self.assertAlmostEqual(decay.retain(2, 7, 70), 35.0, places=6)


class TestQueue(unittest.TestCase):
    def test_sorted_by_lowest_r_first(self):
        recs = {
            "A": {"掌握度": 100, "档位": 6, "上次复习": "2026-11-05"},
            "B": {"掌握度": 25, "档位": 0, "上次复习": "2026-11-03"},
            "C": {"掌握度": 80, "档位": 4, "上次复习": "2026-10-20"},
        }
        q = decay.build_queue(recs, today="2026-11-05")
        self.assertEqual(q[0][0], "B")
        self.assertEqual([q[i][0] for i in range(3)], ["B", "C", "A"])

    def test_never_reviewed_shows_base_score(self):
        recs = {"X": {"掌握度": 60, "档位": 2, "上次复习": None}}
        q = decay.build_queue(recs, today="2026-11-05")
        self.assertEqual(q[0][1], 60.0)
        self.assertIn(q[0][2], ("松动", "未掌握"))

    def test_old_shape_record_without_tier_still_works(self):
        recs = {"Y": {"掌握度": 55, "最近复习": "2026-11-01"}}
        q = decay.build_queue(recs, today="2026-11-05")
        self.assertEqual(len(q), 1)
        self.assertLess(q[0][1], 100)


class TestCommittedAnswers(unittest.TestCase):
    """回归：档位会随答对变高、随答错变低，且 R 不会超过 100。"""

    def test_cycle(self):
        tier, ev = 0, 0
        for _ in range(7):   # 每次只升1档，6次以上证据才允许到档6
            ev += 1
            tier = decay.next_tier(tier, ok=True, evidence=ev)
        self.assertEqual(tier, 6)
        self.assertLessEqual(decay.retain(tier, 0), 100.0)
        tier = decay.next_tier(tier, ok=False, evidence=ev)
        self.assertEqual(tier, 4)


if __name__ == "__main__":
    unittest.main()
