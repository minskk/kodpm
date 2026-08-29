from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def parse_git_link(link: str) -> dict[str, str]:
    parts = link.split()
    url = parts[0]
    branch = parts[1] if len(parts) > 1 else "master"
    name = url.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    name = name.replace(".", "-")
    return {"name": name, "url": url, "branch": branch}


def parse_modules(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def parse_dependencies(raw: Any) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    if not raw:
        return repos
    if isinstance(raw, dict):
        raw = [raw]
    for item in raw:
        if isinstance(item, str):
            repos.append(parse_git_link(item))
        elif isinstance(item, dict):
            if "url" in item or "git" in item or "odoo_git_link" in item:
                url = str(item.get("url") or item.get("git") or item.get("odoo_git_link"))
                parsed = parse_git_link(url)
                repos.append(
                    {
                        "name": str(item.get("name") or parsed["name"]),
                        "url": parsed["url"] if "://" in url or url.startswith("git@") else url,
                        "branch": str(item.get("branch") or item.get("version") or parsed["branch"]),
                        "depth": int(item.get("depth") or 1),
                    }
                )
            elif item:
                # odpm-style: {"OCA/web": "17.0"} is unusual; skip unknown shapes
                link = item.get("git_link") or item.get("link")
                if link:
                    parsed = parse_git_link(str(link))
                    parsed["name"] = str(item.get("name") or parsed["name"])
                    repos.append(parsed)
    return repos


class ProjectFiles:
    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir.resolve()
        self.odpm = load_json(self.project_dir / "odpm.json")
        if not self.odpm:
            self.odpm = load_json(self.project_dir / "kodpm.json")
        self.user_settings = load_json(self.project_dir / "user_settings.json")
        if not self.user_settings:
            self.user_settings = load_json(self.project_dir / "usersettings.json")

    @property
    def name(self) -> str:
        return self.project_dir.name

    @property
    def odoo_version(self) -> str:
        return str(self.odpm.get("odoo_version") or "17.0")

    @property
    def platform_name(self) -> str:
        return str(self.odpm.get("platform_name") or "odoo")

    @property
    def odoo_git_link(self) -> str:
        return str(self.odpm.get("odoo_git_link") or "")

    def addon_repos(self) -> list[dict[str, Any]]:
        return parse_dependencies(self.odpm.get("dependencies"))

    def init_modules(self) -> list[str]:
        return parse_modules(self.user_settings.get("init_modules"))

    def update_modules(self) -> list[str]:
        return parse_modules(self.user_settings.get("update_modules"))

    def admin_password(self) -> str:
        data = self.user_settings.get("db_creation_data") or {}
        return str(
            data.get("db_default_admin_password")
            or self.user_settings.get("db_manager_password")
            or "admin"
        )

    def admin_login(self) -> str:
        data = self.user_settings.get("db_creation_data") or {}
        return str(data.get("db_default_admin_login") or "admin")

    def db_manager_password(self) -> str:
        return str(self.user_settings.get("db_manager_password") or self.admin_password())

    def create_demo(self) -> bool:
        data = self.user_settings.get("db_creation_data") or {}
        return bool(data.get("create_demo"))

    def db_lang(self) -> str:
        data = self.user_settings.get("db_creation_data") or {}
        return str(data.get("db_lang") or "en_US")

    def dev_mode(self) -> str:
        value = self.user_settings.get("dev_mode")
        if value is True:
            return "reload,xml"
        return str(value or "")

    def developing_project_path(self) -> Path | None:
        raw = self.user_settings.get("developing_project")
        if not raw:
            return self.project_dir
        text = str(raw)
        if text.startswith("file://"):
            return Path(text[7:]).expanduser()
        if "://" in text or text.startswith("git@"):
            return None
        path = Path(text).expanduser()
        if not path.is_absolute():
            path = self.project_dir / path
        return path
