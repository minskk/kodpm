from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kodpm.catalog import get_platform, get_version, load_platforms, load_versions, normalize_odoo_version
from kodpm.project import ODPM_JSON_NAME, parse_git_link, parse_modules
from kodpm.sources import default_data_dir

PLATFORM_ALIASES = {
    "foncomtech": "fincomtech",
    "fincom": "fincomtech",
}

DONE_TOKENS = {"готово", "done", "q", "quit", ".", "-", "конец"}
REQUIREMENTS_TXT = "requirements.txt"


def normalize_addon_links(links: list[str], default_branch: str) -> list[str]:
    """Drop duplicate repo names; use default_branch when the link has no branch."""
    branch = normalize_odoo_version((default_branch or "").strip() or "master")
    seen: set[str] = set()
    out: list[str] = []
    for raw in links:
        text = str(raw).strip()
        if not text:
            continue
        parsed = parse_git_link(text)
        name = parsed["name"]
        if name in seen:
            continue
        seen.add(name)
        if len(text.split()) == 1:
            out.append(f"{parsed['url']} {branch}")
        else:
            out.append(text)
    return out


def known_versions() -> list[str]:
    return sorted(load_versions().keys(), key=lambda v: float(v.replace(".0", "")))


def known_platforms() -> list[str]:
    return sorted(load_platforms().keys())


def normalize_platform(name: str) -> str:
    key = (name or "odoo").strip().lower()
    return PLATFORM_ALIASES.get(key, key)


def _platform_git(platform_name: str, odoo_git_link: str = "") -> str:
    if odoo_git_link.strip():
        return odoo_git_link.strip().split()[0]
    try:
        git = str(get_platform(platform_name).get("git") or "").strip()
    except KeyError:
        git = ""
    return git or "https://github.com/odoo/odoo.git"


def build_odpm_v2_json(
    odoo_version: str,
    platform_name: str,
    developing_url: str = "",
    dependency_urls: list[str] | None = None,
    *,
    addons_branch: str = "",
    odoo_git_link: str = "",
    image: str = "",
    bin_name: str = "",
) -> dict[str, Any]:
    version = get_version(odoo_version)
    platform = normalize_platform(platform_name)
    default_branch = normalize_odoo_version((addons_branch or "").strip() or version.key)
    developing = ""
    dependencies: list[str] = []
    if developing_url.strip():
        developing = parse_git_link(developing_url, default_branch=default_branch)["url"]
    for link in dependency_urls or []:
        parsed = parse_git_link(link, default_branch=default_branch)
        if parsed["url"] != developing:
            dependencies.append(parsed["url"])
    data: dict[str, Any] = {
        "manifest_schema": 2,
        "platform": {
            "git": _platform_git(platform, odoo_git_link),
            "build_date": "latest",
        },
        "odoo_version": version.key,
        "database": {"language": "ru_RU", "country": "by"},
        "python": version.python,
        "distro": {"name": version.distro, "version": version.distro_version},
        "postgres": version.postgres,
        "addons_branch": default_branch,
        "dependencies": dependencies,
        "scenarios": {
            "developer": {
                "requirements": [],
                "odoo_conf": {"options": {}},
                "services": {},
            }
        },
    }
    if developing:
        data["developing"] = {"git": developing}
    if platform != "odoo":
        data["platform_name"] = platform
    if image.strip():
        data["image"] = image.strip()
    if bin_name.strip():
        data["bin"] = bin_name.strip()
    return data


def build_kodpm_json(
    odoo_version: str,
    platform_name: str,
    addon_links: list[str],
    *,
    image: str = "",
    odoo_git_link: str = "",
    bin_name: str = "",
    addons_branch: str = "",
) -> dict[str, Any]:
    """Build ODPM v2 odpm.json. First addon URL is developing; the rest are dependencies."""
    normalized = normalize_addon_links(addon_links, addons_branch or odoo_version)
    developing = normalized[0] if normalized else ""
    rest = normalized[1:] if len(normalized) > 1 else []
    return build_odpm_v2_json(
        odoo_version,
        platform_name,
        developing,
        rest,
        addons_branch=addons_branch,
        odoo_git_link=odoo_git_link,
        image=image,
        bin_name=bin_name,
    )


def build_user_settings(
    init_modules: str | list[str],
    *,
    update_modules: str = "",
    db_lang: str = "ru_RU",
    db_country_code: str | bool = "ru",
    admin_login: str = "admin",
    admin_password: str = "admin",
    create_demo: bool = False,
    dev_mode: str = "reload,xml",
    addons_branch: str = "",
) -> dict[str, Any]:
    modules = parse_modules(init_modules)
    data: dict[str, Any] = {
        "init_modules": ",".join(modules),
        "update_modules": ",".join(parse_modules(update_modules)),
        "db_creation_data": {
            "db_lang": db_lang,
            "db_country_code": db_country_code,
            "create_demo": create_demo,
            "db_default_admin_login": admin_login,
            "db_default_admin_password": admin_password,
        },
        "dev_mode": dev_mode,
        "db_manager_password": admin_password,
        "update_git_repos": False,
        "clean_git_repos": False,
    }
    if addons_branch.strip():
        data["addons_branch"] = addons_branch.strip()
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_requirements_txt(project_dir: Path) -> Path:
    path = project_dir / REQUIREMENTS_TXT
    if not path.exists():
        path.write_text("", encoding="utf-8")
    return path


def write_project_files(
    project_dir: Path,
    odpm: dict[str, Any],
    user_settings: dict[str, Any],
    *,
    odpm_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write odpm.json (unless a symlink already points at the developing clone) and user_settings.json."""
    project_dir.mkdir(parents=True, exist_ok=True)
    dest = odpm_path or project_dir / ODPM_JSON_NAME
    settings_path = project_dir / "user_settings.json"
    link = project_dir / ODPM_JSON_NAME
    if link.is_symlink() and (dest == link or dest.resolve() == link.resolve()):
        write_json(link.resolve(), odpm)
    else:
        write_json(dest, odpm)
    write_json(settings_path, user_settings)
    write_requirements_txt(project_dir)
    return dest if dest.exists() else link, settings_path


def write_odpm_and_link(project_dir: Path, repo_name: str, odpm: dict[str, Any]) -> Path:
    """Write odpm.json into the developing clone and symlink it from the workspace root."""
    from kodpm.sources import ensure_symlink

    target = project_dir / repo_name / ODPM_JSON_NAME
    write_json(target, odpm)
    link = project_dir / ODPM_JSON_NAME
    if link.exists() or link.is_symlink():
        if link.is_symlink() or link.is_file():
            link.unlink()
    ensure_symlink(link, target, directory=False)
    return link


build_odpm_json = build_kodpm_json
