# civitai-hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `civitai_hub` — an importable Python library + `civitai` CLI that inspects a CivitAI model URL and downloads its model/LoRA file into a deduplicated managed cache (and optional target dir), mirroring `huggingface_hub`.

**Architecture:** Library-first with a thin Typer CLI. Layers (each independently unit-tested, no real network in tests): `urls` → `client` → `models`, plus `resolver`, `cache`, `download`, `config`, `errors`, `render`, and `cli`. See `docs/superpowers/specs/2026-06-16-civitai-cli-design.md`.

**Tech Stack:** Python ≥3.10 · httpx · pydantic v2 · typer · rich · platformdirs · pytest + respx · ruff. Packaged with hatchling; console command `civitai`.

---

## File structure (created across tasks)

| File | Responsibility |
|---|---|
| `pyproject.toml` | packaging, deps, console script, pytest/ruff config |
| `src/civitai_hub/__init__.py` | public API: `model_info`, `download`, `__version__` |
| `src/civitai_hub/errors.py` | exception hierarchy with `exit_code` |
| `src/civitai_hub/urls.py` | `parse_model_url` → `ModelRef` |
| `src/civitai_hub/models.py` | pydantic models + `ModelInfo`, `PlanItem` |
| `src/civitai_hub/config.py` | `Settings` + `resolve_settings` (flag>env>default) |
| `src/civitai_hub/client.py` | `CivitaiClient` (httpx, auth, retry, error mapping) |
| `src/civitai_hub/resolver.py` | `pick_version`, `pick_files`, `FileSelectors` |
| `src/civitai_hub/cache.py` | `CacheStore` (blobs + snapshot symlinks) |
| `src/civitai_hub/download.py` | `download_file`, stream/resume/verify/materialize |
| `src/civitai_hub/render.py` | rich tables / dry-run / progress |
| `src/civitai_hub/cli.py` | typer app: `info`, `download` |
| `tests/conftest.py` | sample JSON fixtures (real CivitAI shapes) |
| `tests/test_*.py` | one module per layer |

**Note on TDD:** each task writes tests first, watches them fail, implements, watches them pass, commits. Run all commands from the repo root `/home/mr8bit/Projects/civit-ai-cli`. Use a virtualenv: `python -m venv .venv && source .venv/bin/activate`.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/civitai_hub/__init__.py` (temporary stub)
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing test**

`tests/test_smoke.py`:
```python
def test_package_imports_and_has_version():
    import civitai_hub

    assert isinstance(civitai_hub.__version__, str)
    assert civitai_hub.__version__
```

- [ ] **Step 2: Create packaging + stub**

`pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "civitai-hub"
version = "0.1.0"
description = "huggingface_hub but for CivitAI — inspect and download models/LoRAs"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.6",
    "typer>=0.15",
    "rich>=13.7",
    "platformdirs>=4.2",
]

[project.optional-dependencies]
dev = ["pytest>=8", "respx>=0.21", "ruff>=0.5"]

[project.scripts]
civitai = "civitai_hub.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/civitai_hub"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.ruff]
line-length = 100
target-version = "py310"
```

`src/civitai_hub/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/__init__.py`: (empty file)

Create a placeholder `README.md` so the build backend is happy:
```markdown
# civitai-hub

huggingface_hub, but for CivitAI. See `docs/superpowers/specs/`.
```

- [ ] **Step 3: Install in editable mode + run test**

Run:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_smoke.py -v
```
Expected: PASS (1 passed).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: scaffold package, deps, and smoke test"
```

---

### Task 2: Error hierarchy

**Files:**
- Create: `src/civitai_hub/errors.py`
- Test: `tests/test_errors.py`

- [ ] **Step 1: Write the failing test**

`tests/test_errors.py`:
```python
import pytest

from civitai_hub import errors


def test_all_errors_subclass_base_and_have_exit_codes():
    classes = [
        errors.InvalidURLError, errors.AuthRequiredError, errors.NotFoundError,
        errors.ForbiddenError, errors.EarlyAccessError, errors.NoMatchingFileError,
        errors.AmbiguousFileError, errors.HashMismatchError, errors.OfflineError,
        errors.RateLimitError,
    ]
    for cls in classes:
        assert issubclass(cls, errors.CivitaiError)
        assert isinstance(cls.exit_code, int)


def test_exit_codes_are_distinct_per_category():
    assert errors.AuthRequiredError.exit_code == 3
    assert errors.NotFoundError.exit_code == 4
    assert errors.HashMismatchError.exit_code == 7
    assert errors.EarlyAccessError.exit_code == errors.ForbiddenError.exit_code


def test_raising_carries_message():
    with pytest.raises(errors.NotFoundError, match="missing"):
        raise errors.NotFoundError("missing model")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_errors.py -v`
Expected: FAIL (ModuleNotFoundError: civitai_hub.errors).

- [ ] **Step 3: Implement**

`src/civitai_hub/errors.py`:
```python
"""Exception hierarchy. Each maps to a distinct CLI exit code."""


class CivitaiError(Exception):
    exit_code = 1


class InvalidURLError(CivitaiError):
    exit_code = 2


class AuthRequiredError(CivitaiError):
    exit_code = 3


class NotFoundError(CivitaiError):
    exit_code = 4


class ForbiddenError(CivitaiError):
    exit_code = 5


class EarlyAccessError(ForbiddenError):
    exit_code = 5


class NoMatchingFileError(CivitaiError):
    exit_code = 6


class AmbiguousFileError(CivitaiError):
    exit_code = 6


class HashMismatchError(CivitaiError):
    exit_code = 7


class OfflineError(CivitaiError):
    exit_code = 8


class RateLimitError(CivitaiError):
    exit_code = 9
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_errors.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/civitai_hub/errors.py tests/test_errors.py
git commit -m "feat: error hierarchy with exit codes"
```

---

### Task 3: URL parsing

**Files:**
- Create: `src/civitai_hub/urls.py`
- Test: `tests/test_urls.py`

- [ ] **Step 1: Write the failing test**

`tests/test_urls.py`:
```python
import pytest

from civitai_hub.errors import InvalidURLError
from civitai_hub.urls import ModelRef, parse_model_url


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://civitai.com/models/580857/realistic-skin", ModelRef(580857, None)),
        ("https://civitai.com/models/580857", ModelRef(580857, None)),
        ("https://civitai.com/models/580857?modelVersionId=649002", ModelRef(580857, 649002)),
        ("https://civitai.com/models/580857/slug?modelVersionId=649002&foo=1", ModelRef(580857, 649002)),
        ("https://civitai.com/api/download/models/649002", ModelRef(None, 649002)),
        ("580857", ModelRef(580857, None)),
        ("  https://civitai.com/models/580857  ", ModelRef(580857, None)),
    ],
)
def test_parse_variants(url, expected):
    assert parse_model_url(url) == expected


