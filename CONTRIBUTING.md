# Contributing

Thanks for helping improve `civitai-hub`. This is a small, layered Python project — please keep changes focused and tested.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Everyday commands

```bash
pytest                                              # full suite (offline)
pytest tests/test_resolver.py::test_fp_selector -v  # a single test
ruff check src tests                                # lint
CIVITAI_LIVE=1 pytest tests/test_live.py -v          # opt-in: hits the real CivitAI API
```

CI runs `ruff check` and `pytest` on Python 3.10–3.13 (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)). The suite is fully offline — `httpx` is mocked with `respx`, so no test touches the network. Keep it that way; the only live test is gated behind `CIVITAI_LIVE=1`.

## Architecture

Library-first; the Typer CLI (`cli.py`) is a thin wrapper over the public API in `__init__.py`. Each module has one responsibility and is unit-tested in isolation:

| Module | Responsibility |
|---|---|
| `urls.py` | parse a CivitAI URL/id → `ModelRef` |
| `client.py` | `httpx` wrapper: auth header, retry/backoff, status → typed errors |
| `models.py` | lenient `pydantic` models for CivitAI responses + helper properties |
| `resolver.py` | pick the version and the file(s) from a model |
| `cache.py` | content-addressed blob store + snapshot symlinks |
| `download.py` | availability/scan gates, stream + range-resume + SHA256 verify + materialize |
| `config.py` | settings resolution (flag → env → default) |
| `errors.py` | exception hierarchy carrying CLI exit codes |
| `render.py` | `rich` tables, dry-run output, and the download progress bar |
| `cli.py` | the `civitai` Typer app (`info`, `download`, `base`) |

Dependencies only point "down": `cli → public API → urls → client → models`, plus `resolver`/`cache`/`download`. No module imports a layer above it.

The original design and step-by-step build plan live in `docs/superpowers/specs/` and `docs/superpowers/plans/`.

## Conventions

- **Tests first.** Add or update a test for any behavior change; the project was built test-driven.
- **Keep it offline.** Mock HTTP with `respx`; never add a test that reaches the network outside `test_live.py`.
- **Lenient parsing.** CivitAI's fields are inconsistent — keep models tolerant (`extra="ignore"`, optionals defaulted) rather than asserting shapes.
- **Small, focused modules.** If a file grows beyond one clear responsibility, split it.
- Run `ruff check src tests` before opening a PR.

## Pull requests

1. Branch from `main`.
2. Make the change with tests; ensure `pytest` and `ruff check src tests` are green.
3. Open a PR describing what changed and how you verified it. CI must pass.
