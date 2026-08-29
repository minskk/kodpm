from __future__ import annotations

from typing import Any

import yaml

from kodpm.iniutil import set_ini_option
from kodpm.project import ProjectFiles

VALUES_LOCAL_NAME = "values.local.yaml"

VALUES_LOCAL_TEMPLATE = """\
# Локальные Helm values этого проекта (накладываются последними).
# Чарта kodpm сюда не копируется.
#
# ingress:
#   host: odoo.127.0.0.1.nip.io
#
# resources:
#   limits:
#     memory: 2Gi
"""

def format_ini_value(value: Any) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def postgres_host(values: dict[str, Any]) -> str:
    postgres = values.get("postgres") or {}
    if postgres.get("enabled", True):
        return f"{values.get('fullnameOverride') or 'instance'}-postgres"
    return str(postgres.get("externalHost") or "")


def addons_path_of(values: dict[str, Any]) -> str:
    paths: list[str] = []
    addons = values.get("addons") or {}
    for repo in addons.get("repos") or []:
        name = (repo or {}).get("name")
        if name:
            paths.append(f"/mnt/extra-addons/{name}")
    host = addons.get("hostPath") or {}
    if host.get("enabled"):
        root = f"/mnt/extra-addons/{host.get('name') or 'developing'}"
        for extra in host.get("extraPaths") or []:
            if not extra:
                continue
            text = str(extra)
            paths.append(text if text.startswith("/") else f"{root}/{text}")
    if not paths:
        return str(values.get("extraAddons") or "/mnt/extra-addons")
    return ",".join(paths)


def cluster_conf_options(values: dict[str, Any]) -> dict[str, str]:
    postgres = values.get("postgres") or {}
    secrets = values.get("secrets") or {}
    return {
        "addons_path": addons_path_of(values),
        "data_dir": str(values.get("dataDir") or "/var/lib/odoo"),
        "db_host": postgres_host(values),
        "db_port": str(postgres.get("port") or 5432),
        "db_user": str(postgres.get("user") or "odoo"),
        "db_name": "False",
        "admin_passwd": str(secrets.get("adminPassword") or "admin"),
    }


def render_conf_from_values(values: dict[str, Any]) -> str:
    reserved = cluster_conf_options(values)
    skip = set(reserved) | {"admin_passwd"}
    lines = ["[options]"]
    for key, value in reserved.items():
        lines.append(f"{key} = {value}")
    options = (values.get("config") or {}).get("options") or {}
    extra = (values.get("config") or {}).get("extra") or {}
    for source in (options, extra):
        for key, value in source.items():
            if key in skip:
                continue
            lines.append(f"{key} = {format_ini_value(value)}")
    return "\n".join(lines) + "\n"


def compose_conf(project: ProjectFiles, values: dict[str, Any]) -> str:
    reserved = cluster_conf_options(values)
    path = project.conf_path
    if path.is_file():
        content = path.read_text(encoding="utf-8")
        if "[options]" not in content.lower():
            content = "[options]\n" + content
        for key, value in reserved.items():
            if key == "admin_passwd" and "admin_passwd" in content:
                continue
            content = set_ini_option(content, key, value)
        return content if content.endswith("\n") else content + "\n"
    return render_conf_from_values(values)


def load_values_local(project: ProjectFiles) -> dict[str, Any]:
    path = project.values_local_path
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def ensure_values_local(project: ProjectFiles) -> Path:
    path = project.values_local_path
    if not path.exists():
        path.write_text(VALUES_LOCAL_TEMPLATE, encoding="utf-8")
    return path


def sync_project_layout(
    project: ProjectFiles,
    values: dict[str, Any],
    *,
    overwrite_conf: bool = False,
) -> dict[str, Any]:
    """Write values.local.yaml and the platform conf file; keep values['config']['raw'] in sync."""
    ensure_values_local(project)
    if overwrite_conf:
        raw = render_conf_from_values(values)
    else:
        raw = str((values.get("config") or {}).get("raw") or compose_conf(project, values))
    project.conf_path.write_text(raw, encoding="utf-8")
    values.setdefault("config", {})["raw"] = raw
    return values
