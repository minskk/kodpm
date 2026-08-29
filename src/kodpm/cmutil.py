from __future__ import annotations

import json
from typing import Any

from kodpm.kube import kubectl


def get_configmap_data(name: str, namespace: str) -> dict[str, str]:
    result = kubectl("get", "configmap", name, "-n", namespace, "-o", "json", capture=True)
    payload = json.loads(result.stdout or "{}")
    data = payload.get("data") or {}
    return {str(k): str(v) for k, v in data.items()}


def apply_configmap_data(name: str, namespace: str, data: dict[str, str]) -> None:
    payload = json.dumps({"data": data})
    kubectl("patch", "configmap", name, "-n", namespace, "--type", "merge", "-p", payload)
