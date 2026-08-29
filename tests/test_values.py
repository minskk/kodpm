from pathlib import Path

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
