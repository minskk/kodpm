import json
from pathlib import Path

from click.testing import CliRunner

from kodpm.cli import cli
from kodpm.initproj import (
    build_kodpm_json,
    build_odpm_v2_json,
    build_user_settings,
    normalize_addon_links,
    normalize_platform,
    write_odpm_and_link,
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
    custom = normalize_addon_links(
        ["git@github.com:digital-autoparts/digital-autoparts.git"],
        "main",
    )
    assert custom[0].endswith(" main")


def test_normalize_foncomtech_alias():
    assert normalize_platform("foncomtech") == "fincomtech"
    assert normalize_platform("Fincomtech") == "fincomtech"


def test_build_odpm_with_addons():
    data = build_kodpm_json(
        "17.0",
        "odoo",
        ["https://github.com/OCA/web.git 17.0"],
    )
    assert data["odoo_version"] == "17.0"
    assert data["manifest_schema"] == 2
    assert data["python"] == "3.10"
    assert data["developing"]["git"].endswith("web.git")
    assert data["dependencies"] == []
    assert data["addons_branch"] == "17.0"
    custom = build_kodpm_json(
        "17.0",
        "odoo",
        ["https://github.com/OCA/web.git", "https://github.com/OCA/queue.git"],
        addons_branch="main",
    )
    assert custom["addons_branch"] == "main"
    assert custom["developing"]["git"].endswith("web.git")
    assert custom["dependencies"] == ["https://github.com/OCA/queue.git"]


def test_build_fincomtech():
    data = build_kodpm_json(
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
            "--addons-branch",
            "17.0",
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
    assert odpm["addons_branch"] == "17.0"
    assert odpm["developing"]["git"].endswith("web.git")
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
        input="готово\n\n",
    )
    assert result.exit_code == 0, result.output
    odpm = json.loads((tmp_path / "odpm.json").read_text(encoding="utf-8"))
    assert odpm["odoo_version"] == "17.0"
    assert odpm["addons_branch"] == "17.0"


def test_init_writes_custom_addons_branch(tmp_path: Path):
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
            "https://github.com/OCA/web.git",
            "--addons-branch",
            "main",
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
    )
    assert result.exit_code == 0, result.output
    odpm = json.loads((tmp_path / "odpm.json").read_text(encoding="utf-8"))
    assert odpm["addons_branch"] == "main"
    assert odpm["developing"]["git"].endswith("web.git")


def test_user_settings_builder():
    settings = build_user_settings("base, web")
    assert settings["init_modules"] == "base,web"
    assert settings["db_creation_data"]["db_lang"] == "ru_RU"


def test_legacy_odpm_json_is_read(tmp_path: Path):
    (tmp_path / "odpm.json").write_text(
        '{"odoo_version":"16.0","platform_name":"odoo","dependencies":[]}\n',
        encoding="utf-8",
    )
    assert ProjectFiles(tmp_path).odoo_version == "16.0"


def test_write_project_files_writes_odpm_json(tmp_path: Path):
    write_project_files(tmp_path, build_kodpm_json("17.0", "odoo", []), build_user_settings("base"))
    assert (tmp_path / "odpm.json").is_file()
    data = json.loads((tmp_path / "odpm.json").read_text(encoding="utf-8"))
    assert data["manifest_schema"] == 2


def test_build_odpm_v2_json_developing_and_deps():
    data = build_odpm_v2_json(
        "17.0",
        "odoo",
        "git@gitverse.ru:fincomtech/extra_module.git",
        ["https://github.com/OCA/queue", "https://github.com/OCA/web"],
        addons_branch="17.0-dev",
    )
    assert data["manifest_schema"] == 2
    assert data["developing"]["git"].endswith("extra_module.git")
    assert data["dependencies"] == ["https://github.com/OCA/queue", "https://github.com/OCA/web"]
    assert data["platform"]["git"].endswith("odoo.git")
    assert data["addons_branch"] == "17.0-dev"
    assert "services" in data["scenarios"]["developer"]


def test_write_odpm_and_link(tmp_path: Path):
    repo = tmp_path / "extra_module"
    repo.mkdir()
    write_odpm_and_link(tmp_path, "extra_module", build_kodpm_json("17.0", "odoo", []))
    link = tmp_path / "odpm.json"
    assert link.is_symlink()
    assert link.resolve() == (repo / "odpm.json").resolve()
    assert json.loads(link.read_text(encoding="utf-8"))["manifest_schema"] == 2


def test_init_flag_parses_url_vs_bare(monkeypatch):
    captured: list[dict] = []

    def fake_run_init(ctx, **kwargs):
        captured.append({"init_url": kwargs.get("init_url"), "addons_branch": kwargs.get("addons_branch")})

    monkeypatch.setattr("kodpm.cli.run_init", fake_run_init)
    runner = CliRunner()
    result = runner.invoke(cli, ["--init", "git@gitverse.ru:fincomtech/extra_module.git", "--branch", "17.0-dev"])
    assert result.exit_code == 0, result.output
    assert captured[-1]["init_url"] == "git@gitverse.ru:fincomtech/extra_module.git"
    assert captured[-1]["addons_branch"] == "17.0-dev"
    result = runner.invoke(cli, ["--init", "--skip-start"])
    assert result.exit_code == 0, result.output
    assert captured[-1]["init_url"] == ""


