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

## Новый проект (из каталога проекта)

kodpm считает **текущий каталог** проектом. `--project-dir` указывать не нужно.

```bash
mkdir ~/projects/kodpm_odoo_test && cd ~/projects/kodpm_odoo_test
source ~/projects/kodpm/.venv/bin/activate
kodpm init
```

Мастер спросит версию, имя ядра (`odoo` / `fincomtech`), git addons и **ветку addons**, запишет `odpm.json` (в том числе `addons_branch` и `branch` у каждой зависимости), `user_settings.json`, пустой `requirements.txt`, `odoo.conf` и `values.local.yaml`, **склонирует ядро и addons в `~/projects/kodpm_data`** и сделает симлинки в корне проекта, затем запустит установку. Дополнительные пакеты Python — из `requirements.txt` проекта; у форка также из корневого `requirements.txt` ядра (официальный образ `odoo:*` уже содержит зависимости Community).

```bash
kodpm up
kodpm status
kodpm -d odoo modules update
kodpm -d odoo db backup --name demo
```

UI: `http://<имя-каталога-проекта>.127.0.0.1.nip.io` (например `http://kodpm-odoo-test.127.0.0.1.nip.io`) — пароль менеджера БД из `user_settings.json`.

`--project-dir` нужен, только если запускаете kodpm из другого каталога. Готовое демо:

```bash
cd /path/to/kodpm/examples/demo-17
kodpm up --dry-run
```

## CLI

```
kodpm init                  # мастер: версия, ядро, addons → файлы + установка
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

Необязательные глобальные флаги: `--project-dir` (по умолчанию `.`), `--profile`, `-d DATABASE`.

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
