# -*- coding: utf-8 -*-
"""Add repo_case_url to case YAML, body line, and cases-index.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "cases"
INDEX = ROOT / "data" / "cases-index.json"
GH = "https://github.com/Lllewellla/masshtabdesign/blob/main/cases/{slug}.md"
BODY_LINE_RE = re.compile(r"^\*\*Исходные данные в репозитории:\*\*.*$", re.M)


def repo_url(slug: str) -> str:
    return GH.format(slug=slug)


def patch_markdown(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    fm = parts[1]
    body = parts[2]
    slug_m = re.search(r"^slug:\s*(.+)$", fm, re.M)
    if not slug_m:
        return False
    slug = slug_m.group(1).strip().strip('"').strip("'")
    url = repo_url(slug)

    if re.search(r"^repo_case_url:\s*", fm, re.M):
        fm = re.sub(r"^repo_case_url:\s*.*$", f"repo_case_url: {url}", fm, count=1, flags=re.M)
    else:
        # after official_case_url or url
        if re.search(r"^official_case_url:\s*", fm, re.M):
            fm = re.sub(
                r"^(official_case_url:\s*.*)$",
                rf"\1\nrepo_case_url: {url}",
                fm,
                count=1,
                flags=re.M,
            )
        elif re.search(r"^url:\s*", fm, re.M):
            fm = re.sub(
                r"^(url:\s*.*)$",
                rf"\1\nrepo_case_url: {url}",
                fm,
                count=1,
                flags=re.M,
            )
        else:
            fm = fm.rstrip("\n") + f"\nrepo_case_url: {url}\n"

    line = f"**Исходные данные в репозитории:** {url}"
    canon = "**Страница на сайте:**"
    if BODY_LINE_RE.search(body):
        body = BODY_LINE_RE.sub(line, body, count=1)
    elif canon in body:
        body = re.sub(
            rf"^({re.escape(canon)}.*)$",
            rf"\1\n{line}",
            body,
            count=1,
            flags=re.M,
        )
    else:
        # after first H1 block meta
        body = "\n" + line + "\n" + body.lstrip("\n")

    new = f"---{fm}---{body}"
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def patch_index() -> int:
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    n = 0
    for case in data.get("cases", []):
        slug = case["slug"]
        url = repo_url(slug)
        if case.get("repo_case_url") != url:
            case["repo_case_url"] = url
            n += 1
    INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return n


def main() -> None:
    changed = 0
    for path in sorted(CASES.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        if patch_markdown(path):
            changed += 1
    idx = patch_index()
    print(f"markdown_changed={changed} index_repo_urls_set={idx} total_md={len(list(CASES.glob('*.md')))}")


if __name__ == "__main__":
    main()
