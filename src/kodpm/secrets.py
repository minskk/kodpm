from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from kodpm.project import ProjectFiles, load_json
from kodpm.sources import addon_odpm_path, cache_dirname, collect_addon_repos, default_data_dir

SECRETS_SCHEMA_VERSION = 1
SECRET_KEY_RE = re.compile(
    r"^(?P<module>partner_[a-z0-9_]+)\.(?P<partner>[a-z0-9_]+)\.(?P<param>apilogin|apipassword)$"
)
PARAM_REFS = {
    "apilogin": "partner_params.res_partner_params_apilogin",
    "apipassword": "partner_params.res_partner_params_apipassword",
}
EMPTY_SECRET_XML = "<?xml version='1.0' encoding='utf-8'?>\n<odoo noupdate=\"0\"/>\n"


def kodpm_dir(project: ProjectFiles) -> Path:
    return project.project_dir / ".kodpm"


def secrets_source_path(project: ProjectFiles) -> Path | None:
    for path in (
        kodpm_dir(project) / "secrets.json",
        project.project_dir / ".odpm" / "secrets.json",
    ):
        if path.is_file():
            return path
    return None


def secrets_runtime_path(project: ProjectFiles) -> Path:
    return kodpm_dir(project) / "runtime" / "secrets.json"


def secrets_example_path(project: ProjectFiles) -> Path:
    return kodpm_dir(project) / "secrets.example.json"


def parse_secrets_payload(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    raw = data.get("secrets")
    if not isinstance(raw, dict):
        return {}
    secrets: dict[str, str] = {}
    for key, value in raw.items():
        if str(key).strip() and isinstance(value, str):
            secrets[str(key)] = value
    return secrets


def load_project_secrets(project: ProjectFiles) -> dict[str, str]:
    path = secrets_source_path(project)
    if not path:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parse_secrets_payload(data)


def required_secret_keys(project: ProjectFiles) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for repo in collect_addon_repos(project):
        name = str(repo["name"])
        branch = str(repo.get("branch") or project.addons_branch)
        path = addon_odpm_path(project, name, branch)
        if not path:
            continue
        data = load_json(path)
        if not data:
            continue
        for key in _keys_from_addon_odpm(data):
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def _keys_from_addon_odpm(data: dict[str, Any]) -> list[str]:
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, dict):
        return []
    chosen: Any = None
    for key in ("developer", "local", "dev"):
        item = scenarios.get(key)
        if isinstance(item, dict) and isinstance(item.get("secrets"), dict):
            chosen = item.get("secrets")
            break
    if chosen is None:
        for item in scenarios.values():
            if isinstance(item, dict) and isinstance(item.get("secrets"), dict):
                chosen = item.get("secrets")
                break
    if not isinstance(chosen, dict):
        return []
    raw = chosen.get("keys")
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _normalize_payload(secrets: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": SECRETS_SCHEMA_VERSION,
        "secrets": dict(sorted(secrets.items())),
    }


def write_json(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, mode)


def ensure_kodpm_gitignore(project: ProjectFiles) -> None:
    path = kodpm_dir(project) / ".gitignore"
    entries = ["secrets.json", "runtime/"]
    existing = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    merged = list(existing)
    for entry in entries:
        if entry not in merged:
            merged.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(merged) + "\n", encoding="utf-8")


def write_secrets_example(project: ProjectFiles, keys: list[str]) -> Path:
    path = secrets_example_path(project)
    payload = _normalize_payload({key: "" for key in keys})
    write_json(path, payload, mode=0o644)
    return path


def materialize_runtime_secrets(project: ProjectFiles, secrets: dict[str, str]) -> Path:
    path = secrets_runtime_path(project)
    write_json(path, _normalize_payload(secrets))
    return path


def _partner_ref(module_name: str, partner_xml_id: str) -> str:
    default_partner = module_name.removeprefix("partner_")
    if partner_xml_id == default_partner:
        return f"{module_name}.{partner_xml_id}"
    if partner_xml_id.startswith("balhim_"):
        return f"balhim.{partner_xml_id}"
    return f"{module_name}.{partner_xml_id}"


