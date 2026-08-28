#!/usr/bin/env python3
"""Build cases/*.md + data/cases-index.json from live m-shtab.ru portfolio.

Sources:
  - Tilda Store product list (portfolio on /projects)
  - Dedicated case pages (sitemap / buttonlink)
Facts only from source text. Does not invent clients, numbers, or outcomes.
"""

from __future__ import annotations

import html as html_lib
import json
import re
import ssl
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "cases"
INDEX_PATH = ROOT / "data" / "cases-index.json"
CACHE = ROOT / "_cache" / "site"
BASE = "https://m-shtab.ru"
STORE_URL = (
    "https://store.tildaapi.com/api/getproductslist/"
    "?storepartuid=463677235311&size=100"
)
UA = "masshtabdesign-fetch/1.0 (+https://github.com/Lllewellla/masshtabdesign)"
CTX = ssl.create_default_context()

# Dedicated case pages featured on site but not always in the store catalog
EXTRA_SLUGS = [
    "pogruzchik-grosler-gi-1300",
    "pro-tok",
    "rfid-schityvatel-isbc",
    "uv-lampa",
]

SKIP_SLUGS = {
    "projects",
    "services",
    "color",
    "production",
    "onepageportfolio",
    "llms",
    "cookies",
}

MARK_SERIAL = "СЕРИЙНОЕ ПРОИЗВОДСТВО"
MARK_SMALL = "МАЛАЯ СЕРИЯ"

NAV_NOISE = {
    "Услуги",
    "Проекты",
    "Производство",
    "Цветографика",
    "Публикации",
    "Контакты",
    "Заказать Дизайн",
    "ЗАКАЗАТЬ ДИЗАЙН",
    "Главная",
    "Сервисы",
    "Инструменты",
    "Отзывы клиентов",
    "Комментарии и отклики",
    "Полезные инструменты",
    "Для создания продуктов",
    "Новости",
    "Лента событий",
    "Фотолента",
    "Живые моменты",
    "Видео про дизайн",
    "Сериал про промдизайн",
    "Видео про производство",
    "Как создается всё",
    "Отправить",
    "Принимаю",
    "Close",
    "BUY NOW",
    "Load more",
    "Даю согласие с",
    "Политикой обработки персональных данных",
    "Согласие на обработку персональных данных",
    "Согласие на передачу персональных данных",
    "Даю",
    "cookies",
    "Мы используем файлы",
}


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE + "/"})
    with urllib.request.urlopen(req, timeout=45, context=CTX) as resp:
        return resp.read()


def fetch_text(url: str) -> str:
    return fetch_bytes(url).decode("utf-8", "replace")


def strip_tags(s: str) -> str:
    s = html_lib.unescape(s or "")
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</p>", "\n\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def yaml_escape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return s


def yaml_str(s: str | None) -> str:
    if s is None:
        return "null"
    if re.search(r'[:#\[\]{}\n"]', s) or s.startswith(" ") or s.endswith(" "):
        return f'"{yaml_escape(s)}"'
    if s == "" or s.lower() in {"true", "false", "null", "yes", "no"}:
        return f'"{yaml_escape(s)}"'
    return f'"{yaml_escape(s)}"'


def yaml_list(items: list[str], indent: int = 0) -> str:
    pad = " " * indent
    if not items:
        return "[]"
    lines = [f"{pad}- {yaml_str(x)[1:-1] if False else x}" for x in items]
    # quote each item safely
    out = []
    for x in items:
        out.append(f"{pad}- {yaml_str(x)}")
    return "\n".join(out)


def normalize_mark(raw: str) -> str:
    t = (raw or "").strip()
    if not t:
        return ""
    u = t.upper()
    if "СЕРИЙН" in u and "ПРОИЗВ" in u:
        return MARK_SERIAL
    if "МАЛАЯ" in u and "СЕР" in u:
        return MARK_SMALL
    return t


