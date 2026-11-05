# -*- coding: utf-8 -*-
"""从题库服务器拉取题库（单向：服务器 → 本地）。

用法：
    python src/sync_bank.py --url http://1.2.3.4:9120 --token <TOKEN>
    python src/sync_bank.py --url ... --token ... --root D:/备考 --dry-run
    TOKEN 也可用环境变量 EXAM_BANK_TOKEN

只下载 sha256 变了的文件；写入前校验哈希，坏的不会覆盖本地。默认不删本地多余文件（--prune 才删）。
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import banksync
import config


def _req(url, token, method="GET", data=None):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def sync(url, token, root=None, dry_run=False, prune=False):
    root = root or config.root()
    bank = os.path.join(root, "做题系统", "题库")
    os.makedirs(bank, exist_ok=True)
    base = url.rstrip("/")

    manifest = json.loads(_req(base + "/manifest.json", token).decode("utf-8"))
    to_fetch, same, extra = banksync.diff(manifest, bank)
    result = {"url": base, "remote_count": manifest.get("count"),
              "updated": manifest.get("updated"), "downloaded": [], "failed": [],
              "unchanged": len(same), "local_only": extra, "pruned": []}

    for name in to_fetch:
        meta = manifest["files"][name]
        if dry_run:
            result["downloaded"].append({"file": name, "size": meta.get("size"), "dry_run": True})
            continue
        try:
            blob = _req(f"{base}/files/{urllib.parse.quote(name)}", token)
        except urllib.error.HTTPError as e:
            result["failed"].append({"file": name, "error": f"HTTP {e.code}"})
            continue
        got = hashlib.sha256(blob).hexdigest()
        if got != meta.get("sha256"):
            result["failed"].append({"file": name, "error": "sha256 mismatch"})
            continue
        target = os.path.join(bank, name)
        tmp = target + ".tmp"
        with open(tmp, "wb") as f:
            f.write(blob)
        os.replace(tmp, target)
        result["downloaded"].append({"file": name, "size": len(blob)})

    if prune and extra:
        for name in extra:
            if banksync.is_safe_name(name):
                os.remove(os.path.join(bank, name))
                result["pruned"].append(name)

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("EXAM_BANK_URL"), help="服务器地址，如 http://1.2.3.4:9120")
    ap.add_argument("--token", default=os.environ.get("EXAM_BANK_TOKEN"))
    ap.add_argument("--root", default=None, help="workspace 目录")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true", help="删除本地多出来、服务器上没有的题库文件")
    a = ap.parse_args()
    if not a.url or not a.token:
        ap.error("需要 --url 和 --token（或环境变量 EXAM_BANK_URL / EXAM_BANK_TOKEN）")
    r = sync(a.url, a.token, a.root, a.dry_run, a.prune)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if not r["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
