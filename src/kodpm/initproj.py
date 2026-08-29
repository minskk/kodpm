from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kodpm.catalog import get_version, load_platforms, load_versions, normalize_odoo_version
from kodpm.project import parse_git_link, parse_modules
from kodpm.sources import default_data_dir

PLATFORM_ALIASES = {
    "foncomtech": "fincomtech",
    "fincom": "fincomtech",
}

DONE_TOKENS = {"готово", "done", "q", "quit", ".", "-", "конец"}
REQUIREMENTS_TXT = "requirements.txt"


def normalize_addon_links(links: list[str], odoo_version: str) -> list[str]:
    """Drop duplicate repo names; default branch to the Odoo series when omitted."""
    version = normalize_odoo_version(odoo_version)
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
            out.append(f"{parsed['url']} {version}")
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


def build_odpm_json(
    odoo_version: str,
    platform_name: str,
    addon_links: list[str],
    *,
    image: str = "",
    odoo_git_link: str = "",
    bin_name: str = "",
) -> dict[str, Any]:
    version = get_version(odoo_version)
    platform = normalize_platform(platform_name)
    dependencies = [
        parse_git_link(link)
        for link in normalize_addon_links(addon_links, version.key)
    ]
    data: dict[str, Any] = {
        "python_version": version.python,
        "distro_name": version.distro,
        "distro_version": version.distro_version,
        "odoo_version": version.key,
        "platform_name": platform,
        "dependencies": dependencies,
        "requirements_txt": [],
        "kodpm_data_dir": str(default_data_dir()),
    }
    if odoo_git_link.strip():
        data["odoo_git_link"] = odoo_git_link.strip()
    if image.strip():
        data["image"] = image.strip()
    if bin_name.strip():
        data["bin"] = bin_name.strip()
    return data


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
) -> dict[str, Any]:
    modules = parse_modules(init_modules)
    return {
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
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
) -> tuple[Path, Path]:
    project_dir.mkdir(parents=True, exist_ok=True)
    odpm_path = project_dir / "odpm.json"
    settings_path = project_dir / "user_settings.json"
    write_json(odpm_path, odpm)
    write_json(settings_path, user_settings)
    write_requirements_txt(project_dir)
    return odpm_path, settings_path