def slug_from_link(link: str) -> tuple[str, str]:
    """Return (slug, canonical_url) from store buttonlink or url."""
    bl = (link or "").strip()
    if not bl:
        return "", ""
    if bl.startswith("/"):
        bl = BASE + bl
    if not bl.startswith("http"):
        bl = BASE + "/" + bl.lstrip("/")
    # tproduct popup: .../tproduct/<part>-<uid>-<slug>
    m = re.search(r"/tproduct/\d+-(\d+)-([a-z0-9_\-]+)/?$", bl, re.I)
    if m:
        slug = m.group(2).rstrip("-")
        return slug, f"{BASE}/{slug}"
    # relative /slug or absolute; allow underscore (rm_frontier, carbogatto_1)
    m = re.search(r"(?:m-shtab\.ru)?/([a-z0-9_][a-z0-9_\-/]*?)(?:/?)$", bl, re.I)
    if m:
        path = m.group(1).rstrip("/")
        if "/tproduct/" in path:
            m2 = re.search(r"/tproduct/\d+-(\d+)-([a-z0-9_\-]+)$", "/" + path, re.I)
            if m2:
                slug = m2.group(2).rstrip("-")
                return slug, f"{BASE}/{slug}"
        slug = path.split("/")[-1]
        if slug and slug not in SKIP_SLUGS and "tproduct" not in slug:
            return slug, f"{BASE}/{slug}"
    return "", bl


