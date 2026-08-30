from pathlib import Path

from kodpm.initproj import build_kodpm_json, build_user_settings, write_project_files
from kodpm.project import ProjectFiles
from kodpm.layout import addons_path_of
from kodpm.iniutil import get_ini_option
from kodpm.values import (
    build_values,
    options_from_addon_odpm,
    python_requirements_values,
    requirements_has_packages,
    sanitize_release,
)


def test_sanitize_release():
    assert sanitize_release("Demo 17!") == "demo-17"


def test_demo_17_local_values():
    project = ProjectFiles(Path("examples/demo-17"))
    values = build_values(project, "local", db_name="odoo")
    assert values["odooVersion"] == "17.0"
    assert values["image"]["repository"] == "odoo"
    assert values["image"]["tag"] == "17"
    assert values["postgres"]["image"] == "postgres:14"
    assert values["platformName"] == "odoo"
    assert values["confName"] == "odoo.conf"
    assert values["modules"]["init"] == ["base", "web"]
    assert values["minio"]["enabled"] is True
    assert values["probes"]["type"] == "http"
    assert values["kodpm"]["namespace"] == "kodpm"
    assert values["devMode"] == "reload,xml"
    assert values["addons"]["repos"] == []
    assert values["addons"]["hostPath"]["extraPaths"] == []
    assert "data_dir" not in values["config"]["options"]
    assert values["ingress"]["host"] == "demo-17.127.0.0.1.nip.io"
    assert values["minio"]["hostPath"].endswith("/examples/demo-17/odoo_backups")
    assert values["minio"]["hostPath"].startswith("/host-home/")


def test_fincomtech_values():
    project = ProjectFiles(Path("examples/fincomtech-17"))
    values = build_values(project, "dev")
    assert values["platformName"] == "fincomtech"
    assert values["confName"] == "fincomtech.conf"
    assert values["image"]["repository"] == "registry.example.com/fincomtech"
    assert values["dump"]["storage"]["type"] == "s3"
    assert values["minio"]["enabled"] is False
    assert values["kodpm"]["odooGitLink"]


def test_old_version_probe():
    project = ProjectFiles(Path("examples/demo-17"))
    project.odpm["odoo_version"] = "12.0"
    values = build_values(project, "test")
    assert values["probes"]["type"] == "tcp"
    assert values["postgres"]["image"] == "postgres:12"
    assert "http_port" in values["config"]["options"]


def test_local_minio_hostpath_override(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    write_project_files(
        project_dir,
        build_kodpm_json("17.0", "odoo", []),
        build_user_settings("base"),
    )
    (project_dir / "values.local.yaml").write_text(
        "minio:\n  hostPath: \"\"\n",
        encoding="utf-8",
    )
    values = build_values(ProjectFiles(project_dir), "local")
    assert values["minio"]["hostPath"] == ""


def test_values_local_overlay(tmp_path: Path):
    write_project_files(
        tmp_path,
        build_kodpm_json("17.0", "odoo", ["https://github.com/OCA/web.git 17.0"]),
        build_user_settings("base,web"),
    )
    (tmp_path / "values.local.yaml").write_text(
        "ingress:\n  host: custom.example.test\n",
        encoding="utf-8",
    )
    values = build_values(ProjectFiles(tmp_path), "local")
    assert values["ingress"]["host"] == "custom.example.test"
    raw = values["config"]["raw"]
    assert raw.count("data_dir") == 1
    assert "web" in raw


def test_addons_path_uses_extra_mounts():
    values = {
        "extraAddons": "/mnt/extra-addons",
        "addons": {
            "repos": [],
            "hostPath": {
                "enabled": True,
                "name": "developing",
                "path": "/host-home/projects/kodpm_autoparts",
                "extraMounts": [
                    {
                        "name": "digital-autoparts",
                        "path": "/host-home/projects/kodpm_data/digital-autoparts-17.0",
                    }
                ],
            },
        },
    }
    path = addons_path_of(values)
    assert path == "/mnt/extra-addons/digital-autoparts"
    assert "kodpm_autoparts" not in path


def test_local_extra_mounts_under_home(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    data = home / "projects" / "kodpm_data"
    project_dir.mkdir(parents=True)
    (data / "web-17.0").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))
    write_project_files(
        project_dir,
        build_kodpm_json("17.0", "odoo", ["https://github.com/OCA/web.git 17.0"]),
        build_user_settings("base"),
    )
    values = build_values(ProjectFiles(project_dir), "local")
    mounts = values["addons"]["hostPath"]["extraMounts"]
    assert mounts == [
        {"name": "web", "path": "/host-home/projects/kodpm_data/web-17.0"},
    ]
    raw = values["config"]["raw"]
    assert "addons_path = /mnt/extra-addons/web" in raw
    assert "db_name = False" in raw


