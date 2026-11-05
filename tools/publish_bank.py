# -*- coding: utf-8 -*-
"""把本地题库发布到服务器（单向：本地 → 服务器）。

用法：
    python tools/publish_bank.py --url http://1.2.3.4:9120 --token <TOKEN> --dir "<题库目录>"
    python tools/publish_bank.py --url ... --token ... --dir ... --dry-run
    TOKEN 也可用环境变量 EXAM_BANK_TOKEN

只上传 sha256 变了的文件，最后上传 manifest。服务器上多出来的旧文件默认不动（--prune 才删，需要服务端支持 DELETE，
当前版本不做，避免误删）。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))
import banksync  # noqa: E402


def _put(url, token, data):
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _get(url, token):
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def publish(url, token, folder, dry_run=False):
    base = url.rstrip("/")
    local = banksync.build_manifest(folder)
    try:
        remote = json.loads(_get(base + "/manifest.json", token).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        remote = {"files": {}}
    rfiles = remote.get("files") or {}

    plan = {"upload": [], "skip": [], "failed": []}
    for name, meta in local["files"].items():
        r = rfiles.get(name)
        if r and r.get("sha256") == meta["sha256"]:
            plan["skip"].append(name)
            continue
        if dry_run:
            plan["upload"].append({"file": name, "size": meta["size"], "dry_run": True})
            continue
        body = open(os.path.join(folder, name), "rb").read()
        try:
            _put(f"{base}/files/{urllib.parse.quote(name)}", token, body)
            plan["upload"].append({"file": name, "size": len(body)})
        except urllib.error.HTTPError as e:
            plan["failed"].append({"file": name, "error": f"HTTP {e.code} {e.read()[:200]!r}"})

    if not dry_run and not plan["failed"]:
        payload = json.dumps(local, ensure_ascii=False).encode("utf-8")
        _put(base + "/manifest.json", token, payload)
        plan["manifest"] = {"count": local["count"], "updated": local["updated"]}

    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("EXAM_BANK_URL"))
    ap.add_argument("--token", default=os.environ.get("EXAM_BANK_TOKEN"))
    ap.add_argument("--dir", required=True, help="本地题库目录")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.url or not a.token:
        ap.error("需要 --url 和 --token（或环境变量 EXAM_BANK_URL / EXAM_BANK_TOKEN）")
    r = publish(a.url, a.token, a.dir, a.dry_run)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if not r["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
