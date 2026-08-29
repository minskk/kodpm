from __future__ import annotations

import os
from pathlib import Path

from kodpm.catalog import get_platform
from kodpm.proc import ToolError, run
from kodpm.project import ProjectFiles, parse_git_link


def default_data_dir() -> Path:
    env = os.environ.get("KODPM_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / "projects" / "kodpm_data").resolve()


def cache_dirname(name: str, branch: str) -> str:
    safe_name = "".join(ch if ch.isalnum() or ch in "-._" else "-" for ch in name)
    safe_branch = "".join(ch if ch.isalnum() or ch in "-._" else "-" for ch in branch)
    return f"{safe_name}-{safe_branch}"


def relative_symlink_target(link: Path, target: Path) -> Path:
    return Path(os.path.relpath(target.resolve(), start=link.parent.resolve()))


def ensure_symlink(link: Path, target: Path) -> None:
    target = target.resolve()
    dest = relative_symlink_target(link, target)
    if link.is_symlink():
        if Path(os.path.normpath(link.parent / link.readlink())) == target or link.resolve() == target:
            return
        link.unlink()
    elif link.exists():
        raise ToolError(f"{link} already exists and is not a symlink")
    link.symlink_to(dest, target_is_directory=True)


def ensure_readable_tree(path: Path) -> None:
    """Make a clone readable for the Odoo container (uid 101)."""
    if not path.exists():
        return
    for root, dirs, files in os.walk(path):
        try:
            os.chmod(root, 0o755)
        except OSError:
            pass
        for name in files:
            try:
                os.chmod(os.path.join(root, name), 0o644)
            except OSError:
                pass


def clone_or_update(url: str, dest: Path, branch: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if (dest / ".git").is_dir():
        run(["git", "-C", str(dest), "fetch", "--depth", "1", "origin", branch])
        run(["git", "-C", str(dest), "checkout", "-B", branch, "FETCH_HEAD"])
        return
    if dest.exists() and any(dest.iterdir()):
        raise ToolError(f"Refusing to clone into non-empty directory {dest}")
    run(["git", "clone", "--progress", "--depth", "1", "--branch", branch, url, str(dest)])


def core_source(project: ProjectFiles) -> tuple[str, str, str] | None:
    """Return (name, url, branch) for the platform git, or None."""
    version = project.odoo_version
    if project.odoo_git_link:
        parsed = parse_git_link(project.odoo_git_link)
        name = project.platform_name or parsed["name"]
        parts = project.odoo_git_link.split()
        branch = parts[1] if len(parts) > 1 else version
        return name, parsed["url"], branch
    try:
        platform = get_platform(project.platform_name)
    except KeyError:
        platform = {}
    git = str(platform.get("git") or "").strip()
    if not git:
        return None
    parsed = parse_git_link(git)
    return project.platform_name or parsed["name"], parsed["url"], version


def core_source_dir(project: ProjectFiles) -> Path | None:
    """Directory of the cloned platform core (Odoo or fork), if present."""
    core = core_source(project)
    if not core:
        return None
    name, _url, branch = core
    dest = default_data_dir() / cache_dirname(name, branch)
    if dest.is_dir():
        return dest
    link = project.project_dir / name
    if link.is_dir():
        return link.resolve()
    return None


def sync_project_sources(project: ProjectFiles, *, log=print) -> list[str]:
    """Clone core and addons into KODPM_DATA_DIR and symlink them in the project root."""
    data = default_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    linked: list[str] = []

    core = core_source(project)
    if core:
        name, url, branch = core
        dest = data / cache_dirname(name, branch)
        log(f"Ядро: {url} ({branch}) → {dest}")
        log("git clone может занять несколько минут, в терминале должен идти прогресс…")
        clone_or_update(url, dest, branch)
        ensure_symlink(project.project_dir / name, dest)
        linked.append(name)
        log(f"Ссылка: {project.project_dir / name} → {dest}")
    else:
        log(f"Git ядра не задан для platform_name={project.platform_name!r}, пропускаю клон ядра.")

    for repo in project.addon_repos():
        name = str(repo["name"])
        url = str(repo["url"])
        branch = str(repo.get("branch") or project.odoo_version)
        dest = data / cache_dirname(name, branch)
        log(f"Addons: {url} ({branch}) → {dest}")
        clone_or_update(url, dest, branch)
        ensure_readable_tree(dest)
        ensure_symlink(project.project_dir / name, dest)
        linked.append(name)
        log(f"Ссылка: {project.project_dir / name} → {dest}")

    return linked
