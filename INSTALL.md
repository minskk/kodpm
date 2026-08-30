# Установка kodpm и зависимостей

Пошаговая установка на Debian/Ubuntu, когда пакетов нет в обычном `apt` (так бывает с `kubectl` и `helm`). После этого — проверка всего набора и первый `kodpm cluster init`.

Каталог клона kodpm в примерах: `/home/user/projects/kodpm`. Подставьте свой путь.

Архитектура CPU:

```bash
uname -m
```

- `x86_64` → в URL бинарников используйте `amd64`
- `aarch64` → `arm64`

---

## Шпаргалка: запуск проекта с нуля

Инструменты (Docker, k3d, kubectl, Helm) и venv kodpm — разделы 1–7 ниже. Дальше — из **пустой папки внутри `$HOME`**.

```bash
mkdir -p ~/projects/myapp && cd ~/projects/myapp
source ~/projects/kodpm/.venv/bin/activate

# файлы + клон developing (визард не нужен, если в репо уже есть odpm.json)
# спросит init_modules (по умолчанию base,web) → user_settings.json
kodpm --init git@github.com:org/repo.git --branch 17.0-dev --skip-start

# если в odpm.json есть scenarios.developer.secrets
cp .kodpm/secrets.example.json .kodpm/secrets.json
# заполнить ключи

# up сам кластер не создаёт
kodpm cluster init

# клоны addons, pip на хосте, образы → k3d, Helm, port-forward extra
kodpm -d odoo up

# модули (Job, не в бегущем поде)
kodpm -d odoo modules install
```

Без `--skip-start` `--init` сам спросит про установку и вызовет `cluster init` + `up`. Модули тогда отдельно или сразу `-i`:

```bash
kodpm --init git@github.com:org/repo.git --branch 17.0-dev
# подтвердить установку
kodpm -d odoo modules install
# или: kodpm -d odoo up -i
```