def html_to_lines(page_html: str) -> list[str]:
    t = re.sub(r"<script[\s\S]*?</script>", " ", page_html, flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = html_lib.unescape(t)
    lines = []
    for x in t.split("\n"):
        x = re.sub(r"\s+", " ", x).strip()
        if not x or x in NAV_NOISE:
            continue
        if x in {"р.", "р"}:
            continue
        if x.startswith("+7 "):
            continue
        if "m-shtab.ru" == x or x == "design@m-shtab.ru":
            continue
        lines.append(x)
    return lines


FOOTER_STOP = (
    "авторы проекта",
    "команда проекта",
    "10:00",
    "©",
    "инн ",
    "портфолио",
    "pdf презентация",
    "все проекты на одной странице",
    "новости и публикации",
    "вакансии",
    "дизайн транспорта",
    "дизайн потребительских",
    "дизайн оборудования",
    "видео про услуги",
    "хотите такой",
    "свяжитесь с нами",
    "другие проекты",
    "buy now",
    "load more",
    "яндекс метрик",
    "google analytics",
    "мы используем файлы",
)


def is_footer_line(line: str) -> bool:
    low = line.lower().strip()
    if not low:
        return True
    if low.startswith("команда") or low.startswith("авторы проекта"):
        return True
    if any(low.startswith(x) or (x in low and len(x) > 8) for x in FOOTER_STOP):
        return True
    if re.fullmatch(r"ул\..*", low):
        return True
    if low in {"москва,", "москва", "р.", "р"}:
        return True
    return False


def page_title(page_html: str, fallback: str = "") -> str:
    m = re.search(r"<title>([^<]+)</title>", page_html, re.I)
    if not m:
        return fallback
    t = html_lib.unescape(m.group(1))
    # drop site suffix only; do NOT split on hyphen (Дизайн-ДНК)
    t = re.split(r"\s[\|\u2014]\s", t)[0]
    t = re.sub(r"\s+[—\-]\s+Бюро.*$", "", t, flags=re.I)
    t = re.sub(r"\s*\|\s*Бюро.*$", "", t, flags=re.I)
    t = re.sub(r"\s*—\s*Бюро.*$", "", t, flags=re.I)
    t = t.strip(" -—|")
    return t or fallback


def product_from_title(title: str, slug: str) -> str:
    return (title or "").strip() or slug


def product_from_page(lines: list[str], title: str, slug: str) -> str:
    """Prefer heading near portfolio mark; else normalize title."""
    for i, line in enumerate(lines):
        if normalize_mark(line) in {MARK_SERIAL, MARK_SMALL} and i > 0:
            prev = lines[i - 1].strip()
            if 3 <= len(prev) <= 100 and prev not in NAV_NOISE:
                return prev
    m = re.search(r"Дизайн(?:-ДНК)?\s+(.+)$", title, re.I)
    if m:
        rest = m.group(1).strip()
        rest = re.sub(r"^погрузчика\s+", "Погрузчик ", rest, flags=re.I)
        rest = re.sub(r"^RFID-считывателя\s+", "RFID-считыватель ", rest, flags=re.I)
        rest = re.sub(r"^считывателя\s+", "Считыватель ", rest, flags=re.I)
        rest = re.sub(r"^UV-лампы\s+", "UV-лампа ", rest, flags=re.I)
        rest = re.sub(r"^лампы\s+", "Лампа ", rest, flags=re.I)
        rest = re.sub(r"^корпуса\s+", "Корпус ", rest, flags=re.I)
        return rest
    return product_from_title(title, slug)


def extract_sections_from_lines(lines: list[str]) -> dict[str, str]:
    """Parse Задача / Решение|Работа / Результат blocks from visible lines."""
    keys = {
        "задача": "task",
        "решение": "work",
        "работа": "work",
        "работы": "work",
        "результат": "result",
    }
    sections: dict[str, list[str]] = {"task": [], "work": [], "result": []}
    current = None
    for line in lines:
        if is_footer_line(line):
            # authors line may still be useful; stop body capture
            if line.lower().startswith("авторы проекта") or line.lower().startswith(
                "команда проекта"
            ):
                current = None
                continue
            if current:
                current = None
            continue
        m = re.match(
            r"^(задача|решение|работа|работы|результат)\b\s*[.:]?\s*(.*)$",
            line,
            re.I,
        )
        if m:
            current = keys[m.group(1).lower()]
            rest = m.group(2).strip()
            if rest:
                sections[current].append(rest)
                # Inline "Результат. …" / "Задача. …" - keep the phrase, do not vacuum the page
                if current == "result":
                    current = None
            continue
        if line in {"Задача", "Решение", "Работа", "Работы", "Результат"}:
            current = keys[line.lower()]
            continue
        if current:
            if line.startswith("Команда") or line.startswith("ДРУГИЕ") or line.startswith(
                "Хотите"
            ):
                current = None
                continue
            if is_footer_line(line):
                current = None
                continue
            if current == "result":
                if sections["result"]:
                    prev = sections["result"][-1]
                    # continue soft-wrapped prose mid-sentence
                    if not prev.endswith((".", "!", "?", ":", ";")) and len(line) < 120:
                        sections["result"][-1] = f"{prev} {line}"
                        continue
                    if len(line) < 70 or line.lower().startswith(
                        ("aimol", "услуги", "презентация", "коллекц")
                    ):
                        current = None
                        continue
                sections[current].append(line)
                if len(sections["result"]) >= 2 and sections["result"][-1].endswith(
                    (".", "!", "?")
                ):
                    # allow one more only if still open; stop after 2 finished paras
                    if len(sections["result"]) >= 2:
                        current = None
                continue
            sections[current].append(line)
    return {
        k: join_soft_breaks("\n".join(v).strip())
        for k, v in sections.items()
        if v
    }


def join_soft_breaks(text: str) -> str:
    """Join accidental single-line wraps from Tilda into readable paragraphs."""
    if not text:
        return ""
    paras_out = []
    for para in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in para.split("\n") if ln.strip()]
        if not lines:
            continue
        buf = lines[0]
        for ln in lines[1:]:
            if len(buf) < 90 and not buf.endswith((".", "!", "?", ":", ";")):
                buf = f"{buf} {ln}"
            else:
                paras_out.append(buf)
                buf = ln
        paras_out.append(buf)
    return "\n\n".join(paras_out)


def extract_mark_from_lines(lines: list[str]) -> str:
    for line in lines:
        nm = normalize_mark(line)
        if nm in {MARK_SERIAL, MARK_SMALL}:
            return nm
        if line.upper() in {MARK_SERIAL, MARK_SMALL}:
            return line.upper()
    return ""


def extract_team(text: str) -> list[str]:
    m = re.search(
        r"(?:Команда(?:\s+проекта)?|Авторы проекта)\s*:\s*([^\n<]+)",
        text,
        re.I,
    )
    if not m:
        return []
    raw = strip_tags(m.group(1))
    parts = re.split(r",| и ", raw)
    return [p.strip(" .") for p in parts if p.strip(" .") and len(p.strip()) > 2]


