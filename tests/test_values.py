from pathlib import Path

from kodpm.initproj import build_odpm_json, build_user_settings, write_project_files
from kodpm.project import ProjectFiles
from kodpm.layout import addons_path_of
from kodpm.values import build_values, sanitize_release


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


def test_values_local_overlay(tmp_path: Path):
    write_project_files(
        tmp_path,
        build_odpm_json("17.0", "odoo", ["https://github.com/OCA/web.git 17.0"]),
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


def test_addons_path_uses_host_home_for_clones():
    values = {
        "extraAddons": "/mnt/extra-addons",
        "addons": {
            "repos": [],
            "hostPath": {
                "enabled": True,
                "name": "developing",
                "path": "/host-home/projects/kodpm_autoparts",
                "extraPaths": ["/host-home/projects/kodpm_data/digital-autoparts-17.0"],
            },
        },
    }
    path = addons_path_of(values)
    assert path == "/host-home/projects/kodpm_data/digital-autoparts-17.0"
    assert "kodpm_autoparts," not in path and not path.endswith("kodpm_autoparts")


def test_local_extra_paths_resolve_under_home(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    data = home / "projects" / "kodpm_data"
    project_dir.mkdir(parents=True)
    (data / "web-17.0").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))
    write_project_files(
        project_dir,
        build_odpm_json("17.0", "odoo", ["https://github.com/OCA/web.git 17.0"]),
        build_user_settings("base"),
    )
    values = build_values(ProjectFiles(project_dir), "local")
    extras = values["addons"]["hostPath"]["extraPaths"]
    assert extras == ["/host-home/projects/kodpm_data/web-17.0"]
    raw = values["config"]["raw"]
    assert "/host-home/projects/kodpm_data/web-17.0" in raw
    assert "/host-home/projects/app," not in raw
    assert "developing/web" not in raw
