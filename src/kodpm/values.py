from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from kodpm.catalog import get_platform, get_version
from kodpm.hostpip import pip_packages_dir
from kodpm.layout import ODOO_BACKUPS_DIR, compose_conf, load_values_local
from kodpm.paths import profiles_dir
from kodpm.project import ProjectFiles, load_json
from kodpm.sources import addon_odpm_path, cache_dirname, collect_addon_repos, default_data_dir


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


def host_home_path(path: Path) -> str | None:
    home = Path.home().resolve()
    try:
        rel = path.resolve().relative_to(home)
    except ValueError:
        return None
    return f"/host-home/{rel.as_posix()}"


def requirements_has_packages(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return True
    return False


def _append_requirements(chunks: list[str], label: str, text: str) -> None:
    if not requirements_has_packages(text):
        return
    body = text.rstrip() + "\n"
    chunks.append(f"# {label}\n{body}" if label else body)


def requirements_from_addon_odpm(data: dict[str, Any]) -> list[str]:
    """Pip lines from an addon ODPM manifest (scenarios.*.requirements or requirements_txt)."""
    lines: list[str] = []
    extra = data.get("requirements_txt")
    if isinstance(extra, list):
        lines.extend(str(item).strip() for item in extra if str(item).strip())
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, dict):
        return lines
    chosen: Any = None
    for key in ("developer", "local", "dev"):
        item = scenarios.get(key)
        if isinstance(item, dict) and item.get("requirements"):
            chosen = item.get("requirements")
            break
    if chosen is None:
        for item in scenarios.values():
            if isinstance(item, dict) and item.get("requirements"):
                chosen = item.get("requirements")
                break
    if isinstance(chosen, list):
        lines.extend(str(item).strip() for item in chosen if str(item).strip())
    return lines


def iter_addon_odpm(project: ProjectFiles) -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    seen: set[Path] = set()
    for repo in collect_addon_repos(project):
        name = str(repo["name"])
        branch = str(repo.get("branch") or project.addons_branch)
        path = addon_odpm_path(project, name, branch)
        if not path:
            continue
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        data = load_json(path)
        if data:
            found.append((name, data))
    return found


def options_from_addon_odpm(data: dict[str, Any]) -> dict[str, Any]:
    """odoo_conf.options from an addon ODPM scenario (developer / local / dev)."""
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, dict):
        return {}
    chosen: Any = None
    for key in ("developer", "local", "dev"):
        item = scenarios.get(key)
        if isinstance(item, dict) and isinstance(item.get("odoo_conf"), dict):
            chosen = item.get("odoo_conf")
            break
    if chosen is None:
        for item in scenarios.values():
            if isinstance(item, dict) and isinstance(item.get("odoo_conf"), dict):
                chosen = item.get("odoo_conf")
                break
    if not isinstance(chosen, dict):
        return {}
    options = chosen.get("options")
    return dict(options) if isinstance(options, dict) else {}


def merge_csv_option(left: Any, right: Any) -> str:
    parts: list[str] = []
    for src in (left, right):
        for item in str(src or "").split(","):
            item = item.strip()
            if item and item not in parts:
                parts.append(item)
    return ",".join(parts)


def addon_odoo_conf_options(project: ProjectFiles) -> dict[str, Any]:
    options: dict[str, Any] = {}
    for _name, data in iter_addon_odpm(project):
        extra = options_from_addon_odpm(data)
        for key, value in extra.items():
            if key == "server_wide_modules" and key in options:
                options[key] = merge_csv_option(options[key], value)
            else:
                options[key] = value
    return options


def python_requirements_values(project: ProjectFiles) -> dict[str, Any]:
    """Only addon odpm.json lists; project/core requirements.txt are ignored."""
    chunks: list[str] = []
    for name, data in iter_addon_odpm(project):
        lines = requirements_from_addon_odpm(data)
        if lines:
            _append_requirements(chunks, f"odpm.json {name}", "\n".join(lines) + "\n")
    project_text = "".join(chunks)
    return {
        "enabled": requirements_has_packages(project_text),
        "project": project_text,
        "odoo": "",
        "hostPath": "",
    }


def local_extra_addon_mounts(project: ProjectFiles) -> list[dict[str, str]]:
    """hostPath mounts for addon clones. Bind the repo dir, not $HOME (home is mode 700)."""
    mounts: list[dict[str, str]] = []
    drop_in = project.project_dir / "addons"
    if drop_in.is_dir():
        mapped = host_home_path(drop_in)
        if mapped:
            mounts.append({"name": "addons", "path": mapped})
    for repo in collect_addon_repos(project):
        dest = default_data_dir() / cache_dirname(
            str(repo["name"]),
            str(repo.get("branch") or project.odoo_version),
        )
        mapped = host_home_path(dest)
        if mapped:
            mounts.append({"name": str(repo["name"]), "path": mapped})
    return mounts


