from __future__ import annotations

import os
from pathlib import Path

_SENTINEL = Path("catalogs") / "versions.yaml"


def kodpm_home() -> Path:
    env = os.environ.get("KODPM_HOME")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent.parent,  # repo root (editable install: src/kodpm)
        here / "share",  # packaged wheel
        here.parent,
        Path.cwd(),
        *list(Path.cwd().parents)[:6],
    ]
    for candidate in candidates:
        if (candidate / _SENTINEL).exists():
            return candidate
        share = candidate / "share"
        if (share / _SENTINEL).exists():
            return share
    raise FileNotFoundError(
        "Cannot find kodpm catalogs (catalogs/versions.yaml). "
        "Run from the kodpm repo or set KODPM_HOME."
    )


def chart_dir() -> Path:
    return kodpm_home() / "charts" / "odoo-instance"


def catalogs_dir() -> Path:
    return kodpm_home() / "catalogs"


def profiles_dir() -> Path:
    return kodpm_home() / "profiles"


def templates_dir() -> Path:
    pkg = Path(__file__).resolve().parent / "templates"
    if pkg.exists():
        return pkg
    return kodpm_home() / "src" / "kodpm" / "templates"