def extract_year(text: str) -> int | None:
    m = re.search(r"Год проекта:\s*(20\d{2})", text, re.I)
    if m:
        return int(m.group(1))
    return None


def trim_result_body(body: str) -> str:
    if not body:
        return ""
    stop_markers = (
        "полюбуйтесь",
        "хотите такой",
        "свяжитесь с нами",
        "другие проекты",
        "«в первую очередь",
        '"в первую очередь',
        "отзыв",
    )
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    kept = []
    for p in paras:
        low = p.lower()
        if any(s in low for s in stop_markers):
            break
        if (p.startswith("“") or p.startswith("«")) and "хочу" in low:
            break
        kept.append(p)
        if len(kept) >= 3:
            break
    return "\n\n".join(kept)


def detect_client(title: str, blob: str) -> tuple[str | None, bool]:
    rules = [
        (r"GROSLER", "GROSLER"),
        (r"\bISBC\b", "ISBC"),
        (r"Про-ток|Pro-Tok|Pro\-Tok", "Про-ток / Pro-Tok"),
        (r"Русская механика|Русской механики", "Русская механика"),
        (r"Kitfort", "Kitfort"),
        (r"Aimol", "Aimol"),
        (r"L-Charge|L\-Charge", "L-Charge"),
        (r"Gladiator", "Gladiator"),
        (r"Kaspersky", "Kaspersky Lab"),
        (r"EKSLi|EKSLI", "EKSLi"),
        (r"Енисей", "Енисей"),
        (r"Infopathy", "Infopathy"),
        (r"Евролифтмаш", "Евролифтмаш"),
        (r"\bRPS\b", "RPS"),
        (r"REZON", "REZON"),
        (r"THIRD PIN", "THIRD PIN"),
        (r"Carbogatto", "Carbogatto"),
        (r"БАРЬЕР", "БАРЬЕР РУС"),
        (r"MiR200|Mobile Industrial Robots", "Mobile Industrial Robots"),
    ]
    for pat, name in rules:
        if re.search(pat, title, re.I) or re.search(pat, blob[:2000], re.I):
            return name, True
    cm = re.search(
        r"(?:Клиент|Заказчик)\s*:\s*([^\n]{2,60})",
        blob,
        re.I,
    )
    if cm:
        val = cm.group(1).strip(" .")
        if val and "не раскрыв" not in val.lower():
            return val, True
    return None, False


def services_from_descr(descr: str) -> list[str]:
    plain = strip_tags(descr)
    # often: title line + services line
    lines = [x.strip(" .") for x in re.split(r"[\n•|;]+", plain) if x.strip()]
    services: list[str] = []
    # look for known service phrases
    blob = " ".join(lines).lower()
    mapping = [
        ("промышленный дизайн", "промышленный дизайн"),
        ("дизайн-днк", "дизайн-ДНК"),
        ("дизайн днк", "дизайн-ДНК"),
        ("эскизн", "эскизный дизайн-проект"),
        ("3d-моделирован", "3D-моделирование"),
        ("трехмерн", "3D-моделирование"),
        ("трёхмерн", "3D-моделирование"),
        ("цветографик", "цветографика"),
        ("cmf", "цветографика"),
        ("авторский надзор", "авторский надзор прототипа"),
        ("функциональн", "функциональная графика"),
        ("визуализац", "визуализация"),
        ("промовизуализац", "промовизуализация"),
        ("концепт", "концепт-дизайн"),
    ]
    found = []
    for needle, label in mapping:
        if needle in blob and label not in found:
            found.append(label)
    if found:
        return found
    # fallback: last non-empty line if it looks like services list
    if len(lines) >= 2 and len(lines[-1]) < 120:
        bits = [b.strip() for b in re.split(r"[,.]", lines[-1]) if b.strip()]
        if 1 <= len(bits) <= 6:
            return bits
    return services


