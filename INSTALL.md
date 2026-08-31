# Installing KODPM and dependencies

Step-by-step setup on Debian/Ubuntu when packages are missing from a normal `apt` (typical for `kubectl` and `helm`). After that: verify the toolchain and run the first `kodpm cluster init`.

Example KODPM clone path: `/home/user/projects/kodpm`. Substitute your own.

CPU architecture:

```bash
uname -m
```

- `x86_64` → use `amd64` in binary URLs
- `aarch64` → `arm64`

Russian version: [INSTALL_RU.md](INSTALL_RU.md).

---

## Cheat sheet: empty project to running stack

Install Docker, k3d, kubectl, Helm, and the KODPM venv (sections 1–7). Then work from an **empty directory under `$HOME`**.

```bash
mkdir -p ~/projects/myapp && cd ~/projects/myapp
source ~/projects/kodpm/.venv/bin/activate

# files + clone of the developing repo (no version wizard if odpm.json is already in the repo)
# asks for init_modules (default base,web) → user_settings.json
kodpm --init git@github.com:org/repo.git --branch 17.0-dev --skip-start

# if odpm.json has scenarios.developer.secrets
cp .kodpm/secrets.example.json .kodpm/secrets.json
# fill in the keys

# `up` does not create the cluster
kodpm cluster init

# addon clones, host pip, images → k3d, Helm, extra port-forwards
kodpm -d odoo up

# modules (Kubernetes Job, not the running Odoo pod)
kodpm -d odoo modules install
```

Without `--skip-start`, `--init` asks whether to install and then runs `cluster init` + `up`. Modules are still a separate step, or use `-i`:

```bash
kodpm --init git@github.com:org/repo.git --branch 17.0-dev
# confirm install
kodpm -d odoo modules install
# or: kodpm -d odoo up -i
```

