# Mapping ODPM → kodpm

kodpm reads the same project files as [ODPM](https://github.com/aayartsev/odpm). Docker Compose is replaced by Helm on Kubernetes.

## Files

| ODPM | kodpm |
|------|--------|
| Developing-repo `odpm.json` (file or workspace symlink) | Source of version, platform, git, addons, extra services |
| `kodpm.json` in the project root | Fallback for older kodpm projects |
| `user_settings.json` (or `usersettings.json`) | Modules, admin password, `dev_mode` |
| Addon `odpm.json` → `dependencies` | Extra git addons (e.g. `OCA/queue`) cloned and mounted like project deps |
| Addon `odpm.json` → `scenarios.developer.requirements` | Extra pip packages installed on `up` / module jobs (`requirements.txt` is ignored) |
| Addon `odpm.json` → `scenarios.developer.odoo_conf.options` | Merged into `odoo.conf` when the key is not already set (`server_wide_modules`, …) |
| Addon / root `odpm.json` → `scenarios.developer.services` | Extra Deployments + Services in the Helm release |
| Addon / root `odpm.json` → `scenarios.developer.service_sources` | Extra git clones (same as addons), used by `${@source:NAME}`. Branch from `URL branch` if given, otherwise the remote default HEAD (not `odoo_version`) |
| `.kodpm/secrets.json` (or `.odpm/secrets.json`) | Module secrets → `/run/odpm/secrets.json` and generated `*/data/secret.xml` |
| `.env` (`BACKUP_DIR`, ports, …) | Profile YAML + cluster port mapping (k3d `:80`) |
| `docker-compose.yml` (generated) | Chart `charts/odoo-instance` |
| `--init` clone + Dockerfile | `kodpm --init URL` + `kodpm -d NAME up` (images from catalog or `image` in json) |

Workspace root `odpm.json` is a **symlink** to `<developing>/odpm.json` after `kodpm --init URL`. kodpm does not write a separate `kodpm.json` when the v2 manifest is complete.

## `odpm.json` (ODPM v2)

| Field | Effect |
|-------|--------|
| `manifest_schema` | `2` for the ODPM-style file |
| `odoo_version` | Catalog key `10.0` … `19.0` (image, PostgreSQL, probes) |
| `platform.git` / `odoo_git_link` | Platform / Odoo git URL |
| `platform_name` | `odoo`, `fincomtech`, or custom → conf file `{name}.conf` (default `odoo`) |
| `developing.git` | First addon repo (cloned and symlinked; branch from `--branch` / `addons_branch` / `odoo_version`) |
| `dependencies` | Git addon repos: URL strings or `{name,url,branch}` objects. Default branch is `odoo_version`, not `--branch` |
| `image` | `repository:tag` if the fork is already built |
| `bin` | Entrypoint binary (`odoo`, or renamed) |
| `addons_branch` | Branch of the developing repo only (`--branch`). Other addons use `odoo_version` |
| `postgres` / `python` / `distro` | Recorded; postgres overrides the catalog image tag |
| `database.language` | Default `db_lang` when `user_settings.json` has none |
| `scenarios.developer.services` | Extra containers (see below) |
| Addon `requirements_txt` or `scenarios.*.requirements` | Pip packages (not the project-root `requirements.txt`) |
| Addon `dependencies` | Nested addon repos; branch defaults to that addon's `odoo_version` |
| Addon `scenarios.*.odoo_conf.options` | Extra `odoo.conf` keys, e.g. `server_wide_modules=base,web,queue_job` |

## Extra services

`scenarios.developer.services` become a Deployment + ClusterIP Service each (`{{release}}-{{name}}`). Supported fields: `image`, `command`, `environment`, `ports` (`host:container`), `volumes` (`host:container`). `depends_on` / `restart` are accepted and ignored (Kubernetes has its own restart policy).

Substitutions:

- `${@service:odoo}` → `{{release}}-odoo`
- `${@service:db1}` → `{{release}}-db1`
- `${@source:NAME}` → hostPath of the clone from `service_sources`

Volumes are mounted only when the host path is under `$HOME` (k3d `/host-home`). Other paths are skipped with a warning. `hooks.post_prepare` (docker) is not run; import images into k3d if needed (`k3d image import`). Host ports are not published by k3d automatically — kodpm prints `kubectl port-forward` after `up`.

## `user_settings.json`

| Field | Effect |
|-------|--------|
| `init_modules` | Default for `kodpm modules install` / `-i` |
| `update_modules` | Default for `kodpm modules update` / `-u` |
| `db_manager_password` / `db_creation_data.db_default_admin_password` | `admin_passwd` in conf |
| `db_creation_data.create_demo` | `without_demo` |
| `dev_mode` | `--dev=…` on the local profile |
| `addons_branch` | Overrides developing-repo branch only |
| `developing_project` | Local path; otherwise the project directory is mounted on `local` via `/host-home/...` |

## CLI

| ODPM | kodpm |
|------|--------|
| `odpm --init URL --branch X` | `kodpm --init URL --branch X` |
| `odpm --init` | `kodpm --init` (wizard; first repo is developing) |
| `odpm --skip-start` | `kodpm --init … --skip-start` (files + clone, no Helm) |
| `odpm -d NAME` | `kodpm -d NAME up` |
| `odpm -d NAME -i` | `kodpm -d NAME up -i` or `kodpm -d NAME modules install` |
| `odpm -d NAME -u` | `kodpm -d NAME up -u` or `kodpm -d NAME modules update` |
| `odpm -d DB -i -u` | `kodpm -d DB modules install` then `modules update` |
| `--db-backup` | `kodpm -d DB db backup` |
| `--db-restore ARCHIVE` | `kodpm -d DB db restore ARCHIVE.tar.gz` |
| `--db-drop` | `kodpm -d DB db drop` |
| `--get-dbs-list` | `kodpm db list` |
| `--odoo-bin …` | `kodpm exec -- …` |

`kodpm cluster init` is unrelated to `--init`.
