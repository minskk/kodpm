from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kodpm.project import ProjectFiles, parse_git_link
from kodpm.sources import cache_dirname, default_data_dir


PLACEHOLDER_RE = re.compile(r"\$\{@(?P<kind>service|source):(?P<name>[A-Za-z0-9_-]+)\}")


def scenario_services(project: ProjectFiles) -> dict[str, Any]:
    scenario = project.chosen_scenario()
    services = scenario.get("services")
    return dict(services) if isinstance(services, dict) else {}


def scenario_service_sources(project: ProjectFiles) -> dict[str, str]:
    scenario = project.chosen_scenario()
    sources = scenario.get("service_sources")
    if not isinstance(sources, dict):
        return {}
    return {str(key): str(value).strip() for key, value in sources.items() if str(value).strip()}


def service_source_repos(project: ProjectFiles) -> list[dict[str, str]]:
    repos: list[dict[str, str]] = []
    for raw in scenario_service_sources(project).values():
        repos.append(parse_git_link(raw, default_branch=""))
    return repos


def _source_host_path(project: ProjectFiles, name: str) -> str:
    from kodpm.values import host_home_path

    parsed = parse_git_link(
        scenario_service_sources(project).get(name) or name,
        default_branch="",
    )
    dest = default_data_dir() / cache_dirname(parsed["name"], parsed["branch"])
    mapped = host_home_path(dest)
    if mapped:
        return mapped
    link = project.project_dir / parsed["name"]
    return host_home_path(link) or str(dest)


def interpolate(text: str, project: ProjectFiles, release: str) -> str:
    def replace(match: re.Match[str]) -> str:
        kind = match.group("kind")
        name = match.group("name")
        if kind == "service":
            if name == "odoo":
                return f"{release}-odoo"
            return f"{release}-{_dns_name(name)}"
        return _source_host_path(project, name)

    return PLACEHOLDER_RE.sub(replace, text)


def _dns_name(name: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    return "-".join(part for part in slug.split("-") if part) or "svc"


def parse_port_pair(raw: Any) -> tuple[int, int] | None:
    text = str(raw).strip()
    if not text:
        return None
    if ":" in text:
        left, right = text.rsplit(":", 1)
        host = left.split(":")[-1]
        try:
            return int(host), int(right)
        except ValueError:
            return None
    try:
        port = int(text)
    except ValueError:
        return None
    return port, port


def parse_volume(raw: Any) -> tuple[str, str] | None:
    """Split host:container. Last colon is the mount path so ${@source:NAME}:/env works."""
    text = str(raw).strip()
    if not text or ":" not in text:
        return None
    src, dest = text.rsplit(":", 1)
    dest = dest.split(":")[0]
    if not src or not dest:
        return None
    return src, dest


def map_volume_host_path(src: str, project: ProjectFiles) -> str | None:
    from kodpm.values import host_home_path

    if "${" in src:
        return None
    if src.startswith("./") or (src and not src.startswith("/")):
        src_path = (project.project_dir / src.removeprefix("./")).resolve()
        return host_home_path(src_path)
    if src.startswith("/host-home/"):
        return src
    return host_home_path(Path(src))


def extra_service_values(project: ProjectFiles) -> list[dict[str, Any]]:
    from kodpm.values import sanitize_release

    release = sanitize_release(project.name)
    result: list[dict[str, Any]] = []
    for name, spec in scenario_services(project).items():
        if not isinstance(spec, dict) or not spec.get("image"):
            continue
        ports: list[dict[str, Any]] = []
        for item in spec.get("ports") or []:
            pair = parse_port_pair(item)
            if not pair:
                continue
            host, container = pair
            ports.append(
                {
                    "name": f"p{container}"[:15],
                    "containerPort": container,
                    "hostPort": host,
                }
            )
        volumes: list[dict[str, str]] = []
        for index, item in enumerate(spec.get("volumes") or []):
            parsed = parse_volume(interpolate(str(item), project, release))
            if not parsed:
                continue
            src, dest = parsed
            if "${" in src or not dest.startswith("/"):
                continue
            mapped = map_volume_host_path(src, project)
            if not mapped:
                continue
            volumes.append(
                {
                    "name": f"vol{index}",
                    "hostPath": mapped,
                    "mountPath": dest,
                }
            )
        env: dict[str, str] = {}
        raw_env = spec.get("environment") or {}
        if isinstance(raw_env, dict):
            for key, value in raw_env.items():
                env[str(key)] = interpolate(str(value), project, release)
        command = spec.get("command")
        cmd_list: list[str] = []
        if isinstance(command, list):
            cmd_list = [interpolate(str(item), project, release) for item in command]
        elif command:
            cmd_list = [interpolate(str(command), project, release)]
        result.append(
            {
                "name": _dns_name(str(name)),
                "image": str(spec["image"]),
                "command": cmd_list,
                "env": env,
                "ports": ports,
                "volumes": volumes,
            }
        )
    return result


def extra_service_warnings(project: ProjectFiles) -> list[str]:
    from kodpm.values import sanitize_release

    warnings: list[str] = []
    from kodpm.images import images_from_docker_hooks, post_prepare_commands

    _hook_images, leftover_hooks = images_from_docker_hooks(post_prepare_commands(project))
    for cmd in leftover_hooks:
        warnings.append(f"hooks.post_prepare пропущен: {' '.join(cmd)}")
    release = sanitize_release(project.name)
    for name, spec in scenario_services(project).items():
        if not isinstance(spec, dict):
            continue
        for item in spec.get("volumes") or []:
            parsed = parse_volume(interpolate(str(item), project, release))
            if not parsed:
                continue
            src, dest = parsed
            if "${" in src or not dest.startswith("/"):
                warnings.append(
                    f"volume {item} сервиса {name} пропущен (не раскрылся ${{@source}})."
                )
                continue
            if not map_volume_host_path(src, project):
                warnings.append(
                    f"volume {item} сервиса {name} пропущен (путь вне $HOME, hostPath недоступен)."
                )
    return warnings
