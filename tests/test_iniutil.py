from kodpm.iniutil import get_ini_option, set_ini_option


def test_set_and_get():
    text = set_ini_option("[options]\nworkers = 0\n", "workers", "2")
    assert get_ini_option(text, "workers") == "2"


def test_add_missing_key():
    text = set_ini_option("[options]\nworkers = 0\n", "proxy_mode", "True")
    assert "proxy_mode = True" in text
