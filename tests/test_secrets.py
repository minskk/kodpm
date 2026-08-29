from pathlib import Path

from kodpm.initproj import build_kodpm_json, build_user_settings, write_project_files
from kodpm.project import ProjectFiles
from kodpm.secrets import (
    build_secret_xml,
    prepare_addon_secrets,
    write_json,
    write_secret_xml_files,
)


def test_build_secret_xml_laximo():
    xml = build_secret_xml(
        "partner_laximo",
        [
            {"partner_xml_id": "laximo", "param": "apipassword", "value": "secret"},
            {"partner_xml_id": "laximo", "param": "apilogin", "value": "user"},
        ],
    )
    assert 'id="res_partner_params_values_apilogin"' in xml
    assert 'ref="partner_laximo.laximo"' in xml
    assert ">user<" in xml
    assert ">secret<" in xml


def test_prepare_writes_stub_secret_xml(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    data = home / "projects" / "kodpm_data"
    addon = data / "digital-autoparts-17.0-dev"
    module = addon / "partner_laximo"
    project_dir.mkdir(parents=True)
    (module / "data").mkdir(parents=True)
    (module / "__manifest__.py").write_text(
        '{"data": ["data/laximo.xml", "data/secret.xml"]}\n',
        encoding="utf-8",
    )
    (addon / "odpm.json").write_text(
        '{"odoo_version":"17.0","scenarios":{"developer":{"secrets":{"required":true,'
        '"keys":["partner_laximo.laximo.apilogin","partner_laximo.laximo.apipassword"]}}}}\n',
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
    result = prepare_addon_secrets(ProjectFiles(project_dir))
    secret = module / "data" / "secret.xml"
    assert secret.is_file()
    assert "<odoo" in secret.read_text(encoding="utf-8")
    assert (project_dir / ".kodpm" / "secrets.example.json").is_file()
    assert (project_dir / ".kodpm" / "runtime" / "secrets.json").is_file()
    assert result["enabled"] is True
    assert result["hostPath"].endswith(".kodpm/runtime/secrets.json")


def test_write_secret_xml_from_values(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "app"
    data = home / "projects" / "kodpm_data"
    addon = data / "digital-autoparts-17.0-dev"
    module = addon / "partner_laximo"
    project_dir.mkdir(parents=True)
    (module / "data").mkdir(parents=True)
    (module / "__manifest__.py").write_text(
        '{"data": ["data/secret.xml"]}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))
    write_project_files(
        project_dir,
        build_kodpm_json(
            "17.0",
            "odoo",
            ["git@github.com:digital-autoparts/digital-autoparts.git 17.0-dev"],
            addons_branch="17.0-dev",
        ),
        build_user_settings("base"),
    )
    write_json(
        project_dir / ".kodpm" / "secrets.json",
        {
            "schema_version": 1,
            "secrets": {
                "partner_laximo.laximo.apilogin": "ru1",
                "partner_laximo.laximo.apipassword": "pw1",
            },
        },
    )
    written = write_secret_xml_files(
        ProjectFiles(project_dir),
        {
            "partner_laximo.laximo.apilogin": "ru1",
            "partner_laximo.laximo.apipassword": "pw1",
        },
    )
    text = written[0].read_text(encoding="utf-8")
    assert ">ru1<" in text
    assert ">pw1<" in text
