from __future__ import annotations

import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from kodpm.cluster import DEFAULT_CLUSTER, cluster_exists, ensure_cluster
from kodpm.hostpip import odoo_image_of
from kodpm.proc import ToolError, run, which
from kodpm.project import ProjectFiles


def post_prepare_commands(project: ProjectFiles) -> list[list[str]]:
    hooks = project.chosen_scenario().get("hooks")
    if not isinstance(hooks, dict):
        return []
    raw = hooks.get("post_prepare")
    if not isinstance(raw, list):
        return []
    commands: list[list[str]] = []
    for item in raw:
        if isinstance(item, list) and item:
            commands.append([str(part) for part in item])
    return commands


def images_from_docker_hooks(commands: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    """Pick images from docker inspect/pull; return leftover commands unchanged."""
    images: list[str] = []
    leftover: list[list[str]] = []
    for cmd in commands:
        image = _image_from_docker_cmd(cmd)
        if image:
            if image not in images:
                images.append(image)
        else:
            leftover.append(cmd)
    return images, leftover


def _image_from_docker_cmd(cmd: list[str]) -> str | None:
    if len(cmd) < 3 or cmd[0] != "docker":
        return None
    if cmd[1:3] == ["image", "inspect"] and len(cmd) >= 4:
        return cmd[3]
    if cmd[1] == "inspect" and len(cmd) >= 3 and ":" in cmd[-1]:
        return cmd[-1]
    if cmd[1] == "pull" and len(cmd) >= 3:
        return cmd[-1]
    return None


def extra_service_images(project: ProjectFiles) -> list[str]:
    from kodpm.extraservices import extra_service_values

    images: list[str] = []
    for item in extra_service_values(project):
        image = str(item.get("image") or "").strip()
        if image and image not in images:
            images.append(image)
    return images


def core_images(values: dict[str, Any]) -> list[str]:
    images = [odoo_image_of(values)]
    postgres = str((values.get("postgres") or {}).get("image") or "").strip()
    if postgres:
        images.append(postgres)
    minio = values.get("minio") or {}
    if minio.get("enabled"):
        image = str(minio.get("image") or "").strip()
        if image:
            images.append(image)
    return images


def collect_up_images(
    project: ProjectFiles,
    values: dict[str, Any],
    *,
    extras: bool,
) -> tuple[list[str], list[list[str]]]:
    images = list(core_images(values))
    leftover: list[list[str]] = []
    if extras:
        hook_images, leftover = images_from_docker_hooks(post_prepare_commands(project))
        for image in hook_images + extra_service_images(project):
            if image not in images:
                images.append(image)
    return images, leftover


def k3d_server_names(cluster: str = DEFAULT_CLUSTER) -> list[str]:
    result = run(
        [
            "docker",
            "ps",
            "--filter",
            f"label=k3d.cluster={cluster}",
            "--filter",
            "label=k3d.role=server",
            "--format",
            "{{.Names}}",
        ],
        capture=True,
        check=False,
    )
    names = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    return names


def host_has_image(image: str) -> bool:
    result = run(["docker", "image", "inspect", image], capture=True, check=False)
    return result.returncode == 0


def node_has_image(server: str, image: str) -> bool:
    result = run(
        ["docker", "exec", server, "crictl", "images"],
        capture=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    wanted = _image_match_keys(image)
    for line in (result.stdout or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        repo, tag = parts[0], parts[1]
        if _image_match_keys(f"{repo}:{tag}") & wanted:
            return True
    return False


def _image_match_keys(image: str) -> set[str]:
    text = image.strip()
    keys = {text}
    if "/" not in text.split(":")[0]:
        keys.add(f"docker.io/library/{text}")
    elif not text.startswith("docker.io/"):
        keys.add(f"docker.io/{text}")
    if text.startswith("docker.io/library/"):
        keys.add(text.removeprefix("docker.io/library/"))
    elif text.startswith("docker.io/"):
        keys.add(text.removeprefix("docker.io/"))
    return keys


def pull_host_image(image: str, *, log: Callable[[str], None]) -> None:
    if host_has_image(image):
        log(f"образ {image} уже есть на хосте")
        return
    log(f"docker pull {image}")
    result = run(["docker", "pull", image], check=False)
    if result.returncode != 0:
        raise ToolError(
            f"Нет образа {image} на хосте и docker pull не удался. "
            "Соберите его локально или проверьте доступ к registry."
        )


def _decode(blob: bytes | str | None) -> str:
    if blob is None:
        return ""
    if isinstance(blob, str):
        return blob.strip()
    return blob.decode("utf-8", "replace").strip()


def _import_via_pipe(server: str, image: str) -> tuple[int | None, int | None, str, str]:
    saver = subprocess.Popen(
        ["docker", "save", image],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    loader = subprocess.Popen(
        ["docker", "exec", "-i", server, "ctr", "-n", "k8s.io", "images", "import", "-"],
        stdin=saver.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    save_err_box: list[bytes] = []

    def _drain_save_err() -> None:
        if saver.stderr:
            save_err_box.append(saver.stderr.read() or b"")

    drain = threading.Thread(target=_drain_save_err)
    drain.start()
    if saver.stdout:
        saver.stdout.close()
    _out, load_err = loader.communicate()
    drain.join()
    saver.wait()
    return saver.returncode, loader.returncode, _decode(save_err_box[0] if save_err_box else b""), _decode(load_err)


def _import_via_tar(server: str, image: str) -> None:
    with tempfile.NamedTemporaryFile(prefix="kodpm-img-", suffix=".tar", delete=False) as tmp:
        tar_path = Path(tmp.name)
    try:
        saved = run(["docker", "save", "-o", str(tar_path), image], capture=True, check=False)
        if saved.returncode != 0:
            detail = (saved.stderr or saved.stdout or "").strip() or f"код {saved.returncode}"
            raise ToolError(f"docker save {image} не удался: {detail}")
        with tar_path.open("rb") as fh:
            loaded = subprocess.run(
                ["docker", "exec", "-i", server, "ctr", "-n", "k8s.io", "images", "import", "-"],
                stdin=fh,
                capture_output=True,
            )
        if loaded.returncode != 0:
            detail = _decode(loaded.stderr or loaded.stdout) or f"код {loaded.returncode}"
            raise ToolError(f"Не удалось импортировать {image} в {server}. {detail}")
    finally:
        tar_path.unlink(missing_ok=True)


def import_image_to_node(server: str, image: str, *, log: Callable[[str], None]) -> None:
    if node_has_image(server, image):
        log(f"образ {image} уже есть в {server}")
        return
    log(f"импорт {image} → {server} (ctr)")
    which("docker")
    save_code, load_code, save_err, load_err = _import_via_pipe(server, image)
    combined = f"{load_err} {save_err}"
    if "is not running" in combined:
        raise ToolError(
            f"нода {server} не запущена. Сначала: kodpm cluster start  или  kodpm cluster init"
        )
    if load_code == 0:
        return
    log(f"повтор импорта {image} через tar (pipe: save={save_code} load={load_code})")
    try:
        _import_via_tar(server, image)
    except ToolError as exc:
        pipe_detail = load_err or save_err or f"save={save_code} load={load_code}"
        raise ToolError(f"{exc} (сначала pipe: {pipe_detail})") from exc


def ensure_cluster_images(
    project: ProjectFiles,
    values: dict[str, Any],
    *,
    extras: bool,
    cluster: str = DEFAULT_CLUSTER,
    log: Callable[[str], None] = print,
) -> list[str]:
    """Pull images on the host (DNS works) and load them into k3d via ctr."""
    images, leftover = collect_up_images(project, values, extras=extras)
    for cmd in leftover:
        log(f"hooks.post_prepare пропущен: {' '.join(cmd)}")
    if not images:
        return []
    if not cluster_exists(cluster):
        log(f"кластер k3d {cluster} не найден — импорт образов пропущен")
        return images
    servers = k3d_server_names(cluster)
    if not servers:
        raise ToolError(
            f"нода k3d {cluster} не запущена. Сначала: kodpm cluster start  или  kodpm cluster init"
        )
    log(f"Образы для k3d ({len(images)}): {', '.join(images)}")
    for image in images:
        pull_host_image(image, log=log)
        for server in servers:
            import_image_to_node(server, image, log=log)
    return images
