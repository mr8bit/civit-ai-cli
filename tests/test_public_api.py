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


@respx.mock
def test_download_invokes_progress_cb(monkeypatch, tmp_path):
    _patch_cache(monkeypatch, tmp_path)
    body = b"weights-data-1234567890"
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
    calls = []
    civitai_hub.download("1", progress_cb=lambda d, t: calls.append((d, t)))
    assert calls  # invoked at least once
    assert calls[-1][0] == len(body)  # final downloaded == file size


@respx.mock
def test_find_base_models(monkeypatch, tmp_path, model_payload):
    _patch_cache(monkeypatch, tmp_path)
    # source model 580857; its LATEST version (649002) has baseModel "Pony"
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    checkpoint = {**model_payload, "id": 999, "name": "Some Checkpoint", "type": "Checkpoint"}
    respx.get(f"{BASE_URL}/models").mock(
        return_value=httpx.Response(200, json={"items": [checkpoint], "metadata": {}})
    )
    matches = civitai_hub.find_base_models("580857")
    assert matches.base_model == "Pony"
    assert [m.id for m in matches.candidates] == [999]
    assert matches.source.id == 580857


@respx.mock
def test_find_base_models_no_base_model(monkeypatch, tmp_path):
    _patch_cache(monkeypatch, tmp_path)
    payload = {
        "id": 7, "name": "No Base", "type": "LORA",
        "modelVersions": [{"id": 70, "status": "Published",
                           "publishedAt": "2024-01-01T00:00:00.000Z", "files": []}],
    }
    respx.get(f"{BASE_URL}/models/7").mock(return_value=httpx.Response(200, json=payload))
    matches = civitai_hub.find_base_models("7")
    assert matches.base_model is None
    assert matches.candidates == []