def guess_category(title: str, text: str) -> list[str]:
    blob = f"{title} {text}".lower()
    cats: list[str] = []
    rules = [
        (r"станк|плазм|шлиф|ленточн|сепаратор|сварочн|сортиров", "промышленное оборудование"),
        (r"погрузчик|вездеход|снего|квадро|мото|трамва|метротрам|дрон|аэролодк|каяк|лодк|sup|снегоход|болотоход|велосипед|байк|хаусбот|лифт", "транспорт"),
        (r"зарядн|l-charge|станци", "энергетика / инфраструктура"),
        (r"томограф|мед|терап|infopathy", "медтехника"),
        (r"rfid|корпус|электроник|линз|uv-?ламп|браслет", "корпуса / электроника"),
        (r"канистр|этикет|упаков|тар", "упаковка / тара"),
        (r"дизайн-днк|фирмстил|днк", "дизайн-ДНК"),
        (r"робот", "робототехника"),
        (r"мебел|карбон", "потребительские товары"),
        (r"банкомат|парковочн|rps", "оборудование самообслуживания"),
        (r"фильтр|kitfort|бытов", "бытовая техника"),
    ]
    for pat, label in rules:
        if re.search(pat, blob) and label not in cats:
            cats.append(label)
    return cats[:3] or ["промышленный дизайн"]