@pytest.mark.parametrize("bad", ["", "   ", "https://example.com/x", "not a url"])
def test_parse_invalid(bad):
    with pytest.raises(InvalidURLError):
        parse_model_url(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_urls.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

`src/civitai_hub/urls.py`:
```python
"""Parse CivitAI URLs / ids into a ModelRef."""
import re
from dataclasses import dataclass

from .errors import InvalidURLError

_DOWNLOAD_RE = re.compile(r"civitai\.com/api/download/models/(\d+)")
_MODEL_RE = re.compile(r"civitai\.com/models/(\d+)")
_VERSION_QS_RE = re.compile(r"[?&]modelVersionId=(\d+)")


@dataclass(frozen=True)
class ModelRef:
    """A reference to a model and (optionally) a pinned version.

    model_id is None only for api/download URLs that carry just a version id.
    """

    model_id: int | None
    version_id: int | None = None


def parse_model_url(value: str) -> ModelRef:
    s = (value or "").strip()
    if not s:
        raise InvalidURLError("Empty model reference")

    if s.isdigit():
        return ModelRef(model_id=int(s))

    m = _DOWNLOAD_RE.search(s)
    if m:
        return ModelRef(model_id=None, version_id=int(m.group(1)))

    m = _MODEL_RE.search(s)
    if m:
        vq = _VERSION_QS_RE.search(s)
        version_id = int(vq.group(1)) if vq else None
        return ModelRef(model_id=int(m.group(1)), version_id=version_id)

    raise InvalidURLError(f"Not a CivitAI model URL or id: {s!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_urls.py -v`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add src/civitai_hub/urls.py tests/test_urls.py
git commit -m "feat: parse CivitAI model/version URLs"
```

---

### Task 4: Data models

**Files:**
- Create: `src/civitai_hub/models.py`
- Test: `tests/test_models.py`
- Create: `tests/conftest.py` (shared fixtures used by later tasks too)

- [ ] **Step 1: Write the failing test + fixtures**

`tests/conftest.py`:
```python
"""Sample CivitAI payloads using real (sometimes messy) response shapes."""
import pytest


@pytest.fixture
def model_payload():
    # A LoRA model with one version; primary flag present, lean metadata.
    return {
        "id": 580857,
        "name": "Realistic Skin Texture Style",
        "type": "LORA",
        "nsfw": False,
        "creator": {"username": "someone", "image": None},
        "tags": ["style", "skin"],
        "stats": {"downloadCount": 1234, "thumbsUpCount": 56},
        "modelVersions": [
            {
                "id": 649001,
                "name": "v1.0",
                "baseModel": "SDXL 1.0",
                "baseModelType": "Standard",
                "status": "Published",
                "publishedAt": "2024-06-01T10:00:00.000Z",
                "trainedWords": ["detailed skin"],
                "downloadUrl": "https://civitai.com/api/download/models/649001",
                "files": [
                    {
                        "id": 11,
                        "name": "skin-v1.safetensors",
                        "sizeKB": 223232.0,
                        "type": "Model",
                        "metadata": {"format": "SafeTensor"},
                        "primary": True,
                        "hashes": {"SHA256": "a" * 64, "AutoV2": "b" * 10},
                        "downloadUrl": "https://civitai.com/api/download/models/649001",
                        "pickleScanResult": "Success",
                        "virusScanResult": "Success",
                    }
                ],
            },
            {
                "id": 649002,
                "name": "v2.0",
                "baseModel": "Pony",
                "status": "Published",
                "publishedAt": "2024-08-01T10:00:00.000Z",
                "trainedWords": [],
                "downloadUrl": "https://civitai.com/api/download/models/649002",
                "files": [
                    {
                        "id": 22,
                        "name": "skin-v2-fp16.safetensors",
                        "sizeKB": 100000.0,
                        "type": "Model",
                        "metadata": {"format": "SafeTensor", "size": "pruned", "fp": "fp16"},
                        "primary": True,
                        "hashes": {"SHA256": "c" * 64},
                        "downloadUrl": "https://civitai.com/api/download/models/649002",
                        "pickleScanResult": "Success",
                        "virusScanResult": "Success",
                    },
                    {
                        "id": 23,
                        "name": "skin-v2-fp32.safetensors",
                        "sizeKB": 200000.0,
                        "type": "Model",
                        "metadata": {"format": "SafeTensor", "size": "full", "fp": "fp32"},
                        # no 'primary' key at all (must default to False)
                        "hashes": {"SHA256": "d" * 64},
                        "downloadUrl": "https://civitai.com/api/download/models/649002",
                        "pickleScanResult": "Success",
                        "virusScanResult": "Success",
                    },
                ],
            },
        ],
    }


@pytest.fixture
def version_payload():
    # Shape returned by /model-versions/{id}: richer, carries modelId.
    return {
        "id": 649002,
        "modelId": 580857,
        "name": "v2.0",
        "baseModel": "Pony",
        "status": "Published",
        "publishedAt": "2024-08-01T10:00:00.000Z",
        "trainedWords": [],
        "model": {"name": "Realistic Skin Texture Style", "type": "LORA", "nsfw": False},
        "downloadUrl": "https://civitai.com/api/download/models/649002",
        "files": [
            {
                "id": 22,
                "name": "skin-v2-fp16.safetensors",
                "sizeKB": 100000.0,
                "type": "Model",
                "metadata": {"format": "SafeTensor", "size": "pruned", "fp": "fp16"},
                "primary": True,
                "hashes": {"SHA256": "c" * 64},
                "downloadUrl": "https://civitai.com/api/download/models/649002",
                "pickleScanResult": "Success",
                "virusScanResult": "Success",
            }
        ],
    }
```

`tests/test_models.py`:
```python
from civitai_hub.models import Model, ModelVersion


def test_model_parses_and_aliases(model_payload):
    model = Model.model_validate(model_payload)
    assert model.id == 580857
    assert model.type == "LORA"
    assert len(model.model_versions) == 2


def test_file_helper_properties(model_payload):
    model = Model.model_validate(model_payload)
    v1 = model.model_versions[0]
    f = v1.files[0]
    assert f.sha256 == "A" * 64  # uppercased
    assert f.size_bytes == round(223232.0 * 1024)
    assert f.is_safetensor is True
    assert v1.primary_file is f


def test_missing_primary_defaults_false_and_metadata_safe(model_payload):
    v2 = Model.model_validate(model_payload).model_versions[1]
    fp32_file = v2.files[1]
    assert fp32_file.primary is False
    assert fp32_file.metadata.fp == "fp32"
    # file with absent metadata keys still parses
    assert v2.files[0].metadata.size == "pruned"


def test_version_endpoint_shape_carries_model_id(version_payload):
    v = ModelVersion.model_validate(version_payload)
    assert v.model_id == 580857
    assert v.base_model == "Pony"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

`src/civitai_hub/models.py`:
```python
"""Pydantic models for CivitAI responses. Lenient: every optional API field
defaults, because metadata/hashes/primary are inconsistent across responses."""
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

_CFG = ConfigDict(extra="ignore", populate_by_name=True, protected_namespaces=())


class FileMetadata(BaseModel):
    model_config = _CFG

    format: str | None = None
    size: str | None = None
    fp: str | None = None


class ModelFile(BaseModel):
    model_config = _CFG

    id: int
    name: str
    size_kb: float | None = Field(default=None, alias="sizeKB")
    type: str | None = None
    metadata: FileMetadata = Field(default_factory=FileMetadata)
    primary: bool = False
    hashes: dict[str, str] = Field(default_factory=dict)
    download_url: str | None = Field(default=None, alias="downloadUrl")
    pickle_scan_result: str | None = Field(default=None, alias="pickleScanResult")
    virus_scan_result: str | None = Field(default=None, alias="virusScanResult")

    @property
    def sha256(self) -> str | None:
        for key, value in self.hashes.items():
            if key.upper() == "SHA256":
                return value.upper()
        return None

    @property
    def size_bytes(self) -> int | None:
        return round(self.size_kb * 1024) if self.size_kb is not None else None

    @property
    def is_safetensor(self) -> bool:
        return (self.metadata.format or "") == "SafeTensor"


class ModelVersion(BaseModel):
    model_config = _CFG

    id: int
    model_id: int | None = Field(default=None, alias="modelId")
    name: str | None = None
    base_model: str | None = Field(default=None, alias="baseModel")
    base_model_type: str | None = Field(default=None, alias="baseModelType")
    trained_words: list[str] = Field(default_factory=list, alias="trainedWords")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    status: str | None = None
    availability: str | None = None
    early_access_ends_at: datetime | None = Field(default=None, alias="earlyAccessEndsAt")
    download_url: str | None = Field(default=None, alias="downloadUrl")
    files: list[ModelFile] = Field(default_factory=list)

    @property
    def primary_file(self) -> ModelFile | None:
        return next((f for f in self.files if f.primary), None)


class Model(BaseModel):
    model_config = _CFG

    id: int
    name: str
    type: str | None = None
    nsfw: bool = False
    creator: dict | None = None
    tags: list[str] = Field(default_factory=list)
    stats: dict | None = None
    model_versions: list[ModelVersion] = Field(default_factory=list, alias="modelVersions")


@dataclass
class ModelInfo:
    """Return value of the public model_info()."""

    model: Model
    version: ModelVersion
    files: list[ModelFile]


@dataclass
class PlanItem:
    """One line of a --dry-run plan."""

    file_name: str
    size_bytes: int | None
    cached: bool
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/civitai_hub/models.py tests/test_models.py tests/conftest.py
git commit -m "feat: lenient pydantic models + fixtures"
```

---

### Task 5: Config / settings precedence

**Files:**
- Create: `src/civitai_hub/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from pathlib import Path

from civitai_hub.config import resolve_settings


def test_flag_beats_env(monkeypatch):
    monkeypatch.setenv("CIVITAI_TOKEN", "from-env")
    s = resolve_settings(token="from-flag")
    assert s.token == "from-flag"


def test_env_used_when_no_flag(monkeypatch):
    monkeypatch.setenv("CIVITAI_TOKEN", "from-env")
    monkeypatch.setenv("CIVITAI_HOME", "/tmp/civ-cache")
    s = resolve_settings()
    assert s.token == "from-env"
    assert s.cache_dir == Path("/tmp/civ-cache")


def test_defaults(monkeypatch):
    for var in ["CIVITAI_TOKEN", "CIVITAI_HOME", "CIVITAI_OFFLINE",
                "CIVITAI_DISABLE_SYMLINKS", "CIVITAI_NO_PROGRESS"]:
        monkeypatch.delenv(var, raising=False)
    s = resolve_settings()
    assert s.token is None
    assert s.offline is False
    assert s.use_symlinks is True
    assert s.progress is True
    assert "civitai" in str(s.cache_dir).lower()


def test_bool_env_parsing(monkeypatch):
    monkeypatch.setenv("CIVITAI_OFFLINE", "1")
    monkeypatch.setenv("CIVITAI_DISABLE_SYMLINKS", "true")
    s = resolve_settings()
    assert s.offline is True
    assert s.use_symlinks is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

`src/civitai_hub/config.py`:
```python
"""Resolve settings with precedence: explicit arg > environment > default."""
import os
from dataclasses import dataclass
from pathlib import Path

import platformdirs


@dataclass
class Settings:
    token: str | None
    cache_dir: Path
    offline: bool
    use_symlinks: bool
    progress: bool


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_settings(
    *,
    token: str | None = None,
    cache_dir: str | os.PathLike | None = None,
    offline: bool | None = None,
    use_symlinks: bool | None = None,
    progress: bool | None = None,
) -> Settings:
    resolved_token = token or os.environ.get("CIVITAI_TOKEN")
    resolved_cache = (
        cache_dir
        or os.environ.get("CIVITAI_HOME")
        or platformdirs.user_cache_dir("civitai")
    )
    return Settings(
        token=resolved_token,
        cache_dir=Path(resolved_cache).expanduser(),
        offline=offline if offline is not None else _env_bool("CIVITAI_OFFLINE"),
        use_symlinks=(
            use_symlinks
            if use_symlinks is not None
            else not _env_bool("CIVITAI_DISABLE_SYMLINKS")
        ),
        progress=progress if progress is not None else not _env_bool("CIVITAI_NO_PROGRESS"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/civitai_hub/config.py tests/test_config.py
git commit -m "feat: settings resolution (flag > env > default)"
```

---

### Task 6: HTTP client

**Files:**
- Create: `src/civitai_hub/client.py`
- Test: `tests/test_client.py`

- [ ] **Step 1: Write the failing test**

`tests/test_client.py`:
```python
import httpx
import pytest
import respx

from civitai_hub.client import BASE_URL, CivitaiClient
from civitai_hub.errors import (
    AuthRequiredError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
)


@respx.mock
def test_get_model_parses(model_payload):
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    model = CivitaiClient().get_model(580857)
    assert model.name.startswith("Realistic")


@respx.mock
def test_auth_header_sent(version_payload):
    route = respx.get(f"{BASE_URL}/model-versions/649002").mock(
        return_value=httpx.Response(200, json=version_payload)
    )
    CivitaiClient(token="secret").get_version(649002)
    assert route.calls.last.request.headers["Authorization"] == "Bearer secret"


@respx.mock
def test_retries_on_429_then_succeeds(model_payload):
    route = respx.get(f"{BASE_URL}/models/1").mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json=model_payload),
        ]
    )
    model = CivitaiClient(max_retries=2, backoff_base=0).get_model(1)
    assert model.id == 580857
    assert route.call_count == 2


