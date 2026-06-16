"""Typer CLI — a thin wrapper over the library API."""
import json as _json
from typing import Optional

import typer

import civitai_hub
from .errors import CivitaiError
from .render import download_progress, render_base_models, render_dry_run, render_model_info

app = typer.Typer(add_completion=False, help="huggingface_hub, but for CivitAI.")


def _fail(exc: CivitaiError) -> None:
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
        return
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
    quiet: bool = typer.Option(False, "-q", "--quiet"),
):
    """Download the chosen version's file(s) into the cache (and optional folder)."""
    fp = "fp16" if fp16 else "fp32" if fp32 else None
    size = "pruned" if pruned else "full" if full else None
    show_progress = not no_progress and not dry_run and not quiet
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
                progress=not no_progress,
                progress_cb=progress_cb,
            )
    except CivitaiError as exc:
        _fail(exc)
        return

    if dry_run:
        typer.echo(render_dry_run(result))
        return
    paths = result if isinstance(result, list) else [result]
    if not quiet:
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
            url, version_id=version_id, limit=limit, token=token, cache_dir=cache_dir
        )
    except CivitaiError as exc:
        _fail(exc)
        return

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
            with download_progress(not no_progress) as progress_cb:
                path = civitai_hub.download(
                    target.id,
                    local_dir=local_dir,
                    cache_dir=cache_dir,
                    token=token,
                    progress=not no_progress,
                    progress_cb=progress_cb,
                )
        except CivitaiError as exc:
            _fail(exc)
            return
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