def test_runtime_db_pins_conf(tmp_path: Path):
    write_project_files(
        tmp_path,
        build_kodpm_json("17.0", "odoo", []),
        build_user_settings("base"),
    )
    values = build_values(ProjectFiles(tmp_path), "test", db_name="shop")
    raw = values["config"]["raw"]
    assert "db_name = shop" in raw
    assert "list_db = False" in raw
    assert "dbfilter = ^shop$" in raw
    assert values["kodpm"]["runtimeDb"] == "shop"


def test_requirements_has_packages():
    assert requirements_has_packages("openupgradelib==3.7.0\n")
    assert not requirements_has_packages("")
    assert not requirements_has_packages("# comment\n\n")


def test_requirements_txt_files_are_ignored(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    data = home / "projects" / "kodpm_data"
    core = data / "odoo-17.0"
    project_dir.mkdir(parents=True)
    core.mkdir(parents=True)
    (core / "requirements.txt").write_text("freezegun==1.2.2\n", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))
    write_project_files(
        project_dir,
        build_kodpm_json("17.0", "odoo", []),
        build_user_settings("base"),
    )
    (project_dir / "requirements.txt").write_text("openupgradelib==3.7.0\n", encoding="utf-8")
    req = python_requirements_values(ProjectFiles(project_dir))
    assert req["enabled"] is False
    assert req["project"] == ""
    assert req["odoo"] == ""


def test_addon_odpm_scenario_requirements(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    data = home / "projects" / "kodpm_data"
    addon = data / "web-17.0"
    project_dir.mkdir(parents=True)
    addon.mkdir(parents=True)
    (addon / "requirements.txt").write_text("ignored-from-txt==1.0\n", encoding="utf-8")
    (addon / "odpm.json").write_text(
        '{"scenarios":{"developer":{"requirements":["httpx==0.26.0","zeep[async]==4.2.1"]}}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))
    write_project_files(
        project_dir,
        build_kodpm_json("17.0", "odoo", ["https://github.com/OCA/web.git 17.0"]),
        build_user_settings("base"),
    )
    req = python_requirements_values(ProjectFiles(project_dir))
    assert req["enabled"] is True
    assert "httpx==0.26.0" in req["project"]
    assert "zeep[async]==4.2.1" in req["project"]
    assert "ignored-from-txt" not in req["project"]
    assert req["odoo"] == ""


def test_addon_odpm_odoo_conf_and_nested_deps(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    data = home / "projects" / "kodpm_data"
    addon = data / "digital-autoparts-17.0-dev"
    project_dir.mkdir(parents=True)
    addon.mkdir(parents=True)
    (data / "queue-17.0").mkdir()
    (data / "web-17.0").mkdir()
    (addon / "odpm.json").write_text(
        """
{
  "odoo_version": "17.0",
  "dependencies": ["https://github.com/OCA/queue", "https://github.com/OCA/web"],
  "scenarios": {
    "developer": {
      "odoo_conf": {
        "options": {
          "proxy_mode": "True",
          "server_wide_modules": "base,web,queue_job"
        }
      }
    }
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))
    write_project_files(
        project_dir,
        build_kodpm_json(
            "17.0",
            "odoo",
            ["git@github.com:digital-autoparts/digital-autoparts.git 17.0-dev"],
            addons_branch="17.0-dev",
        ),
        build_user_settings("setup_all"),
    )
    values = build_values(ProjectFiles(project_dir), "local")
    mounts = {item["name"]: item["path"] for item in values["addons"]["hostPath"]["extraMounts"]}
    assert mounts["digital-autoparts"].endswith("digital-autoparts-17.0-dev")
    assert mounts["queue"].endswith("queue-17.0")
    assert mounts["web"].endswith("web-17.0")
    raw = values["config"]["raw"]
    assert get_ini_option(raw, "server_wide_modules") == "base,web,queue_job"
    assert "/mnt/extra-addons/queue" in (get_ini_option(raw, "addons_path") or "")
    assert values["config"]["options"]["server_wide_modules"] == "base,web,queue_job"


def test_options_from_addon_odpm():
    data = {
        "scenarios": {
            "developer": {
                "odoo_conf": {
                    "options": {
                        "proxy_mode": "True",
                        "server_wide_modules": "base,web,queue_job",
                    }
                }
            }
        }
    }
    assert options_from_addon_odpm(data) == {
        "proxy_mode": "True",
        "server_wide_modules": "base,web,queue_job",
    }


def test_empty_requirements_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("KODPM_DATA_DIR", str(tmp_path / "missing-data"))
    write_project_files(tmp_path, build_kodpm_json("17.0", "odoo", []), build_user_settings("base"))
    req = python_requirements_values(ProjectFiles(tmp_path))
    assert req["enabled"] is False
    assert req["project"] == ""
    assert req["odoo"] == ""