@respx.mock
@pytest.mark.parametrize(
    "status, exc",
    [(401, AuthRequiredError), (403, ForbiddenError), (404, NotFoundError)],
)
def test_status_maps_to_error(status, exc):
    respx.get(f"{BASE_URL}/models/9").mock(return_value=httpx.Response(status))
    with pytest.raises(exc):
        CivitaiClient().get_model(9)


@respx.mock
def test_429_exhausted_raises_rate_limit():
    respx.get(f"{BASE_URL}/models/9").mock(return_value=httpx.Response(429))
    with pytest.raises(RateLimitError):
        CivitaiClient(max_retries=1, backoff_base=0).get_model(9)


@respx.mock
def test_get_version_by_hash(version_payload):
    respx.get(f"{BASE_URL}/model-versions/by-hash/ABC123").mock(
        return_value=httpx.Response(200, json=version_payload)
    )
    v = CivitaiClient().get_version_by_hash("ABC123")
    assert v.id == 649002
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_client.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

`src/civitai_hub/client.py`:
```python
"""Typed httpx wrapper over the CivitAI REST API."""
import time

import httpx

from .errors import (
    AuthRequiredError,
    CivitaiError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
)
from .models import Model, ModelVersion

BASE_URL = "https://civitai.com/api/v1"
_USER_AGENT = "civitai-hub/0.1 (+https://github.com/)"


class CivitaiClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        client: httpx.Client | None = None,
    ):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        headers = {"User-Agent": _USER_AGENT}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # follow_redirects matters for the download endpoint reusing this client.
        self.http = client or httpx.Client(
            timeout=timeout, headers=headers, follow_redirects=True
        )

    def _get_json(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        last: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            resp = self.http.get(url)
            if resp.status_code == 429 or resp.status_code >= 500:
                last = resp
                if attempt < self.max_retries:
                    time.sleep(self.backoff_base * (2**attempt))
                    continue
            self._raise_for_status(resp)
            return resp.json()
        if last is not None and last.status_code == 429:
            raise RateLimitError("Rate limited by CivitAI (HTTP 429). Try again later.")
        raise CivitaiError(
            f"Request failed after {self.max_retries} retries "
            f"(last status {last.status_code if last else 'unknown'})."
        )

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        code = resp.status_code
        if code == 401:
            raise AuthRequiredError(
                "Requires authentication — set CIVITAI_TOKEN or pass --token."
            )
        if code == 403:
            raise ForbiddenError("Forbidden — gated or early-access resource.")
        if code == 404:
            raise NotFoundError("Model or version not found.")
        if code == 429:
            raise RateLimitError("Rate limited by CivitAI (HTTP 429).")
        if code >= 400:
            raise CivitaiError(f"HTTP {code}: {resp.text[:200]}")

    def get_model(self, model_id: int) -> Model:
        return Model.model_validate(self._get_json(f"/models/{model_id}"))

    def get_version(self, version_id: int) -> ModelVersion:
        return ModelVersion.model_validate(self._get_json(f"/model-versions/{version_id}"))

    def get_version_by_hash(self, file_hash: str) -> ModelVersion:
        return ModelVersion.model_validate(
            self._get_json(f"/model-versions/by-hash/{file_hash}")
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_client.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add src/civitai_hub/client.py tests/test_client.py
git commit -m "feat: CivitaiClient with auth, retry, and error mapping"
```

---

### Task 7: Resolver (version + file selection)

**Files:**
- Create: `src/civitai_hub/resolver.py`
- Test: `tests/test_resolver.py`

- [ ] **Step 1: Write the failing test**