def build_values(
    project: ProjectFiles,
    profile: str,
    *,
    extra: dict[str, Any] | None = None,
    db_name: str | None = None,
    extra_services: bool = True,
) -> dict[str, Any]:
    profile_values = load_profile(profile)
    version = get_version(project.odoo_version)
    platform_key = project.platform_name
    # Allow kodpm.json platform_name that is a fork not in catalog: use custom + overlay
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
        "list_db": not bool(db_name),
        "max_cron_threads": 1,
        "without_demo": not project.create_demo(),
        "db_maxconn": 64,
        "logfile": False,
    }
    if db_name:
        options["dbfilter"] = f"^{db_name}$"
    for key, value in addon_odoo_conf_options(project).items():
        if key == "server_wide_modules" and key in options:
            options[key] = merge_csv_option(options[key], value)
        else:
            options[key] = value

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
            "image": f"postgres:{project.postgres_version or version.postgres}",
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
            "repos": collect_addon_repos(project),
            "hostPath": {
                "enabled": False,
                "name": "developing",
                "path": "",
                "extraPaths": [],
                "extraMounts": [],
            },
        },
        "kodpm": {
            "profile": profile,
            "dbName": db_name or "odoo",
            "runtimeDb": db_name or "",
            "adminLogin": project.admin_login(),
            "dbLang": project.db_lang(),
            "python": version.python,
            "odooGitLink": odoo_git,
        },
        "pythonRequirements": python_requirements_values(project),
        "odpmSecrets": {"enabled": False, "hostPath": ""},
        "extraServices": [],
    }

    if profile == "local":
        host_path = host_home_path(project.project_dir)
        if host_path:
            values["addons"]["repos"] = []
            values["addons"]["hostPath"] = {
                "enabled": True,
                "name": "developing",
                "path": host_path,
                "extraPaths": [],
                "extraMounts": local_extra_addon_mounts(project),
            }
        if project.dev_mode():
            values["devMode"] = project.dev_mode()
        from kodpm.secrets import secrets_runtime_path

        runtime = secrets_runtime_path(project)
        mapped = host_home_path(runtime) if runtime.is_file() else None
        if mapped:
            values["odpmSecrets"] = {"enabled": True, "hostPath": mapped}

    from kodpm.extraservices import extra_service_values

    values["extraServices"] = extra_service_values(project) if extra_services else []

    merged = deep_merge(values, profile_values)
    namespace = merged.pop("namespace", None)
    local = load_values_local(project)
    if local:
        namespace = local.pop("namespace", namespace)
        merged = deep_merge(merged, local)
    if extra:
        merged = deep_merge(merged, extra)
    if profile == "local":
        user_host = ((local or {}).get("ingress") or {}).get("host")
        extra_host = ((extra or {}).get("ingress") or {}).get("host") if extra else None
        if not user_host and not extra_host:
            merged.setdefault("ingress", {})["host"] = (
                f"{sanitize_release(project.name)}.127.0.0.1.nip.io"
            )
        if (merged.get("minio") or {}).get("enabled"):
            local_minio = (local or {}).get("minio") or {}
            extra_minio = ((extra or {}).get("minio") or {}) if extra else {}
            if "hostPath" not in local_minio and "hostPath" not in extra_minio:
                mapped = host_home_path(project.project_dir / ODOO_BACKUPS_DIR)
                if mapped:
                    merged.setdefault("minio", {})["hostPath"] = mapped
        reqs = merged.setdefault("pythonRequirements", {})
        local_req = (local or {}).get("pythonRequirements") or {}
        extra_req = ((extra or {}).get("pythonRequirements") or {}) if extra else {}
        if reqs.get("enabled") and "hostPath" not in local_req and "hostPath" not in extra_req:
            mapped = host_home_path(pip_packages_dir(project))
            if mapped:
                reqs["hostPath"] = mapped
    if namespace:
        merged.setdefault("kodpm", {})["namespace"] = namespace
    merged.setdefault("kodpm", {})["profile"] = profile
    if db_name:
        merged.setdefault("kodpm", {})["dbName"] = db_name
        merged.setdefault("kodpm", {})["runtimeDb"] = db_name
    if not extra_services:
        merged["extraServices"] = []
    merged.setdefault("config", {})["raw"] = compose_conf(project, merged)
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