def test_init_from_repo_symlinks_existing_odpm(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "fincom_extra"
    data = home / "projects" / "kodpm_data"
    project_dir.mkdir(parents=True)
    dest = data / "extra_module-17.0-dev"
    dest.mkdir(parents=True)
    manifest = {
        "manifest_schema": 2,
        "odoo_version": "17.0",
        "platform": {"git": "https://github.com/odoo/odoo.git"},
        "developing": {"git": "git@gitverse.ru:fincomtech/extra_module.git"},
        "dependencies": ["https://github.com/OCA/queue"],
        "database": {"language": "ru_RU"},
    }
    (dest / "odpm.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))

    def fake_clone(url, dest_path, branch):
        dest_path.mkdir(parents=True, exist_ok=True)
        if not (dest_path / "odpm.json").is_file() and dest_path == dest:
            (dest_path / "odpm.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    monkeypatch.setattr("kodpm.cli.clone_or_update", fake_clone)
    monkeypatch.setattr("kodpm.sources.clone_or_update", fake_clone)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project-dir",
            str(project_dir),
            "--init",
            "git@gitverse.ru:fincomtech/extra_module.git",
            "--branch",
            "17.0-dev",
            "--skip-start",
        ],
    )
    assert result.exit_code == 0, result.output
    link = project_dir / "odpm.json"
    assert link.is_symlink()
    assert link.resolve() == (dest / "odpm.json").resolve()
    assert json.loads(link.read_text(encoding="utf-8"))["developing"]["git"].endswith("extra_module.git")
    assert "Версия ядра" not in result.output
    settings = json.loads((project_dir / "user_settings.json").read_text(encoding="utf-8"))
    assert settings["init_modules"] == "base,web"
    assert (project_dir / "extra_module").is_symlink()


def test_init_from_repo_prompts_init_modules(tmp_path: Path, monkeypatch):
    home = tmp_path / "user"
    project_dir = home / "projects" / "fincom_extra"
    data = home / "projects" / "kodpm_data"
    project_dir.mkdir(parents=True)
    dest = data / "extra_module-17.0-dev"
    dest.mkdir(parents=True)
    manifest = {
        "manifest_schema": 2,
        "odoo_version": "17.0",
        "platform": {"git": "https://github.com/odoo/odoo.git"},
        "developing": {"git": "git@gitverse.ru:fincomtech/extra_module.git"},
    }
    (dest / "odpm.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("KODPM_DATA_DIR", str(data.resolve()))
    monkeypatch.setattr("kodpm.cli.clone_or_update", lambda url, dest_path, branch: dest_path.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr("kodpm.sources.clone_or_update", lambda url, dest_path, branch: None)
    monkeypatch.setattr(
        "kodpm.cli._ask_init_modules",
        lambda modules, default="base,web": "sale,stock",
    )
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project-dir",
            str(project_dir),
            "--init",
            "git@gitverse.ru:fincomtech/extra_module.git",
            "--branch",
            "17.0-dev",
            "--skip-start",
        ],
    )
    assert result.exit_code == 0, result.output
    settings = json.loads((project_dir / "user_settings.json").read_text(encoding="utf-8"))
    assert settings["init_modules"] == "sale,stock"


def test_d_flag_without_up_prints_help(tmp_path: Path, monkeypatch):
    write_project_files(tmp_path, build_kodpm_json("17.0", "odoo", []), build_user_settings("base"))
    called: list[str] = []
    monkeypatch.setattr("kodpm.cli.perform_up", lambda ctx, **kwargs: called.append("up"))
    runner = CliRunner()
    result = runner.invoke(cli, ["--project-dir", str(tmp_path), "-d", "odoo"])
    assert result.exit_code == 0, result.output
    assert called == []
    assert "Usage:" in result.output


def test_up_command_runs_stack(tmp_path: Path, monkeypatch):
    write_project_files(tmp_path, build_kodpm_json("17.0", "odoo", []), build_user_settings("base"))
    called: list[str] = []
    monkeypatch.setattr("kodpm.cli.perform_up", lambda ctx, **kwargs: called.append("up"))
    monkeypatch.setattr("kodpm.cli._run_modules", lambda ctx, action, names: called.append(action))
    runner = CliRunner()
    result = runner.invoke(cli, ["--project-dir", str(tmp_path), "-d", "odoo", "up"])
    assert result.exit_code == 0, result.output
    assert called == ["up"]
    result = runner.invoke(cli, ["--project-dir", str(tmp_path), "-d", "odoo", "up", "-i"])
    assert result.exit_code == 0, result.output
    assert called[-2:] == ["up", "install"]


def test_no_extras_flag_on_up(tmp_path: Path, monkeypatch):
    write_project_files(tmp_path, build_kodpm_json("17.0", "odoo", []), build_user_settings("base"))
    seen: list[bool] = []

    def fake_up(ctx, **kwargs):
        seen.append(bool(ctx.obj.get("no_extras")))

    monkeypatch.setattr("kodpm.cli.perform_up", fake_up)
    runner = CliRunner()
    result = runner.invoke(cli, ["--project-dir", str(tmp_path), "--no-extras", "-d", "odoo", "up"])
    assert result.exit_code == 0, result.output
    assert seen == [True]
    result = runner.invoke(cli, ["--project-dir", str(tmp_path), "-d", "odoo", "up", "--no-extras"])
    assert result.exit_code == 0, result.output
    assert seen == [True, True]


def test_no_project_prints_help(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["--project-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
    assert "init" in result.output


def test_write_requirements_txt_keeps_existing(tmp_path: Path):
    existing = tmp_path / "requirements.txt"
    existing.write_text("openupgradelib==3.7.0\n", encoding="utf-8")
    write_project_files(tmp_path, build_kodpm_json("17.0", "odoo", []), build_user_settings("base"))
    assert write_requirements_txt(tmp_path).read_text(encoding="utf-8") == "openupgradelib==3.7.0\n"
