# kodpm

Kubernetes environment for **Odoo Community 10–19** and rebranded forks (for example Fincomtech). Same idea as [ODPM](https://github.com/aayartsev/odpm): one project description (`odpm.json` + `user_settings.json`), CLI for dumps and module install/update. Runtime is Helm on Kubernetes instead of Docker Compose.

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
mkdir ~/projects/kodpm_odoo_test && cd ~/projects/kodpm_odoo_test
source ~/projects/kodpm/.venv/bin/activate
kodpm init
```

The wizard asks for Odoo version, core name (`odoo` / `fincomtech`), addon git repos and the **addons branch**, writes `odpm.json` (including `addons_branch` and each dependency `branch`), `user_settings.json`, an empty `requirements.txt`, `odoo.conf` and `values.local.yaml`, **clones the core and addons into `~/projects/kodpm_data`** (symlinks in the project root), then installs. Extra Python packages come from the project `requirements.txt`; forks also install the core tree's root file (the official `odoo:*` image already has Community deps).

```bash
kodpm up
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
kodpm init                  # wizard: version, core, addons → files + install
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

Optional global flags: `--project-dir` (default: `.`), `--profile`, `-d DATABASE`.

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
