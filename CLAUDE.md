# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`civitai_hub` — an importable Python library + `civitai` CLI: "huggingface_hub but for CivitAI". Inspect a model URL and download its checkpoint/LoRA into a deduplicated managed cache.

## Commands

- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- Run all tests: `pytest`
- Run one test: `pytest tests/test_resolver.py::test_fp_selector -v`
- Lint: `ruff check src tests`
- Live smoke (hits real API, opt-in): `CIVITAI_LIVE=1 pytest tests/test_live.py -v`
- Run the CLI: `civitai info <url>` / `civitai download <url>`

## Architecture

Library-first; the Typer CLI (`cli.py`, commands `info`/`download`/`base`) is a thin wrapper over the public API in `__init__.py` (`model_info`, `download`, `find_base_models`). Layered, each unit-tested with `respx` (no real network in tests):

`urls` (parse URL→ModelRef) → `client` (httpx + auth + retry + error mapping) → `models` (lenient pydantic). Plus `resolver` (pick version/file), `cache` (content-addressed blobs + snapshot symlinks, keyed by immutable version id), `download` (stream + range-resume + SHA256 verify + materialize), `config` (flag>env>default), `errors` (exit-code-bearing hierarchy), `render` (rich tables).

## CivitAI API notes that bit us

- Downloads `302`-redirect to a CDN that strips the `Authorization` header → the download endpoint uses `?token=`, while metadata calls use `Bearer`.
- File `metadata`/`hashes`/`primary` fields are inconsistent — models are lenient (`extra=ignore`, all optionals defaulted). Fields like `model_id`/`model_versions` need pydantic `protected_namespaces=()`.
- "Parent model" = `modelId` (owning listing); "base model" = `baseModel` string family. Exact LoRA→checkpoint lineage is not exposed by the API.

Design docs: `docs/superpowers/specs/2026-06-16-civitai-cli-design.md`, plan: `docs/superpowers/plans/2026-06-16-civitai-cli.md`.
