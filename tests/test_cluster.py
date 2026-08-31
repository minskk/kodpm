from kodpm.cluster import cluster_running, ensure_cluster
from kodpm.proc import ToolError


def test_cluster_running_uses_docker_ps(monkeypatch):
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = "k3d-kodpm-server-0\n"

    monkeypatch.setattr(
        "kodpm.cluster.run",
        lambda args, **kwargs: calls.append(list(args)) or Result(),
    )
    assert cluster_running("kodpm") is True
    assert calls[0][:2] == ["docker", "ps"]
    assert "-a" not in calls[0]


def test_ensure_cluster_starts_when_stopped(monkeypatch):
    logs: list[str] = []
    started: list[str] = []
    monkeypatch.setattr("kodpm.cluster.cluster_exists", lambda name="kodpm": True)
    monkeypatch.setattr("kodpm.cluster.cluster_running", lambda name="kodpm": name in started)
    monkeypatch.setattr("kodpm.cluster.start_cluster", lambda name="kodpm": started.append(name))
    ensure_cluster(log=logs.append)
    assert started == ["kodpm"]
    assert any("остановлен" in line for line in logs)


def test_ensure_cluster_missing(monkeypatch):
    monkeypatch.setattr("kodpm.cluster.cluster_exists", lambda name="kodpm": False)
    try:
        ensure_cluster(log=lambda _msg: None)
    except ToolError as exc:
        assert "cluster init" in str(exc)
    else:
        raise AssertionError("expected ToolError")
