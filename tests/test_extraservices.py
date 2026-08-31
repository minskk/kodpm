from pathlib import Path

import pytest
import yaml

from kodpm.extraservices import (
    extra_service_values,
    extra_service_warnings,
    interpolate,
    parse_port_pair,
    parse_volume,
    service_source_repos,
)
from kodpm.initproj import build_user_settings, write_project_files
from kodpm.project import ProjectFiles
from kodpm.values import build_values, dump_values, release_name


V2_WITH_SERVICES = {
    "manifest_schema": 2,
    "platform": {"git": "https://github.com/odoo/odoo.git"},
    "odoo_version": "17.0",
    "developing": {"git": "https://github.com/example/extra_module.git"},
    "dependencies": [],
    "addons_branch": "17.0-dev",
    "scenarios": {
        "developer": {
            "service_sources": {
                "digital_autoparts_env": "git@github.com:digital-autoparts/digital-autoparts-env.git"
            },
            "hooks": {"post_prepare": [["docker", "image", "inspect", "autoparts_env:emulator"]]},
            "services": {
                "mailpit": {
                    "image": "axllent/mailpit",
                    "restart": "unless-stopped",
                    "ports": ["8025:8025", "1025:1025"],
                    "volumes": ["./data/mailpit/data:/data"],
                    "environment": {"MP_MAX_MESSAGES": "5000"},
                },
                "expresspay_test": {
                    "image": "autoparts_env:emulator",
                    "ports": ["8510:8510"],
                    "volumes": ["${@source:digital_autoparts_env}:/env"],
                    "environment": {
                        "ODOO_BASE_URL": "http://${@service:odoo}:8069",
                        "DB_HOST": "${@service:db1}",
                    },
                    "command": ["bash", "-c", "python3 /env/main.py"],
                },
                "outside": {
                    "image": "adminer",
                    "volumes": ["/var/lib/outside:/data"],
                },
            },
        }
    },
}


def _project_with_services(tmp_path: Path, monkeypatch) -> ProjectFiles:
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    data = home / "projects" / "kodpm_data"
    project_dir.mkdir(parents=True)
    (data / "digital-autoparts-env").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))
    write_project_files(project_dir, V2_WITH_SERVICES, build_user_settings("base"))
    return ProjectFiles(project_dir)


def test_parse_volume_keeps_source_placeholder():
    assert parse_volume("${@source:digital_autoparts_env}:/env") == (
        "${@source:digital_autoparts_env}",
        "/env",
    )
    assert parse_volume("./data/mailpit/data:/data") == ("./data/mailpit/data", "/data")


def test_parse_port_pair():
    assert parse_port_pair("8025:8025") == (8025, 8025)
    assert parse_port_pair("8510") == (8510, 8510)


def test_interpolate_service_and_source(tmp_path: Path, monkeypatch):
    project = _project_with_services(tmp_path, monkeypatch)
    release = "app"
    assert interpolate("http://${@service:odoo}:8069", project, release) == "http://app-odoo:8069"
    assert interpolate("${@service:db1}", project, release) == "app-db1"
    mapped = interpolate("${@source:digital_autoparts_env}", project, release)
    assert mapped.endswith("kodpm_data/digital-autoparts-env")
    assert mapped.startswith("/host-home/")


def test_extra_service_values_image_ports_env(tmp_path: Path, monkeypatch):
    project = _project_with_services(tmp_path, monkeypatch)
    services = {item["name"]: item for item in extra_service_values(project)}
    mailpit = services["mailpit"]
    assert mailpit["image"] == "axllent/mailpit"
    assert [port["containerPort"] for port in mailpit["ports"]] == [8025, 1025]
    assert [port["hostPort"] for port in mailpit["ports"]] == [8025, 1025]
    assert mailpit["env"]["MP_MAX_MESSAGES"] == "5000"
    assert mailpit["volumes"][0]["mountPath"] == "/data"
    assert mailpit["volumes"][0]["hostPath"].endswith("app/data/mailpit/data")
    express = services["expresspay-test"]
    assert express["env"]["ODOO_BASE_URL"] == "http://app-odoo:8069"
    assert express["env"]["DB_HOST"] == "app-db1"
    assert express["command"] == ["bash", "-c", "python3 /env/main.py"]
    assert express["volumes"][0]["hostPath"].startswith("/host-home/")
    assert "digital-autoparts-env" in express["volumes"][0]["hostPath"]
    assert "${@source" not in express["volumes"][0]["hostPath"]
    assert express["volumes"][0]["mountPath"] == "/env"
    assert "outside" in services
    assert services["outside"]["volumes"] == []


def test_extra_service_warnings(tmp_path: Path, monkeypatch):
    project = _project_with_services(tmp_path, monkeypatch)
    warnings = extra_service_warnings(project)
    assert not any("пропущены (docker)" in item for item in warnings)
    assert any("outside" in item and "$HOME" in item for item in warnings)


def test_service_source_repos(tmp_path: Path, monkeypatch):
    project = _project_with_services(tmp_path, monkeypatch)
    repos = service_source_repos(project)
    assert repos[0]["name"] == "digital-autoparts-env"
    assert repos[0]["url"].endswith("digital-autoparts-env.git")
    assert repos[0]["branch"] == ""


def test_build_values_skips_extra_services(tmp_path: Path, monkeypatch):
    project = _project_with_services(tmp_path, monkeypatch)
    values = build_values(project, "local", extra_services=False)
    assert values["extraServices"] == []


@pytest.mark.skipif(__import__("shutil").which("helm") is None, reason="helm not installed")
def test_helm_template_extra_service(tmp_path: Path, monkeypatch):
    import subprocess

    from kodpm.paths import chart_dir

    project = _project_with_services(tmp_path, monkeypatch)
    values = build_values(project, "local", db_name="odoo")
    extras = {item["name"]: item for item in values["extraServices"]}
    assert extras["mailpit"]["image"] == "axllent/mailpit"
    assert extras["expresspay-test"]["env"]["ODOO_BASE_URL"] == "http://app-odoo:8069"
    values_file = dump_values(values, tmp_path / "values.yaml")
    result = subprocess.run(
        [
            "helm",
            "template",
            release_name(project),
            str(chart_dir()),
            "--namespace",
            "kodpm",
            "-f",
            str(values_file),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    docs = [doc for doc in yaml.safe_load_all(result.stdout) if doc]
    names = {doc["metadata"]["name"] for doc in docs}
    assert "app-mailpit" in names
    assert "app-expresspay-test" in names
    mailpit = next(
        doc
        for doc in docs
        if doc.get("kind") == "Deployment" and doc["metadata"]["name"] == "app-mailpit"
    )
    container = mailpit["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "axllent/mailpit"
    assert {port["containerPort"] for port in container["ports"]} == {8025, 1025}
    env = {item["name"]: item["value"] for item in container["env"]}
    assert env["MP_MAX_MESSAGES"] == "5000"
    svc = next(
        doc
        for doc in docs
        if doc.get("kind") == "Service" and doc["metadata"]["name"] == "app-mailpit"
    )
    assert {port["port"] for port in svc["spec"]["ports"]} == {8025, 1025}
    express = next(
        doc
        for doc in docs
        if doc.get("kind") == "Deployment" and doc["metadata"]["name"] == "app-expresspay-test"
    )
    express_env = {
        item["name"]: item["value"] for item in express["spec"]["template"]["spec"]["containers"][0]["env"]
    }
    assert express_env["ODOO_BASE_URL"] == "http://app-odoo:8069"
