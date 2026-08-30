from kodpm.portforward import (
    extra_forward_specs,
    extra_launch_summary_lines,
    parse_extra_pod_status,
    stop_extra_port_forwards,
    wait_extra_deployments,
)
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
        "kodpm.portforward.run_while_showing_progress",
        lambda work, **kwargs: work(),
    )
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


def test_parse_extra_pod_status_ready_and_waiting():
    doc = {
        "items": [
            {
                "metadata": {"labels": {"app.kubernetes.io/component": "odoo"}},
                "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}]},
            },
            {
                "metadata": {"labels": {"app.kubernetes.io/component": "extra-mailpit"}},
                "status": {
                    "phase": "Running",
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "containerStatuses": [{"state": {"running": {}}}],
                },
            },
            {
                "metadata": {"labels": {"app.kubernetes.io/component": "extra-expresspay-test"}},
                "status": {
                    "phase": "Pending",
                    "conditions": [{"type": "Ready", "status": "False"}],
                    "containerStatuses": [
                        {"state": {"waiting": {"reason": "ImagePullBackOff"}}}
                    ],
                },
            },
        ]
    }
    rows = parse_extra_pod_status(doc, ["mailpit", "expresspay-test", "db1"])
    assert rows["mailpit"]["ready"] is True
    assert rows["expresspay-test"]["ready"] is False
    assert rows["expresspay-test"]["reason"] == "ImagePullBackOff"
    assert rows["db1"]["reason"] == "нет пода"


def test_extra_launch_summary_lists_not_ready():
    lines = extra_launch_summary_lines(
        [{"name": "mailpit"}, {"name": "db1"}, {"name": "expresspay-test"}],
        [{"name": "mailpit"}, {"name": "db1"}, {"name": "expresspay-test"}],
        {
            "mailpit": {"ready": True, "reason": "Running"},
            "db1": {"ready": True, "reason": "Running"},
            "expresspay-test": {"ready": False, "reason": "ImagePullBackOff"},
        },
    )
    assert lines[0] == "Итог extra: 3 сервисов, поды Ready 2/3, port-forward 3/3"
    assert lines[1] == "  expresspay-test: ImagePullBackOff, порт открыт"
