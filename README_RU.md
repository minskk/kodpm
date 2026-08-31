# kodpm

Kubernetes-среда для **Odoo Community 10–19** и переименованных форков (например Fincomtech). Та же идея, что у [ODPM](https://github.com/aayartsev/odpm): одно описание проекта (`odpm.json` + `user_settings.json`; у старых проектов ещё может быть `kodpm.json`), CLI для дампов и установки/обновления модулей. Вместо Docker Compose — Helm в Kubernetes.

Профили: **local** (k3d), **test**, **dev**.

English: [README.md](README.md). Пошаговая установка пакетов: **[INSTALL.md](INSTALL.md)**.

## Требования

- Python 3.11+
- Helm 3, kubectl
- Для профиля local: [k3d](https://k3d.io/) и Docker
- Каталог проекта должен быть внутри `$HOME`, чтобы на local работали живые addons (k3d монтирует `$HOME` в `/host-home`)

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

kodpm --init git@gitverse.ru:fincomtech/extra_module.git --branch 17.0-dev --skip-start
# спросит init_modules (по умолчанию base,web) → user_settings.json

kodpm cluster init          # один раз; дальше `up` сам поднимает остановленный кластер
kodpm -d odoo up
kodpm -d odoo modules install
```

`--init URL` клонирует разрабатываемый репозиторий в `~/projects/kodpm_data`, делает симлинк в корне проекта и, если в клоне уже есть `odpm.json`, **не запускает визард версии/ядра**. Модули для инициализации (`init_modules`) спрашивает всегда. В корне workspace — симлинк `odpm.json` → `<имя>/odpm.json`. `user_settings.json` и `values.local.yaml` дописываются, если их нет.

Без `--skip-start` `--init` может сам создать/запустить кластер и сделать Helm (спросит). Модули всё равно отдельно (`modules install` или `up -i`).

Без URL (`kodpm --init` или `kodpm init`) — полный визард. Первый git URL — **developing**, остальные — `"dependencies"` в ODPM v2.

`kodpm -d odoo up` **не создаёт** кластер, но запускает остановленный. После `up` печатает URL UI и, если есть extra, port-forward на `127.0.0.1` плюс `Дальше: kodpm -d odoo modules install`.

Из `odpm.json` addons: вложенные git `dependencies`, pip (`scenarios.developer.requirements`, не `requirements.txt`), опции `odoo.conf`, extra-сервисы (`${@service:odoo}` / `${@source:NAME}`). Ключи API — в `.kodpm/secrets.json`; kodpm пишет `*/data/secret.xml` и монтирует `/run/odpm/secrets.json`. Старые проекты с `kodpm.json` продолжают работать.

На local MinIO пишет дампы в `{проект}/odoo_backups` (каталог `kodpm-dumps/`). pip ставится на хосте (Docker + образ Odoo) в `{проект}/.kodpm/pip-packages`. `up` качает образы на хосте и импортирует в k3d (`ctr`). Локальный тег вроде `autoparts_env:emulator` должен уже быть в Docker.

UI: `http://<имя-каталога-проекта>.127.0.0.1.nip.io` — пароль менеджера БД из `user_settings.json`.

`--project-dir` нужен, только если запускаете kodpm из другого каталога. Демо:

```bash
cd /path/to/kodpm/examples/demo-17
kodpm up --dry-run
```

## CLI

```
kodpm --init [URL] [--branch X] [--skip-start]
kodpm cluster init | start | delete
kodpm -d NAME up              # helm up (одного -d мало)
kodpm -d NAME up --no-extras  # без extra-сервисов из odpm.json
kodpm -d NAME up -i           # up, затем install init_modules
kodpm -d NAME modules install | update
kodpm init                    # синоним визарда
kodpm up [--profile local|test|dev] [--dry-run]
kodpm down                    # helm uninstall; extra port-forward останавливаются
kodpm status
kodpm values
kodpm config get [KEY]
kodpm config set KEY=VALUE ...
kodpm db list | backup | restore ARCHIVE | drop
kodpm modules install [names]
kodpm modules update [names]
kodpm exec -- [odoo args...]
```

Необязательные глобальные флаги: `--project-dir` (по умолчанию `.`), `--profile`, `-d DATABASE`, `--init`, `--branch`, `-i`, `-u`, `--skip-start`, `--no-extras`.

Установка и обновление модулей — **`--stop-after-init` в Kubernetes Job**, не на работающем Deployment. После install/update kodpm снова печатает URL UI.

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

- [Установка (Debian/Ubuntu)](INSTALL.md)
- [Соответствие полей ODPM](docs/odpm-mapping.md)
- [Профили](docs/profiles.md)
- [Форки](docs/forks.md)

## Тесты

```bash
pytest
```
