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
