# Profiles: local, test, dev

One Helm chart, three value overlays in `profiles/`.

| | local | test | dev |
|---|---|---|---|
| Cluster | k3d (`kodpm cluster init`) | shared Kubernetes | shared Kubernetes |
| Ingress | Traefik, `odoo.127.0.0.1.nip.io` | nginx, set `ingress.host` | nginx, set `ingress.host` |
| Dumps | MinIO in the namespace | MinIO in the namespace | S3 (`dump.storage.s3`) |
| HostPath addons | `$HOME` → `/host-home` | no | no |
| `--dev` | from `user_settings.json` | off | off |
| Workers | 0 | 0 | 2 |

## Local

```bash
kodpm cluster init
kodpm --project-dir examples/demo-17 up --profile local
```

k3d publishes host ports 80/443. Open http://odoo.127.0.0.1.nip.io

The project directory must live under `$HOME` so live addons appear at `/host-home/…`.

## Test / dev

Point kubectl at the target cluster, then:

```bash
kodpm --project-dir examples/demo-17 up --profile test
kodpm --project-dir examples/demo-17 --profile dev up
```

Edit `profiles/test.yaml` / `profiles/dev.yaml` for hostname, StorageClass, and S3 keys (prefer a Secret, not git).
