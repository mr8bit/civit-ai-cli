# civitai-hub — Usage Guide

Full reference for the `civitai` CLI and the `civitai_hub` library. For a quick overview see the [README](../README.md).

## Contents

- [Accepted URLs / ids](#accepted-urls--ids)
- [`civitai info`](#civitai-info)
- [`civitai download`](#civitai-download)
- [`civitai base`](#civitai-base)
- [`civitai search`](#civitai-search)
- [`civitai by-hash`](#civitai-by-hash)
- [`civitai login` / `logout` / `config`](#civitai-login--logout--config)
- [`civitai cache`](#civitai-cache)
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

**Mirror.** `civitai.red` URLs (a transparent CivitAI proxy) are accepted identically and route the API + downloads through that host automatically. For bare ids or `search`, set `CIVITAI_HOST=civitai.red`. Only `civitai.com` and `civitai.red` are trusted.

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

## `civitai base`

Find the **base checkpoints** a model (typically a LoRA) runs on.

```
civitai base <url|id>
    [--version-id N] [--limit 10] [--json]
    [--download N] [-o, --local-dir DIR] [--cache-dir DIR] [--token TOK] [--no-progress]
```

CivitAI only records a model's base model as a **family string** (`baseModel`, e.g. `Pony`, `SDXL 1.0`, `ZImageBase`) — there is **no direct link** from a LoRA to the exact checkpoint it was trained on. So `base` reads that family and searches CivitAI for checkpoints of the same family (`GET /api/v1/models?types=Checkpoint&baseModels=<family>&sort=Most Downloaded`), most-downloaded first:

```console
$ civitai base 580857 --limit 3
For:        Realistic Skin Texture style ... (#580857, LORA)
Base model: ZImageBase
Matches:    3 checkpoints
┏━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ # ┃ id      ┃ name                         ┃ base       ┃ downloads ┃
┡━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ 1 │ 958009  │ RedCraft | 红潮 | ERNIE …    │ ZImageBase │   240,687 │
│ 2 │ 2384856 │ Moody Wild Mix (ZIB/ZID)     │ ZImageBase │    36,692 │
│ 3 │ 2342797 │ Z Image Base                 │ ZImageBase │    16,186 │
└───┴─────────┴──────────────────────────────┴────────────┴───────────┘
```

| Flag | Effect |
|---|---|
| `--limit N` | How many checkpoints to list (default 10). |
| `--json` | Machine-readable output (`{"source": ..., "candidates": [...]}`). |
| `--download N` | Download the **Nth listed** checkpoint (1-based) — equivalent to `civitai download <that id>`. |
| `-o, --local-dir` / `--cache-dir` / `--token` / `--no-progress` | As for `download`, applied to the `--download` fetch. |

So the full loop is: `civitai base <lora>` → pick a number → `civitai base <lora> --download <N> -o <your models folder>` (or copy the listed id into `civitai download <id>`).

> Note: the displayed list is "most downloaded" of that family — popularity, not a guarantee of compatibility. Pick the checkpoint that matches your intended style/version.

## `civitai search`

```
civitai search [QUERY] [--type T] [--base-model B] [--sort S] [--limit N] [--token TOK] [--json]
```

Search CivitAI models from the terminal. `--type` (Checkpoint/LORA/…), `--base-model` (e.g. `Pony`, `SDXL 1.0`), `--sort` (`Most Downloaded`/`Highest Rated`/`Newest`), `--limit` (paginates past one page if needed). Prints a table (id · name · type · base · downloads) or `--json`.

## `civitai by-hash`

```
civitai by-hash <SHA256 | AutoV2 | path/to/file> [--token TOK] [--json]
```

Identify a model from a hash, or from a **local file** (it computes the SHA256 and looks it up) — the reverse of `download`. Useful for "what is this orphaned `.safetensors`?". Prints the same view as `info`.

## `civitai login` / `logout` / `config`

```
civitai login [--token TOK]     # prompts if --token omitted; saves to a 0600 file in the config dir
civitai logout                  # deletes the stored token
civitai config                  # show resolved cache dir, token presence, flags
```

Token precedence is **`--token` flag > `CIVITAI_TOKEN` env > stored login file > anonymous**.

## `civitai cache`

```
civitai cache ls [--json]       # list cached files (model · version · file · size · sha)
civitai cache verify            # re-hash every blob; non-zero exit if any is corrupt
civitai cache rm <modelId>      # evict a model's cached files
civitai cache prune             # remove leftover .incomplete temps and dangling links
```

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

- **Metadata** and **download** requests both send `Authorization: Bearer <token>`, and only ever to `civitai.com` (the download URL's host is validated first). On the cross-host CDN redirect httpx drops the header (the CDN URL is already signed), so the token never reaches a third-party host or appears in a URL/log.
- **Early-access / gated** versions are detected (`availability != "Public"` with a future `earlyAccessEndsAt`) and fail fast with a clear message before any download — these require a CivitAI Supporter entitlement on your account.

## Library API

```python
import civitai_hub

def model_info(url_or_id, *, version_id=None, token=None) -> ModelInfo: ...

def download(
    url_or_id, *,
    version_id=None, file=None, type=None, format=None, fp=None, size=None, all=False,
    cache_dir=None, local_dir=None, use_symlinks=True,
    token=None, force=False, allow_unscanned=False,
    dry_run=False, progress_cb=None,
): ...  # -> Path | list[Path] | list[PlanItem] (when dry_run=True)

def find_base_models(url_or_id, *, version_id=None, limit=10, token=None) -> BaseModelMatches: ...
```

`ModelInfo` carries `.model`, `.version`, and `.files`. `BaseModelMatches` carries `.source`, `.version`, `.base_model`, and `.candidates` (the `civitai base` command's programmatic form). Pass `progress_cb=lambda downloaded, total: ...` to drive your own progress UI.

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
| 10 | network/transport error (connection/timeout) |

## Troubleshooting

- **"Requires authentication"** — the resource needs a token; set `CIVITAI_TOKEN` or pass `--token`.
- **"Early access / gated"** — the version is behind CivitAI's early-access window; it requires a Supporter entitlement on your account.
- **"Multiple files match"** — narrow with `--fp16/--fp32`, `--pruned/--full`, `--format`, or `--file`, or use `--all`. Run `--dry-run` to list candidates.
- **"SHA256 mismatch"** — the download was corrupted; the partial is removed automatically — just retry.
- **Offline** — set `CIVITAI_OFFLINE=1` to serve only from the cache; uncached requests then error instead of hitting the network.
