from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Sequence


class ToolError(RuntimeError):
    pass


def which(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ToolError(f"Required executable {name!r} not found in PATH")
    return path


def run(
    args: Sequence[str],
    *,
    check: bool = True,
    capture: bool = False,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    which(args[0])
    result = subprocess.run(
        list(args),
        check=False,
        text=True,
        capture_output=capture,
        input=input_text,
        env=env,
    )
    if check and result.returncode != 0:
        stderr = result.stderr or result.stdout or ""
        raise ToolError(f"Command failed ({result.returncode}): {' '.join(args)}\n{stderr}")
    return result
