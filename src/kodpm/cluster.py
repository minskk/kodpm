from __future__ import annotations

from pathlib import Path

from kodpm.proc import ToolError, run


DEFAULT_CLUSTER = "kodpm"


def cluster_exists(name: str = DEFAULT_CLUSTER) -> bool:
    import json

    result = run(["k3d", "cluster", "list", "-o", "json"], capture=True, check=False)
    if result.returncode == 0 and result.stdout:
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            return any(isinstance(item, dict) and item.get("name") == name for item in data)
    text = run(["k3d", "cluster", "list"], capture=True, check=False).stdout or ""
    for line in text.splitlines()[1:]:
        if line.split()[:1] == [name]:
            return True
    return False


def init_cluster(
    name: str = DEFAULT_CLUSTER,
    *,
    host_home: Path | None = None,
    api_port: str = "6550",
) -> None:
    if cluster_exists(name):
        return
    host_home = (host_home or Path.home()).resolve()
    args = [
        "k3d",
        "cluster",
        "create",
        name,
        "--api-port",
        api_port,
        "-p",
        "80:80@loadbalancer",
        "-p",
        "443:443@loadbalancer",
        "--kubeconfig-update-default",
        "--kubeconfig-switch-context",
        "--volume",
        f"{host_home}:/host-home@all",
    ]
    run(args)


def delete_cluster(name: str = DEFAULT_CLUSTER) -> None:
    if not cluster_exists(name):
        return
    run(["k3d", "cluster", "delete", name])


def require_k3d() -> None:
    try:
        run(["k3d", "version"], capture=True)
    except ToolError as exc:
        raise ToolError(
            "k3d is required for local cluster init. Install: https://k3d.io/"
        ) from exc
