# -*- coding: utf-8 -*-
"""题库同步：清单/哈希/差异判定。"""
import json
import os
import tempfile
import unittest

import banksync


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        for name, body in (("第一章.json", '{"a":1}'), ("6600_第一章.json", '{"b":2}')):
            open(os.path.join(self.d, name), "w", encoding="utf-8").write(body)
        open(os.path.join(self.d, "已做.json"), "w", encoding="utf-8").write("{}")

    def test_only_json_counted(self):
        open(os.path.join(self.d, "notes.md"), "w").write("x")
        m = banksync.build_manifest(self.d)
        self.assertEqual(m["count"], 2)          # 已做.json 属个人状态，不共享
        self.assertNotIn("notes.md", m["files"])
        self.assertNotIn("已做.json", m["files"])

    def test_hash_stable(self):
        m1 = banksync.build_manifest(self.d)["files"]["第一章.json"]["sha256"]
        m2 = banksync.build_manifest(self.d)["files"]["第一章.json"]["sha256"]
        self.assertEqual(m1, m2)

    def test_changed_file_detected(self):
        before = banksync.build_manifest(self.d)
        open(os.path.join(self.d, "第一章.json"), "w", encoding="utf-8").write('{"a":999}')
        fetch, same, extra = banksync.diff(before, self.d)
        self.assertEqual(fetch, ["第一章.json"])
        self.assertIn("6600_第一章.json", same)

    def test_new_local_file_reported_as_extra_for_publish(self):
        before = banksync.build_manifest(self.d)
        open(os.path.join(self.d, "第二章.json"), "w", encoding="utf-8").write("{}")
        fetch, same, extra = banksync.diff(before, self.d)
        self.assertEqual(extra, ["第二章.json"])     # 本地新增 -> 发布方向要上传
        self.assertEqual(fetch, [])

    def test_remote_only_file_goes_to_fetch(self):
        m = banksync.build_manifest(self.d)
        os.remove(os.path.join(self.d, "6600_第一章.json"))
        fetch, same, extra = banksync.diff(m, self.d)
        self.assertEqual(fetch, ["6600_第一章.json"])  # 远端有本地没有 -> 拉取
        self.assertEqual(extra, [])


class TestPersonalState(unittest.TestCase):
    def test_personal_files_never_shared(self):
        import banksync as b
        for name in ("已做.json", "弃用.json", "进度.json", "掌握度.json"):
            self.assertFalse(b.is_safe_name(name), name)
        self.assertTrue(b.is_safe_name("6600_第七章.json"))

    def test_manifest_skips_done_record(self):
        d = tempfile.mkdtemp()
        for n in ("第一章.json", "已做.json"):
            open(os.path.join(d, n), "w", encoding="utf-8").write("{}")
        m = banksync.build_manifest(d)
        self.assertEqual(list(m["files"]), ["第一章.json"])


class TestSafety(unittest.TestCase):
    def test_rejects_traversal(self):
        for bad in ("../x.json", "a/b.json", "a\\b.json", "manifest.json", "x.txt", ""):
            self.assertFalse(banksync.is_safe_name(bad), bad)

    def test_accepts_normal(self):
        self.assertTrue(banksync.is_safe_name("6600_第一章.json"))
