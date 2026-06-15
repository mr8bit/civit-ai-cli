# civitai-hub — Design Spec

**Date:** 2026-06-16
**Status:** Approved design, pending spec review
**One-liner:** `huggingface_hub` but for [CivitAI](https://civitai.com) — point at a model URL, inspect it, and download the model/LoRA file into a managed, deduplicated cache (and optionally a target folder).

---

## 1. Goals & non-goals

### Goals (v1)
- Resolve a CivitAI model URL (or id) and **show its info**: model type, base/parent model, available versions, and the list of files (count, sizes, formats, hashes, scan status).
- **Download** the chosen version's chosen file (checkpoint, LoRA adapter, VAE, etc.) into a managed content-addressed cache, with optional materialization into a user-chosen directory (e.g. `ComfyUI/models/loras`).
- Ship as **both** an importable Python library (`civitai_hub`) and a CLI (`civitai`), mirroring `hf_hub_download` / `snapshot_download` ergonomics.
- Be **scriptable** (smart defaults + explicit flags, no required interactivity) and **testable offline** (no real network in tests).

### Non-goals (v1, YAGNI)
- Search / browse (`civitai search`).
- `login` / credential storage subcommand, cache-management subcommands (`cache ls/rm/prune/verify`).
- Uploading models.
- A `by-hash` CLI command (the client *capability* exists for internal resolution; no user-facing command yet).
- Parallel multi-file downloads (`--all` downloads sequentially in v1; a `max_workers` knob is a later enhancement).
- NSFW browsing controls beyond sending the token so authorized mature content resolves.

---

## 2. Glossary

| Term | Meaning |
|---|---|
| **Model** | A CivitAI listing (`/models/{modelId}`). Has a `type` (Checkpoint, LORA, …) and one or more versions. |
| **Version** | An immutable revision of a model (`modelVersionId`, an integer). The download/cache key. |
| **File** | A downloadable artifact within a version (main `Model`, `VAE`, `Config`, `Training Data`, …). A version often has several. |
| **Base model** | The foundation family a version targets/was trained on — `baseModel` string (e.g. `SD 1.5`, `SDXL 1.0`, `Pony`, `Flux.1 D`) + `baseModelType` (`Standard`/`Inpainting`/`Refiner`). |
| **Parent model** | The owning CivitAI model, referenced from a version by `modelId`. Distinct from base model. |

> **Lineage caveat:** CivitAI exposes only the base-model *family*, not the exact checkpoint a LoRA was trained on or the sources of a merge. "Parent model" in the user's sense maps to **`baseModel`** (foundation) and/or **`modelId`** (owning listing); exact training lineage is **not available** from the API.

---

## 3. Grounded API reference (the facts the design relies on)

Base URL: `https://civitai.com/api/v1`. Verified against live responses during research; low-confidence items are flagged and listed in §13.

### 3.1 Endpoints used
| Endpoint | Returns | Use |
|---|---|---|
| `GET /models/{id}` | bare Model object incl. `modelVersions[]` | primary info/resolve call |
| `GET /model-versions/{id}` | single Version (richer: adds `modelId`, `model{}`, `air`) | resolve when URL gives only a version id; pin a version |
| `GET /model-versions/by-hash/{hash}` | same Version shape | internal capability only (not a v1 command) |

### 3.2 URL shapes to parse
| URL | Extract |
|---|---|
| `civitai.com/models/{modelId}/{slug}` | `modelId` (slug ignored) |
| `civitai.com/models/{modelId}` | `modelId` |
| `civitai.com/models/{modelId}?modelVersionId={vid}` | `modelId` + pinned `vid` |
| `civitai.com/api/download/models/{vid}` | path number is a **version id**, not a model id |
| bare integer | treated as `modelId` |

Rules: `modelId` via regex `civitai\.com/models/(\d+)`; pin via `[?&]modelVersionId=(\d+)`; wrong slug still resolves.

### 3.3 File object (the critical shape)
`id`, `name` (real filename incl. ext), `sizeKB` (float; **bytes = sizeKB × 1024**), `type` (`Model`/`VAE`/`Config`/`Training Data`/`Pruned Model`/`Negative`/`Text Encoder`/`Archive`), `metadata.{format,size,fp}`, `primary` (bool, **may be absent**), `hashes` (**variable keys**: SHA256/AutoV2/BLAKE3/…), `downloadUrl`, `pickleScanResult`, `virusScanResult`.

- `metadata.format`: `SafeTensor`/`PickleTensor`/`Other`/`Diffusers`/`GGUF`/`ONNX`/`Core ML`
- `metadata.size`: `full`/`pruned`/`null` (often absent for LoRA)
- `metadata.fp`: `fp16`/`fp32`/`bf16`/`fp8`/`nf4`/`null`
- **Defensive access required**: `metadata` keys and `primary`/`hashes` keys may be missing entirely.

### 3.4 Download mechanics
- URL: `GET https://civitai.com/api/download/models/{versionId}` (+ optional `?type=&format=&size=&fp=` to select a non-primary variant). Bare URL serves the version's **primary** file.
- Responds **3xx** → short-lived signed CDN URL. **Must follow redirects** and honor `Content-Disposition` for the real filename.
- **Auth:** one account API key. Metadata calls use `Authorization: Bearer <key>`. **Downloads must pass `?token=<key>` as a query param** — on the cross-domain CDN redirect, HTTP clients strip the `Authorization` header, so the bearer header alone can fail for gated files. (Medium confidence on exact strip behavior; `?token=` is the safe path.)
- **Gating:** most public files download tokenless. Auth/entitlement required for login-gated, **Early Access** (`availability != "Public"` + `earlyAccessEndsAt` in the future), and purchase-gated resources → `401`/`403`.
- **Rate limit:** `429` possible, no published numbers → exponential backoff + small inter-call delay.

---

## 4. Architecture & package layout

Library-first; the CLI is a thin shell over pure functions. Each layer has one responsibility and is unit-testable in isolation (no real network in tests).

```
civit-ai-cli/
├── pyproject.toml                 # hatchling; console_scripts: civitai = civitai_hub.cli:app
├── README.md
├── src/civitai_hub/
│   ├── __init__.py                # public API: model_info, download, __version__
│   ├── urls.py                    # parse_model_url() -> ModelRef
│   ├── client.py                  # CivitaiClient: httpx wrapper, auth, retry/backoff
│   ├── models.py                  # pydantic v2 lenient models: Model, ModelVersion, ModelFile
│   ├── resolver.py                # pick_version(), pick_files() — pure selection logic
│   ├── cache.py                   # CacheStore: blobs/<sha256> + snapshots/<ver>/ symlinks
│   ├── download.py                # stream + resume + hash verify + ?token=
│   ├── config.py                  # env/flag precedence (token, cache dir, offline, progress)
│   ├── errors.py                  # exception hierarchy
│   ├── render.py                  # rich tables / progress / dry-run output
│   └── cli.py                     # typer app: info, download
└── tests/
    ├── conftest.py                # respx fixtures + sample JSON (real shapes from research)
    ├── test_urls.py
    ├── test_client.py
    ├── test_models.py
    ├── test_resolver.py
    ├── test_cache.py
    ├── test_download.py
    └── test_cli.py
```

**Dependency direction (no upward references):**
`cli → render, config, public API` · public API → `urls → client → models`, `resolver`, `cache`, `download`. `urls`, `resolver`, `cache` are pure/IO-light.

**Stack:** `typer` (CLI), `httpx` (HTTP: redirects, streaming, range), `pydantic v2` (lenient models), `rich` (tables + progress), `platformdirs` (cache location). Dev: `pytest`, `respx` (httpx mocking), `ruff` (lint/format). Python ≥ 3.10.

---

## 5. Data models (`models.py`)

Pydantic v2 with `model_config = ConfigDict(extra="ignore", populate_by_name=True, protected_namespaces=())`; every field that the API may omit is `Optional` with a default.

> **Pydantic gotcha:** fields like `model_id` and `model_versions` start with the `model_` prefix that pydantic v2 reserves; `protected_namespaces=()` is required on every model that has such a field, or pydantic raises warnings/errors.

```python
class FileMetadata(BaseModel):
    format: str | None = None         # SafeTensor / PickleTensor / ...
    size:   str | None = None         # full / pruned / None
    fp:     str | None = None         # fp16 / fp32 / ...

class ModelFile(BaseModel):
    id: int
    name: str
    size_kb: float | None = Field(None, alias="sizeKB")
    type: str | None = None           # Model / VAE / Config / ...
    metadata: FileMetadata = FileMetadata()
    primary: bool = False
    hashes: dict[str, str] = {}
    download_url: str | None = Field(None, alias="downloadUrl")
    pickle_scan_result: str | None = Field(None, alias="pickleScanResult")
    virus_scan_result: str | None = Field(None, alias="virusScanResult")

    @property
    def sha256(self) -> str | None:     # uppercase hex; None if absent
    @property
    def size_bytes(self) -> int | None: # size_kb * 1024, rounded
    @property
    def is_safetensor(self) -> bool:

class ModelVersion(BaseModel):
    id: int
    model_id: int | None = Field(None, alias="modelId")   # only on /model-versions/{id}
    name: str | None = None
    base_model: str | None = Field(None, alias="baseModel")
    base_model_type: str | None = Field(None, alias="baseModelType")
    trained_words: list[str] = Field(default_factory=list, alias="trainedWords")
    published_at: datetime | None = Field(None, alias="publishedAt")
    status: str | None = None
    availability: str | None = None
    early_access_ends_at: datetime | None = Field(None, alias="earlyAccessEndsAt")
    download_url: str | None = Field(None, alias="downloadUrl")
    files: list[ModelFile] = Field(default_factory=list)

    @property
    def primary_file(self) -> ModelFile | None:

class Model(BaseModel):
    id: int
    name: str
    type: str | None = None
    nsfw: bool = False
    creator: dict | None = None
    tags: list[str] = Field(default_factory=list)
    stats: dict | None = None
    model_versions: list[ModelVersion] = Field(default_factory=list, alias="modelVersions")
```

`ModelInfo` (the `model_info()` return) bundles the resolved `Model`, the chosen `ModelVersion`, and a convenience `files` list.

---

## 6. Selection logic (`resolver.py`, pure)

### `pick_version(model, version_id) -> ModelVersion`
- If `version_id` given: return the matching version or raise `NotFoundError`.
- Else: among versions with `status == "Published"` (fallback: all, if none are marked), pick the **latest by `published_at` desc**; tie-break on `id` desc. (More robust than trusting array order.)

### `pick_files(version, selectors) -> list[ModelFile]`
`selectors`: `file_name`, `type`, `format`, `size` (`full`/`pruned`), `fp` (`fp16`/`fp32`), `all: bool`. Let `has_selectors` = any of `file_name/type/format/size/fp` was provided.

Algorithm, in order:
1. `candidates` = `version.files` filtered by each provided selector (case-insensitive; `fp16`/`fp32` → `metadata.fp`, `pruned`/`full` → `metadata.size`).
2. `len(candidates) == 0` → if `has_selectors` raise `NoMatchingFileError` (list available files); else the version has no files → `NoMatchingFileError`.
3. `all` is set → return `candidates`.
4. `len(candidates) == 1` → return it.
5. `len(candidates) > 1` and **not** `has_selectors` → return `[primary]` if a primary file exists, else fall back to the first `type == "Model"` SafeTensor (else the first file) **with a warning**.
6. `len(candidates) > 1` and `has_selectors` → raise `AmbiguousFileError` (list candidates + the flags to disambiguate).

---

## 7. Cache (`cache.py`)

HF-style content-addressed store, keyed by the immutable version id (no git-hash indirection needed).

```
<cache_root>/
├── CACHEDIR.TAG                              # so backup tools skip the cache
└── models/<modelId>/
    ├── blobs/<sha256>                        # content-addressed; dedups files reused across versions
    └── snapshots/<versionId>/<filename>      # symlink -> ../../blobs/<sha256>
```

- `cache_root` default: `platformdirs.user_cache_dir("civitai")` (Linux: `~/.cache/civitai`), overridable.
- `is_cached(model_id, version_id, file) -> bool`: blob for `file.sha256` exists (and, when a hash is known, matches).
- `store(tmp_path, sha256, model_id, version_id, filename) -> Path`: atomically move temp → `blobs/<sha256>`, create/refresh the snapshot symlink, return the symlink path.
- **Symlink fallback:** when symlinks are unavailable (Windows without privilege, some NAS) or `CIVITAI_DISABLE_SYMLINKS` is set, copy the blob into the snapshot path instead.
- When `file.sha256` is absent, fall back to a blob name of `file-{file.id}` and skip dedup/verify for that file.

---

## 8. Download algorithm (`download.py`)

`download_file(client, model_id, version, file, store, *, token, force, local_dir, use_symlinks, allow_unscanned, progress) -> Path`

1. **Scan gate.** If `pickle_scan_result`/`virus_scan_result` not `Success`, or `metadata.format == "PickleTensor"`: warn. Proceed only if `allow_unscanned` (in a non-TTY, refuse without the flag).
2. **Cache hit.** If `not force` and `store.is_cached(...)`: skip to step 6.
3. **Offline.** If offline mode and not cached: raise `OfflineError`.
4. **Stream.** `GET file.download_url` with `?token=` appended (if token set), `follow_redirects=True`. Write to `blobs/<sha256|fileid>.incomplete`. If a partial temp exists and the server honors ranges, send `Range: bytes=<n>-` to **resume**; else restart. Drive a `rich` progress bar (bytes, speed, ETA) unless disabled.
5. **Verify & store.** Compute SHA256 while streaming; compare to `file.sha256` (fallback AutoV2/BLAKE3 if SHA256 absent). Mismatch → delete temp, raise `HashMismatchError`. No usable hash → warn, skip verify. Then `store.store(...)`.
6. **Materialize.** If `local_dir` given: place the file there (symlink into the blob, or copy when `use_symlinks` is false / unsupported), creating dirs as needed.
7. Return the path (cache symlink, or the `local_dir` path when materialized).

`--dry-run` short-circuits before step 4: print the plan (each file: name, size, cached?/would-download, and total bytes to fetch), then exit 0.

---

## 9. Public library API (`__init__.py`)

```python
def model_info(url_or_id, *, version_id=None, token=None, cache_dir=None) -> ModelInfo: ...

def download(url_or_id, *, version_id=None, file=None, type=None, format=None,
             fp=None, size=None, all=False,
             cache_dir=None, local_dir=None, use_symlinks=True,
             token=None, force=False, allow_unscanned=False,
             dry_run=False, progress=True) -> Path | list[Path]: ...
```
Returns a `Path` for a single file, `list[Path]` when `all=True`. Mirrors `hf_hub_download` (single file) and `snapshot_download` (`all=True`).

---

## 10. CLI surface (`cli.py`, typer)

```
civitai info <url|id> [--version-id N] [--json]

civitai download <url|id>
        [--version-id N]                    # pin a version (else URL pin, else latest)
        [--file NAME] [--type T] [--format SafeTensor]
        [--fp16 | --fp32] [--pruned | --full] [--all]
        [-o, --local-dir DIR] [--no-symlinks]
        [--cache-dir DIR] [--token TOK]
        [--force] [--dry-run] [--allow-unscanned] [--no-progress] [-q, --quiet]
```

- **`info`** output (human default; `--json` for machine): model name / type / id, **base model** (`baseModel` + `baseModelType`), **parent model** (`modelId`), creator, stats, trigger words, and a **files table** headed with the count ("**N files**"), each row: name · type · format · fp · size · primary · scan-status.
- **`download`** prints resulting path(s); `--dry-run` prints the plan and exits.
- Global `--version` prints the tool version.

---

## 11. Errors & exit codes (`errors.py`)

Base `CivitaiError`. CLI catches it, prints a clean message (no traceback), and exits with a distinct code:

| Exception | Trigger | Exit | Message gist |
|---|---|---|---|
| `InvalidURLError` | unparseable url/id | 2 | "Not a CivitAI model URL or id: …" |
| `AuthRequiredError` | `401` | 3 | "Requires authentication — set `CIVITAI_TOKEN` or pass `--token`." |
| `EarlyAccessError` / `ForbiddenError` | `403`, early access | 5 | "Early Access / gated — needs a CivitAI Supporter entitlement." |
| `NotFoundError` | `404` / missing version | 4 | "Model/version not found." |
| `NoMatchingFileError` / `AmbiguousFileError` | selector mismatch | 6 | lists files + disambiguating flags |
| `HashMismatchError` | checksum fail | 7 | "Download corrupted (SHA256 mismatch); partial removed." |
| `OfflineError` | offline + uncached | 8 | "Offline and not in cache." |
| `RateLimitError` | `429` after retries | 9 | "Rate limited — retry later." |
| other `CivitaiError` | — | 1 | the message |

Early-access is **pre-checked** (`availability != "Public"` + `earlyAccessEndsAt` future) to fail fast with a clear message before attempting the download.

---

## 12. Config / env precedence (`config.py`)

`--flag` > environment > default:

| Setting | Flag | Env | Default |
|---|---|---|---|
| API token | `--token` | `CIVITAI_TOKEN` | none (anonymous) |
| Cache root | `--cache-dir` | `CIVITAI_HOME` | `platformdirs.user_cache_dir("civitai")` |
| Offline | — | `CIVITAI_OFFLINE` | off |
| Disable symlinks | `--no-symlinks` | `CIVITAI_DISABLE_SYMLINKS` | symlinks on |
| Disable progress | `--no-progress` | `CIVITAI_NO_PROGRESS` | progress on |

---

## 13. Testing strategy

TDD, fully offline via `respx` mocking `httpx`. Fixtures reuse real response shapes from the research, including the messy cases (absent `metadata` keys, missing `primary`, varying `hashes` algorithms, multi-file versions, early-access version).

- **urls**: table test of all five input shapes + invalid inputs.
- **models**: lenient parsing of messy payloads; helper props (`sha256`, `size_bytes`, `primary_file`).
- **client**: auth header set; `429`/`5xx` backoff-and-retry; `401/403/404` → typed errors (mock responses).
- **resolver**: latest-by-`publishedAt`, pinned version, each selector filter, `--all`, ambiguity, no-primary fallback, no-match.
- **cache**: blob store, snapshot symlink, dedup (same blob reused across versions), `is_cached`, symlink→copy fallback, `CACHEDIR.TAG`.
- **download**: range-resume from a partial temp, SHA256 verify pass + mismatch (temp deleted), token appended to query, redirect followed, `Content-Disposition` filename, scan-gate refusal without `--allow-unscanned`, `--dry-run` plan.
- **cli**: typer `CliRunner` — `info` table + `--json`, `download --dry-run`, error→exit-code mapping.

---

## 14. Open / low-confidence items to validate during implementation

Carried from research; resolve with a live probe when implementing the relevant layer:

- **Auth header stripping on CDN redirect** (medium) — `?token=` is the chosen safe path regardless.
- **`401` vs `403` split** for login-gated vs early-access vs purchase (low) — error mapping should degrade gracefully if the split differs.
- **`requireAuth` per-version field** (low) — use it if present, otherwise rely on `availability`/`earlyAccessEndsAt`.
- **Exhaustive `format`/`fp`/file-`type` enums** (medium) — treat as open string sets, never hard-fail on an unknown value.
- **Pagination/`sort` enums** — not needed in v1 (no search), noted for later.
```