UI: `http://<имя-папки>.127.0.0.1.nip.io` (каталог `kodpm_autoparts` → <http://kodpm-autoparts.127.0.0.1.nip.io>).

`up` сам: клоны в `~/projects/kodpm_data`, pip в `.kodpm/pip-packages`, образы в k3d, дампы MinIO в `odoo_backups`, extra-сервисы на `127.0.0.1:<порт>` из `odpm.json`. Локальный образ вроде `autoparts_env:emulator` должен уже быть в Docker на хосте. Только ядро: `kodpm -d odoo up --no-extras`. Снять стек: `kodpm down`.

---

## 1. Docker

k3d поднимает Kubernetes внутри Docker.

```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo usermod -aG docker "$USER"
```

Выйдите из сессии и войдите снова (или `newgrp docker`), затем:

```bash
docker info
```

Должен ответить без `permission denied`.

---

## 2. Python venv и пакет kodpm

На Debian/Ubuntu `python3 -m venv` часто падает с `ensurepip is not available`. Ставят пакет venv:

```bash
sudo apt-get install -y python3.12-venv
```

(Для другой версии Python: `python3.11-venv` и т.д.)

```bash
cd /home/user/projects/kodpm
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
which kodpm
kodpm --help
```

`which kodpm` должен указать на `.../kodpm/.venv/bin/kodpm`. Дальше в этой сессии держите venv включённым (`source .venv/bin/activate`).

Если ставите wheel не из клона, задайте `KODPM_HOME` на путь к репозиторию (нужны `catalogs/`, `profiles/`, `charts/`).

---

## 3. k3d

В стандартном apt пакета обычно нет. Официальный скрипт:

```bash
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
k3d version
```

Должна появиться строка с версией k3d и встроенного k3s, например `k3s version v1.35.x-k3s1`.

Документация: <https://k3d.io/>

---

## 4. kubectl

Пакет `kubectl` в обычных репозиториях Ubuntu **не находится** (`E: Невозможно найти пакет kubectl`). `kubectx` — другое, его ставить не нужно.

Бинарник с сайта Kubernetes:

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/kubectl
kubectl version --client
```

На ARM64 замените в URL `amd64` на `arm64`.

Альтернатива — официальный apt Kubernetes: <https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/>

---

## 5. Helm 3

В обычном apt пакета `helm` нет (`elm-compiler` — другое).

Официальный скрипт:

```bash
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version
```

Вручную:

```bash
HELM_VER=v3.16.4
curl -fsSL "https://get.helm.sh/helm-${HELM_VER}-linux-amd64.tar.gz" -o /tmp/helm.tgz
tar -xzf /tmp/helm.tgz -C /tmp
sudo mv /tmp/linux-amd64/helm /usr/local/bin/helm
helm version
```

На ARM64 архив: `linux-arm64`.

---

## 6. Проверка всего набора

```bash
docker info >/dev/null && echo docker:ok
k3d version
kubectl version --client
helm version
python3 --version
source /home/user/projects/kodpm/.venv/bin/activate
kodpm --help
```

Ожидается:

| Команда | Признак успеха |
|---------|----------------|
| `docker info` | без ошибки прав |
| `k3d version` | версия k3d и k3s |
| `kubectl version --client` | `Client Version: v1.…` |
| `helm version` | `version.BuildInfo` / `v3.…` |
| `kodpm --help` | список команд (`cluster`, `up`, `db`, …) |

Если `kodpm: command not found` — не активирован `.venv`.

---

## 7. Локальный кластер

```bash
source /home/user/projects/kodpm/.venv/bin/activate
kodpm cluster init
```

Создаётся k3d-кластер `kodpm` (`$HOME` монтируется в `/host-home`, порты 80/443 на хосте). Если кластер уже есть, команда его не пересоздаёт.

Проверка:

```bash
k3d cluster list
kubectl get nodes
```

Нода должна быть `Ready`.

---

## 8. Новый проект

Работать нужно **из каталога проекта** (он должен быть внутри `$HOME`). `--project-dir` не нужен.

Нужен SSH-доступ к GitHub (`git@github.com:…`): ключ в `ssh-agent` или `~/.ssh`.

```bash
mkdir -p /home/user/projects/fincom_extra
cd /home/user/projects/fincom_extra
source /home/user/projects/kodpm/.venv/bin/activate
kodpm --init git@gitverse.ru:fincomtech/extra_module.git --branch 17.0-dev --skip-start
kodpm -d odoo up
```

`--init URL` клонирует разрабатываемый репозиторий. Если в клоне есть `odpm.json`, визард не запускается: в корне появляется симлинк `odpm.json` → `<имя>/odpm.json`. В обоих случаях спрашиваются модули для инициализации (`init_modules` в `user_settings.json`, по умолчанию `base,web`). Без URL (`kodpm --init` или `kodpm init`) мастер ещё спросит:

- git-репозитории (первый — developing, остальные — `dependencies` строками);
- ветку (`--branch` или один общий вопрос);
- версию ядра (10.0–19.0), если манифеста нет;
- наименование ядра (`odoo`, `fincomtech`, …);
- язык БД, пароль.

Затем:

1. Пишется ODPM v2 `odpm.json` (в клон developing + симлинк в корне) либо используется уже существующий манифест. `user_settings.json`, пустой `requirements.txt`, `odoo.conf` (или `{platform}.conf`) и `values.local.yaml` дописываются, если их нет. Старые проекты с `kodpm.json` по-прежнему читаются.
2. Ядро клонируется в `~/projects/kodpm_data` (для Odoo 17: `https://github.com/odoo/odoo.git`, ветка `17.0` → `~/projects/kodpm_data/odoo-17.0`) и в корне проекта появляется симлинк `odoo`.
3. Каждый репозиторий addons и `service_sources` клонируется туда же (`~/projects/kodpm_data/<имя>-<ветка>`) и тоже линкуется в корень проекта. Зависимости из `odpm.json` addons (например `OCA/queue`) клонируются так же.
4. Без `--skip-start` поднимаются кластер k3d (если ещё нет) и Helm. Extra-сервисы из `scenarios.developer.services` входят в тот же релиз; после `up` kodpm поднимает `kubectl port-forward` на `127.0.0.1` (останавливает `kodpm down`).

`odoo.conf` — исходник настроек Odoo (уходит в ConfigMap). В него же попадают `scenarios.developer.odoo_conf.options` из `odpm.json` addons, если ключа ещё нет (например `server_wide_modules`). `values.local.yaml` — overlay Helm только этого проекта; чарта kodpm сюда не копируется. Пакеты Python ставятся из `odpm.json` addons (`scenarios.developer.requirements`); файлы `requirements.txt` не читаются.

Каталог клонов можно сменить: `export KODPM_DATA_DIR=/path/to/data`.

Только файлы, без Helm:

```bash
kodpm --init --skip-start
kodpm init --no-up --no-clone
```

UI (имя из каталога проекта): <http://kodpm-odoo-test.127.0.0.1.nip.io>

Дальше: [README_RU.md](README_RU.md), [docs/odpm-mapping.md](docs/odpm-mapping.md).
