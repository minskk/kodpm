from pathlib import Path

from kodpm.initproj import build_odpm_json, build_user_settings, write_project_files
from kodpm.project import ProjectFiles
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
