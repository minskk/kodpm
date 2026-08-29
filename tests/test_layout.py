from pathlib import Path

from kodpm.initproj import build_odpm_json, build_user_settings, write_project_files
from kodpm.iniutil import get_ini_option, set_ini_option
from kodpm.layout import compose_conf, render_conf_from_values, sync_project_layout
from kodpm.project import ProjectFiles
from kodpm.values import build_values


def test_conf_name_for_platforms(tmp_path: Path):
    write_project_files(tmp_path, build_odpm_json("17.0", "odoo", []), build_user_settings("base"))
    assert ProjectFiles(tmp_path).conf_name == "odoo.conf"
    write_project_files(
        tmp_path,
        build_odpm_json("17.0", "fincomtech", [], image="registry.example.com/fincomtech:17"),
        build_user_settings("base"),
    )
    assert ProjectFiles(tmp_path).conf_name == "fincomtech.conf"


def test_sync_layout_writes_files(tmp_path: Path):
    write_project_files(tmp_path, build_odpm_json("17.0", "odoo", []), build_user_settings("base"))
    project = ProjectFiles(tmp_path)
    values = build_values(project, "local")
    sync_project_layout(project, values)
    assert project.values_local_path.is_file()
    assert project.conf_path.is_file()
    assert "workers" in project.conf_path.read_text(encoding="utf-8")


def test_compose_keeps_user_option(tmp_path: Path):
    write_project_files(tmp_path, build_odoo_json(), build_user_settings("base"))
    project = ProjectFiles(tmp_path)
    values = build_values(project, "local")
    project.conf_path.write_text(
        set_ini_option(render_conf_from_values(values), "workers", "4"),
        encoding="utf-8",
    )
    raw = compose_conf(project, values)
    assert get_ini_option(raw, "workers") == "4"
    assert get_ini_option(raw, "db_host") == f"{values['fullnameOverride']}-postgres"


def build_odoo_json():
    return build_odpm_json("17.0", "odoo", [])
