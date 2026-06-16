"""Tests for the 0.3.0 feature batch: search, by-hash, token store, cache
management, and the download --offline/--json flags."""
import hashlib
import json

import httpx
import respx
from typer.testing import CliRunner

import civitai_hub
from civitai_hub.cache import CacheStore
from civitai_hub.cli import app
from civitai_hub.client import BASE_URL, CivitaiClient
from civitai_hub.config import (
    delete_token,
    read_stored_token,
    resolve_settings,
    store_token,
)
from civitai_hub.models import ModelFile

runner = CliRunner()


def _dl_payload(body):
    sha = hashlib.sha256(body).hexdigest().upper()
    return {
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


def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("CIVITAI_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    for v in ["CIVITAI_TOKEN", "CIVITAI_OFFLINE", "CIVITAI_DISABLE_SYMLINKS", "CIVITAI_NO_PROGRESS"]:
        monkeypatch.delenv(v, raising=False)


# --- client -----------------------------------------------------------------

@respx.mock
def test_get_version_by_hash(version_payload):
    respx.get(f"{BASE_URL}/model-versions/by-hash/ABC123").mock(
        return_value=httpx.Response(200, json=version_payload)
    )
    assert CivitaiClient().get_version_by_hash("ABC123").id == 649002


@respx.mock
def test_search_models_paginates(model_payload):
    page1 = {"items": [model_payload], "metadata": {"nextCursor": "c2"}}
    page2 = {"items": [{**model_payload, "id": 2}], "metadata": {}}
    route = respx.get(f"{BASE_URL}/models").mock(
        side_effect=[httpx.Response(200, json=page1), httpx.Response(200, json=page2)]
    )
    results = CivitaiClient().search_models(limit=2)
    assert [m.id for m in results] == [580857, 2]
    assert route.call_count == 2
    assert "cursor=c2" in str(route.calls.last.request.url)


# --- config token store -----------------------------------------------------

def test_token_store_roundtrip_and_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("CIVITAI_TOKEN", raising=False)
    assert read_stored_token() is None
    path = store_token("secret-key")
    assert path.exists() and oct(path.stat().st_mode)[-3:] == "600"
    assert read_stored_token() == "secret-key"
    assert resolve_settings().token == "secret-key"  # stored used when no flag/env
    monkeypatch.setenv("CIVITAI_TOKEN", "env-key")
    assert resolve_settings().token == "env-key"  # env beats stored
    assert resolve_settings(token="flag-key").token == "flag-key"  # flag beats all
    assert delete_token() is True
    assert read_stored_token() is None


# --- cache management --------------------------------------------------------

def _file(file_id, name, sha):
    return ModelFile.model_validate({"id": file_id, "name": name, "hashes": {"SHA256": sha}})


def test_cache_iter_entries_and_total(tmp_path):
    store = CacheStore(tmp_path)
    f = _file(1, "a.safetensors", "A" * 64)
    src = tmp_path / "in"
    src.write_bytes(b"hello")
    store.store(src, 10, 100, f)
    entries = store.iter_entries()
    assert len(entries) == 1
    e = entries[0]
    assert (e["model_id"], e["version_id"], e["filename"]) == (10, "100", "a.safetensors")
    assert e["sha"] == "A" * 64
    assert store.total_size() == 5


def test_cache_verify_detects_corruption(tmp_path):
    store = CacheStore(tmp_path)
    body = b"weights"
    f = _file(1, "a.safetensors", hashlib.sha256(body).hexdigest().upper())
    src = tmp_path / "in"
    src.write_bytes(body)
    store.store(src, 10, 100, f)
    assert all(ok for _, ok in store.verify())
    store.blob_path(10, f).write_bytes(b"TAMPERED")
    assert any(not ok for _, ok in store.verify())


def test_cache_remove_and_prune(tmp_path):
    store = CacheStore(tmp_path)
    f = _file(1, "a.safetensors", "A" * 64)
    src = tmp_path / "in"
    src.write_bytes(b"x")
    snap = store.store(src, 10, 100, f)
    store.incomplete_path(10, f).write_bytes(b"partial")  # leftover temp
    store.blob_path(10, f).unlink()  # makes the snapshot dangling
    stats = store.prune()
    assert stats == {"temps": 1, "dangling_snapshots": 1}
    assert not snap.exists()
    assert store.remove_model(10) is True
    assert store.remove_model(10) is False


# --- public API -------------------------------------------------------------

@respx.mock
def test_public_search(monkeypatch, tmp_path, model_payload):
    _env(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/models").mock(
        return_value=httpx.Response(200, json={"items": [model_payload], "metadata": {}})
    )
    assert [m.id for m in civitai_hub.search("skin", type="LORA")] == [580857]


@respx.mock
def test_public_find_by_hash(monkeypatch, tmp_path, version_payload, model_payload):
    _env(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/model-versions/by-hash/DEAD").mock(
        return_value=httpx.Response(200, json=version_payload)
    )
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    info = civitai_hub.find_by_hash("DEAD")
    assert info.model.id == 580857 and info.version.id == 649002


# --- CLI --------------------------------------------------------------------

@respx.mock
def test_cli_search(monkeypatch, tmp_path, model_payload):
    _env(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/models").mock(
        return_value=httpx.Response(200, json={"items": [model_payload], "metadata": {}})
    )
    result = runner.invoke(app, ["search", "skin", "--type", "LORA"])
    assert result.exit_code == 0
    assert "Realistic Skin Texture Style" in result.stdout


@respx.mock
def test_cli_by_hash_from_local_file(monkeypatch, tmp_path, version_payload, model_payload):
    _env(monkeypatch, tmp_path)
    blob = tmp_path / "model.safetensors"
    blob.write_bytes(b"weights")
    sha = hashlib.sha256(b"weights").hexdigest().upper()  # sha256_file returns uppercase
    respx.get(f"{BASE_URL}/model-versions/by-hash/{sha}").mock(
        return_value=httpx.Response(200, json=version_payload)
    )
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    result = runner.invoke(app, ["by-hash", str(blob)])
    assert result.exit_code == 0
    assert "580857" in result.stdout


def test_cli_login_config_logout(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    assert runner.invoke(app, ["login", "--token", "k-123"]).exit_code == 0
    cfg = runner.invoke(app, ["config"])
    assert cfg.exit_code == 0 and "token:      set" in cfg.stdout
    out = runner.invoke(app, ["logout"])
    assert out.exit_code == 0 and "removed" in out.stdout.lower()
    assert "No stored token" in runner.invoke(app, ["logout"]).stdout


@respx.mock
def test_cli_cache_ls_rm_prune(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    body = b"weights"
    respx.get(f"{BASE_URL}/models/1").mock(return_value=httpx.Response(200, json=_dl_payload(body)))
    respx.get("https://civitai.com/api/download/models/5").mock(
        return_value=httpx.Response(200, content=body)
    )
    assert runner.invoke(app, ["download", "1", "--no-progress"]).exit_code == 0
    ls = runner.invoke(app, ["cache", "ls"])
    assert ls.exit_code == 0 and "m.safetensors" in ls.stdout
    assert runner.invoke(app, ["cache", "verify"]).exit_code == 0
    assert runner.invoke(app, ["cache", "prune"]).exit_code == 0
    assert runner.invoke(app, ["cache", "rm", "1"]).exit_code == 0
    assert "m.safetensors" not in runner.invoke(app, ["cache", "ls"]).stdout


@respx.mock
def test_cli_download_json(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    body = b"weights"
    respx.get(f"{BASE_URL}/models/1").mock(return_value=httpx.Response(200, json=_dl_payload(body)))
    respx.get("https://civitai.com/api/download/models/5").mock(
        return_value=httpx.Response(200, content=body)
    )
    result = runner.invoke(app, ["download", "1", "--json", "--no-progress"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data[0]["filename"] == "m.safetensors"
    assert data[0]["size_bytes"] == len(body)


@respx.mock
def test_cli_download_offline_uncached_exits_8(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/models/1").mock(
        return_value=httpx.Response(200, json=_dl_payload(b"weights"))
    )
    # no download route mocked: --offline must error before any stream request
    result = runner.invoke(app, ["download", "1", "--offline", "--no-progress"])
    assert result.exit_code == 8  # OfflineError
