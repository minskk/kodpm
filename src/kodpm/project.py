from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_JSON_NAME = "kodpm.json"
LEGACY_PROJECT_JSON_NAME = "odpm.json"
ODPM_JSON_NAME = "odpm.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def parse_git_link(link: str, default_branch: str | None = "master") -> dict[str, str]:
    parts = link.split()
    url = parts[0]
    if len(parts) > 1:
        branch = parts[1]
    elif default_branch:
        branch = default_branch
    else:
        branch = ""
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


def parse_dependencies(raw: Any, default_branch: str | None = None) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    if not raw:
        return repos
    branch_default = (default_branch or "").strip() or "master"
    if isinstance(raw, dict):
        raw = [raw]
    for item in raw:
        if isinstance(item, str):
            repos.append(parse_git_link(item, default_branch=branch_default))
        elif isinstance(item, dict):
            if "url" in item or "git" in item or "odoo_git_link" in item:
                url = str(item.get("url") or item.get("git") or item.get("odoo_git_link"))
                parsed = parse_git_link(url, default_branch=branch_default)
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
                    parsed = parse_git_link(str(link), default_branch=branch_default)
                    parsed["name"] = str(item.get("name") or parsed["name"])
                    repos.append(parsed)
    return repos


def has_project_manifest(project_dir: Path) -> bool:
    root = project_dir.resolve()
    odpm = root / ODPM_JSON_NAME
    kodpm = root / PROJECT_JSON_NAME
    return odpm.is_file() or odpm.is_symlink() or kodpm.is_file()


class ProjectFiles:
    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir.resolve()
        self.odpm = load_json(self.project_dir / ODPM_JSON_NAME)
        if not self.odpm:
            self.odpm = load_json(self.project_dir / PROJECT_JSON_NAME)
        self.user_settings = load_json(self.project_dir / "user_settings.json")
        if not self.user_settings:
            self.user_settings = load_json(self.project_dir / "usersettings.json")

    @property
    def project_json_path(self) -> Path:
        odpm_path = self.project_dir / ODPM_JSON_NAME
        if odpm_path.is_file() or odpm_path.is_symlink():
            return odpm_path
        return self.project_dir / PROJECT_JSON_NAME

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
        platform = self.odpm.get("platform")
        if isinstance(platform, dict) and platform.get("git"):
            return str(platform["git"]).strip()
        return str(self.odpm.get("odoo_git_link") or "").strip()

    @property
    def postgres_version(self) -> str:
        raw = self.odpm.get("postgres")
        if isinstance(raw, dict):
            return str(raw.get("version") or raw.get("image") or "").strip()
        return str(raw or "").strip()

    @property
    def conf_name(self) -> str:
        try:
            from kodpm.catalog import get_platform

            platform = get_platform(self.platform_name)
            return str(platform.get("conf_name") or f"{self.platform_name}.conf")
        except KeyError:
            if self.platform_name == "odoo":
                return "odoo.conf"
            return f"{self.platform_name}.conf"

    @property
    def conf_path(self) -> Path:
        return self.project_dir / self.conf_name

    @property
    def values_local_path(self) -> Path:
        return self.project_dir / "values.local.yaml"

    @property
    def requirements_path(self) -> Path:
        return self.project_dir / "requirements.txt"

    @property
    def addons_branch(self) -> str:
        """Branch of the developing repo (`--branch`). Dependencies use `odoo_version`."""
        from_settings = str(self.user_settings.get("addons_branch") or "").strip()
        if from_settings:
            return from_settings
        return str(self.odpm.get("addons_branch") or "").strip() or self.odoo_version

    def addon_repos(self) -> list[dict[str, Any]]:
        """Developing repo plus `dependencies` from the project odpm.json / kodpm.json."""
        repos: list[dict[str, Any]] = []
        seen: set[str] = set()
        developing = self.odpm.get("developing")
        if isinstance(developing, dict):
            url = str(developing.get("git") or developing.get("url") or "").strip()
            if url:
                parsed = parse_git_link(url, default_branch=self.addons_branch)
                parsed["branch"] = str(developing.get("branch") or parsed["branch"])
                repos.append(parsed)
                seen.add(parsed["name"])
        elif isinstance(developing, str) and developing.strip():
            parsed = parse_git_link(developing, default_branch=self.addons_branch)
            repos.append(parsed)
            seen.add(parsed["name"])
        for repo in parse_dependencies(self.odpm.get("dependencies"), default_branch=self.odoo_version):
            name = str(repo["name"])
            if name in seen:
                continue
            seen.add(name)
            repos.append(repo)
        return repos

    def chosen_scenario(self) -> dict[str, Any]:
        scenarios = self.odpm.get("scenarios")
        if not isinstance(scenarios, dict):
            return {}
        for key in ("developer", "local", "dev"):
            item = scenarios.get(key)
            if isinstance(item, dict):
                return item
        for item in scenarios.values():
            if isinstance(item, dict):
                return item
        return {}

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
        if data.get("db_lang"):
            return str(data["db_lang"])
        database = self.odpm.get("database")
        if isinstance(database, dict) and database.get("language"):
            return str(database["language"])
        return "en_US"

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
