from __future__ import annotations

import re


def set_ini_option(content: str, key: str, value: str, section: str = "options") -> str:
    lines = content.splitlines()
    if not lines:
        lines = [f"[{section}]"]
    section_header = f"[{section}]"
    in_section = False
    found = False
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section and not found:
                out.append(f"{key} = {value}")
                found = True
            in_section = stripped.lower() == section_header.lower()
            out.append(line)
            continue
        if in_section and pattern.match(line):
            out.append(f"{key} = {value}")
            found = True
            continue
        out.append(line)
    if not found:
        if not any(line.strip().lower() == section_header.lower() for line in out):
            out.insert(0, section_header)
        out.append(f"{key} = {value}")
    return "\n".join(out) + "\n"


def get_ini_option(content: str, key: str) -> str | None:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.*)$")
    for line in content.splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return None