`tests/test_resolver.py`:
```python
import pytest

from civitai_hub.errors import AmbiguousFileError, NoMatchingFileError, NotFoundError
from civitai_hub.models import Model
from civitai_hub.resolver import FileSelectors, pick_files, pick_version


def test_pick_latest_version_by_published_at(model_payload):
    model = Model.model_validate(model_payload)
    v = pick_version(model)
    assert v.id == 649002  # newer publishedAt than 649001


def test_pick_pinned_version(model_payload):
    model = Model.model_validate(model_payload)
    assert pick_version(model, version_id=649001).id == 649001


def test_pick_unknown_version_raises(model_payload):
    model = Model.model_validate(model_payload)
    with pytest.raises(NotFoundError):
        pick_version(model, version_id=999)


def test_default_picks_primary_file(model_payload):
    v = Model.model_validate(model_payload).model_versions[0]
    files = pick_files(v, FileSelectors())
    assert len(files) == 1 and files[0].id == 11


def test_fp_selector(model_payload):
    v = Model.model_validate(model_payload).model_versions[1]
    files = pick_files(v, FileSelectors(fp="fp32"))
    assert [f.id for f in files] == [23]


def test_all_returns_every_file(model_payload):
    v = Model.model_validate(model_payload).model_versions[1]
    files = pick_files(v, FileSelectors(all=True))
    assert {f.id for f in files} == {22, 23}


def test_no_match_raises(model_payload):
    v = Model.model_validate(model_payload).model_versions[1]
    with pytest.raises(NoMatchingFileError):
        pick_files(v, FileSelectors(fp="bf16"))


def test_ambiguous_selector_raises(model_payload):
    v = Model.model_validate(model_payload).model_versions[1]
    with pytest.raises(AmbiguousFileError):
        pick_files(v, FileSelectors(type="Model"))


def test_no_primary_falls_back_to_first_safetensor(model_payload):
    # Build a version where no file is primary.
    model = Model.model_validate(model_payload)
    v = model.model_versions[1]
    for f in v.files:
        f.primary = False
    files = pick_files(v, FileSelectors())
    assert files[0].id == 22  # first Model-type safetensor


def test_no_files_no_selectors_raises(model_payload):
    v = Model.model_validate(model_payload).model_versions[0]
    v.files = []
    with pytest.raises(NoMatchingFileError):
        pick_files(v, FileSelectors())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resolver.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

`src/civitai_hub/resolver.py`:
```python
"""Pure selection logic: which version, which file(s)."""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .errors import AmbiguousFileError, NoMatchingFileError, NotFoundError
from .models import Model, ModelFile, ModelVersion

logger = logging.getLogger(__name__)
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


@dataclass
class FileSelectors:
    file_name: str | None = None
    type: str | None = None
    format: str | None = None
    size: str | None = None
    fp: str | None = None
    all: bool = False

    @property
    def has_selectors(self) -> bool:
        return any([self.file_name, self.type, self.format, self.size, self.fp])


def _sort_key(version: ModelVersion):
    dt = version.published_at
    if dt is None:
        return (_EPOCH, version.id)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt, version.id)


def pick_version(model: Model, version_id: int | None = None) -> ModelVersion:
    versions = model.model_versions
    if not versions:
        raise NotFoundError(f"Model {model.id} has no versions.")
    if version_id is not None:
        for v in versions:
            if v.id == version_id:
                return v
        raise NotFoundError(f"Version {version_id} not found in model {model.id}.")
    published = [v for v in versions if (v.status or "Published") == "Published"]
    pool = published or versions
    return max(pool, key=_sort_key)


def _matches(file: ModelFile, sel: FileSelectors) -> bool:
    def eq(value: str | None, want: str | None) -> bool:
        return want is None or (value or "").lower() == want.lower()

    return (
        eq(file.name, sel.file_name)
        and eq(file.type, sel.type)
        and eq(file.metadata.format, sel.format)
        and eq(file.metadata.size, sel.size)
        and eq(file.metadata.fp, sel.fp)
    )


def _describe(files: list[ModelFile]) -> str:
    return "; ".join(
        f"{f.name} (type={f.type}, fp={f.metadata.fp}, size={f.metadata.size})"
        for f in files
    )


