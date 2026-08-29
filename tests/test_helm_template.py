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
