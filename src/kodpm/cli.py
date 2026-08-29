from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import click
import yaml

from kodpm import __version__
from kodpm.cluster import DEFAULT_CLUSTER, delete_cluster, init_cluster, require_k3d
from kodpm.cmutil import apply_configmap_data, get_configmap_data
from kodpm.helm import helm_status, helm_template, helm_uninstall, helm_upgrade
from kodpm.iniutil import get_ini_option, set_ini_option
from kodpm.jobs import render_job, run_job, timestamp_suffix
from kodpm.kube import exec_in, kubectl, rollout_odoo, scale_odoo
from kodpm.proc import ToolError
from kodpm.catalog import resolve_odoo_version
from kodpm.layout import ensure_values_local, sync_project_layout
from kodpm.initproj import (
    DONE_TOKENS,
    build_odpm_json,
    build_user_settings,
    known_platforms,
    known_versions,
    normalize_addon_links,
    normalize_platform,
    write_project_files,
)
from kodpm.project import ProjectFiles, parse_modules
from kodpm.sources import sync_project_sources
from kodpm.values import build_values, dump_values, namespace_of, release_name


def _project(ctx: click.Context) -> ProjectFiles:
    return ProjectFiles(Path(ctx.obj["project_dir"]))


def _values(ctx: click.Context, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    project = _project(ctx)
    return build_values(
        project,
        ctx.obj["profile"],
        extra=extra,
        db_name=ctx.obj.get("db_name"),
    )


def _sync_layout(ctx: click.Context, *, overwrite_conf: bool = False) -> dict[str, Any]:
    project = _project(ctx)
    ensure_values_local(project)
    return sync_project_layout(_project(ctx), _values(ctx), overwrite_conf=overwrite_conf)


def _ns(ctx: click.Context, values: dict[str, Any] | None = None) -> str:
    values = values or _values(ctx)
    return namespace_of(values, ctx.obj["profile"])


def _release(ctx: click.Context) -> str:
    return release_name(_project(ctx))


def _fullname(ctx: click.Context, values: dict[str, Any] | None = None) -> str:
    values = values or _values(ctx)
    return str(values.get("fullnameOverride") or _release(ctx))


def _values_file(values: dict[str, Any]) -> Path:
    tmp = Path(tempfile.gettempdir()) / f".kodpm-values-{values.get('fullnameOverride', 'instance')}.yaml"
    return dump_values(values, tmp)


def _apply_profile(ctx: click.Context, profile: str | None) -> None:
    if profile:
        ctx.obj["profile"] = profile.lower()


_PROFILE_OPTION = click.option(
    "--profile",
    type=click.Choice(["local", "test", "dev"], case_sensitive=False),
    default=None,
    help="local, test or dev (same as global kodpm --profile … <command>)",
)


def perform_up(ctx: click.Context, *, dry_run: bool = False, wait: bool = True) -> None:
    if ctx.obj["profile"] == "local" and not dry_run and not ctx.obj.get("no_clone"):
        click.echo("Клонирование ядра и addons в kodpm_data…")
        sync_project_sources(_project(ctx), log=click.echo)
    values = _sync_layout(ctx) if not dry_run else _values(ctx)
    values_file = _values_file(values)
    release = _release(ctx)
    namespace = _ns(ctx, values)
    if dry_run:
        click.echo(yaml.safe_dump(values, sort_keys=False, allow_unicode=True))
        click.echo("---")
        click.echo(helm_template(release, namespace, values_file))
        return
    click.echo(f"helm upgrade --install {release} (namespace={namespace}, profile={ctx.obj['profile']})")
    try:
        helm_upgrade(release, namespace, values_file, wait=wait)
    except ToolError:
        click.echo(
            "Helm не дождался Ready. Поды этого релиза:\n"
            f"  kubectl get pods -n {namespace} -l app.kubernetes.io/instance={release}\n"
            f"  kubectl logs -n {namespace} -l app.kubernetes.io/instance={release},app.kubernetes.io/component=odoo --tail=80",
            err=True,
        )
        raise
    host = (values.get("ingress") or {}).get("host")
    click.echo(f"Release {release} is installed.")
    if host:
        click.echo(f"URL: http://{host}")


@click.group()
@click.version_option(__version__, prog_name="kodpm")
@click.option(
    "--project-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=".",
    show_default=True,
    help="Project directory; default is the current working directory",
)
@click.option(
    "--profile",
    type=click.Choice(["local", "test", "dev"], case_sensitive=False),
    default="local",
    show_default=True,
)
@click.option("-d", "--db", "db_name", default=None, help="Odoo database name")
@click.pass_context
def cli(ctx: click.Context, project_dir: Path, profile: str, db_name: str | None) -> None:
    """Kubernetes environment for Odoo and rebranded forks."""
    ctx.ensure_object(dict)
    ctx.obj["project_dir"] = project_dir.resolve()
    ctx.obj["profile"] = profile.lower()
    ctx.obj["db_name"] = db_name


@cli.group()
def cluster() -> None:
    """Local k3d cluster."""


@cluster.command("init")
@click.option("--name", default=DEFAULT_CLUSTER, show_default=True)
@click.option("--host-home", type=click.Path(file_okay=False, path_type=Path), default=None)
@click.option("--api-port", default="6550", show_default=True)
def cluster_init(name: str, host_home: Path | None, api_port: str) -> None:
    """Create a k3d cluster with host $HOME mounted at /host-home."""
    require_k3d()
    click.echo(f"Creating k3d cluster {name} (or reusing if it exists)...")
    init_cluster(name, host_home=host_home, api_port=api_port)
    click.echo("Cluster is ready. Next: cd <project> && kodpm up")


@cluster.command("delete")
@click.option("--name", default=DEFAULT_CLUSTER, show_default=True)
@click.confirmation_option(prompt="Delete the k3d cluster?")
def cluster_delete(name: str) -> None:
    require_k3d()
    delete_cluster(name)
    click.echo(f"Deleted cluster {name}")


@cli.command("init")
@_PROFILE_OPTION
@click.option("--odoo-version", default=None, help="Odoo/fork series, e.g. 17.0")
@click.option("--platform", default=None, help="Core name: odoo, fincomtech, …")
@click.option("--addon", "addons", multiple=True, help="Addon git URL, optionally 'URL branch'. Repeatable.")
@click.option("--modules", default=None, help="Modules to install, comma-separated")
@click.option("--image", default=None, help="Container image for a fork (registry/name:tag)")
@click.option("--odoo-git-link", default=None, help="Git of the platform fork")
@click.option("--db-lang", default=None, help="Database language, e.g. ru_RU")
@click.option("--admin-password", default=None, help="Admin / DB manager password")
@click.option("--no-up", is_flag=True, help="Only write project files, do not helm up")
@click.option("--no-clone", is_flag=True, help="Do not clone core/addons into kodpm_data")
@click.option("--yes", "overwrite", is_flag=True, help="Overwrite existing files without asking")
@click.pass_context
def init_project(
    ctx: click.Context,
    profile: str | None,
    odoo_version: str | None,
    platform: str | None,
    addons: tuple[str, ...],
    modules: str | None,
    image: str | None,
    odoo_git_link: str | None,
    db_lang: str | None,
    admin_password: str | None,
    no_up: bool,
    no_clone: bool,
    overwrite: bool,
) -> None:
    """Create the project layout (json, conf, values.local.yaml, source links), then install."""
    _apply_profile(ctx, profile)
    project_dir = Path(ctx.obj["project_dir"])
    versions = ", ".join(known_versions())
    platforms = ", ".join(p for p in known_platforms() if p != "custom")

    click.echo(f"Проект kodpm: {project_dir}")
    while True:
        if odoo_version is None:
            odoo_version = click.prompt(f"Версия ядра ({versions})", default="17.0")
        try:
            odoo_version = resolve_odoo_version(odoo_version)
            break
        except KeyError as exc:
            click.echo(str(exc))
            odoo_version = None

    if platform is None:
        platform = click.prompt(f"Наименование ядра ({platforms})", default="odoo")
    platform = normalize_platform(platform)

    image_val = image or ""
    git_val = odoo_git_link or ""
    if platform != "odoo":
        if image is None:
            image_val = click.prompt(
                "Образ ядра (registry/name:tag, пусто — пропустить)",
                default="",
                show_default=False,
            )
        if odoo_git_link is None:
            git_val = click.prompt(
                "Git-репозиторий ядра (пусто — пропустить)",
                default="",
                show_default=False,
            )

    addon_links = list(addons)
    if not addon_links:
        click.echo("Репозитории addons. Формат: URL или URL и ветка.")
        click.echo("Пример: git@github.com:org/addons.git 17.0")
        click.echo("Нажмите Enter (или введите «готово») — закончить список.")
        while True:
            line = click.prompt("  addons git", default="готово", show_default=True)
            text = str(line).strip()
            if text.lower() in DONE_TOKENS:
                break
            addon_links.append(text)
            click.echo(f"    добавлен {text}")
        addon_links = normalize_addon_links(addon_links, odoo_version)
        if addon_links:
            click.echo("Итого addons: " + "; ".join(addon_links))
        else:
            click.echo("Addons не указаны, иду дальше.")
    else:
        addon_links = normalize_addon_links(addon_links, odoo_version)

    if modules is None:
        modules = click.prompt("Модули для установки (-i)", default="base,web")
    if db_lang is None:
        db_lang = click.prompt("Язык базы", default="ru_RU")
    if admin_password is None:
        admin_password = click.prompt("Пароль admin / менеджера БД", default="admin")

    odpm_path = project_dir / "odpm.json"
    settings_path = project_dir / "user_settings.json"
    existing = [path for path in (odpm_path, settings_path) if path.exists()]
    if existing and not overwrite:
        if not click.confirm("Файлы проекта уже есть. Перезаписать?", default=False):
            raise click.Abort()

    odpm = build_odpm_json(
        odoo_version,
        platform,
        addon_links,
        image=image_val,
        odoo_git_link=git_val,
    )
    settings = build_user_settings(
        modules or "base,web",
        db_lang=db_lang or "ru_RU",
        db_country_code="ru" if str(db_lang or "").startswith("ru") else False,
        admin_password=admin_password or "admin",
        dev_mode="reload,xml" if ctx.obj["profile"] == "local" else "",
    )
    write_project_files(project_dir, odpm, settings)
    project = ProjectFiles(project_dir)
    _sync_layout(ctx, overwrite_conf=overwrite)
    written = [
        odpm_path.name,
        settings_path.name,
        project.conf_name,
        project.values_local_path.name,
    ]
    click.echo("Записано: " + ", ".join(written))
    ctx.obj["no_clone"] = no_clone
    if not no_clone:
        click.echo("Клонирование ядра и addons…")
        sync_project_sources(ProjectFiles(project_dir), log=click.echo)

    if no_up:
        click.echo("Дальше из этого каталога: kodpm up")
        return
    if click.get_text_stream("stdin").isatty() and not overwrite:
        if not click.confirm("Запустить установку (кластер + helm up)?", default=True):
            click.echo("Дальше из этого каталога: kodpm up")
            return

    if ctx.obj["profile"] == "local":
        require_k3d()
        click.echo("Проверка / создание k3d-кластера…")
        init_cluster()
    perform_up(ctx, wait=True)
    if parse_modules(settings.get("init_modules")):
        ctx.obj["db_name"] = ctx.obj.get("db_name") or "odoo"
        _run_modules(ctx, "install", None)


@cli.command()
@_PROFILE_OPTION
@click.option("--dry-run", is_flag=True, help="Print Helm template, do not install")
@click.option("--wait/--no-wait", default=True, show_default=True)
@click.option("--no-clone", is_flag=True, help="Do not clone core/addons into kodpm_data")
@click.pass_context
def up(ctx: click.Context, dry_run: bool, wait: bool, profile: str | None, no_clone: bool) -> None:
    """Install or upgrade the instance (Helm). Run from the project directory."""
    _apply_profile(ctx, profile)
    ctx.obj["no_clone"] = no_clone
    perform_up(ctx, dry_run=dry_run, wait=wait)


@cli.command()
@_PROFILE_OPTION
@click.pass_context
def down(ctx: click.Context, profile: str | None) -> None:
    """Uninstall the Helm release (PVCs may remain)."""
    _apply_profile(ctx, profile)
    values = _values(ctx)
    helm_uninstall(_release(ctx), _ns(ctx, values))
    click.echo("Release uninstalled.")


@cli.command()
@_PROFILE_OPTION
@click.pass_context
def status(ctx: click.Context, profile: str | None) -> None:
    """Show Helm and workload status."""
    _apply_profile(ctx, profile)
    values = _values(ctx)
    release = _release(ctx)
    namespace = _ns(ctx, values)
    click.echo(helm_status(release, namespace))
    click.echo("")
    kubectl("get", "pods,svc,ingress,pvc", "-n", namespace, "-l", f"app.kubernetes.io/instance={release}")


@cli.group()
def config() -> None:
    """Odoo / fork configuration file (ConfigMap)."""


@config.command("get")
@click.argument("key", required=False)
@click.pass_context
def config_get(ctx: click.Context, key: str | None) -> None:
    values = _values(ctx)
    project = _project(ctx)
    conf_name = str(values.get("confName") or "odoo.conf")
    if project.conf_path.is_file():
        content = project.conf_path.read_text(encoding="utf-8")
    else:
        content = str((values.get("config") or {}).get("raw") or "")
        if not content:
            data = get_configmap_data(f"{_fullname(ctx, values)}-config", _ns(ctx, values))
            content = data.get(conf_name, "")
    if key:
        found = get_ini_option(content, key)
        if found is None:
            raise click.ClickException(f"Option {key!r} not found in {conf_name}")
        click.echo(found)
        return
    click.echo(content, nl=not content.endswith("\n"))


@config.command("set")
@click.argument("pairs", nargs=-1, required=True)
@click.pass_context
def config_set(ctx: click.Context, pairs: tuple[str, ...]) -> None:
    """Set options: kodpm config set workers=2 proxy_mode=True"""
    values = _values(ctx)
    project = _project(ctx)
    conf_name = str(values.get("confName") or "odoo.conf")
    content = (
        project.conf_path.read_text(encoding="utf-8")
        if project.conf_path.is_file()
        else str((values.get("config") or {}).get("raw") or "[options]\n")
    )
    for pair in pairs:
        if "=" not in pair:
            raise click.ClickException(f"Expected KEY=VALUE, got {pair!r}")
        option, value = pair.split("=", 1)
        content = set_ini_option(content, option.strip(), value.strip())
    project.conf_path.write_text(content, encoding="utf-8")
    values = _sync_layout(ctx)
    content = str(values["config"]["raw"])
    fullname = _fullname(ctx, values)
    namespace = _ns(ctx, values)
    cm_name = f"{fullname}-config"
    try:
        data = get_configmap_data(cm_name, namespace)
        data[conf_name] = content
        apply_configmap_data(cm_name, namespace, data)
        rollout_odoo(fullname, namespace)
        click.echo(f"Updated {project.conf_path.name} and restarted Odoo.")
    except (ToolError, FileNotFoundError, KeyError):
        click.echo(f"Updated {project.conf_path.name} (cluster not updated).")


@cli.group()
def db() -> None:
    """Database dumps and lifecycle."""


@db.command("list")
@click.pass_context
def db_list(ctx: click.Context) -> None:
    values = _values(ctx)
    fullname = _fullname(ctx, values)
    namespace = _ns(ctx, values)
    exec_in(
        f"sts/{fullname}-postgres",
        namespace,
        "psql",
        "-U",
        str((values.get("postgres") or {}).get("user") or "odoo"),
        "-d",
        "postgres",
        "-c",
        r"\l",
    )


@db.command("backup")
@click.option("--name", "dump_name", default=None, help="Archive name without path")
@click.pass_context
def db_backup(ctx: click.Context, dump_name: str | None) -> None:
    values = _values(ctx)
    fullname = _fullname(ctx, values)
    namespace = _ns(ctx, values)
    db_name = ctx.obj.get("db_name") or (values.get("kodpm") or {}).get("dbName") or "odoo"
    name = dump_name or f"{db_name}-{timestamp_suffix()}"
    job_name = f"{fullname}-backup-{timestamp_suffix()}"[:63]
    manifest = render_job(
        "backup",
        values,
        job_name=job_name,
        namespace=namespace,
        release=_release(ctx),
        db_name=db_name,
        dump_name=name,
        deadline=1800,
    )
    click.echo(f"Backing up database {db_name} as {name}.tar.gz ...")
    run_job(manifest, job_name, namespace)
    click.echo("Backup finished.")


@db.command("restore")
@click.argument("archive")
@click.pass_context
def db_restore(ctx: click.Context, archive: str) -> None:
    values = _values(ctx)
    fullname = _fullname(ctx, values)
    namespace = _ns(ctx, values)
    db_name = ctx.obj.get("db_name") or (values.get("kodpm") or {}).get("dbName") or "odoo"
    job_name = f"{fullname}-restore-{timestamp_suffix()}"[:63]
    click.echo("Scaling Odoo down for restore...")
    scale_odoo(fullname, namespace, 0)
    try:
        manifest = render_job(
            "restore",
            values,
            job_name=job_name,
            namespace=namespace,
            release=_release(ctx),
            db_name=db_name,
            restore_from=archive,
            deadline=3600,
        )
        click.echo(f"Restoring {archive} into {db_name} ...")
        run_job(manifest, job_name, namespace, timeout="30m")
    finally:
        scale_odoo(fullname, namespace, int(values.get("replicaCount") or 1))
    click.echo("Restore finished.")


@db.command("drop")
@click.pass_context
def db_drop(ctx: click.Context) -> None:
    values = _values(ctx)
    fullname = _fullname(ctx, values)
    namespace = _ns(ctx, values)
    db_name = ctx.obj.get("db_name")
    if not db_name:
        raise click.ClickException("Pass -d DATABASE")
    user = str((values.get("postgres") or {}).get("user") or "odoo")
    scale_odoo(fullname, namespace, 0)
    try:
        exec_in(
            f"sts/{fullname}-postgres",
            namespace,
            "dropdb",
            "-U",
            user,
            "--if-exists",
            db_name,
        )
    finally:
        scale_odoo(fullname, namespace, int(values.get("replicaCount") or 1))
    click.echo(f"Dropped database {db_name}")


@cli.group()
def modules() -> None:
    """Install or update addons via Kubernetes Job (not on the running pod)."""


def _run_modules(ctx: click.Context, action: str, names: str | None) -> None:
    values = _values(ctx)
    fullname = _fullname(ctx, values)
    namespace = _ns(ctx, values)
    project = _project(ctx)
    if names:
        module_list = parse_modules(names)
    elif action == "install":
        module_list = project.init_modules()
    else:
        module_list = project.update_modules()
    if not module_list:
        raise click.ClickException(
            f"No modules for {action}. Pass names or set init_modules/update_modules in user_settings.json"
        )
    db_name = ctx.obj.get("db_name") or (values.get("kodpm") or {}).get("dbName") or "odoo"
    job_name = f"{fullname}-mods-{action[:2]}-{timestamp_suffix()}"[:63]
    joined = ",".join(module_list)
    click.echo(f"Scaling Odoo down for module {action} ({joined})...")
    scale_odoo(fullname, namespace, 0)
    try:
        manifest = render_job(
            action,
            values,
            job_name=job_name,
            namespace=namespace,
            release=_release(ctx),
            db_name=db_name,
            modules=joined,
            deadline=3600,
        )
        run_job(manifest, job_name, namespace, timeout="30m")
    finally:
        scale_odoo(fullname, namespace, int(values.get("replicaCount") or 1))
    click.echo(f"Module {action} finished.")


@modules.command("install")
@click.argument("names", required=False)
@click.pass_context
def modules_install(ctx: click.Context, names: str | None) -> None:
    _run_modules(ctx, "install", names)


@modules.command("update")
@click.argument("names", required=False)
@click.pass_context
def modules_update(ctx: click.Context, names: str | None) -> None:
    _run_modules(ctx, "update", names)


@cli.command(name="exec", context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.pass_context
def exec_cmd(ctx: click.Context) -> None:
    """Pass extra args to the platform binary inside the Odoo pod."""
    values = _values(ctx)
    fullname = _fullname(ctx, values)
    namespace = _ns(ctx, values)
    extra = list(ctx.args)
    if extra[:1] == ["--"]:
        extra = extra[1:]
    bin_name = str(values.get("bin") or "odoo")
    args = extra or ["--help"]
    kubectl(
        "exec",
        f"deploy/{fullname}-odoo",
        "-n",
        namespace,
        "-c",
        "odoo",
        "--",
        bin_name,
        *args,
    )


@cli.command("values")
@_PROFILE_OPTION
@click.pass_context
def show_values(ctx: click.Context, profile: str | None) -> None:
    """Print merged Helm values (profile + catalogs + odpm.json)."""
    _apply_profile(ctx, profile)
    click.echo(yaml.safe_dump(_values(ctx), sort_keys=False, allow_unicode=True))


def main() -> None:
    try:
        cli(standalone_mode=True)
    except (ToolError, FileNotFoundError, KeyError) as exc:
        raise SystemExit(f"error: {exc}") from exc


if __name__ == "__main__":
    main()
