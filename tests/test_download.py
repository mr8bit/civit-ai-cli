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
