from __future__ import annotations

from pathlib import Path

from kodpm.paths import chart_dir
from kodpm.proc import run


def helm_upgrade(
    release: str,
    namespace: str,
    values_file: Path,
    *,
    wait: bool = True,
    timeout: str = "10m",
) -> None:
    args = [
        "helm",
        "upgrade",
        "--install",
        release,
        str(chart_dir()),
        "--namespace",
        namespace,
        "--create-namespace",
        "-f",
        str(values_file),
        "--timeout",
        timeout,
    ]
    if wait:
        args.append("--wait")
    run(args)


def helm_uninstall(release: str, namespace: str) -> None:
    run(["helm", "uninstall", release, "--namespace", namespace], check=False)


def helm_template(release: str, namespace: str, values_file: Path) -> str:
    result = run(
        [
            "helm",
            "template",
            release,
            str(chart_dir()),
            "--namespace",
            namespace,
            "-f",
            str(values_file),
        ],
        capture=True,
    )
    return result.stdout or ""


def helm_status(release: str, namespace: str) -> str:
    result = run(
        ["helm", "status", release, "--namespace", namespace],
        capture=True,
        check=False,
    )
    return (result.stdout or result.stderr or "").strip()
