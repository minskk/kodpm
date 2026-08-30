from pathlib import Path

import yaml
from click.testing import CliRunner

from kodpm.cli import cli
from kodpm.jobs import render_job
from kodpm.project import ProjectFiles
from kodpm.values import build_values


def _demo_values():
    return build_values(ProjectFiles(Path("examples/demo-17")), "local", db_name="odoo")


def test_render_backup_job():
    values = _demo_values()
    manifest = render_job(
        "backup",
        values,
        job_name="demo-17-backup-1",
        namespace="kodpm",
        release="demo-17",
        db_name="odoo",
        dump_name="odoo-test",
    )
    docs = list(yaml.safe_load_all(manifest))
    assert docs[0]["kind"] == "Job"
    assert docs[0]["spec"]["template"]["spec"]["initContainers"][0]["name"] == "dump"
    upload = docs[0]["spec"]["template"]["spec"]["containers"][0]
    assert upload["image"].startswith("quay.io/minio/mc:")


def test_render_modules_job():
    values = _demo_values()
    manifest = render_job(
        "update",
        values,
        job_name="demo-17-mods-up-1",
        namespace="kodpm",
        release="demo-17",
        db_name="odoo",
        modules="sale,crm",
    )
    job = yaml.safe_load(manifest)
    container = job["spec"]["template"]["spec"]["containers"][0]
    assert container["command"] == ["sh", "/scripts/modules.sh"]
    env = {item["name"]: item.get("value") for item in container["env"]}
    assert env["MODULES"] == "sale,crm"
    assert env["MODULE_ACTION"] == "update"
    password = next(item for item in container["env"] if item["name"] == "PASSWORD")
    assert password["valueFrom"]["secretKeyRef"]["key"] == "db-password"


def test_render_modules_job_pip_req():
    values = _demo_values()
    values["pythonRequirements"] = {
        "enabled": True,
        "project": "openupgradelib==3.7.0\n",
        "odoo": "freezegun==1.2.2\n",
    }
    manifest = render_job(
        "install",
        values,
        job_name="demo-17-mods-in-1",
        namespace="kodpm",
        release="demo-17",
        db_name="odoo",
        modules="base",
    )
    job = yaml.safe_load(manifest)
    spec = job["spec"]["template"]["spec"]
    assert spec["initContainers"][0]["name"] == "pip-req"
    env = {item["name"]: item.get("value") for item in spec["containers"][0]["env"]}
    assert env["PYTHONPATH"] == "/usr/lib/python3/dist-packages:/pip-packages"
    vol_names = {vol["name"] for vol in spec["volumes"]}
    assert "pip-packages" in vol_names
    assert "python-req" in vol_names


def test_render_modules_job_host_pip():
    values = _demo_values()
    values["pythonRequirements"] = {
        "enabled": True,
        "project": "httpx==0.26.0\n",
        "odoo": "",
        "hostPath": "/host-home/projects/app/.kodpm/pip-packages",
    }
    manifest = render_job(
        "install",
        values,
        job_name="demo-17-mods-in-1",
        namespace="kodpm",
        release="demo-17",
        db_name="odoo",
        modules="base",
    )
    job = yaml.safe_load(manifest)
    spec = job["spec"]["template"]["spec"]
    assert not spec.get("initContainers")
    env = {item["name"]: item.get("value") for item in spec["containers"][0]["env"]}
    assert env["PYTHONPATH"] == "/usr/lib/python3/dist-packages:/pip-packages"
    pip_vol = next(vol for vol in spec["volumes"] if vol["name"] == "pip-packages")
    assert pip_vol["hostPath"]["path"] == "/host-home/projects/app/.kodpm/pip-packages"


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "up" in result.output


def test_cli_values_demo():
    runner = CliRunner()
    result = runner.invoke(cli, ["--project-dir", "examples/demo-17", "values"])
    assert result.exit_code == 0, result.output
    parsed = yaml.safe_load(result.output)
    assert parsed["odooVersion"] == "17.0"


def test_up_help_accepts_profile():
    runner = CliRunner()
    result = runner.invoke(cli, ["up", "--help"])
    assert result.exit_code == 0
    assert "--profile" in result.output


def test_values_profile_after_subcommand():
    runner = CliRunner()
    result = runner.invoke(cli, ["--project-dir", "examples/demo-17", "values", "--profile", "dev"])
    assert result.exit_code == 0, result.output
    parsed = yaml.safe_load(result.output)
    assert parsed["odooVersion"] == "17.0"
    assert parsed["kodpm"]["profile"] == "dev"
    assert parsed["kodpm"]["namespace"] == "kodpm-dev"
