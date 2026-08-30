from pathlib import Path

import pytest

from kodpm.hostpip import (
    STAMP_NAME,
    install_host_pip,
    pip_packages_dir,
    requirement_lines,
    requirements_stamp,
)
from kodpm.initproj import build_kodpm_json, build_user_settings, write_project_files
from kodpm.proc import ToolError
from kodpm.project import ProjectFiles
from kodpm.values import build_values


def test_requirement_lines_skips_comments():
    text = "# odpm.json digital-autoparts\nemail_validator==2.3.0\n\nhttpx==0.26.0\n"
    assert requirement_lines(text, "") == ["email_validator==2.3.0", "httpx==0.26.0"]


def test_local_values_set_pip_hostpath(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    write_project_files(project_dir, build_kodpm_json("17.0", "odoo", []), build_user_settings("base"))
    monkeypatch.setattr(
        "kodpm.values.python_requirements_values",
        lambda _project: {
            "enabled": True,
            "project": "httpx==0.26.0\n",
            "odoo": "",
            "hostPath": "",
        },
    )
    values = build_values(ProjectFiles(project_dir), "local")
    assert values["pythonRequirements"]["enabled"] is True
    assert values["pythonRequirements"]["hostPath"].endswith(".kodpm/pip-packages")
    assert values["pythonRequirements"]["hostPath"].startswith("/host-home/")


def test_install_host_pip_docker_and_stamp(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "app"
    write_project_files(project_dir, build_kodpm_json("17.0", "odoo", []), build_user_settings("base"))
    project = ProjectFiles(project_dir)
    values = {
        "image": {"repository": "odoo", "tag": "17"},
        "pythonRequirements": {
            "enabled": True,
            "project": "httpx==0.26.0\naiohttp==3.9.1\n",
            "odoo": "",
        },
    }
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("kodpm.hostpip.run", fake_run)
    dest = install_host_pip(project, values, log=lambda _msg: None)
    assert dest == pip_packages_dir(project)
    docker = next(item for item in calls if item[:2] == ["docker", "run"])
    assert "--network" in docker and "host" in docker
    assert any(item.startswith("HOST_UID=") for item in docker)
    assert any(item.startswith("HOST_GID=") for item in docker)
    assert "chmod" in docker[docker.index("-c") + 1]
    assert "chown" in docker[docker.index("-c") + 1]
    assert "httpx==0.26.0" in docker
    assert "aiohttp==3.9.1" in docker
    assert docker.index("httpx==0.26.0") < docker.index("aiohttp==3.9.1")
    assert not any(item[:1] == ["chmod"] for item in calls)
    stamp = dest / STAMP_NAME
    assert stamp.read_text(encoding="utf-8").strip() == requirements_stamp(
        "odoo:17", ["httpx==0.26.0", "aiohttp==3.9.1"]
    )
    calls.clear()
    install_host_pip(project, values, log=lambda _msg: None)
    assert not any(item[:2] == ["docker", "run"] for item in calls)


def test_install_host_pip_stops_on_error(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "app"
    write_project_files(project_dir, build_kodpm_json("17.0", "odoo", []), build_user_settings("base"))
    project = ProjectFiles(project_dir)
    values = {
        "image": {"repository": "odoo", "tag": "17"},
        "pythonRequirements": {"enabled": True, "project": "httpx==0.26.0\n", "odoo": ""},
    }

    def fake_run(args, **kwargs):
        class Result:
            returncode = 1

        return Result()

    monkeypatch.setattr("kodpm.hostpip.run", fake_run)
    with pytest.raises(ToolError, match="FAILED"):
        install_host_pip(project, values, log=lambda _msg: None)
    assert not (pip_packages_dir(project) / STAMP_NAME).exists()
