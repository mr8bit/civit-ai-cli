#!/usr/bin/env python3
"""Generate terminal screenshots for the README from live CivitAI data.

Renders real command output via rich -> SVG -> PNG (PNGs render reliably on
GitHub). Requires network and `pip install cairosvg`.

Usage:  python scripts/gen_screenshots.py
"""
from __future__ import annotations

import pathlib

import cairosvg
from rich.console import Console

import civitai_hub
import civitai_hub.render as render

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "docs" / "assets"
MODEL = "580857"  # the LoRA used throughout the README/docs


def _capture_svg(fn, *args, title: str, width: int = 104) -> str:
    """Run a render_* function, tee-ing each rich renderable it draws into a
    recording console, and return the resulting SVG (with terminal chrome)."""
    console = Console(record=True, width=width)
    original = render._capture

    def tee(renderable):
        console.print(renderable)
        return original(renderable)

    render._capture = tee
    try:
        fn(*args)
    finally:
        render._capture = original
    return console.export_svg(title=title)


def _write_png(svg: str, name: str) -> None:
    # rich hard-codes "Fira Code" (not installed here); swap in a locally
    # available monospace that ships the box-drawing glyphs so the table borders
    # rasterize instead of becoming tofu.
    # cairosvg renders a whole <text> run with the first resolvable font (no
    # per-glyph fallback), so the primary font must carry both box-drawing and
    # CJK glyphs. Noto Sans Mono CJK does.
    svg = svg.replace(
        "Fira Code, monospace",
        "Noto Sans Mono CJK SC, DejaVu Sans Mono, monospace",
    )
    out = ASSETS / name
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(out), scale=2)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)

    info = civitai_hub.model_info(MODEL)
    _write_png(
        _capture_svg(render.render_model_info, info, title=f"civitai info {MODEL}"),
        "info.png",
    )

    matches = civitai_hub.find_base_models(MODEL, limit=5)
    _write_png(
        _capture_svg(render.render_base_models, matches, title=f"civitai base {MODEL}"),
        "base.png",
    )


if __name__ == "__main__":
    main()
