from kodpm.project import parse_dependencies, parse_git_link, parse_modules


def test_parse_modules_csv():
    assert parse_modules("base, web") == ["base", "web"]
    assert parse_modules(["sale", "crm"]) == ["sale", "crm"]


def test_parse_git_link():
    parsed = parse_git_link("https://github.com/OCA/web.git 17.0")
    assert parsed["name"] == "web"
    assert parsed["branch"] == "17.0"


def test_parse_dependencies_mixed():
    repos = parse_dependencies(
        [
            "https://github.com/OCA/server-tools.git 17.0",
            {"name": "web", "url": "https://github.com/OCA/web.git", "branch": "17.0"},
        ]
    )
    assert len(repos) == 2
    assert repos[0]["name"] == "server-tools"
    assert repos[1]["url"].endswith("web.git")