def _record_id(partner_xml_id: str, module_name: str, param: str) -> str:
    default_partner = module_name.removeprefix("partner_")
    base = f"res_partner_params_values_{param}"
    if partner_xml_id == default_partner:
        return base
    if partner_xml_id.startswith("balhim_"):
        return f"{base}_{partner_xml_id.removeprefix('balhim_')}"
    return f"{base}_{partner_xml_id}"


def build_secret_xml(module_name: str, records: list[dict[str, str]]) -> str:
    if not records:
        return EMPTY_SECRET_XML
    lines = ["<?xml version='1.0' encoding='utf-8'?>", '<odoo noupdate="0">']
    for record in sorted(
        records,
        key=lambda item: (item["partner_xml_id"], 0 if item["param"] == "apilogin" else 1),
    ):
        lines.extend(
            [
                f'  <record id="{_record_id(record["partner_xml_id"], module_name, record["param"])}" '
                f'model="res.partner.params.values">',
                f'    <field name="name">{escape(record["value"])}</field>',
                f'    <field name="partner_id" ref="{_partner_ref(module_name, record["partner_xml_id"])}"/>',
                f'    <field name="param_id" ref="{PARAM_REFS[record["param"]]}"/>',
                "  </record>",
            ]
        )
    lines.append("</odoo>")
    return "\n".join(lines) + "\n"


def _group_partner_secrets(secrets: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for key, value in secrets.items():
        match = SECRET_KEY_RE.match(key)
        if not match:
            continue
        module_name = match.group("module")
        grouped.setdefault(module_name, []).append(
            {
                "partner_xml_id": match.group("partner"),
                "param": match.group("param"),
                "value": value,
            }
        )
    return grouped


def addon_clone_dirs(project: ProjectFiles) -> list[Path]:
    dirs: list[Path] = []
    seen: set[Path] = set()
    for repo in collect_addon_repos(project):
        dest = default_data_dir() / cache_dirname(
            str(repo["name"]),
            str(repo.get("branch") or project.addons_branch),
        )
        for path in (dest, project.project_dir / str(repo["name"])):
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen or not path.is_dir():
                continue
            seen.add(resolved)
            dirs.append(resolved)
            break
    return dirs


def modules_needing_secret_xml(addon_root: Path) -> list[Path]:
    found: list[Path] = []
    for manifest in sorted(addon_root.glob("*/__manifest__.py")):
        try:
            text = manifest.read_text(encoding="utf-8")
        except OSError:
            continue
        if "data/secret.xml" in text:
            found.append(manifest.parent)
    return found


def write_secret_xml_files(project: ProjectFiles, secrets: dict[str, str]) -> list[Path]:
    grouped = _group_partner_secrets(secrets)
    written: list[Path] = []
    for addon_root in addon_clone_dirs(project):
        for module_dir in modules_needing_secret_xml(addon_root):
            dest = module_dir / "data" / "secret.xml"
            records = grouped.get(module_dir.name) or []
            if dest.is_file() and not records:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(build_secret_xml(module_dir.name, records), encoding="utf-8")
            written.append(dest)
    return written


def prepare_addon_secrets(project: ProjectFiles, *, log=None) -> dict[str, Any]:
    """Materialize ODPM-compatible secrets and generate gitignored secret.xml files."""
    echo = log or (lambda *_args, **_kwargs: None)
    keys = required_secret_keys(project)
    if keys:
        write_secrets_example(project, keys)
    secrets = load_project_secrets(project)
    ensure_kodpm_gitignore(project)
    runtime = materialize_runtime_secrets(project, secrets)
    written = write_secret_xml_files(project, secrets)
    missing = [key for key in keys if not str(secrets.get(key) or "").strip()]
    if keys and not secrets:
        echo(
            "Нет .kodpm/secrets.json (или .odpm/secrets.json). "
            f"Скопируйте шаблон: cp {secrets_example_path(project)} {kodpm_dir(project) / 'secrets.json'}"
        )
    elif missing:
        echo(f"В secrets.json нет значений для: {', '.join(missing)}")
    if written:
        echo(f"Секреты: записано {len(written)} secret.xml, runtime {runtime}")
    from kodpm.values import host_home_path

    mapped = host_home_path(runtime)
    return {
        "enabled": bool(mapped),
        "hostPath": mapped or "",
        "missing": missing,
        "written": [str(path) for path in written],
    }
