# kodpm

Kubernetes-среда для **Odoo Community 10–19** и переименованных форков (например Fincomtech). Та же идея, что у [ODPM](https://github.com/aayartsev/odpm): одно описание проекта (`odpm.json` + `user_settings.json`; у старых проектов ещё может быть `kodpm.json`), CLI для дампов и установки/обновления модулей. Вместо Docker Compose — Helm в Kubernetes.

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
mkdir ~/projects/fincom_extra && cd ~/projects/fincom_extra
source ~/projects/kodpm/.venv/bin/activate
kodpm --init git@gitverse.ru:fincomtech/extra_module.git --branch 17.0-dev
kodpm -d odoo up       # поднять стек
kodpm -d odoo modules install
```

`--init URL` клонирует разрабатываемый репозиторий в `~/projects/kodpm_data`, делает симлинк в корне проекта и, если в клоне уже есть `odpm.json`, **не запускает визард**. В корне workspace появляется симлинк `odpm.json` → `<имя>/odpm.json`. `user_settings.json` и `values.local.yaml` дописываются, если их нет.

Без URL (`kodpm --init` или `kodpm init`) — визард. Первый git URL — **developing**, остальные попадают в `"dependencies": ["https://…"]` в ODPM v2 `odpm.json`. Если манифеста в клоне нет, визард пишет v2 в `<имя>/odpm.json` и делает тот же симлинк.

`--skip-start` — только файлы и клон, без Helm. Подкоманды остаются синонимами: `kodpm init`, `kodpm up`, `kodpm modules install|update`.

Из `odpm.json` addons берутся вложенные git `dependencies`, пакеты Python (`scenarios.developer.requirements`, не `requirements.txt`), опции `odoo.conf` и extra-сервисы (`scenarios.developer.services` → Deployment+Service в том же Helm-релизе; подстановки `${@service:odoo}` / `${@source:NAME}`). Ключи API — в `.kodpm/secrets.json` (или `.odpm/secrets.json`); kodpm пишет `*/data/secret.xml` и монтирует `/run/odpm/secrets.json`. Существующие проекты с `kodpm.json` продолжают работать.

```bash
kodpm -d odoo up
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
kodpm --init [URL] [--branch X] [--skip-start]
kodpm -d NAME up            # helm up (нужна подкоманда up; одного -d мало)
kodpm -d NAME up -i         # up, затем install init_modules
kodpm -d NAME modules install | update
kodpm init                  # синоним визарда
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

Необязательные глобальные флаги: `--project-dir` (по умолчанию `.`), `--profile`, `-d DATABASE`, `--init`, `--branch`, `-i`, `-u`, `--skip-start`.

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