def pick_files(version: ModelVersion, selectors: FileSelectors) -> list[ModelFile]:
    candidates = [f for f in version.files if _matches(f, selectors)]

    if not candidates:
        if selectors.has_selectors:
            raise NoMatchingFileError(
                f"No file in version {version.id} matches the given filters. "
                f"Available: {_describe(version.files)}"
            )
        raise NoMatchingFileError(f"Version {version.id} has no files.")

    if selectors.all:
        return candidates
    if len(candidates) == 1:
        return candidates

    if not selectors.has_selectors:
        primary = version.primary_file
        if primary is not None:
            return [primary]
        for f in candidates:
            if (f.type or "") == "Model" and f.is_safetensor:
                logger.warning("No primary file; defaulting to %s", f.name)
                return [f]
        logger.warning("No primary file; defaulting to %s", candidates[0].name)
        return [candidates[0]]

    raise AmbiguousFileError(
        f"Multiple files match in version {version.id}; narrow with "
        f"--file/--format/--fp/--size or use --all. Candidates: {_describe(candidates)}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resolver.py -v`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add src/civitai_hub/resolver.py tests/test_resolver.py
git commit -m "feat: version/file selection logic"
```

---

### Task 8: Cache store

**Files:**
- Create: `src/civitai_hub/cache.py`
- Test: `tests/test_cache.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cache.py`:
```python
from civitai_hub.cache import CacheStore
from civitai_hub.models import ModelFile


def _file(file_id, name, sha):
    return ModelFile.model_validate(
        {"id": file_id, "name": name, "hashes": {"SHA256": sha}}
    )


def test_store_creates_blob_and_symlink(tmp_path):
    store = CacheStore(tmp_path)
    f = _file(1, "a.safetensors", "A" * 64)
    src = tmp_path / "incoming.bin"
    src.write_bytes(b"weights")

    snap = store.store(src, model_id=10, version_id=100, file=f)

    assert snap.read_bytes() == b"weights"
    blob = store.blob_path(10, f)
    assert blob.exists()
    assert store.is_cached(10, 100, f) is True
    assert (tmp_path / "CACHEDIR.TAG").exists()


def test_dedup_same_blob_across_versions(tmp_path):
    store = CacheStore(tmp_path)
    f = _file(1, "a.safetensors", "A" * 64)
    src1 = tmp_path / "v1.bin"
    src1.write_bytes(b"same")
    store.store(src1, 10, 100, f)
    # second version, identical content/hash -> reuse blob, new snapshot
    src2 = tmp_path / "v2.bin"
    src2.write_bytes(b"same")
    snap2 = store.store(src2, 10, 200, f)

    blobs = list((tmp_path / "models" / "10" / "blobs").iterdir())
    assert len(blobs) == 1
    assert snap2.read_bytes() == b"same"


def test_copy_fallback_when_symlinks_disabled(tmp_path):
    store = CacheStore(tmp_path, use_symlinks=False)
    f = _file(1, "a.safetensors", "A" * 64)
    src = tmp_path / "incoming.bin"
    src.write_bytes(b"data")
    snap = store.store(src, 10, 100, f)
    assert snap.is_symlink() is False
    assert snap.read_bytes() == b"data"


def test_not_cached_before_store(tmp_path):
    store = CacheStore(tmp_path)
    f = _file(1, "a.safetensors", "A" * 64)
    assert store.is_cached(10, 100, f) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cache.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

`src/civitai_hub/cache.py`:
```python
"""Content-addressed cache: blobs/<sha256> + snapshots/<versionId>/<name> links."""
import os
import shutil
from pathlib import Path

from .models import ModelFile

_CACHEDIR_TAG = (
    "Signature: 8a477f597d28d172789f06886806bc55\n"
    "# This file marks this directory as a cache for civitai-hub.\n"
)


class CacheStore:
    def __init__(self, root, use_symlinks: bool = True):
        self.root = Path(root).expanduser()
        self.use_symlinks = use_symlinks

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tag = self.root / "CACHEDIR.TAG"
        if not tag.exists():
            tag.write_text(_CACHEDIR_TAG)

    def _model_dir(self, model_id: int) -> Path:
        return self.root / "models" / str(model_id)

    def blob_path(self, model_id: int, file: ModelFile) -> Path:
        key = file.sha256 or f"file-{file.id}"
        return self._model_dir(model_id) / "blobs" / key

    def incomplete_path(self, model_id: int, file: ModelFile) -> Path:
        blob = self.blob_path(model_id, file)
        return blob.parent / (blob.name + ".incomplete")

    def snapshot_path(self, model_id: int, version_id: int, filename: str) -> Path:
        return self._model_dir(model_id) / "snapshots" / str(version_id) / filename

    def is_cached(self, model_id: int, version_id: int, file: ModelFile) -> bool:
        return self.blob_path(model_id, file).exists()

    def store(self, tmp_path, model_id: int, version_id: int, file: ModelFile) -> Path:
        self.ensure_root()
        blob = self.blob_path(model_id, file)
        blob.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp_path, blob)
        snap = self.snapshot_path(model_id, version_id, file.name)
        snap.parent.mkdir(parents=True, exist_ok=True)
        self._link(blob, snap)
        return snap

    def _link(self, blob: Path, snap: Path) -> None:
        if snap.is_symlink() or snap.exists():
            snap.unlink()
        if self.use_symlinks:
            try:
                snap.symlink_to(os.path.relpath(blob, snap.parent))
                return
            except OSError:
                pass
        shutil.copy2(blob, snap)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cache.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/civitai_hub/cache.py tests/test_cache.py
git commit -m "feat: content-addressed cache with symlink snapshots"
```

---

### Task 9: Download (stream, resume, verify, materialize)

**Files:**
- Create: `src/civitai_hub/download.py`
- Test: `tests/test_download.py`

- [ ] **Step 1: Write the failing test**

`tests/test_download.py`:
```python
import hashlib
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from civitai_hub.cache import CacheStore
from civitai_hub.client import CivitaiClient
from civitai_hub.config import Settings
from civitai_hub.download import download_file
from civitai_hub.errors import (
    CivitaiError,
    EarlyAccessError,
    HashMismatchError,
    OfflineError,
)
from civitai_hub.models import ModelFile, ModelVersion


def _settings(tmp_path, token=None, offline=False, use_symlinks=True):
    return Settings(
        token=token, cache_dir=tmp_path, offline=offline,
        use_symlinks=use_symlinks, progress=False,
    )


def _version_with_payload(payload_bytes):
    sha = hashlib.sha256(payload_bytes).hexdigest().upper()
    file = ModelFile.model_validate({
        "id": 22, "name": "w.safetensors", "type": "Model",
        "metadata": {"format": "SafeTensor"}, "primary": True,
        "hashes": {"SHA256": sha},
        "downloadUrl": "https://civitai.com/api/download/models/649002",
        "pickleScanResult": "Success", "virusScanResult": "Success",
    })
    version = ModelVersion.model_validate({"id": 649002, "files": [file.model_dump(by_alias=True)]})
    return version, version.files[0]


@respx.mock
def test_download_verifies_and_caches(tmp_path):
    body = b"model-weights-bytes"
    version, file = _version_with_payload(body)
    respx.get("https://civitai.com/api/download/models/649002").mock(
        return_value=httpx.Response(200, content=body)
    )
    store = CacheStore(tmp_path)
    path = download_file(
        CivitaiClient(), 10, version, file, store, settings=_settings(tmp_path),
    )
    assert path.read_bytes() == body
    assert store.is_cached(10, version.id, file)


@respx.mock
def test_download_appends_token(tmp_path):
    body = b"x"
    version, file = _version_with_payload(body)
    route = respx.get("https://civitai.com/api/download/models/649002").mock(
        return_value=httpx.Response(200, content=body)
    )
    download_file(
        CivitaiClient(token="tok"), 10, version, file, CacheStore(tmp_path),
        settings=_settings(tmp_path, token="tok"),
    )
    assert "token=tok" in str(route.calls.last.request.url)


@respx.mock
def test_hash_mismatch_deletes_and_raises(tmp_path):
    body = b"good"
    version, file = _version_with_payload(body)
    respx.get("https://civitai.com/api/download/models/649002").mock(
        return_value=httpx.Response(200, content=b"TAMPERED")
    )
    store = CacheStore(tmp_path)
    with pytest.raises(HashMismatchError):
        download_file(CivitaiClient(), 10, version, file, store, settings=_settings(tmp_path))
    assert not store.incomplete_path(10, file).exists()
    assert not store.is_cached(10, version.id, file)


@respx.mock
def test_cache_hit_skips_network(tmp_path):
    body = b"cached-body"
    version, file = _version_with_payload(body)
    route = respx.get("https://civitai.com/api/download/models/649002").mock(
        return_value=httpx.Response(200, content=body)
    )
    store = CacheStore(tmp_path)
    download_file(CivitaiClient(), 10, version, file, store, settings=_settings(tmp_path))
    assert route.call_count == 1
    download_file(CivitaiClient(), 10, version, file, store, settings=_settings(tmp_path))
    assert route.call_count == 1  # second call served from cache


def test_offline_uncached_raises(tmp_path):
    version, file = _version_with_payload(b"z")
    with pytest.raises(OfflineError):
        download_file(
            CivitaiClient(), 10, version, file, CacheStore(tmp_path),
            settings=_settings(tmp_path, offline=True),
        )


@respx.mock
def test_materialize_into_local_dir(tmp_path):
    body = b"into-local"
    version, file = _version_with_payload(body)
    respx.get("https://civitai.com/api/download/models/649002").mock(
        return_value=httpx.Response(200, content=body)
    )
    local = tmp_path / "loras"
    path = download_file(
        CivitaiClient(), 10, version, file, CacheStore(tmp_path),
        settings=_settings(tmp_path), local_dir=local,
    )
    assert path == local / "w.safetensors"
    assert path.read_bytes() == body


@respx.mock
def test_resume_from_partial(tmp_path):
    full = b"0123456789abcdef" * 4  # 64 bytes
    version, file = _version_with_payload(full)
    store = CacheStore(tmp_path)
    tmp = store.incomplete_path(10, file)
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(full[:10])  # pre-seed a partial download

    def responder(request):
        assert request.headers.get("Range") == "bytes=10-"
        return httpx.Response(
            206, content=full[10:], headers={"Content-Length": str(len(full) - 10)}
        )

    respx.get("https://civitai.com/api/download/models/649002").mock(side_effect=responder)
    path = download_file(CivitaiClient(), 10, version, file, store, settings=_settings(tmp_path))
    assert path.read_bytes() == full


@respx.mock
def test_scan_danger_blocks_then_allows(tmp_path):
    body = b"risky-bytes"
    sha = hashlib.sha256(body).hexdigest().upper()
    version = ModelVersion.model_validate({
        "id": 700,
        "files": [{
            "id": 30, "name": "r.safetensors", "type": "Model",
            "metadata": {"format": "SafeTensor"}, "primary": True,
            "hashes": {"SHA256": sha},
            "downloadUrl": "https://civitai.com/api/download/models/700",
            "pickleScanResult": "Danger", "virusScanResult": "Success",
        }],
    })
    file = version.files[0]
    respx.get("https://civitai.com/api/download/models/700").mock(
        return_value=httpx.Response(200, content=body)
    )
    store = CacheStore(tmp_path)
    with pytest.raises(CivitaiError):
        download_file(CivitaiClient(), 10, version, file, store, settings=_settings(tmp_path))
    path = download_file(
        CivitaiClient(), 10, version, file, store,
        settings=_settings(tmp_path), allow_unscanned=True,
    )
    assert path.read_bytes() == body


def test_early_access_blocks_before_download(tmp_path):
    version, file = _version_with_payload(b"x")
    version.availability = "EarlyAccess"
    version.early_access_ends_at = datetime.now(timezone.utc) + timedelta(days=3)
    with pytest.raises(EarlyAccessError):
        download_file(
            CivitaiClient(), 10, version, file, CacheStore(tmp_path),
            settings=_settings(tmp_path),
        )


@respx.mock
def test_materialize_copy_when_symlinks_disabled(tmp_path):
    body = b"copy-me"
    version, file = _version_with_payload(body)
    respx.get("https://civitai.com/api/download/models/649002").mock(
        return_value=httpx.Response(200, content=body)
    )
    local = tmp_path / "out"
    path = download_file(
        CivitaiClient(), 10, version, file,
        CacheStore(tmp_path, use_symlinks=False),
        settings=_settings(tmp_path, use_symlinks=False), local_dir=local,
    )
    assert path.is_symlink() is False
    assert path.read_bytes() == body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_download.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

`src/civitai_hub/download.py`:
```python
"""Download a single file: availability + scan gates, stream+resume, verify,
store, materialize."""
import hashlib
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .cache import CacheStore
from .client import CivitaiClient
from .config import Settings
from .errors import CivitaiError, EarlyAccessError, HashMismatchError, OfflineError
from .models import ModelFile, ModelVersion

logger = logging.getLogger(__name__)
_CHUNK = 1 << 16
_DANGER_SCAN = {"Danger", "Error"}
ProgressCb = Callable[[int, int], None]


def check_availability(version: ModelVersion) -> None:
    """Fail fast on early-access / non-public versions before downloading."""
    if version.availability and version.availability != "Public":
        ends = version.early_access_ends_at
        if ends is not None and ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        if ends is None or ends > datetime.now(timezone.utc):
            raise EarlyAccessError(
                f"Version {version.id} is '{version.availability}' (early access / gated) — "
                "requires a CivitAI Supporter entitlement and a token."
            )


def _scan_blocks(file: ModelFile) -> bool:
    """True when the file is actively flagged unsafe and must be gated."""
    if file.pickle_scan_result in _DANGER_SCAN or file.virus_scan_result in _DANGER_SCAN:
        return True
    return (file.metadata.format or "") == "PickleTensor"


def _scan_unverified(file: ModelFile) -> bool:
    """True when scans are merely missing/pending (warn, do not block)."""
    return file.pickle_scan_result != "Success" or file.virus_scan_result != "Success"


def _stream_to_temp(
    client: CivitaiClient,
    file: ModelFile,
    store: CacheStore,
    model_id: int,
    token: str | None,
    progress_cb: ProgressCb | None,
) -> Path:
    url = file.download_url
    if not url:
        raise CivitaiError(f"File {file.name} has no downloadUrl.")
    # Token goes via params (httpx can redact it) rather than baked into the URL string.
    params = {"token": token} if token else None
    tmp = store.incomplete_path(model_id, file)
    tmp.parent.mkdir(parents=True, exist_ok=True)

    for _ in (0, 1):  # second pass restarts from byte 0 if the byte range is rejected (416)
        resume_from = tmp.stat().st_size if tmp.exists() else 0
        headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}
        with client.http.stream("GET", url, params=params, headers=headers) as resp:
            if resp.status_code == 416 and resume_from:
                tmp.unlink(missing_ok=True)  # stale/oversized partial -> drop and restart
                continue
            if resp.status_code not in (200, 206):
                resp.read()  # body must be read before mapping a streaming error (B1)
                CivitaiClient._raise_for_status(resp)
            append = resp.status_code == 206 and resume_from > 0
            if not append:
                resume_from = 0
            total = int(resp.headers.get("Content-Length", 0)) + (resume_from if append else 0)
            downloaded = resume_from
            try:
                with open(tmp, "ab" if append else "wb") as fh:
                    for chunk in resp.iter_bytes(_CHUNK):
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb:
                            progress_cb(downloaded, total)
            except BaseException:
                if not append:  # keep a clean partial for resume; discard a fresh-start temp
                    tmp.unlink(missing_ok=True)
                raise
        return tmp
    raise CivitaiError(f"Server rejected the byte range for {file.name} (HTTP 416).")