UI: `http://<directory-name>.127.0.0.1.nip.io` (folder `kodpm_autoparts` → <http://kodpm-autoparts.127.0.0.1.nip.io>).

What `up` does: clones into `~/projects/kodpm_data`, pip into `.kodpm/pip-packages`, images into k3d, MinIO dumps in `odoo_backups`, extra services on `127.0.0.1:<port>` from `odpm.json`. Extra Deployments are waited for up to 300s, but wait stops early if the remaining pods are in `Error` / `CrashLoopBackOff`. A local-only image such as `autoparts_env:emulator` must already exist in Docker on the host. Core only: `kodpm -d odoo up --no-extras`. Tear down: `kodpm down`.

---

## 1. Docker

k3d runs Kubernetes inside Docker.

```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo usermod -aG docker "$USER"
```

Log out and back in (or `newgrp docker`), then:

```bash
docker info
```

It must succeed without `permission denied`.

---

## 2. Python venv and the KODPM package

On Debian/Ubuntu `python3 -m venv` often fails with `ensurepip is not available`. Install the venv package:

```bash
sudo apt-get install -y python3.12-venv
```

(For another Python: `python3.11-venv`, etc. KODPM needs Python 3.11+.)

```bash
cd /home/user/projects/kodpm
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
which kodpm
kodpm --help
```

`which kodpm` should print `.../kodpm/.venv/bin/kodpm`. Keep the venv active in that session (`source .venv/bin/activate`).

If you install the wheel from outside the clone, set `KODPM_HOME` to the repository path (`catalogs/`, `profiles/`, and `charts/` are required).

---

## 3. k3d

Usually not in distro apt. Official installer:

```bash
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
k3d version
```

You should see a k3d version and the bundled k3s, for example `k3s version v1.35.x-k3s1`.

Docs: <https://k3d.io/>

---

## 4. kubectl

The `kubectl` package is **not** in default Ubuntu repos (`Unable to locate package kubectl`). `kubectx` is unrelated; you do not need it.

Binary from Kubernetes:

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/kubectl
kubectl version --client
```

On ARM64 replace `amd64` with `arm64` in the URL.

Alternative — official Kubernetes apt: <https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/>

---

## 5. Helm 3

Not in default apt (`elm-compiler` is something else).

Official script:

```bash
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version
```

Manual:

```bash
HELM_VER=v3.16.4
curl -fsSL "https://get.helm.sh/helm-${HELM_VER}-linux-amd64.tar.gz" -o /tmp/helm.tgz
tar -xzf /tmp/helm.tgz -C /tmp
sudo mv /tmp/linux-amd64/helm /usr/local/bin/helm
helm version
```

On ARM64 the archive is `linux-arm64`.

---

## 6. Check the toolchain

```bash
docker info >/dev/null && echo docker:ok
k3d version
kubectl version --client
helm version
python3 --version
source /home/user/projects/kodpm/.venv/bin/activate
kodpm --help
```

Expected:

| Command | Success looks like |
|---------|-------------------|
| `docker info` | no permission error |
| `k3d version` | k3d and k3s versions |
| `kubectl version --client` | `Client Version: v1.…` |
| `helm version` | `version.BuildInfo` / `v3.…` |
| `kodpm --help` | command list (`cluster`, `up`, `db`, …) |

If you get `kodpm: command not found`, the `.venv` is not activated.

---

## 7. Local cluster

```bash
source /home/user/projects/kodpm/.venv/bin/activate
kodpm cluster init
```

Creates a k3d cluster named `kodpm` (`$HOME` mounted at `/host-home`, host ports 80/443). If the cluster already exists it is not recreated; if the node is stopped (after a reboot) it is started. `kodpm -d odoo up` also starts a stopped cluster. Manually: `kodpm cluster start`.

Check:

```bash
k3d cluster list
kubectl get nodes
```

The node should be `Ready`.

---

## 8. New project

Work **from the project directory** (it must be under `$HOME`). `--project-dir` is not needed.

You need SSH access to Git (`git@github.com:…`): key in `ssh-agent` or `~/.ssh`.

```bash
mkdir -p /home/user/projects/fincom_extra
cd /home/user/projects/fincom_extra
source /home/user/projects/kodpm/.venv/bin/activate
kodpm --init git@gitverse.ru:fincomtech/extra_module.git --branch 17.0-dev --skip-start
kodpm cluster init
kodpm -d odoo up
kodpm -d odoo modules install
```

`--init URL` clones the developing repository. If the clone has `odpm.json`, the version/platform wizard is skipped: the project root gets a symlink `odpm.json` → `<name>/odpm.json`. In both cases KODPM asks for init modules (`init_modules` in `user_settings.json`, default `base,web`). Without a URL (`kodpm --init` or `kodpm init`) the wizard also asks for:

- git repositories (first is developing, the rest become `dependencies` strings);
- branch (`--branch` or one shared prompt);
- core version (10.0–19.0) if there is no manifest;
- core name (`odoo`, `fincomtech`, …);
- database language, password.

Then:

1. ODPM v2 `odpm.json` is written into the developing clone (plus a root symlink), or the existing manifest is used. `user_settings.json`, empty `requirements.txt`, `odoo.conf` (or `{platform}.conf`), and `values.local.yaml` are created if missing. Older projects with `kodpm.json` are still read.
2. The core is cloned into `~/projects/kodpm_data` (Odoo 17: `https://github.com/odoo/odoo.git`, branch `17.0` → `~/projects/kodpm_data/odoo-17.0`) and the project root gets an `odoo` symlink.
3. Each addon repo and `service_sources` clone goes to the same data dir (`~/projects/kodpm_data/<name>-<branch>`) and is also symlinked in the project root. Nested `odpm.json` dependencies (for example `OCA/queue`) are cloned the same way.
4. Without `--skip-start`, the k3d cluster is created or started and Helm runs. Extra services from `scenarios.developer.services` join the same release; after `up`, KODPM waits for them (up to 300s, earlier if they are in Error/CrashLoop) and starts `kubectl port-forward` on `127.0.0.1` (`kodpm down` stops those forwards). At the end of `up` it prints the URL and `kodpm -d odoo modules install`.

`odoo.conf` is the Odoo settings source (it goes into a ConfigMap). Addon `scenarios.developer.odoo_conf.options` are merged in when the key is not already set (for example `server_wide_modules`). `values.local.yaml` is a Helm overlay for this project only; the KODPM chart is not copied here. Python packages come from addon `odpm.json` (`scenarios.developer.requirements`); project-root `requirements.txt` files are not read.

Clone directory override: `export KODPM_DATA_DIR=/path/to/data`.

Files only, no Helm:

```bash
kodpm --init --skip-start
kodpm init --no-up --no-clone
```

UI (from the project directory name `fincom_extra`): <http://fincom-extra.127.0.0.1.nip.io>

Next: [README.md](README.md), [docs/odpm-mapping.md](docs/odpm-mapping.md).