def first_sentence(text: str, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    s = parts[0] if parts else text
    if len(s) > max_len:
        s = s[: max_len - 1].rstrip() + "…"
    return s


def build_result(mark: str, result_text: str, fallback_bits: list[str]) -> str:
    body = trim_result_body((result_text or "").strip())
    if mark == MARK_SERIAL:
        lead = "поставлено на серийное производство"
        if not body:
            return lead[0].upper() + lead[1:] + "."
        # avoid duplicating if already present
        if body.lower().startswith("поставлено на серийное"):
            return body
        # if body already narrates serial production, still lead with canonical phrase
        return f"{lead[0].upper()}{lead[1:]}. {body}"
    if mark == MARK_SMALL:
        lead = "выпуск малой серией"
        if not body:
            return lead[0].upper() + lead[1:] + "."
        if body.lower().startswith("выпуск малой сер"):
            return body
        if "мал" in body.lower() and "сер" in body.lower():
            return body
        return f"{lead[0].upper()}{lead[1:]}. {body}"
    if body:
        return body
    if fallback_bits:
        return fallback_bits[0]
    return "Итог стадии зафиксирован на странице кейса; детали - по ссылке на сайт."


def short_work(services: list[str], work: str) -> str:
    if services:
        return ", ".join(services)
    return first_sentence(work, 180) or "промышленный дизайн"


def clean_infostyle(text: str) -> str:
    """Light cleanup: collapse spaces, keep paragraphs, no first-person rewrite of whole texts."""
    if not text:
        return ""
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
    paras = [p for p in paras if p]
    # drop FAQ / CTA junk if leaked
    filtered = []
    for p in paras:
        if p.startswith("Можно ли заказать"):
            continue
        if p.startswith("Что сделало бюро"):
            continue
        if p.startswith("Какие этапы"):
            continue
        if "Оставьте бриф" in p:
            continue
        filtered.append(p)
    return "\n\n".join(filtered)


def load_store_products() -> list[dict[str, Any]]:
    data = json.loads(fetch_text(STORE_URL))
    return list(data.get("products") or [])


def fetch_page(slug: str) -> str | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{slug}.html"
    try:
        body = fetch_bytes(f"{BASE}/{slug}")
        path.write_bytes(body)
        return body.decode("utf-8", "replace")
    except Exception as e:
        print(f"warn fetch /{slug}: {e}")
        return None


def case_from_store(product: dict[str, Any]) -> dict[str, Any] | None:
    store_title = strip_tags(product.get("title") or "").strip()
    if not store_title:
        return None
    link = (product.get("buttonlink") or product.get("url") or "").strip()
    slug, url = slug_from_link(link)
    if not slug:
        slug = f"case-{product.get('uid')}"
        url = link if link.startswith("http") else f"{BASE}/{slug}"
    mark = normalize_mark(product.get("mark") or "")
    descr = product.get("descr") or ""
    text_html = product.get("text") or ""
    plain = strip_tags(text_html)
    descr_plain = strip_tags(descr)

    page_html = fetch_page(slug)
    task = work = result = ""
    team = extract_team(plain)
    year = extract_year(plain) or extract_year(descr_plain)
    page_title_str = ""
    if page_html:
        page_title_str = page_title(page_html, store_title)
        lines = html_to_lines(page_html)
        if not mark:
            mark = extract_mark_from_lines(lines)
        secs = extract_sections_from_lines(lines)
        task = secs.get("task", "")
        work = secs.get("work", "")
        result = secs.get("result", "")
        team = team or extract_team("\n".join(lines))
        year = year or extract_year("\n".join(lines[:80]))

    if not task:
        # descr first line is often the short pitch; drop services line
        dlines = [x.strip() for x in descr_plain.split("\n") if x.strip()]
        task = dlines[0] if dlines else first_sentence(descr_plain, 300)
    if not work:
        body = re.sub(r"(?:Команда(?:\s+проекта)?|Авторы проекта)\s*:.*$", "", plain, flags=re.I | re.S).strip()
        work = clean_infostyle(body) or first_sentence(descr_plain, 400)
    if not result:
        result = ""

    services = services_from_descr(descr) or services_from_descr(plain)
    product_name = store_title
    title = page_title_str or f"Дизайн: {store_title}"
    if not title.lower().startswith("дизайн"):
        title = f"Дизайн: {store_title}"
    category = guess_category(product_name, f"{descr_plain} {plain}")
    client, client_public = detect_client(product_name, f"{descr_plain}\n{plain}\n{task}\n{work}")

    result_final = build_result(
        mark,
        clean_infostyle(result),
        [first_sentence(plain, 200)] if plain else [],
    )

    facts = []
    if mark == MARK_SERIAL:
        facts.append("Поставлено на серийное производство")
    if mark:
        facts.append(f"Маркер портфолио: {mark}")
    if services:
        facts.append("Работы: " + ", ".join(services))
    if category:
        facts.append("Категория: " + ", ".join(category))
    if client:
        facts.append(f"Клиент: {client}")
    facts.append(f"Страница: {url}")

    return {
        "title": title,
        "slug": slug,
        "client": client,
        "client_public": client_public,
        "product": product_name,
        "category": category,
        "mark": mark,
        "location": "Россия",
        "year": year,
        "url": url,
        "services": services,
        "team": team,
        "task": clean_infostyle(task) or first_sentence(descr_plain, 280) or "См. страницу кейса.",
        "work": clean_infostyle(work) or short_work(services, ""),
        "result": result_final,
        "facts": facts,
        "short_task": first_sentence(task or descr_plain, 180),
        "short_work": short_work(services, work),
        "source": "store",
        "uid": product.get("uid"),
    }


def case_from_extra_page(slug: str) -> dict[str, Any] | None:
    page_html = fetch_page(slug)
    if not page_html:
        return None
    lines = html_to_lines(page_html)
    title = page_title(page_html, slug)
    product_name = product_from_page(lines, title, slug)
    mark = extract_mark_from_lines(lines)
    secs = extract_sections_from_lines(lines)
    team = extract_team("\n".join(lines))
    year = extract_year("\n".join(lines[:80]))
    services: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("Какие этапы") and i + 1 < len(lines):
            services = services_from_descr(lines[i + 1])
            break
    blob = "\n".join(lines)
    category = guess_category(product_name, blob)
    task = secs.get("task") or ""
    work = secs.get("work") or ""
    result = secs.get("result") or ""
    client, client_public = detect_client(title + " " + product_name, blob)

    if slug == "uv-lampa" and not mark:
        if "вышло на рынок" in blob.lower() or "серийн" in blob.lower():
            mark = MARK_SERIAL

    result_final = build_result(mark, clean_infostyle(result), [])
    services = services or services_from_descr(work)
    facts = []
    if mark == MARK_SERIAL:
        facts.append("Поставлено на серийное производство")
    if mark:
        facts.append(f"Маркер портфолио: {mark}")
    if services:
        facts.append("Работы: " + ", ".join(services))
    if client:
        facts.append(f"Клиент: {client}")
    facts.append(f"Страница: {BASE}/{slug}")

    card_title = title if title.lower().startswith("дизайн") else f"Дизайн: {product_name}"

    return {
        "title": card_title,
        "slug": slug,
        "client": client,
        "client_public": client_public,
        "product": product_name,
        "category": category,
        "mark": mark,
        "location": "Россия",
        "year": year,
        "url": f"{BASE}/{slug}",
        "services": services,
        "team": team,
        "task": clean_infostyle(task) or "См. страницу кейса.",
        "work": clean_infostyle(work) or "См. страницу кейса.",
        "result": result_final,
        "facts": facts,
        "short_task": first_sentence(task, 180),
        "short_work": short_work(services, work),
        "source": "page",
        "uid": None,
    }


def render_md(c: dict[str, Any]) -> str:
    fm = ["---"]
    fm.append(f"title: {yaml_str(c['title'])}")
    fm.append(f"slug: {c['slug']}")
    if c.get("client"):
        fm.append(f"client: {yaml_str(c['client'])}")
        fm.append("client_public: true")
    else:
        fm.append("client: null")
        fm.append("client_public: false")
    fm.append(f"product: {yaml_str(c['product'])}")
    cats = c.get("category") or []
    if cats:
        fm.append("category:")
        fm.append(yaml_list(cats, 2))
    else:
        fm.append("category: []")
    if c.get("mark"):
        fm.append(f"mark: {yaml_str(c['mark'])}")
    else:
        fm.append('mark: ""')
    fm.append(f"location: {yaml_str(c.get('location') or 'Россия')}")
    if c.get("year"):
        fm.append(f"year: {c['year']}")
    fm.append('author: "Бюро промышленного дизайна «Масштаб»"')
    fm.append(f"url: {c['url']}")
    fm.append(f"official_case_url: {c['url']}")
    services = c.get("services") or []
    if services:
        fm.append("services:")
        fm.append(yaml_list(services, 2))
    else:
        fm.append("services: []")
    team = c.get("team") or []
    if team:
        fm.append("team:")
        fm.append(yaml_list(team, 2))
    else:
        fm.append("team: []")
    fm.append("---")
    fm.append("")

    h1 = c["product"]
    body = [f"# {h1}", ""]
    if c.get("client"):
        body.append(f"**Клиент:** {c['client']}  ")
    elif c.get("client_public") is False:
        body.append("**Клиент:** имя в открытую не публикуем  ")
    body.append(f"**Продукт:** {c['product']}  ")
    if c.get("mark"):
        body.append(f"**Стадия / маркер:** {c['mark']}  ")
    body.append("**Бюро:** «Масштаб», Москва  ")
    body.append(f"**Страница на сайте:** {c['url']}")
    body.append("")
    body.append("## Короткая карточка")
    body.append("")
    body.append(f"**{c['product']}**  ")
    body.append(f"**Задача:** {c.get('short_task') or first_sentence(c['task'], 180)}  ")
    body.append(f"**Работа:** {c.get('short_work') or short_work(services, c['work'])}  ")
    body.append(f"**Результат:** {first_sentence(c['result'], 220)}")
    body.append("")
    body.append("## Задача")
    body.append("")
    body.append(c["task"])
    body.append("")
    body.append("## Работа")
    body.append("")
    body.append(c["work"])
    body.append("")
    body.append("## Результат")
    body.append("")
    body.append(c["result"])
    body.append("")
    body.append("## Ключевые факты для цитирования")
    body.append("")
    for f in c.get("facts") or []:
        body.append(f"- {f}")
    if team:
        body.append("")
        body.append("## Команда")
        body.append("")
        body.append(", ".join(team))
    body.append("")
    body.append("## CTA")
    body.append("")
    body.append(
        "Бриф и контакты: [m-shtab.ru](https://m-shtab.ru/) · design@m-shtab.ru · +7 495 101-22-55"
    )
    body.append("")
    return "\n".join(fm + body)


def write_index(cases: list[dict[str, Any]]) -> None:
    cases_sorted = sorted(cases, key=lambda c: c["slug"])
    payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Masshtab design cases index",
        "description": "Machine-readable index of portfolio cases for GEO / LLM",
        "publisher": {
            "name": "Бюро промышленного дизайна «Масштаб»",
            "url": "https://m-shtab.ru/",
            "repository": "https://github.com/Lllewellla/masshtabdesign",
        },
        "updated": date.today().isoformat(),
        "source": {
            "portfolio": "https://m-shtab.ru/projects",
            "note": "Карточки собраны из портфолио и страниц кейсов; цифры бюро - только claims.json",
        },
        "cases": [],
    }
    for c in cases_sorted:
        entry = {
            "slug": c["slug"],
            "title": c["title"],
            "product": c["product"],
            "category": c.get("category") or [],
            "mark": c.get("mark") or None,
            "location": c.get("location") or "Россия",
            "services": c.get("services") or [],
            "url": c["url"],
            "official_case_url": c["url"],
            "markdown": f"cases/{c['slug']}.md",
        }
        if c.get("client"):
            entry["client"] = c["client"]
        else:
            entry["client"] = None
            entry["client_public"] = False
        if c.get("year"):
            entry["year"] = c["year"]
        payload["cases"].append(entry)
    INDEX_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_readme(cases: list[dict[str, Any]]) -> None:
    lines = [
        "# Кейсы бюро «Масштаб»",
        "",
        "Markdown-карточки для AI-поиска (GEO). Полные страницы с фото - на сайте. "
        "Канон цифр бюро: [`../data/claims.json`](../data/claims.json).",
        "",
        "| Slug | Продукт | Маркер | Сайт |",
        "|------|---------|--------|------|",
    ]
    for c in sorted(cases, key=lambda x: x["slug"]):
        mark = c.get("mark") or "—"
        lines.append(
            f"| [{c['slug']}]({c['slug']}.md) | {c['product']} | {mark} | {c['url']} |"
        )
    lines += [
        "",
        f"Всего карточек: **{len(cases)}**. Машинный индекс: [`../data/cases-index.json`](../data/cases-index.json).",
        "",
        "Автор: **Бюро промышленного дизайна «Масштаб»**, Москва. "
        "Имена клиентов - только уже открытые на сайте.",
        "",
    ]
    (CASES_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    products = load_store_products()
    print(f"store products: {len(products)}")

    by_slug: dict[str, dict[str, Any]] = {}

    for p in products:
        c = case_from_store(p)
        if not c:
            continue
        if c["slug"] in SKIP_SLUGS:
            continue
        by_slug[c["slug"]] = c
        print(f"ok store {c['slug']} mark={c.get('mark') or '-'}")

    for slug in EXTRA_SLUGS:
        if slug in by_slug:
            # enrich from dedicated page
            extra = case_from_extra_page(slug)
            if extra:
                # prefer page sections when richer
                cur = by_slug[slug]
                for k in ("task", "work", "result", "team", "services", "mark", "client", "year", "title", "facts", "short_task", "short_work"):
                    if extra.get(k):
                        cur[k] = extra[k]
                cur["client_public"] = extra.get("client_public", cur.get("client_public"))
                cur["url"] = extra["url"]
                print(f"ok enrich {slug}")
            continue
        extra = case_from_extra_page(slug)
        if extra:
            by_slug[slug] = extra
            print(f"ok extra {slug} mark={extra.get('mark') or '-'}")

    # Remove old case md except README
    for path in CASES_DIR.glob("*.md"):
        if path.name == "README.md":
            continue
        path.unlink()

    cases = list(by_slug.values())
    for c in cases:
        # re-apply serial result rule after merges
        c["result"] = build_result(c.get("mark") or "", c.get("result") or "", [])
        if c.get("mark") == MARK_SERIAL:
            facts = c.get("facts") or []
            if not any("Поставлено на серийное" in f for f in facts):
                facts = ["Поставлено на серийное производство", *facts]
            c["facts"] = facts
        (CASES_DIR / f"{c['slug']}.md").write_text(render_md(c), encoding="utf-8")

    write_index(cases)
    write_readme(cases)
    print(f"written cases: {len(cases)}")
    serial = sum(1 for c in cases if c.get("mark") == MARK_SERIAL)
    print(f"serial mark: {serial}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
