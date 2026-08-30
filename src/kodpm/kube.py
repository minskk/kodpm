from __future__ import annotations

import sys
import threading
import time
from typing import Any, Callable

from kodpm.proc import run


def kubectl(*args: str, check: bool = True, capture: bool = False, input_text: str | None = None):
    return run(["kubectl", *args], check=check, capture=capture, input_text=input_text)


def apply_yaml(manifest: str, namespace: str) -> None:
    kubectl("apply", "-n", namespace, "-f", "-", input_text=manifest)


def delete_job(name: str, namespace: str) -> None:
    kubectl("delete", "job", name, "-n", namespace, "--ignore-not-found", "--wait=true", check=False)


def delete_jobs_by_labels(namespace: str, labels: dict[str, str]) -> None:
    selector = ",".join(f"{key}={value}" for key, value in labels.items())
    kubectl(
        "delete",
        "job",
        "-n",
        namespace,
        "-l",
        selector,
        "--ignore-not-found",
        "--wait=true",
        check=False,
    )


def delete_release_jobs(namespace: str, release: str, actions: tuple[str, ...] = ("install", "update")) -> None:
    """Stop leftover module Jobs so they cannot write the same DB as a new Job or the Odoo pod."""
    for action in actions:
        delete_jobs_by_labels(
            namespace,
            {
                "app.kubernetes.io/instance": release,
                "kodpm.io/job": action,
            },
        )


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


def pods_status(namespace: str, release: str) -> str:
    result = kubectl(
        "get",
        "pods",
        "-n",
        namespace,
        "-l",
        f"app.kubernetes.io/instance={release}",
        capture=True,
        check=False,
    )
    return (result.stdout or "").strip()


def odoo_container_tail(namespace: str, release: str, container: str, *, tail: int = 8) -> str:
    result = kubectl(
        "logs",
        "-n",
        namespace,
        "-l",
        f"app.kubernetes.io/instance={release},app.kubernetes.io/component=odoo",
        "-c",
        container,
        f"--tail={tail}",
        capture=True,
        check=False,
    )
    return (result.stdout or "").strip()


def follow_job_logs(job_name: str, namespace: str, container: str = "modules") -> None:
    """Attach to Job logs; retry until the container exists."""
    for _ in range(60):
        result = kubectl(
            "logs",
            "-f",
            f"job/{job_name}",
            "-n",
            namespace,
            "-c",
            container,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(2)


def _progress_block(pods: str, container: str, snippet: str) -> str:
    parts = [pods] if pods else ["(поды ещё не созданы)"]
    if snippet:
        parts.append(f"--- {container} ---")
        parts.append(snippet)
    return "\n".join(parts)


def _replace_progress_block(text: str, prev_lines: int, stream) -> int:
    """Overwrite the previous multi-line progress block in a TTY."""
    lines = text.splitlines() or [""]
    if prev_lines:
        stream.write("\033[1A\033[2K" * prev_lines)
    stream.write("\n".join(lines) + "\n")
    stream.flush()
    return len(lines)


def run_while_showing_progress(
    work: Callable[[], Any],
    *,
    namespace: str,
    release: str,
    log: Callable[[str], None] = print,
    interval: float = 15,
    tty: bool | None = None,
) -> Any:
    """Run `work` and print pod / init-container progress until it finishes.

    On a TTY the progress block is redrawn in place; otherwise new snapshots append.
    """
    done = threading.Event()
    box: dict[str, Any] = {}
    use_tty = sys.stderr.isatty() if tty is None else tty
    stream = sys.stderr

    def runner() -> None:
        try:
            box["result"] = work()
        except BaseException as exc:
            box["error"] = exc
        finally:
            done.set()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    last_text = ""
    printed_lines = 0

    def snapshot() -> None:
        nonlocal last_text, printed_lines
        table = pods_status(namespace, release)
        container = ""
        snippet = ""
        for name in ("wait-postgres", "pip-req", "odoo"):
            snippet = odoo_container_tail(namespace, release, name)
            if snippet:
                container = name
                break
        text = _progress_block(table, container, snippet)
        if use_tty:
            printed_lines = _replace_progress_block(text, printed_lines, stream)
            last_text = text
            return
        if text != last_text:
            log(text)
            last_text = text

    snapshot()
    while not done.wait(interval):
        snapshot()
    snapshot()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("result")
