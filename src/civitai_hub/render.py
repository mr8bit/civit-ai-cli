"""Human-readable rendering with rich. Functions return plain strings so they
are easy to test; the CLI prints them."""
import contextlib

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from .models import ModelInfo, PlanItem


def _human_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "-"
    value = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _capture(renderable) -> str:
    # capture() redirects output into a buffer so nothing is written to the real
    # stdout — otherwise the renderable would print here AND again when the CLI
    # echoes the returned string.
    console = Console(width=100)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


def render_model_info(info: ModelInfo) -> str:
    m, v = info.model, info.version
    creator = (m.creator or {}).get("username") or "-"
    stats = m.stats or {}
    header = Table.grid(padding=(0, 1))
    header.add_row("Model:", f"{m.name}  (#{m.id})")
    header.add_row("Type:", m.type or "-")
    header.add_row("Creator:", creator)
    header.add_row("Base model:", " ".join(filter(None, [v.base_model, v.base_model_type])) or "-")
    header.add_row("Parent model id:", str(v.model_id or m.id))
    header.add_row("Version:", f"{v.name or '-'}  (#{v.id})")
    header.add_row("Trigger words:", ", ".join(v.trained_words) or "-")
    header.add_row(
        "Stats:",
        f"{stats.get('downloadCount', 0)} downloads, {stats.get('thumbsUpCount', 0)} likes",
    )
    header.add_row("Files:", f"{len(info.files)} files")

    files = Table(title=f"{len(info.files)} files", show_lines=False)
    for col in ["name", "type", "format", "fp", "size", "primary", "scan"]:
        files.add_column(col)
    for f in info.files:
        scan = "ok" if (f.pickle_scan_result == "Success" and f.virus_scan_result == "Success") else "!"
        files.add_row(
            f.name, f.type or "-", f.metadata.format or "-", f.metadata.fp or "-",
            _human_size(f.size_bytes), "yes" if f.primary else "", scan,
        )
    return _capture(header) + "\n" + _capture(files)


def render_dry_run(plan: list[PlanItem]) -> str:
    table = Table(title="Dry run")
    table.add_column("file")
    table.add_column("size")
    table.add_column("status")
    to_download = 0
    for item in plan:
        status = "cached" if item.cached else "download"
        if not item.cached and item.size_bytes:
            to_download += item.size_bytes
        table.add_row(item.file_name, _human_size(item.size_bytes), status)
    summary = f"Will download {sum(1 for p in plan if not p.cached)} file(s), " \
              f"{_human_size(to_download)} total."
    return _capture(table) + "\n" + summary


def render_base_models(matches) -> str:
    src = matches.source
    header = Table.grid(padding=(0, 1))
    header.add_row("For:", f"{src.name}  (#{src.id}, {src.type or '-'})")
    header.add_row("Base model:", matches.base_model or "-")
    header.add_row("Matches:", f"{len(matches.candidates)} checkpoints")

    table = Table(title=f"Base checkpoints for '{matches.base_model or '-'}'")
    table.add_column("#")
    table.add_column("id")
    table.add_column("name")
    table.add_column("base")
    table.add_column("downloads", justify="right")
    for i, m in enumerate(matches.candidates, start=1):
        base = m.model_versions[0].base_model if m.model_versions else None
        downloads = (m.stats or {}).get("downloadCount", 0)
        table.add_row(str(i), str(m.id), m.name, base or "-", f"{downloads:,}")
    return _capture(header) + "\n" + _capture(table)


@contextlib.contextmanager
def download_progress(enabled: bool):
    """Context manager yielding a progress callback (downloaded, total) for
    download_file's progress_cb, or None when disabled. Renders to stderr so
    stdout stays clean for the downloaded path(s)."""
    if not enabled:
        yield None
        return

    bar = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=Console(stderr=True),
    )
    state = {"task": None, "last": -1}

    def callback(downloaded: int, total: int) -> None:
        # A drop in `downloaded` marks the start of a new file (e.g. with --all).
        if state["task"] is None or downloaded < state["last"]:
            state["task"] = bar.add_task("downloading", total=total or None)
        bar.update(state["task"], completed=downloaded, total=total or None)
        state["last"] = downloaded

    with bar:
        yield callback
