# AGENTS — masshtabdesign

Публичный репозиторий открытых данных бюро промышленного дизайна «Масштаб».
GitHub: https://github.com/Lllewellla/masshtabdesign  
Сайт (канон для посетителя): https://m-shtab.ru/

Это **не** репозиторий сайта. HTML, Layero-деплой и `m-shtab/site/` сюда не класть и отсюда не публиковать.

## Канон

- Цифры и контакты: [`data/claims.json`](data/claims.json). Не выдумывать клиентов, выручку, численность команды, заводские цены.
- Карточка бюро: [`README.md`](README.md), [`llms.txt`](llms.txt), [`organization.json`](organization.json).
- Кейсы: [`playbooks/case-card.md`](playbooks/case-card.md) + [`data/cases-index.json`](data/cases-index.json).
- Очередь наполнения: [`docs/BACKLOG.md`](docs/BACKLOG.md).
- Не коммитить: `CLAIMS.md`, `.env`, `_cache/`.
- Тексты - инфостиль, дефис `-`, не первое лицо. Не оферта.

## Данные с сайта

Живой сайт публичный, секреты не нужны.

```bash
python3 scripts/fetch_site.py
```

Кладёт HTML/`llms.txt` в `_cache/site/` (gitignored). Сначала смотреть кэш и `https://m-shtab.ru/llms.txt`, потом писать markdown-кейс. Факты только из страницы или `claims.json`. Нет на странице - не додумывать.

Дополнительно: `curl -fsSL https://m-shtab.ru/llms.txt`

Если в облачной среде клонирован `masshtab-site` - можно читать HTML оттуда, но канон для смысла страницы - то, что отдаёт https://m-shtab.ru/ .

## Git

- Remote: `origin` = GitHub `Lllewellla/masshtabdesign`. Пушить сюда.
- GitVerse (`gitverse.ru/izhdanova/masshtabdesign`) с облака **не** пушить, пока нет отдельного remote и доступа. Зеркало догоняет человек локально.
- Не `--force`, не `--no-verify`. Не коммитить секреты.
- Ветка: для наполнения - отдельная ветка и PR в `main`, либо `main`, если в задаче явно сказано пушить в main.

## Cursor Cloud specific instructions

Облачный агент должен запускаться **на этом репозитории** (`Lllewellla/masshtabdesign`), не на родительской папке `layero-WEBSITE-m-shtab` (там нет единого git).

1. Проверить сеть к сайту: `curl -fsI https://m-shtab.ru/llms.txt`
2. Снять страницы: `python3 scripts/fetch_site.py`
3. Менять только файлы этого репо (markdown, JSON, playbooks).
4. После правок: `git status` / `git diff` / `git log -5 --oneline`, затем commit и `git push -u origin HEAD`.
5. Сайт на Layero не деплоить. Страницы m-shtab.ru не править из этого репо.

Опционально в дашборде Cloud Agents: multi-repo, добавить `Lllewellla/masshtab-site` (чтение HTML). Для наполнения open-data достаточно живого сайта.

Секреты в Cursor Secrets для этой задачи не обязательны. Не класть OAuth Метрики/Директа в это репо.
