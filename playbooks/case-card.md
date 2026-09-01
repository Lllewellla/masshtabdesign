# Карточка кейса (open-data)

Канон front matter: [`../data/case-frontmatter.schema.json`](../data/case-frontmatter.schema.json).

Обязательные поля: `id`, `title`, `slug`, `organization`, `url`, `official_case_url`, `repo_case_url`, `status`, `updated`.

Тело файла - человеческая история (задача / работа / результат). Цифры бюро - только из [`../data/claims.json`](../data/claims.json).

Сборка/обновление полей: `python scripts/normalize_case_frontmatter.py`, генерация карточек: `python scripts/build_case_cards.py`.
