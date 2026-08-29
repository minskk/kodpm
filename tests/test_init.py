import json
from pathlib import Path

from click.testing import CliRunner

from kodpm.cli import cli
from kodpm.initproj import (
    build_odpm_json,
    build_user_settings,
    normalize_addon_links,
    normalize_platform,
    write_project_files,
    write_requirements_txt,
)
from kodpm.project import ProjectFiles


def test_normalize_addon_links_dedupe_and_default_branch():
    links = normalize_addon_links(
        [
            "git@github.com:digital-autoparts/digital-autoparts.git",
            "https://github.com/digital-autoparts/digital-autoparts.git",
        ],
        "17.0",
    )
    assert len(links) == 1
    assert links[0].endswith(" 17.0")
    assert "digital-autoparts.git" in links[0]


def test_normalize_foncomtech_alias():
    assert normalize_platform("foncomtech") == "fincomtech"
    assert normalize_platform("Fincomtech") == "fincomtech"


def test_build_odpm_with_addons():
    data = build_odpm_json(
        "17.0",
        "odoo",
        ["https://github.com/OCA/web.git 17.0"],
    )
    assert data["odoo_version"] == "17.0"
    assert data["platform_name"] == "odoo"
    assert data["python_version"] == "3.10"
    assert data["dependencies"][0]["name"] == "web"
    assert data["dependencies"][0]["branch"] == "17.0"


def test_build_fincomtech():
    data = build_odpm_json(
        "17",
        "fincomtech",
        [],
        image="registry.example.com/fincomtech:17.0",
        odoo_git_link="git@example.com:org/fincomtech.git 17.0",
    )
    assert data["platform_name"] == "fincomtech"
    assert data["image"].endswith("fincomtech:17.0")


def test_init_command_writes_files(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project-dir",
            str(tmp_path),
            "init",
            "--odoo-version",
            "17.0",
            "--platform",
            "odoo",
            "--addon",
            "https://github.com/OCA/web.git 17.0",
            "--modules",
            "base,web,my_module",
            "--db-lang",
            "ru_RU",
            "--admin-password",
            "secret",
            "--no-up",
            "--no-clone",
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    odpm = json.loads((tmp_path / "odpm.json").read_text(encoding="utf-8"))
    settings = json.loads((tmp_path / "user_settings.json").read_text(encoding="utf-8"))
    assert odpm["odoo_version"] == "17.0"
    assert odpm["dependencies"][0]["url"].endswith("web.git")
    assert settings["init_modules"] == "base,web,my_module"
    assert settings["db_manager_password"] == "secret"
    project = ProjectFiles(tmp_path)
    assert project.init_modules() == ["base", "web", "my_module"]
    assert (tmp_path / "odoo.conf").is_file()
    assert (tmp_path / "values.local.yaml").is_file()
    assert (tmp_path / "requirements.txt").is_file()
    assert (tmp_path / "requirements.txt").read_text(encoding="utf-8") == ""
    conf = (tmp_path / "odoo.conf").read_text(encoding="utf-8")
    assert "data_dir =" in conf
    assert conf.lower().count("data_dir") == 1
    assert "addons_path =" in conf


def test_init_accepts_comma_version(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project-dir",
            str(tmp_path),
            "init",
            "--odoo-version",
            "17,0",
            "--platform",
            "odoo",
            "--modules",
            "base",
            "--db-lang",
            "ru_RU",
            "--admin-password",
            "admin",
            "--no-up",
            "--no-clone",
            "--yes",
        ],
        input="готово\n",
    )
    assert result.exit_code == 0, result.output
    odpm = json.loads((tmp_path / "odpm.json").read_text(encoding="utf-8"))
    assert odpm["odoo_version"] == "17.0"


def test_user_settings_builder():
    settings = build_user_settings("base, web")
    assert settings["init_modules"] == "base,web"
    assert settings["db_creation_data"]["db_lang"] == "ru_RU"


def test_write_requirements_txt_keeps_existing(tmp_path: Path):
    existing = tmp_path / "requirements.txt"
    existing.write_text("openupgradelib==3.7.0\n", encoding="utf-8")
    write_project_files(tmp_path, build_odpm_json("17.0", "odoo", []), build_user_settings("base"))
    assert write_requirements_txt(tmp_path).read_text(encoding="utf-8") == "openupgradelib==3.7.0\n"
