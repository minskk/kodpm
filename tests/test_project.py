import json
from pathlib import Path

from kodpm.project import (
    ProjectFiles,
    has_project_manifest,
    parse_dependencies,
    parse_git_link,
    parse_modules,
)


def test_parse_modules_csv():
    assert parse_modules("base, web") == ["base", "web"]
    assert parse_modules(["sale", "crm"]) == ["sale", "crm"]


def test_parse_git_link():
    parsed = parse_git_link("https://github.com/OCA/web.git 17.0")
    assert parsed["name"] == "web"
    assert parsed["branch"] == "17.0"
    no_default = parse_git_link(
        "git@github.com:digital-autoparts/digital-autoparts-env.git",
        default_branch="",
    )
    assert no_default["name"] == "digital-autoparts-env"
    assert no_default["branch"] == ""


def test_parse_dependencies_mixed():
    repos = parse_dependencies(
        [
            "https://github.com/OCA/server-tools.git 17.0",
            {"name": "web", "url": "https://github.com/OCA/web.git", "branch": "17.0"},
        ]
    )
    assert len(repos) == 2
    assert repos[0]["name"] == "server-tools"
    assert repos[1]["url"].endswith("web.git")


def test_parse_dependencies_url_only_uses_default_branch():
    repos = parse_dependencies(
        ["https://github.com/OCA/queue", "https://github.com/OCA/web"],
        default_branch="17.0",
    )
    assert [repo["name"] for repo in repos] == ["queue", "web"]
    assert all(repo["branch"] == "17.0" for repo in repos)


def test_v2_odpm_maps_developing_and_string_deps(tmp_path: Path):
    (tmp_path / "odpm.json").write_text(
        json.dumps(
            {
                "manifest_schema": 2,
                "platform": {"git": "https://github.com/odoo/odoo.git", "build_date": "latest"},
                "odoo_version": "17.0",
                "database": {"language": "ru_RU", "country": "by"},
                "developing": {"git": "git@gitverse.ru:fincomtech/extra_module.git"},
                "postgres": "14",
                "dependencies": ["https://github.com/OCA/queue", "https://github.com/OCA/web"],
                "addons_branch": "17.0-dev",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    project = ProjectFiles(tmp_path)
    assert project.odoo_version == "17.0"
    assert project.odoo_git_link == "https://github.com/odoo/odoo.git"
    assert project.postgres_version == "14"
    assert project.db_lang() == "ru_RU"
    repos = project.addon_repos()
    assert [repo["name"] for repo in repos] == ["extra_module", "queue", "web"]
    assert repos[0]["branch"] == "17.0-dev"
    assert repos[1]["url"] == "https://github.com/OCA/queue"
    assert repos[1]["branch"] == "17.0"
    assert repos[2]["branch"] == "17.0"


def test_user_settings_addons_branch_only_affects_developing(tmp_path: Path):
    (tmp_path / "odpm.json").write_text(
        json.dumps(
            {
                "odoo_version": "17.0",
                "developing": {"git": "git@github.com:digital-autoparts/digital-autoparts.git"},
                "dependencies": ["https://github.com/OCA/queue", "https://github.com/OCA/web"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "user_settings.json").write_text(
        '{"addons_branch":"17.0-dev","init_modules":"base"}\n',
        encoding="utf-8",
    )
    repos = ProjectFiles(tmp_path).addon_repos()
    assert repos[0]["name"] == "digital-autoparts"
    assert repos[0]["branch"] == "17.0-dev"
    assert [repo["branch"] for repo in repos[1:]] == ["17.0", "17.0"]


def test_kodpm_json_fallback(tmp_path: Path):
    (tmp_path / "kodpm.json").write_text(
        '{"odoo_version":"16.0","platform_name":"odoo","odoo_git_link":"https://github.com/odoo/odoo.git","dependencies":[]}\n',
        encoding="utf-8",
    )
    project = ProjectFiles(tmp_path)
    assert project.odoo_version == "16.0"
    assert project.project_json_path.name == "kodpm.json"
    assert has_project_manifest(tmp_path)


def test_odpm_json_preferred_over_kodpm_json(tmp_path: Path):
    (tmp_path / "kodpm.json").write_text('{"odoo_version":"16.0"}\n', encoding="utf-8")
    (tmp_path / "odpm.json").write_text('{"odoo_version":"17.0"}\n', encoding="utf-8")
    assert ProjectFiles(tmp_path).odoo_version == "17.0"
