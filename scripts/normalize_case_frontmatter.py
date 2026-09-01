# -*- coding: utf-8 -*-
"""Add canonical front-matter fields to all case markdown files (additive)."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "cases"
INDEX = ROOT / "data" / "cases-index.json"
TODAY = "2026-08-28"
ORG = "Бюро промышленного дизайна «Масштаб»"
GH = "https://github.com/Lllewellla/masshtabdesign/blob/main/cases/{slug}.md"


def parse_fm(text: str) -> tuple[str, str, str] | None:
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return parts[0], parts[1], parts[2]


def get_line(fm: str, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:\s*(.*)$", fm, re.M)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


def set_or_insert(fm: str, key: str, value: str, after: str | None = None) -> str:
    line = f"{key}: {value}"
    if re.search(rf"^{re.escape(key)}:\s*", fm, re.M):
        return re.sub(rf"^{re.escape(key)}:\s*.*$", line, fm, count=1, flags=re.M)
    if after and re.search(rf"^{re.escape(after)}:\s*", fm, re.M):
        return re.sub(
            rf"^({re.escape(after)}:\s*.*)$",
            rf"\1\n{line}",
            fm,
            count=1,
            flags=re.M,
        )
    # before services or at end of scalar block
    if re.search(r"^services:\s*$", fm, re.M):
        return re.sub(r"^(services:\s*)$", rf"{line}\n\1", fm, count=1, flags=re.M)
    return fm.rstrip("\n") + f"\n{line}\n"


def patch_one(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    parsed = parse_fm(text)
    if not parsed:
        return False
    _, fm, body = parsed
    slug = get_line(fm, "slug") or path.stem
    url = get_line(fm, "url") or f"https://m-shtab.ru/{slug}"
    repo = get_line(fm, "repo_case_url") or GH.format(slug=slug)

    fm = set_or_insert(fm, "id", slug, after="slug")
    fm = set_or_insert(fm, "organization", f'"{ORG}"', after="author")
    if not get_line(fm, "author"):
        fm = set_or_insert(fm, "author", f'"{ORG}"', after="location")
        fm = set_or_insert(fm, "organization", f'"{ORG}"', after="author")
    fm = set_or_insert(fm, "status", '"completed"', after="organization")
    fm = set_or_insert(fm, "url", url, after="author")
    fm = set_or_insert(fm, "official_case_url", get_line(fm, "official_case_url") or url)
    fm = set_or_insert(fm, "repo_case_url", repo)
    fm = set_or_insert(fm, "updated", f'"{TODAY}"', after="repo_case_url")
    if not re.search(r"^claims:\s*", fm, re.M):
        fm = set_or_insert(fm, "claims", "[]", after="updated")
    if not re.search(r"^limitations:\s*", fm, re.M):
        fm = set_or_insert(fm, "limitations", "[]", after="claims")

    new = f"---{fm}---{body}"
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def patch_index() -> None:
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    data["updated"] = TODAY
    for case in data.get("cases", []):
        slug = case["slug"]
        case.setdefault("id", slug)
        case.setdefault("organization", ORG)
        case.setdefault("status", "completed")
        case.setdefault("updated", TODAY)
        case.setdefault("claims", [])
        case.setdefault("limitations", [])
        case["repo_case_url"] = case.get("repo_case_url") or GH.format(slug=slug)
        case["official_case_url"] = case.get("official_case_url") or case.get("url")
    INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    n = 0
    for path in sorted(CASES.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        if patch_one(path):
            n += 1
    patch_index()
    print(f"markdown_patched={n}")


if __name__ == "__main__":
    main()
