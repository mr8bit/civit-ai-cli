"""Typer CLI — a thin wrapper over the library API."""
import json as _json
from pathlib import Path
from typing import NoReturn, Optional

import typer

import civitai_hub
from .cache import CacheStore, sha256_file
from .config import (
    delete_token,
    resolve_settings,
    store_token,
    token_file,
)
from .errors import CivitaiError
from .render import (
    download_progress,
    render_base_models,
    render_cache_list,
    render_dry_run,
    render_model_info,
    render_search_results,
)


def _progress_enabled(no_progress: bool) -> bool:
    """Resolve the progress flag honoring --no-progress AND CIVITAI_NO_PROGRESS."""
    return resolve_settings(progress=False if no_progress else None).progress

app = typer.Typer(help="huggingface_hub, but for CivitAI.")


def _fail(exc: CivitaiError) -> NoReturn:
    typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=exc.exit_code)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(civitai_hub.__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
):
    """huggingface_hub, but for CivitAI."""


@app.command()
def info(
    url: str = typer.Argument(..., help="CivitAI model URL or id"),
    version_id: Optional[int] = typer.Option(None, "--version-id"),
    json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
):
    """Show model info: type, base/parent model, versions, and file list."""
    try:
        result = civitai_hub.model_info(url, version_id=version_id)
    except CivitaiError as exc:
        _fail(exc)
    if json:
        payload = {
            "model": result.model.model_dump(by_alias=True),
            "version": result.version.model_dump(by_alias=True),
        }
        typer.echo(_json.dumps(payload, default=str, indent=2))
    else:
        typer.echo(render_model_info(result))


