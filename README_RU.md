# kodpm

Kubernetes-среда для **Odoo Community 10–19** и переименованных форков (например Fincomtech). Та же идея, что у [ODPM](https://github.com/aayartsev/odpm): одно описание проекта (`odpm.json` + `user_settings.json`), CLI для дампов и установки/обновления модулей. Вместо Docker Compose — Helm в Kubernetes.

Профили: **local** (k3d), **test**, **dev**.

Английская версия: [README.md](README.md).

## Требования

- Python 3.11+
- Helm 3, kubectl
- Для профиля local: [k3d](https://k3d.io/) и Docker
- Каталог проекта должен быть внутри `$HOME`, чтобы на local работали живые addons (k3d монтирует `$HOME` в `/host-home`)

Пошаговая установка при отсутствии пакетов (Ubuntu/Debian): **[INSTALL.md](INSTALL.md)**.

## Установка

Из этого репозитория (каталоги версий и Helm-чарт лежат рядом с кодом):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Если ставите wheel в другое место, задайте `KODPM_HOME` на путь к клону, чтобы CLI нашёл `catalogs/`, `profiles/` и `charts/`.

## Демо (Odoo 17 Community)

```bash
kodpm cluster init
kodpm --project-dir examples/demo-17 --profile local up
# http://odoo.127.0.0.1.nip.io
kodpm --project-dir examples/demo-17 status
```

Пароль менеджера баз данных — `admin` (см. `user_settings.json`).

```bash
kodpm --project-dir examples/demo-17 -d odoo modules install base,web
kodpm --project-dir examples/demo-17 -d odoo db backup --name demo
kodpm --project-dir examples/demo-17 -d odoo db restore demo.tar.gz
kodpm --project-dir examples/demo-17 config set workers=0
kodpm --project-dir examples/demo-17 exec -- --help
```

Предпросмотр манифестов без кластера:

```bash
kodpm --project-dir examples/demo-17 up --dry-run
```

## CLI

```
kodpm cluster init | delete
kodpm up [--profile local|test|dev] [--dry-run]
kodpm down
kodpm status
kodpm values
kodpm config get [KEY]
kodpm config set KEY=VALUE ...
kodpm db list | backup | restore ARCHIVE | drop
kodpm modules install [names]
kodpm modules update [names]
kodpm exec -- [odoo args...]
```

Глобальные флаги: `--project-dir`, `--profile`, `-d DATABASE`.

Установка и обновление модулей выполняются **`--stop-after-init` в Kubernetes Job**, а не на работающем Deployment (чтобы liveness-пробы не убивали долгий `-u`).

## Структура

```
catalogs/           # Odoo 10.0–19.0 и платформы (odoo, fincomtech)
profiles/           # local, test, dev
charts/odoo-instance/
src/kodpm/          # CLI
examples/demo-17/
docs/
```

## Документация

- [Соответствие полей ODPM](docs/odpm-mapping.md)
- [Профили](docs/profiles.md)
- [Форки](docs/forks.md)

## Тесты

```bash
pytest
```
