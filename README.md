# kodpm

Kubernetes environment for **Odoo Community 10–19** and rebranded forks (for example Fincomtech). Same idea as [ODPM](https://github.com/aayartsev/odpm): one project description (`odpm.json` + `user_settings.json`), CLI for dumps and module install/update. Runtime is Helm on Kubernetes instead of Docker Compose.

Profiles: **local** (k3d), **test**, **dev**.

## Requirements

- Python 3.11+
- Helm 3, kubectl
- Local profile: [k3d](https://k3d.io/) and Docker
- Project directory under `$HOME` for live addons on local (k3d mounts `$HOME` at `/host-home`)

## Install

From this repository (catalogs and Helm chart live next to the code):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

If you install the wheel elsewhere, set `KODPM_HOME` to the clone path so CLI can find `catalogs/`, `profiles/`, and `charts/`.

## Demo (Odoo 17 Community)

```bash
kodpm cluster init
kodpm --project-dir examples/demo-17 up --profile local
# http://odoo.127.0.0.1.nip.io
kodpm --project-dir examples/demo-17 status
```

Database manager password is `admin` (see `user_settings.json`).

```bash
kodpm --project-dir examples/demo-17 -d odoo modules install base,web
kodpm --project-dir examples/demo-17 -d odoo db backup --name demo
kodpm --project-dir examples/demo-17 -d odoo db restore demo.tar.gz
kodpm --project-dir examples/demo-17 config set workers=0
kodpm --project-dir examples/demo-17 exec -- --help
```

Preview manifests without a cluster:

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

Global flags: `--project-dir`, `--profile`, `-d DATABASE`.

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
