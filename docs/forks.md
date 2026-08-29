# Forks (Fincomtech and other rebrands)

A fork is treated as Odoo with a different image, conf file name, and optional binary name. XML-RPC, `odoo-bin` flags (`-i`, `-u`, `--stop-after-init`), PostgreSQL and filestore stay the same.

## Catalog

`catalogs/platforms.yaml`:

- `odoo` — official Community, image from `catalogs/versions.yaml`
- `fincomtech` — rebranded fork; set `image` and/or `odoo_git_link` in `odpm.json`
- `custom` — template for any other rename

`odoo_version` must be the **upstream series** the fork is based on (`17.0`, not a marketing name). That selects PostgreSQL, Python, and health probes.

## `odpm.json` for Fincomtech

```json
{
  "odoo_version": "17.0",
  "platform_name": "fincomtech",
  "image": "registry.example.com/fincomtech:17.0",
  "odoo_git_link": "git@example.com:org/fincomtech.git 17.0",
  "bin": "odoo"
}
```

Conf file is `fincomtech.conf` (see `conf_name`). Override `bin` if the fork renamed the executable.

## Build an image from git

```bash
docker build -f images/Dockerfile.fork \
  --build-arg ODOO_GIT=git@example.com:org/fincomtech.git \
  --build-arg ODOO_BRANCH=17.0 \
  --build-arg PLATFORM_NAME=fincomtech \
  -t registry.example.com/fincomtech:17.0 .
```

Private addons: create a Secret with key `ssh-privatekey` and set `addons.sshSecretName` in extra Helm values.