@app.command()
def download(
    url: str = typer.Argument(..., help="CivitAI model URL or id"),
    version_id: Optional[int] = typer.Option(None, "--version-id"),
    file: Optional[str] = typer.Option(None, "--file", help="Exact filename"),
    type: Optional[str] = typer.Option(None, "--type", help="File type, e.g. Model/VAE"),
    format: Optional[str] = typer.Option(None, "--format", help="e.g. SafeTensor"),
    fp16: bool = typer.Option(False, "--fp16"),
    fp32: bool = typer.Option(False, "--fp32"),
    pruned: bool = typer.Option(False, "--pruned"),
    full: bool = typer.Option(False, "--full"),
    all_files: bool = typer.Option(False, "--all", help="Download every file in the version"),
    local_dir: Optional[str] = typer.Option(None, "-o", "--local-dir"),
    no_symlinks: bool = typer.Option(False, "--no-symlinks"),
    cache_dir: Optional[str] = typer.Option(None, "--cache-dir"),
    token: Optional[str] = typer.Option(None, "--token"),
    force: bool = typer.Option(False, "--force"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    allow_unscanned: bool = typer.Option(False, "--allow-unscanned"),
    no_progress: bool = typer.Option(False, "--no-progress"),
    offline: bool = typer.Option(False, "--offline", help="Serve from cache only; never hit the network"),
    json: bool = typer.Option(False, "--json", help="Emit JSON (path/size per file)"),
    quiet: bool = typer.Option(False, "-q", "--quiet"),
):
    """Download the chosen version's file(s) into the cache (and optional folder)."""
    fp = "fp16" if fp16 else "fp32" if fp32 else None
    size = "pruned" if pruned else "full" if full else None
    show_progress = _progress_enabled(no_progress) and not dry_run and not quiet
    try:
        with download_progress(show_progress) as progress_cb:
            result = civitai_hub.download(
                url,
                version_id=version_id,
                file=file,
                type=type,
                format=format,
                fp=fp,
                size=size,
                all=all_files,
                cache_dir=cache_dir,
                local_dir=local_dir,
                use_symlinks=not no_symlinks,
                token=token,
                force=force,
                allow_unscanned=allow_unscanned,
                dry_run=dry_run,
                offline=True if offline else None,
                progress_cb=progress_cb,
            )
    except CivitaiError as exc:
        _fail(exc)

    if dry_run:
        if json:
            typer.echo(_json.dumps(
                [{"file_name": p.file_name, "size_bytes": p.size_bytes, "cached": p.cached}
                 for p in result], indent=2))
        else:
            typer.echo(render_dry_run(result))
        return
    paths = result if isinstance(result, list) else [result]
    if json:
        typer.echo(_json.dumps(
            [{"path": str(p), "filename": p.name, "size_bytes": p.stat().st_size}
             for p in paths], indent=2))
    elif not quiet:
        for p in paths:
            typer.echo(str(p))


@app.command()
def base(
    url: str = typer.Argument(..., help="CivitAI model URL or id (e.g. a LoRA)"),
    version_id: Optional[int] = typer.Option(None, "--version-id"),
    limit: int = typer.Option(10, "--limit", help="How many base checkpoints to list"),
    json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
    download: Optional[int] = typer.Option(
        None, "--download", help="Download the Nth listed checkpoint (1-based)"
    ),
    local_dir: Optional[str] = typer.Option(None, "-o", "--local-dir"),
    cache_dir: Optional[str] = typer.Option(None, "--cache-dir"),
    token: Optional[str] = typer.Option(None, "--token"),
    no_progress: bool = typer.Option(False, "--no-progress"),
):
    """Find base checkpoints matching a model's base model (e.g. for a LoRA)."""
    try:
        matches = civitai_hub.find_base_models(
            url, version_id=version_id, limit=limit, token=token
        )
    except CivitaiError as exc:
        _fail(exc)

    if download is not None:
        if not 1 <= download <= len(matches.candidates):
            typer.secho(
                f"error: --download {download} is out of range "
                f"(1..{len(matches.candidates)})",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)
        target = matches.candidates[download - 1]
        try:
            with download_progress(_progress_enabled(no_progress)) as progress_cb:
                path = civitai_hub.download(
                    target.id,
                    local_dir=local_dir,
                    cache_dir=cache_dir,
                    token=token,
                    progress_cb=progress_cb,
                )
        except CivitaiError as exc:
            _fail(exc)
        typer.echo(str(path))
        return

    if json:
        payload = {
            "source": {
                "id": matches.source.id,
                "name": matches.source.name,
                "baseModel": matches.base_model,
            },
            "candidates": [m.model_dump(by_alias=True) for m in matches.candidates],
        }
        typer.echo(_json.dumps(payload, default=str, indent=2))
    else:
        typer.echo(render_base_models(matches))


@app.command()
def search(
    query: Optional[str] = typer.Argument(None, help="Search text"),
    type: Optional[str] = typer.Option(None, "--type", help="Checkpoint / LORA / ..."),
    base_model: Optional[str] = typer.Option(None, "--base-model", help="e.g. Pony, SDXL 1.0"),
    sort: str = typer.Option("Most Downloaded", "--sort"),
    limit: int = typer.Option(20, "--limit"),
    token: Optional[str] = typer.Option(None, "--token"),
    json: bool = typer.Option(False, "--json"),
):
    """Search CivitAI models."""
    try:
        models = civitai_hub.search(
            query, type=type, base_model=base_model, sort=sort, limit=limit, token=token
        )
    except CivitaiError as exc:
        _fail(exc)
    if json:
        typer.echo(_json.dumps([m.model_dump(by_alias=True) for m in models], default=str, indent=2))
    else:
        typer.echo(render_search_results(models, query))


@app.command("by-hash")
def by_hash(
    hash_or_file: str = typer.Argument(..., help="A SHA256/AutoV2 hash, or a path to a local file"),
    token: Optional[str] = typer.Option(None, "--token"),
    json: bool = typer.Option(False, "--json"),
):
    """Identify a model from a file hash (or a local file)."""
    target = Path(hash_or_file)
    file_hash = sha256_file(target) if target.is_file() else hash_or_file
    try:
        info = civitai_hub.find_by_hash(file_hash, token=token)
    except CivitaiError as exc:
        _fail(exc)
    if json:
        typer.echo(_json.dumps(
            {"model": info.model.model_dump(by_alias=True),
             "version": info.version.model_dump(by_alias=True)},
            default=str, indent=2))
    else:
        typer.echo(render_model_info(info))


@app.command()
def login(token: Optional[str] = typer.Option(None, "--token", help="API key (prompted if omitted)")):
    """Store a CivitAI API token for future commands."""
    if not token:
        token = typer.prompt("CivitAI API token", hide_input=True)
    path = store_token(token)
    typer.echo(f"Token saved to {path}")


@app.command()
def logout():
    """Remove the stored API token."""
    typer.echo("Token removed." if delete_token() else "No stored token.")


@app.command("config")
def config_show():
    """Show the resolved configuration."""
    s = resolve_settings()
    tf = token_file()
    typer.echo(f"cache_dir:  {s.cache_dir}")
    typer.echo(f"token:      {'set' if s.token else 'none'}")
    typer.echo(f"token_file: {tf} {'(exists)' if tf.exists() else '(none)'}")
    typer.echo(f"offline:    {s.offline}")
    typer.echo(f"symlinks:   {s.use_symlinks}")
    typer.echo(f"progress:   {s.progress}")


cache_app = typer.Typer(help="Inspect and manage the local cache.")
app.add_typer(cache_app, name="cache")


def _store(cache_dir: Optional[str]) -> CacheStore:
    return CacheStore(resolve_settings(cache_dir=cache_dir).cache_dir)


@cache_app.command("ls")
def cache_ls(
    cache_dir: Optional[str] = typer.Option(None, "--cache-dir"),
    json: bool = typer.Option(False, "--json"),
):
    """List cached files."""
    store = _store(cache_dir)
    entries = store.iter_entries()
    if json:
        typer.echo(_json.dumps(entries, indent=2))
    else:
        typer.echo(render_cache_list(entries, store.total_size()))


@cache_app.command("verify")
def cache_verify(cache_dir: Optional[str] = typer.Option(None, "--cache-dir")):
    """Re-hash cached blobs and report corruption."""
    results = _store(cache_dir).verify()
    bad = [b for b, ok in results if not ok]
    for b in bad:
        typer.secho(f"CORRUPT: {b}", fg=typer.colors.RED, err=True)
    typer.echo(f"{len(results)} blob(s) checked, {len(bad)} corrupt.")
    if bad:
        raise typer.Exit(code=1)


@cache_app.command("rm")
def cache_rm(
    model_id: int = typer.Argument(..., help="Model id to evict from the cache"),
    cache_dir: Optional[str] = typer.Option(None, "--cache-dir"),
):
    """Remove a model's cached files."""
    removed = _store(cache_dir).remove_model(model_id)
    typer.echo(f"Removed model {model_id}." if removed else f"Model {model_id} is not cached.")


@cache_app.command("prune")
def cache_prune(cache_dir: Optional[str] = typer.Option(None, "--cache-dir")):
    """Remove leftover temp files and dangling links."""
    stats = _store(cache_dir).prune()
    typer.echo(f"Pruned {stats['temps']} temp(s), {stats['dangling_snapshots']} dangling link(s).")
