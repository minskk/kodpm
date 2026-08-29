from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from kodpm.catalog import get_platform, get_version
from kodpm.paths import profiles_dir
from kodpm.project import ProjectFiles


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_profile(name: str) -> dict[str, Any]:
    path = profiles_dir() / f"{name}.yaml"
    if not path.exists():
        known = ", ".join(p.stem for p in profiles_dir().glob("*.yaml"))
        raise FileNotFoundError(f"Unknown profile {name!r}. Available: {known}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _image_parts(image: str) -> tuple[str, str]:
    if ":" in image.rsplit("/", 1)[-1]:
        repo, tag = image.rsplit(":", 1)
        return repo, tag
    return image, "latest"


def _host_home_path(project_dir: Path) -> str | None:
    home = Path.home().resolve()
    try:
        rel = project_dir.resolve().relative_to(home)
    except ValueError:
        return None
    return f"/host-home/{rel.as_posix()}"


def build_values(
    project: ProjectFiles,
    profile: str,
    *,
    extra: dict[str, Any] | None = None,
    db_name: str | None = None,
) -> dict[str, Any]:
    profile_values = load_profile(profile)
    version = get_version(project.odoo_version)
    platform_key = project.platform_name
    # Allow odpm.json platform_name that is a fork not in catalog: use custom + overlay
    try:
        platform = get_platform(platform_key)
    except KeyError:
        platform = get_platform("custom")
        platform = {**platform, "platform_name": platform_key, "conf_name": f"{platform_key}.conf"}

    repo, tag = _image_parts(version.image)
    if not platform.get("image_from_version"):
        img = platform.get("image") or {}
        if img.get("repository"):
            repo = str(img["repository"])
            tag = str(img.get("tag") or tag)
    odoo_git = project.odoo_git_link
    if odoo_git:
        # Fork source is recorded; runtime still needs a built image unless provided.
        pass
    if project.odpm.get("image"):
        repo, tag = _image_parts(str(project.odpm["image"]))

    probes = dict(version.probes)
    probe_type = probes.get("type", "tcp")

    options: dict[str, Any] = {
        version.http_option: 8069,
        version.longpolling_option: 8072,
        "workers": 0,
        "proxy_mode": True,
        "list_db": True,
        "max_cron_threads": 1,
        "without_demo": not project.create_demo(),
        "db_maxconn": 64,
        "logfile": False,
    }

    conf_name = str(platform.get("conf_name") or f"{platform.get('platform_name', 'odoo')}.conf")
    conf_mount = str(platform.get("conf_mount") or "/etc/odoo")
    bin_name = str(platform.get("bin") or version.bin)
    if project.odpm.get("bin"):
        bin_name = str(project.odpm["bin"])

    values: dict[str, Any] = {
        "fullnameOverride": sanitize_release(project.name),
        "platform": platform_key,
        "platformName": str(platform.get("platform_name") or platform_key),
        "odooVersion": version.key,
        "confName": conf_name,
        "confMount": conf_mount,
        "bin": bin_name,
        "extraAddons": str(platform.get("extra_addons") or version.extra_addons),
        "dataDir": version.data_dir,
        "image": {
            "repository": repo,
            "tag": tag,
            "pullPolicy": "IfNotPresent",
        },
        "postgres": {
            "enabled": True,
            "image": f"postgres:{version.postgres}",
            "user": "odoo",
            "database": "postgres",
            "password": "odoo",
            "port": 5432,
        },
        "secrets": {
            "dbPassword": "odoo",
            "adminPassword": project.db_manager_password(),
        },
        "probes": {
            "type": probe_type,
            "httpPath": probes.get("path", "/web/health"),
        },
        "config": {"options": options, "extra": {}},
        "modules": {
            "init": project.init_modules(),
            "update": project.update_modules(),
        },
        "addons": {
            "repos": project.addon_repos(),
            "hostPath": {"enabled": False, "name": "developing", "path": "", "extraPaths": []},
        },
        "kodpm": {
            "profile": profile,
            "dbName": db_name or "odoo",
            "adminLogin": project.admin_login(),
            "dbLang": project.db_lang(),
            "python": version.python,
            "odooGitLink": odoo_git,
        },
    }

    if profile == "local":
        host_path = _host_home_path(project.project_dir)
        if host_path:
            values["addons"]["repos"] = []
            values["addons"]["hostPath"] = {
                "enabled": True,
                "name": "developing",
                "path": host_path,
                "extraPaths": [str(repo["name"]) for repo in project.addon_repos()],
            }
        if project.dev_mode():
            values["devMode"] = project.dev_mode()

    merged = deep_merge(values, profile_values)
    namespace = merged.pop("namespace", None)
    if extra:
        merged = deep_merge(merged, extra)
    if namespace:
        merged.setdefault("kodpm", {})["namespace"] = namespace
    merged.setdefault("kodpm", {})["profile"] = profile
    if db_name:
        merged.setdefault("kodpm", {})["dbName"] = db_name
    return merged


def sanitize_release(name: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    slug = "-".join(part for part in slug.split("-") if part)
    return (slug or "instance")[:40]


def dump_values(values: dict[str, Any], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(values, fh, sort_keys=False, allow_unicode=True)
    return dest


def release_name(project: ProjectFiles) -> str:
    return sanitize_release(project.name)


def namespace_of(values: dict[str, Any], profile: str) -> str:
    ns = (values.get("kodpm") or {}).get("namespace")
    if ns:
        return str(ns)
    profile_values = load_profile(profile)
    return str(profile_values.get("namespace") or "kodpm")
