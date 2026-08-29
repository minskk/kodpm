from kodpm.kube import delete_release_jobs, scale_odoo


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
