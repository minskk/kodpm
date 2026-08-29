import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from kodpm.paths import chart_dir
from kodpm.project import ProjectFiles
from kodpm.values import build_values, dump_values, release_name


@pytest.mark.skipif(not shutil.which("helm"), reason="helm not installed")
def test_helm_template_demo(tmp_path: Path):
    project = ProjectFiles(Path("examples/demo-17"))
    values = build_values(project, "local", db_name="odoo")
    values_file = dump_values(values, tmp_path / "values.yaml")
    result = subprocess.run(
        [
            "helm",
            "template",
            release_name(project),
            str(chart_dir()),
            "--namespace",
            "kodpm",
            "-f",
            str(values_file),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    docs = [doc for doc in yaml.safe_load_all(result.stdout) if doc]
    kinds = {doc["kind"] for doc in docs}
    assert "Deployment" in kinds
    assert "StatefulSet" in kinds
    assert "ConfigMap" in kinds
    assert "Secret" in kinds
    assert "Ingress" in kinds
    names = {doc["metadata"]["name"] for doc in docs}
    assert "demo-17-odoo" in names
    assert "demo-17-postgres" in names
    assert "demo-17-minio" in names
    assert "demo-17-minio-bucket" not in names
    odoo = next(
        doc
        for doc in docs
        if doc.get("kind") == "Deployment" and doc["metadata"]["name"] == "demo-17-odoo"
    )
    vol_names = {vol["name"] for vol in odoo["spec"]["template"]["spec"]["volumes"]}
    assert "host-home" not in vol_names
    assert not any(
        (doc.get("metadata") or {}).get("annotations", {}).get("helm.sh/hook")
        for doc in docs
    )

    conf = next(
        doc["data"]["odoo.conf"]
        for doc in docs
        if doc.get("kind") == "ConfigMap" and (doc.get("data") or {}).get("odoo.conf")
    )
    keys: list[str] = []
    for line in conf.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("[") or stripped.startswith(";") or stripped.startswith("#"):
            continue
        if "=" in stripped:
            keys.append(stripped.split("=", 1)[0].strip())
    assert keys, conf
    dupes = sorted({key for key in keys if keys.count(key) > 1})
    assert not dupes, f"duplicate odoo.conf options: {dupes}\n{conf}"
    odoo_spec = odoo["spec"]["template"]["spec"]
    assert "pip-req" in [item["name"] for item in odoo_spec.get("initContainers") or []]
    req_cm = next(
        doc
        for doc in docs
        if doc.get("kind") == "ConfigMap" and doc["metadata"]["name"] == "demo-17-python-req"
    )
    assert "odoo-requirements.txt" in req_cm["data"]


@pytest.mark.skipif(not shutil.which("helm"), reason="helm not installed")
def test_helm_template_pip_req(tmp_path: Path):
    project = ProjectFiles(Path("examples/demo-17"))
    values = build_values(project, "local", db_name="odoo")
    values["pythonRequirements"] = {
        "enabled": True,
        "project": "openupgradelib==3.7.0\n",
        "odoo": "freezegun==1.2.2\n",
    }
    values_file = dump_values(values, tmp_path / "values.yaml")
    result = subprocess.run(
        [
            "helm",
            "template",
            release_name(project),
            str(chart_dir()),
            "--namespace",
            "kodpm",
            "-f",
            str(values_file),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    docs = [doc for doc in yaml.safe_load_all(result.stdout) if doc]
    odoo = next(
        doc
        for doc in docs
        if doc.get("kind") == "Deployment" and doc["metadata"]["name"] == "demo-17-odoo"
    )
    spec = odoo["spec"]["template"]["spec"]
    init_names = [item["name"] for item in spec.get("initContainers") or []]
    assert "pip-req" in init_names
    env = {item["name"]: item.get("value") for item in spec["containers"][0]["env"]}
    assert env["PYTHONPATH"] == "/usr/lib/python3/dist-packages:/pip-packages"
    req_cm = next(
        doc
        for doc in docs
        if doc.get("kind") == "ConfigMap" and doc["metadata"]["name"] == "demo-17-python-req"
    )
    assert "openupgradelib==3.7.0" in req_cm["data"]["project-requirements.txt"]
    assert "freezegun==1.2.2" in req_cm["data"]["odoo-requirements.txt"]
    scripts = next(
        doc
        for doc in docs
        if doc.get("kind") == "ConfigMap" and "pip-req.sh" in (doc.get("data") or {})
    )
    assert "pip install --target" in scripts["data"]["pip-req.sh"]
    assert "--db_password=" in scripts["data"]["modules.sh"]
    assert "PASSWORD" in scripts["data"]["modules.sh"]
