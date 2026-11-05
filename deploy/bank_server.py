#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题库同步服务（单文件、零第三方依赖）。

用途：把题库放在自己的服务器上，自己 push、朋友的 Hermes pull，不用 scp / 不用网盘。

接口（全部要求令牌）：
    GET  /healthz                  → 200 ok（不要令牌）
    GET  /manifest.json            → 清单 {files:{name:{size,sha256}}}
    GET  /files/<name>.json        → 单个题库文件
    PUT  /files/<name>.json        → 上传（原子写入）
    PUT  /manifest.json            → 上传清单

令牌位置三选一：请求头 `Authorization: Bearer <token>`、`X-Bank-Token: <token>`、查询参数 `?token=`。

启动：
    EXAM_BANK_TOKEN=xxx python3 bank_server.py --data /srv/exam-bank/data --port 9120
"""
import argparse
import json
import os
import re
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

MANIFEST = "manifest.json"
MAX_BODY = 64 * 1024 * 1024          # 单文件上限 64MB
SAFE = re.compile(r"^[^/\\]*\.json$")


def safe_name(name):
    name = unquote(name or "").strip()
    if not name or name == MANIFEST or ".." in name:
        return None
    return name if SAFE.match(name) else None


class Handler(BaseHTTPRequestHandler):
    server_version = "exam-bank/1"
    data_dir = "."
    token = ""

    # ---------------- helpers ----------------
    def _token_ok(self):
        want = self.token
        got = None
        auth = self.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            got = auth[7:].strip()
        if not got:
            got = self.headers.get("X-Bank-Token")
        if not got:
            qs = parse_qs(urlparse(self.path).query)
            got = (qs.get("token") or [None])[0]
        return bool(want) and got == want

    def _send(self, code, body=b"", ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _path_parts(self):
        return [p for p in urlparse(self.path).path.split("/") if p]

    # ---------------- GET ----------------
    def do_GET(self):
        parts = self._path_parts()
        if parts == ["healthz"]:
            return self._json(200, {"ok": True})
        if not self._token_ok():
            return self._json(401, {"error": "token required"})
        if parts == [MANIFEST]:
            p = os.path.join(self.data_dir, MANIFEST)
            if not os.path.isfile(p):
                return self._json(404, {"error": "manifest not published yet"})
            return self._send(200, open(p, "rb").read())
        if len(parts) == 2 and parts[0] == "files":
            name = safe_name(parts[1])
            if not name:
                return self._json(400, {"error": "bad file name"})
            p = os.path.join(self.data_dir, name)
            if not os.path.isfile(p):
                return self._json(404, {"error": "not found"})
            return self._send(200, open(p, "rb").read())
        return self._json(404, {"error": "not found"})

    # ---------------- PUT ----------------
    def do_PUT(self):
        if not self._token_ok():
            return self._json(401, {"error": "token required"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._json(400, {"error": "bad length"})
        if length <= 0 or length > MAX_BODY:
            return self._json(400, {"error": f"body size {length} out of range"})
        body = self.rfile.read(length)
        parts = self._path_parts()

        if len(parts) == 2 and parts[0] == "files":
            name = safe_name(parts[1])
            if not name:
                return self._json(400, {"error": "bad file name"})
            if not body.lstrip().startswith(b"{") and not body.lstrip().startswith(b"["):
                return self._json(400, {"error": "not json"})
            self._atomic_write(name, body)
            return self._json(200, {"ok": True, "file": name, "size": len(body)})

        if parts == [MANIFEST]:
            try:
                m = json.loads(body.decode("utf-8"))
            except Exception as e:
                return self._json(400, {"error": f"bad manifest: {e}"})
            if not isinstance(m.get("files"), dict):
                return self._json(400, {"error": "manifest.files missing"})
            # 只允许清单里出现安全文件名，避免服务端写入越界
            for k in m["files"]:
                if not safe_name(k):
                    return self._json(400, {"error": f"bad name in manifest: {k}"})
            self._atomic_write(MANIFEST, body)
            return self._json(200, {"ok": True, "count": len(m["files"])})

        return self._json(404, {"error": "not found"})

    def _atomic_write(self, name, data):
        path = os.path.join(self.data_dir, name)
        fd, tmp = tempfile.mkstemp(dir=self.data_dir, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("EXAM_BANK_DATA", "/srv/exam-bank/data"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("EXAM_BANK_PORT", 9120)))
    ap.add_argument("--host", default=os.environ.get("EXAM_BANK_HOST", "0.0.0.0"))
    ap.add_argument("--token", default=os.environ.get("EXAM_BANK_TOKEN", ""))
    a = ap.parse_args()

    token = a.token or ""
    if not token:
        token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.txt")
        if os.path.isfile(token_file):
            token = open(token_file, encoding="utf-8").read().strip()
    if len(token) < 16:
        sys.exit("EXAM_BANK_TOKEN 必须至少 16 字符（用 openssl rand -hex 16 生成）")

    os.makedirs(a.data, exist_ok=True)
    Handler.data_dir = a.data
    Handler.token = token
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"exam-bank serving {a.data} on {a.host}:{a.port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
