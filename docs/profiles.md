# Profiles: local, test, dev

One Helm chart, three value overlays in `profiles/`.

| | local | test | dev |
|---|---|---|---|
| Cluster | k3d (`kodpm cluster init`) | shared Kubernetes | shared Kubernetes |
| Ingress | Traefik, `<project>.127.0.0.1.nip.io` | nginx, set `ingress.host` | nginx, set `ingress.host` |
| Dumps | MinIO in the namespace | MinIO in the namespace | S3 (`dump.storage.s3`) |
| HostPath addons | `$HOME` → `/host-home` | no | no |
| `--dev` | from `user_settings.json` | off | off |
| Workers | 0 | 0 | 2 |

## Local

```bash
cd examples/demo-17
kodpm cluster init
kodpm up
```

k3d publishes host ports 80/443. Open `http://<project-dir>.127.0.0.1.nip.io`.

The project directory must live under `$HOME` so live addons appear at `/host-home/…`.

## Test / dev

Point kubectl at the target cluster, then:

```bash
cd examples/demo-17
kodpm up --profile test
kodpm --profile dev up
```

Edit `profiles/test.yaml` / `profiles/dev.yaml` for hostname, StorageClass, and S3 keys (prefer a Secret, not git).
