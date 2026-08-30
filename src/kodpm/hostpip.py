from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Callable

from kodpm.proc import ToolError, run
from kodpm.project import ProjectFiles
from kodpm.secrets import kodpm_dir

STAMP_NAME = ".kodpm-requirements.sha256"

_INSTALLER = """
import os
import subprocess
import sys

dest = "/pip-packages"
for req in sys.argv[1:]:
    print(f"pip: {req}", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--target", dest, req]
    )
    if result.returncode != 0:
        print(f"pip: FAILED {req} — stop", flush=True)
        sys.exit(1)
    print(f"pip: ok {req}", flush=True)
subprocess.run(["chmod", "-R", "a+rX", dest], check=True)
uid = os.environ.get("HOST_UID", "0")
gid = os.environ.get("HOST_GID", "0")
subprocess.run(["chown", "-R", f"{uid}:{gid}", dest], check=True)
"""


def pip_packages_dir(project: ProjectFiles) -> Path:
    return kodpm_dir(project) / "pip-packages"


def requirement_lines(*texts: str | None) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for raw in str(text or "").splitlines():
            item = raw.strip()
            if not item or item.startswith("#") or item in seen:
                continue
            seen.add(item)
            lines.append(item)
    return lines


def requirements_stamp(image: str, lines: list[str]) -> str:
    body = image + "\n" + "\n".join(lines) + "\n"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def odoo_image_of(values: dict[str, Any]) -> str:
    image = values.get("image") or {}
    repo = str(image.get("repository") or "odoo")
    tag = str(image.get("tag") or "17")
    return f"{repo}:{tag}"


def install_host_pip(
    project: ProjectFiles,
    values: dict[str, Any],
    *,
    log: Callable[[str], None] = print,
) -> Path | None:
    """Install project pip deps on the host via the Odoo image (host DNS)."""
    reqs = values.get("pythonRequirements") or {}
    if not reqs.get("enabled"):
        return None
    lines = requirement_lines(reqs.get("project"), reqs.get("odoo"))
    if not lines:
        return None
    dest = pip_packages_dir(project)
    dest.mkdir(parents=True, exist_ok=True)
    image = odoo_image_of(values)
    stamp = requirements_stamp(image, lines)
    stamp_path = dest / STAMP_NAME
    if stamp_path.is_file() and stamp_path.read_text(encoding="utf-8").strip() == stamp:
        _fix_host_ownership(dest, image, log=log)
        log(f"pip: host packages already installed ({dest})")
        return dest
    log(f"pip: install {len(lines)} packages on host via {image} → {dest}")
    result = run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "--user",
            "0",
            "-e",
            f"HOST_UID={os.getuid()}",
            "-e",
            f"HOST_GID={os.getgid()}",
            "-v",
            f"{dest.resolve()}:/pip-packages",
            image,
            "python3",
            "-c",
            _INSTALLER,
            *lines,
        ],
        check=False,
    )
    if result.returncode != 0:
        raise ToolError(
            f"pip: FAILED — host install stopped. Packages go to {dest}. "
            f"Image {image}."
        )
    stamp_path.write_text(stamp + "\n", encoding="utf-8")
    log(f"pip: host packages ready ({dest})")
    return dest


def _tree_owned_by_user(dest: Path) -> bool:
    uid = os.getuid()
    try:
        if dest.stat().st_uid != uid:
            return False
        for child in dest.iterdir():
            if child.stat().st_uid != uid:
                return False
            break
    except OSError:
        return False
    return True


def _fix_host_ownership(
    dest: Path,
    image: str,
    *,
    log: Callable[[str], None],
) -> None:
    if _tree_owned_by_user(dest):
        return
    log(f"pip: fix ownership of {dest}")
    run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            "0",
            "-e",
            f"HOST_UID={os.getuid()}",
            "-e",
            f"HOST_GID={os.getgid()}",
            "-v",
            f"{dest.resolve()}:/pip-packages",
            image,
            "sh",
            "-c",
            'chmod -R a+rX /pip-packages && chown -R "${HOST_UID}:${HOST_GID}" /pip-packages',
        ],
        check=False,
    )
