# kodpm

Kubernetes environment for **Odoo Community 10–19** and rebranded forks (for example Fincomtech). Same idea as [ODPM](https://github.com/aayartsev/odpm): one project description (`odpm.json` + `user_settings.json`; existing projects may still use `kodpm.json`), CLI for dumps and module install/update. Runtime is Helm on Kubernetes instead of Docker Compose.

Profiles: **local** (k3d), **test**, **dev**.

## Requirements

- Python 3.11+
- Helm 3, kubectl
- Local profile: [k3d](https://k3d.io/) and Docker
- Project directory under `$HOME` for live addons on local (k3d mounts `$HOME` at `/host-home`)

Step-by-step when packages are missing (Ubuntu/Debian): **[INSTALL.md](INSTALL.md)**.

## Install

From this repository (catalogs and Helm chart live next to the code):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

If you install the wheel elsewhere, set `KODPM_HOME` to the clone path so CLI can find `catalogs/`, `profiles/`, and `charts/`.

## New project (from the project directory)

kodpm uses the **current directory** as the project. You do not need `--project-dir`.

```bash
mkdir ~/projects/fincom_extra && cd ~/projects/fincom_extra
source ~/projects/kodpm/.venv/bin/activate
kodpm --init git@gitverse.ru:fincomtech/extra_module.git --branch 17.0-dev
kodpm -d odoo up       # start the stack
kodpm -d odoo modules install
```

`--init URL` clones the developing repo into `~/projects/kodpm_data`, symlinks it into the project root, and if that clone already has `odpm.json`, **skips the wizard**. The workspace root gets a symlink `odpm.json` → `<name>/odpm.json`. `user_settings.json` and `values.local.yaml` are created if missing.

Bare `--init` (or `kodpm init`) starts the wizard. The first git URL is **developing**; the rest become `"dependencies": ["https://…"]` strings in ODPM v2 `odpm.json`. If the clone has no manifest, the wizard writes v2 into `<name>/odpm.json` and creates the same symlink.

`--skip-start` writes files and clones sources without Helm. Subcommands stay as synonyms: `kodpm init`, `kodpm up`, `kodpm modules install|update`.

Addon `odpm.json` also supplies nested git `dependencies`, `scenarios.developer.requirements` (pip; not `requirements.txt`), `scenarios.developer.odoo_conf.options` (e.g. `server_wide_modules`), and `scenarios.developer.services` (extra Deployments/Services in the same Helm release; `${@service:odoo}` / `${@source:NAME}` are interpolated). Module API keys go in `.kodpm/secrets.json` (or `.odpm/secrets.json`); kodpm writes `*/data/secret.xml` and mounts `/run/odpm/secrets.json`. Existing projects that still have `kodpm.json` keep working.

```bash
kodpm -d odoo up
kodpm status
kodpm -d odoo modules update
kodpm -d odoo db backup --name demo
```

UI: `http://<project-dir-name>.127.0.0.1.nip.io` (for example `http://kodpm-odoo-test.127.0.0.1.nip.io`) — DB manager password comes from `user_settings.json`.

`--project-dir` is only for calling kodpm while standing in another directory. Existing demo:

```bash
cd /path/to/kodpm/examples/demo-17
kodpm up --dry-run
```

## CLI

```
kodpm --init [URL] [--branch X] [--skip-start]
kodpm -d NAME up            # helm up (required; -d alone is not enough)
kodpm -d NAME up --no-extras  # without odpm.json extra services
kodpm -d NAME up -i         # up, then install init_modules
kodpm -d NAME modules install | update
kodpm init                  # wizard synonym
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

Optional global flags: `--project-dir` (default: `.`), `--profile`, `-d DATABASE`, `--init`, `--branch`, `-i`, `-u`, `--skip-start`, `--no-extras`.

Module jobs run **`--stop-after-init` in a Kubernetes Job**, not on the running Deployment (so liveness probes cannot kill a long `-u`).

## Layout

```
catalogs/           # Odoo 10.0–19.0 and platforms (odoo, fincomtech)
profiles/           # local, test, dev
charts/odoo-instance/
src/kodpm/          # CLI
examples/demo-17/
docs/
```

## Docs

- [ODPM field mapping](docs/odpm-mapping.md)
- [Profiles](docs/profiles.md)
- [Forks](docs/forks.md)

## Tests

```bash
pytest
```
