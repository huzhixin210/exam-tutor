# -*- coding: utf-8 -*-
"""题库同步的公共逻辑（纯函数，不联网）：清单、哈希、差异判定。

设计：
- 服务器是**题库唯一真源**，本地只是镜像；单向（发布/拉取）不会产生冲突
- 每个文件带 sha256，只在哈希不同时才传输
- 只认 `.json`，拒绝任何带路径分隔符的文件名
"""
import datetime
import hashlib
import json
import os

MANIFEST_NAME = "manifest.json"


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def is_safe_name(name):
    return bool(name) and name.endswith(".json") and name != MANIFEST_NAME \
        and "/" not in name and "\\" not in name and ".." not in name


def bank_files(folder):
    """目录下的题库文件（只认 .json，排除 manifest）。"""
    if not os.path.isdir(folder):
        return []
    return sorted(n for n in os.listdir(folder) if is_safe_name(n))


def build_manifest(folder, extra=None):
    files = {}
    for name in bank_files(folder):
        p = os.path.join(folder, name)
        files[name] = {"size": os.path.getsize(p), "sha256": sha256_file(p)}
    m = {"version": 1,
         "updated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
         "count": len(files),
         "files": files}
    if extra:
        m.update(extra)
    return m


def diff(manifest, folder):
    """本地目录 vs 远端清单 -> (需要下载, 已是同版, 远端没有的本地文件)。"""
    remote = ((manifest or {}).get("files") or {})
    local = build_manifest(folder).get("files", {})
    to_fetch, same = [], []
    for name, meta in remote.items():
        if not is_safe_name(name):
            continue
        cur = local.get(name)
        (same if cur and cur["sha256"] == meta.get("sha256") else to_fetch).append(name)
    extra_local = sorted(set(local) - set(remote))
    return sorted(to_fetch), sorted(same), extra_local


def manifest_from_dir_or_file(path):
    """读一个 manifest.json 文件（给 CLI 用）。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
