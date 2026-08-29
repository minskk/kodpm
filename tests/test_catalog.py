from kodpm.catalog import get_platform, get_version, load_platforms, load_versions, normalize_odoo_version


def test_all_series_present():
    versions = load_versions()
    for major in range(10, 20):
        assert f"{major}.0" in versions


def test_normalize():
    assert normalize_odoo_version("17") == "17.0"
    assert normalize_odoo_version("17.0") == "17.0"
    assert normalize_odoo_version("17,0") == "17.0"
    assert normalize_odoo_version(" 17,0 ") == "17.0"


def test_get_version_accepts_comma():
    assert get_version("17,0").key == "17.0"


def test_version_17():
    spec = get_version("17.0")
    assert spec.postgres == "14"
    assert spec.image == "odoo:17"
    assert spec.probes["type"] == "http"


def test_version_10_tcp_probe():
    spec = get_version("10")
    assert spec.python == "2.7"
    assert spec.probes["type"] == "tcp"
    assert spec.http_option == "xmlrpc_port"


def test_platforms():
    platforms = load_platforms()
    assert "odoo" in platforms
    assert "fincomtech" in platforms
    fin = get_platform("fincomtech")
    assert fin["conf_name"] == "fincomtech.conf"
    assert fin["platform_name"] == "fincomtech"
