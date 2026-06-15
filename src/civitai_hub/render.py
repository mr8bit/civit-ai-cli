"""Human-readable rendering with rich. Functions return plain strings so they
are easy to test; the CLI prints them."""
from rich.console import Console
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
    console = Console(record=True, width=100)
    console.print(renderable)
    return console.export_text()


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
