from pathlib import Path

from kodpm.initproj import build_kodpm_json, build_user_settings, write_project_files
from kodpm.project import ProjectFiles
from kodpm.sources import cache_dirname, collect_addon_repos, ensure_symlink, relative_symlink_target


def test_cache_dirname():
    assert cache_dirname("odoo", "17.0") == "odoo-17.0"
    assert cache_dirname("OCA/web", "17.0") == "OCA-web-17.0"
    assert cache_dirname("digital-autoparts-env", "") == "digital-autoparts-env"


def test_relative_symlink_under_projects(tmp_path: Path):
    data = tmp_path / "kodpm_data" / "odoo-17.0"
    data.mkdir(parents=True)
    (data / "marker").write_text("ok", encoding="utf-8")
    project = tmp_path / "kodpm_odoo_test"
    project.mkdir()
    link = project / "odoo"
    ensure_symlink(link, data)
    assert link.is_symlink()
    assert link.resolve() == data.resolve()
    assert relative_symlink_target(link, data) == Path("../kodpm_data/odoo-17.0")
    assert (link / "marker").read_text(encoding="utf-8") == "ok"
    ensure_symlink(link, data)
    assert link.resolve() == data.resolve()


def test_collect_nested_addon_repos(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    data = home / "projects" / "kodpm_data"
    addon = data / "digital-autoparts-17.0-dev"
    project_dir.mkdir(parents=True)
    addon.mkdir(parents=True)
    (addon / "odpm.json").write_text(
        '{"odoo_version":"17.0","dependencies":["https://github.com/OCA/queue","https://github.com/OCA/web"]}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))
    write_project_files(
        project_dir,
        build_kodpm_json(
            "17.0",
            "odoo",
            ["git@github.com:digital-autoparts/digital-autoparts.git 17.0-dev"],
            addons_branch="17.0-dev",
        ),
        build_user_settings("base"),
    )
    repos = collect_addon_repos(ProjectFiles(project_dir))
    assert [repo["name"] for repo in repos] == ["digital-autoparts", "queue", "web"]
    assert repos[1]["url"] == "https://github.com/OCA/queue"
    assert repos[1]["branch"] == "17.0"
    assert repos[2]["branch"] == "17.0"
