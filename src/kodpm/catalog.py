from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from kodpm.paths import catalogs_dir


@dataclass(frozen=True)
class VersionSpec:
    key: str
    python: str
    postgres: str
    image: str
    bin: str
    conf_path: str
    data_dir: str
    extra_addons: str
    http_option: str
    longpolling_option: str
    probes: dict[str, Any]
    distro: str
    distro_version: str
    raw: dict[str, Any]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_versions() -> dict[str, dict[str, Any]]:
    return _load_yaml(catalogs_dir() / "versions.yaml")


def load_platforms() -> dict[str, dict[str, Any]]:
    return _load_yaml(catalogs_dir() / "platforms.yaml")


def normalize_odoo_version(version: str) -> str:
    text = str(version).strip().replace(" ", "").replace(",", ".")
    if text.isdigit():
        return f"{text}.0"
    if text.endswith(".") and text[:-1].isdigit():
        return f"{text}0"
    return text


def known_version_keys() -> list[str]:
    return sorted(load_versions().keys(), key=lambda v: float(v.replace(".0", "")))


def resolve_odoo_version(version: str) -> str:
    key = normalize_odoo_version(version)
    versions = load_versions()
    if key not in versions:
        known = ", ".join(known_version_keys())
        raise KeyError(
            f"Неизвестная версия {version!r} (нормализовано как {key!r}). "
            f"Допустимы: {known}"
        )
    return key


def get_version(version: str) -> VersionSpec:
    key = resolve_odoo_version(version)
    versions = load_versions()
    raw = versions[key]
    return VersionSpec(
        key=key,
        python=str(raw["python"]),
        postgres=str(raw["postgres"]),
        image=str(raw["image"]),
        bin=str(raw.get("bin", "odoo")),
        conf_path=str(raw.get("conf_path", "/etc/odoo/odoo.conf")),
        data_dir=str(raw.get("data_dir", "/var/lib/odoo")),
        extra_addons=str(raw.get("extra_addons", "/mnt/extra-addons")),
        http_option=str(raw.get("http_option", "http_port")),
        longpolling_option=str(raw.get("longpolling_option", "longpolling_port")),
        probes=dict(raw.get("probes") or {"type": "tcp"}),
        distro=str(raw.get("distro", "debian")),
        distro_version=str(raw.get("distro_version", "12")),
        raw=raw,
    )


def get_platform(name: str) -> dict[str, Any]:
    platforms = load_platforms()
    key = (name or "odoo").strip().lower()
    if key not in platforms:
        known = ", ".join(sorted(platforms))
        raise KeyError(f"Unknown platform {name!r}. Known: {known}")
    return platforms[key]
