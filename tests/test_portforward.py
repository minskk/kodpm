from kodpm.portforward import extra_forward_specs, stop_extra_port_forwards, wait_extra_deployments
from kodpm.project import ProjectFiles


def test_extra_forward_specs_uses_host_port():
    specs = extra_forward_specs(
        "app",
        [
            {
                "name": "mailpit",
                "ports": [
                    {"containerPort": 8025, "hostPort": 8025},
                    {"containerPort": 1025, "hostPort": 1025},
                ],
            }
        ],
    )
    assert specs[0]["service"] == "app-mailpit"
    assert specs[0]["maps"] == [(8025, 8025), (1025, 1025)]


def test_stop_extra_port_forwards_missing_dir(tmp_path):
    stop_extra_port_forwards(ProjectFiles(tmp_path))


def test_wait_extra_deployments_one_kubectl(monkeypatch):
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = ""

    monkeypatch.setattr(
        "kodpm.portforward.run",
        lambda args, **kwargs: calls.append(list(args)) or Result(),
    )
    ok = wait_extra_deployments(
        "kodpm",
        "app",
        [{"name": "mailpit"}, {"name": "db1"}],
        log=lambda _msg: None,
    )
    assert ok is True
    assert calls[0][:3] == ["kubectl", "wait", "deploy/app-mailpit"]
    assert "deploy/app-db1" in calls[0]
