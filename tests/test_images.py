from pathlib import Path

from kodpm.images import (
    collect_up_images,
    extra_service_images,
    images_from_docker_hooks,
    node_has_image,
)
from kodpm.initproj import build_user_settings, write_project_files
from kodpm.project import ProjectFiles
from kodpm.values import build_values

from tests.test_extraservices import V2_WITH_SERVICES


def test_images_from_docker_inspect_and_pull():
    images, leftover = images_from_docker_hooks(
        [
            ["docker", "image", "inspect", "autoparts_env:emulator"],
            ["docker", "pull", "axllent/mailpit"],
            ["docker", "compose", "build"],
        ]
    )
    assert images == ["autoparts_env:emulator", "axllent/mailpit"]
    assert leftover == [["docker", "compose", "build"]]


def test_collect_up_images_includes_hooks_and_core(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    data = home / "projects" / "kodpm_data"
    project_dir.mkdir(parents=True)
    (data / "digital-autoparts-env").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))
    write_project_files(project_dir, V2_WITH_SERVICES, build_user_settings("base"))
    project = ProjectFiles(project_dir)
    values = build_values(project, "local")
    images, leftover = collect_up_images(project, values, extras=True)
    assert leftover == []
    assert "odoo:17" in images
    assert "autoparts_env:emulator" in images
    assert "axllent/mailpit" in images
    assert "adminer" in images
    core_only, _ = collect_up_images(project, values, extras=False)
    assert "autoparts_env:emulator" not in core_only
    assert "odoo:17" in core_only


def test_extra_service_images(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    data = home / "projects" / "kodpm_data"
    project_dir.mkdir(parents=True)
    (data / "digital-autoparts-env").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))
    write_project_files(project_dir, V2_WITH_SERVICES, build_user_settings("base"))
    images = extra_service_images(ProjectFiles(project_dir))
    assert "autoparts_env:emulator" in images


def test_node_has_image_parses_crictl(monkeypatch):
    class Result:
        returncode = 0
        stdout = (
            "IMAGE                          TAG      IMAGE ID   SIZE\n"
            "docker.io/library/odoo         17       abc        1GB\n"
        )

    monkeypatch.setattr("kodpm.images.run", lambda *args, **kwargs: Result())
    assert node_has_image("k3d-kodpm-server-0", "odoo:17")
    assert not node_has_image("k3d-kodpm-server-0", "postgres:13")
