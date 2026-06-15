# civitai-hub — Usage Guide

Full reference for the `civitai` CLI and the `civitai_hub` library. For a quick overview see the [README](../README.md).

## Contents

- [Accepted URLs / ids](#accepted-urls--ids)
- [`civitai info`](#civitai-info)
- [`civitai download`](#civitai-download)
- [File selection rules](#file-selection-rules)
- [The cache](#the-cache)
- [Authentication & gated content](#authentication--gated-content)
- [Library API](#library-api)
- [Exit codes](#exit-codes)
- [Troubleshooting](#troubleshooting)

## Accepted URLs / ids

Every command accepts any of these for its first argument:

| Input | Resolves to |
|---|---|
| `https://civitai.com/models/580857/some-slug` | model `580857`, latest version |
| `https://civitai.com/models/580857` | model `580857`, latest version |
| `https://civitai.com/models/580857?modelVersionId=649002` | model `580857`, version `649002` |
| `https://civitai.com/api/download/models/649002` | version `649002` (its parent model is looked up) |
| `580857` | model `580857`, latest version |

The slug is cosmetic and ignored. A `--version-id` flag overrides any version implied by the URL.

## `civitai info`

```
civitai info <url|id> [--version-id N] [--json]
```

Prints the model name and id, type, creator, **base model** (`baseModel` + `baseModelType`), **parent model id**, the selected version, trigger words, download/like stats, and a table of every file in the version: name · type · format · precision (`fp`) · size · whether it's primary · scan status.

- `--version-id N` — inspect a specific version instead of the latest.
- `--json` — emit machine-readable JSON (`{"model": ..., "version": ...}`) instead of the table.

## `civitai download`

```
civitai download <url|id>
    [--version-id N]
    [--file NAME] [--type T] [--format SafeTensor]
    [--fp16 | --fp32] [--pruned | --full] [--all]
    [-o, --local-dir DIR] [--no-symlinks]
    [--cache-dir DIR] [--token TOK]
    [--force] [--dry-run] [--allow-unscanned]
    [--no-progress] [-q, --quiet]
```

| Flag | Effect |
|---|---|
| `--version-id N` | Download a specific version (else the URL pin, else the latest). |
| `--file NAME` | Select the exact file by name. |
| `--type T` | Filter by file role (`Model`, `VAE`, `Config`, `Training Data`, …). |
| `--format F` | Filter by format (`SafeTensor`, `PickleTensor`, …). |
| `--fp16` / `--fp32` | Select a precision variant. |
| `--pruned` / `--full` | Select a size variant. |
| `--all` | Download **every** file in the version (sequential). |
| `-o, --local-dir DIR` | Also place the file(s) into `DIR` (symlink, or copy with `--no-symlinks`). |
| `--cache-dir DIR` | Override the cache root for this run. |
| `--token TOK` | API token (else `CIVITAI_TOKEN`). |
| `--force` | Re-download even if already cached. |
| `--dry-run` | Print the plan (files, sizes, what's cached, total bytes) and exit. |
| `--allow-unscanned` | Proceed with a file CivitAI flagged unsafe. |
| `--no-progress` | Disable the progress bar. |
| `-q, --quiet` | Suppress the printed path(s). |

The resulting local path(s) are written to **stdout**; the progress bar renders on **stderr**, so `$(civitai download …)` captures just the path.

## File selection rules

A CivitAI version can bundle several files (a full + pruned checkpoint, fp16/fp32, a VAE, a training-data zip…). Selection works as follows:

1. Start from the version's files and apply every provided filter (`--file/--type/--format/--fp16|--fp32/--pruned|--full`), case-insensitively.
2. **No matches** → error listing the available files.
3. `--all` → every matching file.
4. **Exactly one match** → that file.
5. **Several matches and no filters** → the file marked `primary` (or, if none is marked, the first `Model`-type `.safetensors`, with a warning).
6. **Several matches with filters** → error asking you to narrow further (or use `--all`).

Run `civitai info <url>` or `civitai download <url> --dry-run` first to see exactly what's available.

## The cache

Downloads are content-addressed and deduplicated:

```
$CIVITAI_HOME/                              # default: ~/.cache/civitai (Linux)
├── CACHEDIR.TAG                            # marks the dir as a cache for backup tools
└── models/<modelId>/
    ├── blobs/<sha256>                      # one blob per unique file content
    └── snapshots/<versionId>/<filename>    # symlink → ../../blobs/<sha256>
```

- A file reused across versions is stored **once**; each version gets a snapshot symlink.
- A cache hit (the blob already exists) skips the network entirely. Use `--force` to re-download.
- `--local-dir DIR` materializes the blob into `DIR` (a symlink, or a copy with `--no-symlinks` / `CIVITAI_DISABLE_SYMLINKS=1` for filesystems without symlink support).
- Interrupted downloads resume via HTTP range requests; every completed download is SHA256-verified, and a mismatch deletes the partial so the next run starts clean.

## Authentication & gated content

Create an API key at <https://civitai.com/user/account>, then set `CIVITAI_TOKEN` or pass `--token`.

- **Metadata** calls send `Authorization: Bearer <token>`.
- **Downloads** send the token as a `?token=` query parameter, because CivitAI redirects to a signed CDN host that strips the `Authorization` header.
- **Early-access / gated** versions are detected (`availability != "Public"` with a future `earlyAccessEndsAt`) and fail fast with a clear message before any download — these require a CivitAI Supporter entitlement on your account.

## Library API

```python
import civitai_hub

def model_info(url_or_id, *, version_id=None, token=None, cache_dir=None) -> ModelInfo: ...

def download(
    url_or_id, *,
    version_id=None, file=None, type=None, format=None, fp=None, size=None, all=False,
    cache_dir=None, local_dir=None, use_symlinks=True,
    token=None, force=False, allow_unscanned=False,
    dry_run=False, progress=True, progress_cb=None,
): ...  # -> Path | list[Path] | list[PlanItem] (when dry_run=True)
```

`ModelInfo` carries `.model`, `.version`, and `.files`. Pass `progress_cb=lambda downloaded, total: ...` to drive your own progress UI.

## Exit codes

The CLI prints a clean error (no traceback) to stderr and exits with:

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | generic error |
| 2 | invalid URL/id (or usage error) |
| 3 | authentication required (`401`) — set `CIVITAI_TOKEN` |
| 4 | model/version not found (`404`) |
| 5 | forbidden / early access (`403`) |
| 6 | no matching file / ambiguous selection |
| 7 | download corrupted (SHA256 mismatch) |
| 8 | offline and not cached |
| 9 | rate limited (`429`) |

## Troubleshooting

- **"Requires authentication"** — the resource needs a token; set `CIVITAI_TOKEN` or pass `--token`.
- **"Early access / gated"** — the version is behind CivitAI's early-access window; it requires a Supporter entitlement on your account.
- **"Multiple files match"** — narrow with `--fp16/--fp32`, `--pruned/--full`, `--format`, or `--file`, or use `--all`. Run `--dry-run` to list candidates.
- **"SHA256 mismatch"** — the download was corrupted; the partial is removed automatically — just retry.
- **Offline** — set `CIVITAI_OFFLINE=1` to serve only from the cache; uncached requests then error instead of hitting the network.
