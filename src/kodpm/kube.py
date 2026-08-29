from __future__ import annotations

from kodpm.proc import run


def kubectl(*args: str, check: bool = True, capture: bool = False, input_text: str | None = None):
    return run(["kubectl", *args], check=check, capture=capture, input_text=input_text)


def apply_yaml(manifest: str, namespace: str) -> None:
    kubectl("apply", "-n", namespace, "-f", "-", input_text=manifest)


def delete_job(name: str, namespace: str) -> None:
    kubectl("delete", "job", name, "-n", namespace, "--ignore-not-found", check=False)


def wait_job(name: str, namespace: str, timeout: str = "15m") -> None:
    kubectl("wait", "--for=condition=complete", f"job/{name}", "-n", namespace, f"--timeout={timeout}")


def scale_odoo(fullname: str, namespace: str, replicas: int) -> None:
    kubectl(
        "scale",
        "deploy",
        f"{fullname}-odoo",
        "-n",
        namespace,
        f"--replicas={replicas}",
    )
    if replicas > 0:
        kubectl(
            "rollout",
            "status",
            f"deploy/{fullname}-odoo",
            "-n",
            namespace,
            "--timeout=180s",
            check=False,
        )


def rollout_odoo(fullname: str, namespace: str) -> None:
    kubectl("rollout", "restart", f"deploy/{fullname}-odoo", "-n", namespace)
    kubectl("rollout", "status", f"deploy/{fullname}-odoo", "-n", namespace, "--timeout=180s", check=False)


def exec_in(resource: str, namespace: str, *cmd: str, check: bool = True, capture: bool = False):
    return kubectl("exec", resource, "-n", namespace, "--", *cmd, check=check, capture=capture)


def current_context() -> str:
    result = kubectl("config", "current-context", capture=True, check=False)
    return (result.stdout or "").strip()