def _verify(tmp: Path, file: ModelFile) -> None:
    expected = file.sha256
    if not expected:
        logger.warning("No SHA256 for %s; skipping verification.", file.name)
        return
    digest = hashlib.sha256()
    with open(tmp, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    actual = digest.hexdigest().upper()
    if actual != expected.upper():
        tmp.unlink(missing_ok=True)
        raise HashMismatchError(
            f"SHA256 mismatch for {file.name}: expected {expected}, got {actual}."
        )


def _materialize(blob: Path, dest: Path, use_symlinks: bool) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.exists():
        dest.unlink()
    if use_symlinks:
        try:
            dest.symlink_to(os.path.relpath(blob, dest.parent))
            return dest
        except OSError:
            pass
    shutil.copy2(blob, dest)
    return dest


def download_file(
    client: CivitaiClient,
    model_id: int,
    version: ModelVersion,
    file: ModelFile,
    store: CacheStore,
    *,
    settings: Settings,
    force: bool = False,
    local_dir: str | os.PathLike | None = None,
    allow_unscanned: bool = False,
    progress_cb: ProgressCb | None = None,
) -> Path:
    check_availability(version)
    if _scan_blocks(file):
        if not allow_unscanned:
            raise CivitaiError(
                f"{file.name} is flagged unsafe "
                f"(pickle={file.pickle_scan_result}, virus={file.virus_scan_result}, "
                f"format={file.metadata.format}). Pass allow_unscanned / --allow-unscanned."
            )
        logger.warning("Proceeding with flagged file %s", file.name)
    elif _scan_unverified(file):
        logger.warning("Scan results for %s are not all 'Success'; proceeding.", file.name)

    if force or not store.is_cached(model_id, version.id, file):
        if settings.offline:
            raise OfflineError(f"{file.name} is not cached and offline mode is on.")
        tmp = _stream_to_temp(client, file, store, model_id, settings.token, progress_cb)
        _verify(tmp, file)
        store.store(tmp, model_id, version.id, file)

    if local_dir is not None:
        return _materialize(
            store.blob_path(model_id, file),
            Path(local_dir).expanduser() / file.name,
            settings.use_symlinks,
        )
    return store.snapshot_path(model_id, version.id, file.name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_download.py -v`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add src/civitai_hub/download.py tests/test_download.py
git commit -m "feat: streaming download with resume, verify, materialize"
```

---

### Task 10: Public library API (`model_info`, `download`)

**Files:**
- Modify: `src/civitai_hub/__init__.py`
- Test: `tests/test_public_api.py`

- [ ] **Step 1: Write the failing test**

`tests/test_public_api.py`:
```python
import hashlib

import httpx
import respx

import civitai_hub
from civitai_hub.client import BASE_URL
from civitai_hub.models import ModelInfo, PlanItem


def _patch_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("CIVITAI_HOME", str(tmp_path))
    for var in ["CIVITAI_TOKEN", "CIVITAI_OFFLINE", "CIVITAI_DISABLE_SYMLINKS"]:
        monkeypatch.delenv(var, raising=False)


@respx.mock
def test_model_info_returns_resolved(monkeypatch, tmp_path, model_payload):
    _patch_cache(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    info = civitai_hub.model_info("https://civitai.com/models/580857/x")
    assert isinstance(info, ModelInfo)
    assert info.model.id == 580857
    assert info.version.id == 649002  # latest
    assert len(info.files) == 2


@respx.mock
def test_model_info_from_download_url_resolves_model(monkeypatch, tmp_path, version_payload, model_payload):
    _patch_cache(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/model-versions/649002").mock(
        return_value=httpx.Response(200, json=version_payload)
    )
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    info = civitai_hub.model_info("https://civitai.com/api/download/models/649002")
    assert info.model.id == 580857
    assert info.version.id == 649002


@respx.mock
def test_version_override_on_download_url(monkeypatch, tmp_path, model_payload):
    # api/download URL pins 649002, but an explicit version_id=649001 must win.
    _patch_cache(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/model-versions/649001").mock(
        return_value=httpx.Response(200, json={"id": 649001, "modelId": 580857, "files": []})
    )
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    info = civitai_hub.model_info(
        "https://civitai.com/api/download/models/649002", version_id=649001
    )
    assert info.version.id == 649001


@respx.mock
def test_download_single_returns_path(monkeypatch, tmp_path):
    _patch_cache(monkeypatch, tmp_path)
    body = b"weights"
    sha = hashlib.sha256(body).hexdigest().upper()
    payload = {
        "id": 1, "name": "m", "type": "LORA",
        "modelVersions": [{
            "id": 5, "baseModel": "Pony", "status": "Published",
            "publishedAt": "2024-01-01T00:00:00.000Z",
            "downloadUrl": "https://civitai.com/api/download/models/5",
            "files": [{
                "id": 9, "name": "m.safetensors", "type": "Model",
                "metadata": {"format": "SafeTensor"}, "primary": True,
                "hashes": {"SHA256": sha},
                "downloadUrl": "https://civitai.com/api/download/models/5",
                "pickleScanResult": "Success", "virusScanResult": "Success",
            }],
        }],
    }
    respx.get(f"{BASE_URL}/models/1").mock(return_value=httpx.Response(200, json=payload))
    respx.get("https://civitai.com/api/download/models/5").mock(
        return_value=httpx.Response(200, content=body)
    )
    path = civitai_hub.download("1")
    assert path.read_bytes() == body


@respx.mock
def test_download_dry_run_returns_plan(monkeypatch, tmp_path, model_payload):
    _patch_cache(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    plan = civitai_hub.download("580857", dry_run=True)
    assert isinstance(plan, list)
    assert all(isinstance(p, PlanItem) for p in plan)
    assert plan[0].cached is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_public_api.py -v`
Expected: FAIL (AttributeError: module has no attribute 'model_info').

- [ ] **Step 3: Implement**

`src/civitai_hub/__init__.py` (replace the stub):
```python
"""civitai_hub — huggingface_hub, but for CivitAI."""
from .cache import CacheStore
from .client import CivitaiClient
from .config import resolve_settings
from .download import download_file
from .errors import NotFoundError
from .models import Model, ModelInfo, ModelVersion, PlanItem
from .resolver import FileSelectors, pick_files, pick_version
from .urls import parse_model_url

__version__ = "0.1.0"
__all__ = ["model_info", "download", "ModelInfo", "PlanItem", "__version__"]


def _resolve(client: CivitaiClient, ref, version_id) -> tuple[Model, ModelVersion]:
    pinned = version_id if version_id is not None else ref.version_id
    if ref.model_id is None:
        version = client.get_version(pinned)  # honor an explicit override, else the URL's vid
        if version.model_id is None:
            raise NotFoundError(f"Version {version.id} has no parent modelId.")
        model = client.get_model(version.model_id)
        return model, pick_version(model, version.id)
    model = client.get_model(ref.model_id)
    return model, pick_version(model, pinned)


def model_info(url_or_id, *, version_id=None, token=None, cache_dir=None) -> ModelInfo:
    settings = resolve_settings(token=token, cache_dir=cache_dir)
    ref = parse_model_url(str(url_or_id))
    client = CivitaiClient(token=settings.token)
    model, version = _resolve(client, ref, version_id)
    return ModelInfo(model=model, version=version, files=list(version.files))


def download(
    url_or_id,
    *,
    version_id=None,
    file=None,
    type=None,
    format=None,
    fp=None,
    size=None,
    all=False,
    cache_dir=None,
    local_dir=None,
    use_symlinks=True,
    token=None,
    force=False,
    allow_unscanned=False,
    dry_run=False,
    progress=True,
    progress_cb=None,
):
    settings = resolve_settings(
        token=token, cache_dir=cache_dir, use_symlinks=use_symlinks, progress=progress
    )
    ref = parse_model_url(str(url_or_id))
    client = CivitaiClient(token=settings.token)
    model, version = _resolve(client, ref, version_id)
    selectors = FileSelectors(
        file_name=file, type=type, format=format, size=size, fp=fp, all=all
    )
    chosen = pick_files(version, selectors)
    store = CacheStore(settings.cache_dir, use_symlinks=settings.use_symlinks)

    if dry_run:
        return [
            PlanItem(
                file_name=f.name,
                size_bytes=f.size_bytes,
                cached=store.is_cached(model.id, version.id, f),
            )
            for f in chosen
        ]

    paths = [
        download_file(
            client, model.id, version, f, store,
            settings=settings, force=force,
            local_dir=local_dir, allow_unscanned=allow_unscanned,
            progress_cb=progress_cb,
        )
        for f in chosen
    ]
    return paths if all else paths[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_public_api.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/civitai_hub/__init__.py tests/test_public_api.py
git commit -m "feat: public model_info + download API"
```

---

### Task 11: Rendering (rich tables, dry-run, progress)

**Files:**
- Create: `src/civitai_hub/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing test**

`tests/test_render.py`:
```python
from civitai_hub.models import Model, ModelInfo, PlanItem
from civitai_hub.render import render_dry_run, render_model_info


def test_render_model_info_mentions_key_facts(model_payload):
    model = Model.model_validate(model_payload)
    version = model.model_versions[1]
    info = ModelInfo(model=model, version=version, files=list(version.files))
    text = render_model_info(info)
    assert "Realistic Skin Texture Style" in text
    assert "LORA" in text
    assert "Pony" in text  # base model
    assert "580857" in text  # parent model id
    assert "2 files" in text
    assert "someone" in text  # creator
    assert "1234" in text  # download count


def test_render_dry_run_lists_files_and_total():
    plan = [
        PlanItem("a.safetensors", 1024 * 1024, cached=False),
        PlanItem("b.safetensors", None, cached=True),
    ]
    text = render_dry_run(plan)
    assert "a.safetensors" in text
    assert "b.safetensors" in text
    assert "cached" in text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_render.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

`src/civitai_hub/render.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_render.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/civitai_hub/render.py tests/test_render.py
git commit -m "feat: rich rendering for info + dry-run"
```

---

### Task 12: CLI (`info`, `download`)

**Files:**
- Create: `src/civitai_hub/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
import hashlib

import json

import httpx
import respx
from typer.testing import CliRunner

import civitai_hub
from civitai_hub.cli import app
from civitai_hub.client import BASE_URL

runner = CliRunner()


def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("CIVITAI_HOME", str(tmp_path))
    for var in ["CIVITAI_TOKEN", "CIVITAI_OFFLINE", "CIVITAI_DISABLE_SYMLINKS", "CIVITAI_NO_PROGRESS"]:
        monkeypatch.delenv(var, raising=False)


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert civitai_hub.__version__ in result.stdout


@respx.mock
def test_info_prints_table(monkeypatch, tmp_path, model_payload):
    _env(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    result = runner.invoke(app, ["info", "https://civitai.com/models/580857/x"])
    assert result.exit_code == 0
    assert "2 files" in result.stdout
    assert "Pony" in result.stdout


@respx.mock
def test_info_json(monkeypatch, tmp_path, model_payload):
    _env(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    result = runner.invoke(app, ["info", "580857", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["model"]["id"] == 580857
    assert data["version"]["id"] == 649002


@respx.mock
def test_download_dry_run(monkeypatch, tmp_path, model_payload):
    _env(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    result = runner.invoke(app, ["download", "580857", "--dry-run"])
    assert result.exit_code == 0
    assert "Will download" in result.stdout


def test_invalid_url_exit_code(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    result = runner.invoke(app, ["info", "not-a-url"])
    assert result.exit_code == 2  # InvalidURLError.exit_code


@respx.mock
def test_download_writes_file(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    body = b"weights"
    sha = hashlib.sha256(body).hexdigest().upper()
    payload = {
        "id": 1, "name": "m", "type": "LORA",
        "modelVersions": [{
            "id": 5, "baseModel": "Pony", "status": "Published",
            "publishedAt": "2024-01-01T00:00:00.000Z",
            "downloadUrl": "https://civitai.com/api/download/models/5",
            "files": [{
                "id": 9, "name": "m.safetensors", "type": "Model",
                "metadata": {"format": "SafeTensor"}, "primary": True,
                "hashes": {"SHA256": sha},
                "downloadUrl": "https://civitai.com/api/download/models/5",
                "pickleScanResult": "Success", "virusScanResult": "Success",
            }],
        }],
    }
    respx.get(f"{BASE_URL}/models/1").mock(return_value=httpx.Response(200, json=payload))
    respx.get("https://civitai.com/api/download/models/5").mock(
        return_value=httpx.Response(200, content=body)
    )
    out = tmp_path / "loras"
    result = runner.invoke(app, ["download", "1", "-o", str(out), "--no-progress"])
    assert result.exit_code == 0
    assert (out / "m.safetensors").read_bytes() == body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

`src/civitai_hub/cli.py`:
```python
"""Typer CLI — a thin wrapper over the library API."""
import json as _json
from typing import Optional

import typer

import civitai_hub
from .errors import CivitaiError
from .render import render_dry_run, render_model_info

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
    try:
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
```

> Note on progress bars: the library accepts an optional `progress_cb`; wiring a live `rich` progress bar from the CLI is deferred to a later enhancement (the spec lists parallel/visual polish as non-blocking). For v1 the CLI passes no callback and prints final paths, honoring `--no-progress` as a no-op-safe flag.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/civitai_hub/cli.py tests/test_cli.py
git commit -m "feat: civitai CLI (info, download)"
```

---

### Task 13: Wire-up, README, lint, and update CLAUDE.md

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Create: `tests/test_live.py` (skipped by default)

- [ ] **Step 1: Full test suite + lint pass**

Run:
```bash
pytest -v
ruff check src tests
```
Expected: all tests PASS; ruff reports no errors (fix any it flags).

- [ ] **Step 2: Add an opt-in live smoke test**

`tests/test_live.py`:
```python
"""Live test against the real CivitAI API. Opt-in only:
    CIVITAI_LIVE=1 pytest tests/test_live.py -v
Never runs in normal/CI runs."""
import os

import pytest

import civitai_hub

pytestmark = pytest.mark.skipif(
    os.environ.get("CIVITAI_LIVE") != "1", reason="set CIVITAI_LIVE=1 to run live"
)


def test_real_model_info():
    info = civitai_hub.model_info("https://civitai.com/models/580857")
    assert info.model.id == 580857
    assert info.files  # at least one file
```

- [ ] **Step 3: Write README usage**

Replace `README.md`:
```markdown
# civitai-hub

`huggingface_hub`, but for [CivitAI](https://civitai.com). Inspect a model and
download its checkpoint / LoRA into a deduplicated managed cache.

## Install

    pipx install civitai-hub      # or: pip install -e ".[dev]" for development

## CLI

    civitai info  https://civitai.com/models/580857/realistic-skin
    civitai download https://civitai.com/models/580857 --fp16 -o ~/ComfyUI/models/loras
    civitai download 580857 --dry-run
    civitai download 580857 --all

Auth (for gated / NSFW): `export CIVITAI_TOKEN=<your key>` or pass `--token`.

## Library

```python
import civitai_hub

info = civitai_hub.model_info("https://civitai.com/models/580857")
path = civitai_hub.download("https://civitai.com/models/580857", fp="fp16",
                            local_dir="~/ComfyUI/models/loras")
```

## Configuration

| Env | Meaning |
|---|---|
| `CIVITAI_TOKEN` | API key |
| `CIVITAI_HOME` | cache root (default: platform cache dir) |
| `CIVITAI_OFFLINE` | serve cache only |
| `CIVITAI_DISABLE_SYMLINKS` | copy instead of symlink |
| `CIVITAI_NO_PROGRESS` | disable progress |

See `docs/superpowers/specs/` and `docs/superpowers/plans/` for design details.
```

- [ ] **Step 4: Update CLAUDE.md with real commands**

Replace the body of `CLAUDE.md` (keep the required header lines at the top) with real, runnable guidance:
```markdown
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

Library-first; the Typer CLI (`cli.py`) is a thin wrapper over the public API in `__init__.py` (`model_info`, `download`). Layered, each unit-tested with `respx` (no real network in tests):

`urls` (parse URL→ModelRef) → `client` (httpx + auth + retry + error mapping) → `models` (lenient pydantic). Plus `resolver` (pick version/file), `cache` (content-addressed blobs + snapshot symlinks, keyed by immutable version id), `download` (stream + range-resume + SHA256 verify + materialize), `config` (flag>env>default), `errors` (exit-code-bearing hierarchy), `render` (rich tables).

## CivitAI API notes that bit us

- Downloads `302`-redirect to a CDN that strips the `Authorization` header → the download endpoint uses `?token=`, while metadata calls use `Bearer`.
- File `metadata`/`hashes`/`primary` fields are inconsistent — models are lenient (`extra=ignore`, all optionals defaulted). Fields like `model_id`/`model_versions` need pydantic `protected_namespaces=()`.
- "Parent model" = `modelId` (owning listing); "base model" = `baseModel` string family. Exact LoRA→checkpoint lineage is not exposed by the API.

Design docs: `docs/superpowers/specs/2026-06-16-civitai-cli-design.md`, plan: `docs/superpowers/plans/2026-06-16-civitai-cli.md`.
```

- [ ] **Step 5: Final test run + commit**

Run:
```bash
pytest -v
ruff check src tests
```
Expected: all PASS, no lint errors.

```bash
git add -A
git commit -m "docs: README, live smoke test, and CLAUDE.md commands"
```

---

## Self-review checklist (completed by plan author)

**Spec coverage:** info command (Task 12) · download with smart-default+flags selection (Tasks 7, 12) · managed cache + dedup + symlink fallback (Task 8) · target-dir materialization (Task 9) · token-via-query + redirect-follow + range-resume + SHA256 verify (Task 9) · lenient models incl. pydantic namespace fix (Task 4) · URL parsing all shapes (Task 3) · error→exit-code mapping (Tasks 2, 12) · config precedence (Task 5) · retry/backoff + error mapping (Task 6) · dry-run (Tasks 10–12) · scan-gate (Task 9) · library API mirroring hf_hub (Task 10) · tests offline via respx (all) · live opt-in test (Task 13). Out-of-scope items (search, login, cache subcommands, parallel `--all`) intentionally omitted.

**Type consistency:** `CacheStore.store/is_cached/blob_path/snapshot_path/incomplete_path` signatures match between `cache.py` (Task 8), `download.py` (Task 9), and `__init__.py` (Task 10). `FileSelectors` fields match between `resolver.py` (Task 7) and the `download()` mapping (Task 10) and CLI (Task 12). `download_file(...)` keyword args (`settings`, `force`, `local_dir`, `allow_unscanned`, `progress_cb`) match call sites. `Settings` fields match `resolve_settings` (Task 5) and `download.py` usage. `ModelInfo`/`PlanItem` defined in `models.py` (Task 4), produced in Task 10, consumed in `render.py` (Task 11) and CLI (Task 12).

**Placeholder scan:** no TBD/TODO/"handle edge cases" — every code step contains complete code; the progress-bar deferral is an explicit, scoped v1 decision (callback hook present), not a placeholder.

## Adversarial review — fixes applied

An independent four-lens review (spec-coverage, type-consistency, code-correctness, python-gotchas) ran against this plan. Resolutions folded in above:

- **B1** streaming `.text` crash → `_stream_to_temp` calls `resp.read()` before mapping non-2xx errors (Task 9).
- **B2** early-access gate → `check_availability()` raises `EarlyAccessError` before I/O; test added (Task 9).
- **M1** broken dep floor → `typer>=0.15` (Task 1).
- **M2** ruff gate → removed unused imports (`__init__.py`, `cli.py`) and split `;` statements (`test_cache.py`).
- **M3** missing tests → added range-resume + scan-gate + materialize-copy + early-access tests (Task 9); **Content-Disposition** decided against in favor of authoritative `file.name` (spec §3.4/§8/§13 amended — not silently dropped).
- **M4** `--version` → `@app.callback()` eager option + test (Task 12).
- **M5** 416 / poisoned partial → 416 restart-from-0 loop + temp cleanup on fresh-start failure; verify-mismatch already unlinks so the next run self-heals (Task 9).
- **m1** `_resolve` override drop → honors explicit `version_id` on download-URL inputs, guards `model_id is None`; test added (Task 10).
- **m3/m4/m5/m7/n1** → render creator+stats, `info --json` test, materialize copy-fallback test, `get_version_by_hash` client method+test, empty-files resolver test.
- **m8** → token sent via `params=` (redactable); scan gate blocks only on `Danger`/`Error`/`PickleTensor`, warns (not blocks) on merely-absent scans.
- **Spec amendments** (deliberate, documented): `is_cached` = existence-by-content-hash; no persistent inter-call delay in v1.
- **Dropped false positives:** the `_json` alias and `protected_namespaces` coverage were both already correct.

## Post-implementation addition (Task 14)

The final whole-implementation review flagged the one spec item the plan had deferred: the **rich progress bar** (spec §8/§9). It was implemented as a follow-up task — `render.download_progress(enabled)` context manager (renders to stderr, indeterminate-total-safe, new task per file for `--all`) wired into `cli.download` via `progress_cb`, gated on `not --no-progress/--dry-run/--quiet`. Tests added at render/library/CLI levels. The spec is now fully covered.
