from types import SimpleNamespace

from kodpm.kube import delete_release_jobs, run_while_showing_progress, scale_odoo


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
    )
    assert any("kodpm-autoparts-odoo" in line for line in lines)
    assert any("pip install" in line for line in lines)
