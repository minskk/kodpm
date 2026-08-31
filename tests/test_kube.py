from io import StringIO
from types import SimpleNamespace

from kodpm.kube import (
    _filter_pod_table,
    _replace_progress_block,
    core_workloads_ready,
    delete_release_jobs,
    run_while_showing_progress,
    scale_odoo,
)


def test_delete_release_jobs_targets_module_actions(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_kubectl(*args: str, **kwargs):
        calls.append(args)
        return None

    monkeypatch.setattr("kodpm.kube.kubectl", fake_kubectl)
    delete_release_jobs("kodpm", "kodpm-autoparts")
    selectors = [call[call.index("-l") + 1] for call in calls]
    assert "app.kubernetes.io/instance=kodpm-autoparts,kodpm.io/job=install" in selectors
    assert "app.kubernetes.io/instance=kodpm-autoparts,kodpm.io/job=update" in selectors
    assert all("--wait=true" in call for call in calls)


def test_scale_odoo_waits_when_scaled_to_zero(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_kubectl(*args: str, **kwargs):
        calls.append(args)
        return None

    monkeypatch.setattr("kodpm.kube.kubectl", fake_kubectl)
    scale_odoo("kodpm-autoparts", "kodpm", 0)
    assert calls[0][:3] == ("scale", "deploy", "kodpm-autoparts-odoo")
    assert "--replicas=0" in calls[0]
    assert calls[1][:2] == ("rollout", "status")


def test_run_while_showing_progress_skips_first_snapshot(monkeypatch):
    gets: list[int] = []

    def fake_kubectl(*args: str, **kwargs):
        if args[:2] == ("get", "pods"):
            gets.append(1)
        return SimpleNamespace(stdout="NAME READY\napp-odoo-1 1/1\n", stderr="")

    monkeypatch.setattr("kodpm.kube.kubectl", fake_kubectl)
    run_while_showing_progress(
        lambda: None,
        namespace="kodpm",
        release="app",
        log=lambda _msg: None,
        interval=0.01,
        tty=False,
        include_logs=False,
    )
    assert gets == [1]


def test_run_while_showing_progress_prints_pods(monkeypatch):
    lines: list[str] = []

    def fake_kubectl(*args: str, **kwargs):
        if args[:2] == ("get", "pods"):
            return SimpleNamespace(stdout="NAME READY STATUS\nkodpm-autoparts-odoo-1 0/1 Init:0/2\n", stderr="")
        return SimpleNamespace(stdout="pip install httpx\n", stderr="")

    monkeypatch.setattr("kodpm.kube.kubectl", fake_kubectl)
    run_while_showing_progress(
        lambda: None,
        namespace="kodpm",
        release="kodpm-autoparts",
        log=lines.append,
        interval=0.01,
        tty=False,
    )
    assert any("kodpm-autoparts-odoo" in line for line in lines)
    assert any("pip install" in line for line in lines)


def test_run_while_showing_progress_can_skip_logs(monkeypatch):
    lines: list[str] = []
    log_calls: list[tuple[str, ...]] = []

    def fake_kubectl(*args: str, **kwargs):
        if args[:2] == ("logs",):
            log_calls.append(args)
        if args[:2] == ("get", "pods"):
            return SimpleNamespace(stdout="NAME READY STATUS\napp-mailpit-1 0/1 Pending\n", stderr="")
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr("kodpm.kube.kubectl", fake_kubectl)
    run_while_showing_progress(
        lambda: None,
        namespace="kodpm",
        release="app",
        log=lines.append,
        interval=0.01,
        tty=False,
        include_logs=False,
    )
    assert any("app-mailpit" in line for line in lines)
    assert not log_calls


def test_filter_pod_table_hides_core():
    table = (
        "NAME READY STATUS\n"
        "app-odoo-1 1/1 Running\n"
        "app-postgres-0 1/1 Running\n"
        "app-minio-1 1/1 Running\n"
        "app-mailpit-1 0/1 ContainerCreating\n"
    )
    filtered = _filter_pod_table(table, ("app-odoo", "app-postgres", "app-minio"))
    assert "mailpit" in filtered
    assert "odoo" not in filtered
    assert "postgres" not in filtered
    assert "minio" not in filtered


def test_core_workloads_ready():
    ready = (
        "NAME READY STATUS\n"
        "app-odoo-1 1/1 Running\n"
        "app-postgres-0 1/1 Running\n"
        "app-minio-1 1/1 Running\n"
        "app-mailpit-1 0/1 ContainerCreating\n"
    )
    assert core_workloads_ready(ready, "app") is True
    starting = (
        "NAME READY STATUS\n"
        "app-odoo-1 0/1 Init:0/2\n"
        "app-postgres-0 1/1 Running\n"
        "app-minio-1 1/1 Running\n"
    )
    assert core_workloads_ready(starting, "app") is False
    no_minio = (
        "NAME READY STATUS\n"
        "app-odoo-1 1/1 Running\n"
        "app-postgres-0 1/1 Running\n"
    )
    assert core_workloads_ready(no_minio, "app") is True


def test_run_while_showing_progress_skips_when_core_ready(monkeypatch):
    lines: list[str] = []

    def fake_kubectl(*args: str, **kwargs):
        if args[:2] == ("get", "pods"):
            return SimpleNamespace(
                stdout=(
                    "NAME READY STATUS\n"
                    "app-odoo-1 1/1 Running\n"
                    "app-postgres-0 1/1 Running\n"
                    "app-minio-1 1/1 Running\n"
                    "app-mailpit-1 0/1 Pending\n"
                ),
                stderr="",
            )
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr("kodpm.kube.kubectl", fake_kubectl)
    run_while_showing_progress(
        lambda: None,
        namespace="kodpm",
        release="app",
        log=lines.append,
        interval=0.01,
        tty=False,
        skip_when_core_ready=True,
    )
    assert lines == []


def test_replace_progress_block_overwrites():
    stream = StringIO()
    first = _replace_progress_block("line-a\nline-b", 0, stream)
    assert first == 2
    assert stream.getvalue().endswith("line-a\nline-b\n")
    _replace_progress_block("only", 2, stream)
    assert "\033[1A\033[2K" in stream.getvalue()
    assert stream.getvalue().endswith("only\n")
