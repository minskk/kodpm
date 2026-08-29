from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from kodpm.kube import apply_yaml, delete_job, kubectl, wait_job
from kodpm.paths import templates_dir
from kodpm.proc import ToolError

DEFAULT_MC_IMAGE = "quay.io/minio/mc:RELEASE.2024-11-21T17-21-54Z"


def s3_endpoint(values: dict[str, Any], fullname: str) -> tuple[str, str, bool]:
    dump = values.get("dump") or {}
    storage = dump.get("storage") or {}
    if storage.get("type") == "s3" and (storage.get("s3") or {}).get("endpoint"):
        s3 = storage["s3"]
        return str(s3["endpoint"]), str(storage.get("bucket") or "kodpm-dumps"), bool(s3.get("insecure"))
    bucket = (values.get("minio") or {}).get("bucket") or storage.get("bucket") or "kodpm-dumps"
    return f"http://{fullname}-minio:9000", str(bucket), True


def render_job(action: str, values: dict[str, Any], **kwargs: Any) -> str:
    fullname = str(values.get("fullnameOverride") or kwargs["release"])
    postgres = values.get("postgres") or {}
    image = values.get("image") or {}
    odoo_image = f"{image.get('repository', 'odoo')}:{image.get('tag', '17')}"
    endpoint, bucket, insecure = s3_endpoint(values, fullname)
    host_path_cfg = (values.get("addons") or {}).get("hostPath") or {}
    addons_repos = (values.get("addons") or {}).get("repos") or []
    ctx = {
        "action": action,
        "job_name": kwargs["job_name"],
        "namespace": kwargs["namespace"],
        "release": kwargs["release"],
        "deadline": kwargs.get("deadline", 900),
        "postgres_image": postgres.get("image", "postgres:14"),
        "postgres_host": f"{fullname}-postgres",
        "postgres_port": str(postgres.get("port") or 5432),
        "postgres_user": str(postgres.get("user") or "odoo"),
        "odoo_image": odoo_image,
        "mc_image": (values.get("minio") or {}).get("mcImage") or DEFAULT_MC_IMAGE,
        "mc_insecure": "--insecure" if insecure else "",
        "s3_endpoint": endpoint,
        "s3_bucket": bucket,
        "secret_name": f"{fullname}-secret",
        "scripts_cm": f"{fullname}-scripts",
        "config_cm": f"{fullname}-config",
        "filestore_pvc": f"{fullname}-filestore",
        "addons_pvc": f"{fullname}-addons" if addons_repos else "",
        "conf_path": f"{values.get('confMount', '/etc/odoo')}/{values.get('confName', 'odoo.conf')}",
        "conf_mount": values.get("confMount", "/etc/odoo"),
        "bin_name": values.get("bin", "odoo"),
        "data_dir": values.get("dataDir", "/var/lib/odoo"),
        "odoo_uid": str(values.get("odooUid") or 101),
        "db_name": kwargs.get("db_name") or (values.get("kodpm") or {}).get("dbName") or "odoo",
        "modules": kwargs.get("modules", ""),
        "dump_name": kwargs.get("dump_name", ""),
        "restore_from": kwargs.get("restore_from", ""),
        "host_path": host_path_cfg.get("path") if host_path_cfg.get("enabled") else "",
        "host_path_name": host_path_cfg.get("name") or "developing",
        "extra_mounts": host_path_cfg.get("extraMounts") or [],
        "pip_req_enabled": bool((values.get("pythonRequirements") or {}).get("enabled")),
        "python_req_cm": f"{fullname}-python-req",
        "odpm_secrets_host_path": str((values.get("odpmSecrets") or {}).get("hostPath") or ""),
    }
    env = Environment(
        loader=FileSystemLoader(str(templates_dir())),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["quote"] = lambda value: json.dumps(str(value))
    return env.get_template("job.yaml.j2").render(**ctx)


def run_job(manifest: str, job_name: str, namespace: str, timeout: str = "15m") -> None:
    delete_job(job_name, namespace)
    apply_yaml(manifest, namespace)
    try:
        wait_job(job_name, namespace, timeout=timeout)
    except KeyboardInterrupt:
        delete_job(job_name, namespace)
        raise
    except ToolError:
        kubectl("logs", f"job/{job_name}", "-n", namespace, "--all-containers=true", check=False)
        raise


def timestamp_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def write_debug_manifest(manifest: str, dest: Path) -> None:
    dest.write_text(manifest, encoding="utf-8")
