#!/usr/bin/env python3
"""Download public pages from https://m-shtab.ru/ into _cache/site/ (gitignored)."""

from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "_cache" / "site"
INDEX = ROOT / "data" / "cases-index.json"
BASE = "https://m-shtab.ru"
UA = "masshtabdesign-fetch/1.0 (+https://github.com/Lllewellla/masshtabdesign)"

FIXED = [
    "/llms.txt",
    "/services",
    "/projects",
    "/color",
    "/industrial-design-rf-market/",
]


def slug_path(url_path: str) -> str:
    p = url_path.strip()
    if not p.startswith("/"):
        p = "/" + p
    if p == "/":
        return "index.html"
    p = p.rstrip("/")
    if p.endswith(".txt") or p.endswith(".xml"):
        return p.lstrip("/").replace("/", "_")
    return p.lstrip("/").replace("/", "_") + ".html"


def fetch(path: str) -> bytes:
    url = BASE + path if path.startswith("/") else path
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        return resp.read()


def save(path: str, body: bytes) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / slug_path(path)
    dest.write_bytes(body)
    return dest


def case_paths() -> list[str]:
    if not INDEX.is_file():
        return []
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    out: list[str] = []
    for case in data.get("cases", []):
        url = case.get("url") or ""
        if url.startswith(BASE):
            out.append(url[len(BASE) :] or "/")
    return out


def main() -> int:
    paths = list(FIXED)
    paths.extend(case_paths())
    seen: set[str] = set()
    ok = 0
    fail = 0
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        try:
            body = fetch(path)
            dest = save(path, body)
            print(f"ok  {path} -> {dest.relative_to(ROOT)}")
            ok += 1
        except urllib.error.HTTPError as e:
            print(f"fail {path} HTTP {e.code}", file=sys.stderr)
            fail += 1
        except Exception as e:
            print(f"fail {path} {e}", file=sys.stderr)
            fail += 1
    print(f"done ok={ok} fail={fail} cache={CACHE}")
    return 1 if fail and not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
