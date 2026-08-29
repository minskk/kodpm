# Mapping ODPM → kodpm

kodpm reads the same project files as [ODPM](https://github.com/aayartsev/odpm). Docker Compose is replaced by Helm on Kubernetes.

## Files

| ODPM | kodpm |
|------|--------|
| `kodpm.json` (legacy `odpm.json` in the project root) | Source of version, platform, git, addons |
| `user_settings.json` (or `usersettings.json`) | Modules, admin password, `dev_mode` |
| Addon `odpm.json` → `dependencies` | Extra git addons (e.g. `OCA/queue`) cloned and mounted like project deps |
| Addon `odpm.json` → `scenarios.developer.requirements` | Extra pip packages installed on `up` / module jobs (`requirements.txt` is ignored) |
| Addon `odpm.json` → `scenarios.developer.odoo_conf.options` | Merged into `odoo.conf` when the key is not already set (`server_wide_modules`, …) |
| `.kodpm/secrets.json` (or `.odpm/secrets.json`) | Module secrets → `/run/odpm/secrets.json` and generated `*/data/secret.xml` |
| `.env` (`BACKUP_DIR`, ports, …) | Profile YAML + cluster port mapping (k3d `:80`) |
| `docker-compose.yml` (generated) | Chart `charts/odoo-instance` |
| `--init` clone + Dockerfile | `kodpm cluster init` + `kodpm up` (images from catalog or `image` in json) |

## `kodpm.json`

| Field | Effect |
|-------|--------|
| `odoo_version` | Catalog key `10.0` … `19.0` (image, PostgreSQL, probes) |
| `platform_name` | `odoo`, `fincomtech`, or custom → conf file `{name}.conf` |
| `odoo_git_link` | Fork git (build image with `images/Dockerfile.fork`) |
| `image` | `repository:tag` if the fork is already built |
| `bin` | Entrypoint binary (`odoo`, or renamed) |
| `addons_branch` | Default git branch for addons (`kodpm init` asks for it) |
| `dependencies` | Git addon repos (`url [branch]` or `{name,url,branch}`) |
| `python_version` / `distro_*` | Recorded; used when you build a fork image |
| Addon `requirements_txt` or `scenarios.*.requirements` | Pip packages (not the project-root `requirements.txt`) |
| Addon `dependencies` | Nested addon repos; branch defaults to that addon's `odoo_version` |
| Addon `scenarios.*.odoo_conf.options` | Extra `odoo.conf` keys, e.g. `server_wide_modules=base,web,queue_job` |

## `user_settings.json`

| Field | Effect |
|-------|--------|
| `init_modules` | Default for `kodpm modules install` |
| `update_modules` | Default for `kodpm modules update` |
| `db_manager_password` / `db_creation_data.db_default_admin_password` | `admin_passwd` in conf |
| `db_creation_data.create_demo` | `without_demo` |
| `dev_mode` | `--dev=…` on the local profile |
| `developing_project` | Local path; otherwise the project directory is mounted on `local` via `/host-home/...` |

## CLI

| ODPM | kodpm |
|------|--------|
| `odpm -d DB -i -u` | `kodpm -d DB modules install` then `modules update` |
| `--db-backup` | `kodpm -d DB db backup` |
| `--db-restore ARCHIVE` | `kodpm -d DB db restore ARCHIVE.tar.gz` |
| `--db-drop` | `kodpm -d DB db drop` |
| `--get-dbs-list` | `kodpm db list` |
| `--odoo-bin …` | `kodpm exec -- …` |
