from pathlib import Path

from kodpm.sources import cache_dirname, ensure_symlink, relative_symlink_target


def test_cache_dirname():
    assert cache_dirname("odoo", "17.0") == "odoo-17.0"
    assert cache_dirname("OCA/web", "17.0") == "OCA-web-17.0"


def test_relative_symlink_under_projects(tmp_path: Path):
    data = tmp_path / "kodpm_data" / "odoo-17.0"
    data.mkdir(parents=True)
    (data / "marker").write_text("ok", encoding="utf-8")
    project = tmp_path / "kodpm_odoo_test"
    project.mkdir()
    link = project / "odoo"
    ensure_symlink(link, data)
    assert link.is_symlink()
    assert link.resolve() == data.resolve()
    assert relative_symlink_target(link, data) == Path("../kodpm_data/odoo-17.0")
    assert (link / "marker").read_text(encoding="utf-8") == "ok"
    ensure_symlink(link, data)
    assert link.resolve() == data.resolve()
