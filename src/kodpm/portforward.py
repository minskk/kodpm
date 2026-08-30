from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from kodpm.kube import run_while_showing_progress
from kodpm.proc import run, which
from kodpm.project import ProjectFiles
from kodpm.secrets import kodpm_dir

WAIT_TIMEOUT_SEC = 300
FORWARD_RETRIES = 8
FORWARD_RETRY_SEC = 3


def forwards_dir(project: ProjectFiles) -> Path:
    return kodpm_dir(project) / "port-forwards"


def extra_forward_specs(release: str, extras: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for item in extras:
        name = str(item.get("name") or "")
        svc = f"{release}-{name}"
        ports = list(item.get("ports") or [])
        if not ports:
            ports = [{"containerPort": 80, "hostPort": 80}]
        maps: list[tuple[int, int]] = []
        for port in ports:
            container = int(port.get("containerPort") or 80)
            host = int(port.get("hostPort") or container)
            maps.append((host, container))
        specs.append({"name": name, "service": svc, "maps": maps})
    return specs


def stop_extra_port_forwards(project: ProjectFiles) -> None:
    dest = forwards_dir(project)
    if not dest.is_dir():
        return
    for pid_path in dest.glob("*.pid"):
        raw = pid_path.read_text(encoding="utf-8").strip()
        try:
            pid = int(raw)
        except ValueError:
            pid_path.unlink(missing_ok=True)
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        pid_path.unlink(missing_ok=True)


def wait_extra_deployments(
    namespace: str,
    release: str,
    extras: list[dict[str, Any]],
    *,
    timeout: int = WAIT_TIMEOUT_SEC,
    log: Callable[[str], None],
) -> bool:
    names = [f"deploy/{release}-{item.get('name')}" for item in extras if item.get("name")]
    if not names:
        return True
    log(f"  ожидание extra-сервисов ({len(names)}, до {timeout}s); прогресс каждые ~15 с")

    def _wait():
        return run(
            [
                "kubectl",
                "wait",
                *names,
                "-n",
                namespace,
                "--for=condition=available",
                f"--timeout={timeout}s",
            ],
            check=False,
            capture=True,
        )

    result = run_while_showing_progress(
        _wait,
        namespace=namespace,
        release=release,
        log=log,
        include_logs=False,
        hide_prefixes=(f"{release}-odoo", f"{release}-postgres", f"{release}-minio"),
    )
    if result.returncode != 0:
        log("  не все extra-сервисы Ready — пробуем port-forward по тем, что уже бегут")
        return False
    return True


def start_extra_port_forwards(
    project: ProjectFiles,
    namespace: str,
    release: str,
    extras: list[dict[str, Any]],
    *,
    log: Callable[[str], None] = print,
) -> list[dict[str, Any]]:
    """Wait for extra Deployments, then background kubectl port-forward on 127.0.0.1."""
    which("kubectl")
    stop_extra_port_forwards(project)
    dest = forwards_dir(project)
    dest.mkdir(parents=True, exist_ok=True)
    wait_extra_deployments(namespace, release, extras, log=log)
    started: list[dict[str, Any]] = []
    for spec in extra_forward_specs(release, extras):
        mappings = [f"{host}:{container}" for host, container in spec["maps"]]
        svc = spec["service"]
        log_path = dest / f"{svc}.log"
        pid_path = dest / f"{svc}.pid"
        proc = None
        for attempt in range(1, FORWARD_RETRIES + 1):
            with log_path.open("w", encoding="utf-8") as log_fh:
                proc = subprocess.Popen(
                    [
                        "kubectl",
                        "port-forward",
                        "-n",
                        namespace,
                        f"svc/{svc}",
                        *mappings,
                        "--address=127.0.0.1",
                    ],
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            time.sleep(0.4)
            if proc.poll() is None:
                break
            if attempt < FORWARD_RETRIES:
                time.sleep(FORWARD_RETRY_SEC)
        if proc is None or proc.poll() is not None:
            tail = log_path.read_text(encoding="utf-8")[-400:] if log_path.is_file() else ""
            log(f"  {svc} не открылся: {tail.strip() or 'port-forward exited'}")
            continue
        pid_path.write_text(f"{proc.pid}\n", encoding="utf-8")
        urls = [f"127.0.0.1:{host}" for host, _container in spec["maps"]]
        spec["urls"] = urls
        started.append(spec)
        log(f"  {', '.join(urls)} → svc/{svc}")
    for line in extra_launch_summary_lines(
        extras,
        started,
        extra_pod_status(namespace, release, extras),
    ):
        log(line)
    return started


def parse_extra_pod_status(doc: dict[str, Any], names: list[str]) -> dict[str, dict[str, Any]]:
    rows = {name: {"ready": False, "reason": "нет пода"} for name in names}
    for item in doc.get("items") or []:
        labels = (item.get("metadata") or {}).get("labels") or {}
        component = str(labels.get("app.kubernetes.io/component") or "")
        if not component.startswith("extra-"):
            continue
        name = component.removeprefix("extra-")
        if name not in rows:
            continue
        status = item.get("status") or {}
        ready = any(
            cond.get("type") == "Ready" and cond.get("status") == "True"
            for cond in status.get("conditions") or []
        )
        reason = str(status.get("phase") or "?")
        for container in status.get("containerStatuses") or []:
            state = container.get("state") or {}
            waiting = state.get("waiting") or {}
            terminated = state.get("terminated") or {}
            if waiting.get("reason"):
                reason = str(waiting["reason"])
            elif terminated.get("reason"):
                reason = str(terminated["reason"])
        rows[name] = {"ready": ready, "reason": "Running" if ready else reason}
    return rows


def extra_pod_status(
    namespace: str,
    release: str,
    extras: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    names = [str(item.get("name")) for item in extras if item.get("name")]
    if not names:
        return {}
    result = run(
        [
            "kubectl",
            "get",
            "pods",
            "-n",
            namespace,
            "-l",
            f"app.kubernetes.io/instance={release}",
            "-o",
            "json",
        ],
        check=False,
        capture=True,
    )
    try:
        doc = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        doc = {}
    if not isinstance(doc, dict):
        doc = {}
    return parse_extra_pod_status(doc, names)


def extra_launch_summary_lines(
    extras: list[dict[str, Any]],
    started: list[dict[str, Any]],
    statuses: dict[str, dict[str, Any]],
) -> list[str]:
    names = [str(item.get("name")) for item in extras if item.get("name")]
    if not names:
        return []
    started_names = {str(item.get("name")) for item in started}
    ready_names = [name for name in names if (statuses.get(name) or {}).get("ready")]
    lines = [
        f"Итог extra: {len(names)} сервисов, поды Ready {len(ready_names)}/{len(names)}, "
        f"port-forward {len(started_names)}/{len(names)}"
    ]
    for name in names:
        status = statuses.get(name) or {}
        if status.get("ready") and name in started_names:
            continue
        reason = status.get("reason") or "нет пода"
        port = "порт открыт" if name in started_names else "без порта"
        if status.get("ready"):
            lines.append(f"  {name}: Ready, {port}")
        else:
            lines.append(f"  {name}: {reason}, {port}")
    return lines
