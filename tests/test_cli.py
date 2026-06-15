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


@respx.mock
def test_download_with_progress_writes_file(monkeypatch, tmp_path):
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
    # NOTE: no --no-progress here, exercising the progress-bar path
    result = runner.invoke(app, ["download", "1", "-o", str(out)])
    assert result.exit_code == 0
    assert (out / "m.safetensors").read_bytes() == body


@respx.mock
def test_info_output_not_duplicated(monkeypatch, tmp_path, model_payload):
    # Regression: _capture must not also print to real stdout (would double output).
    _env(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    result = runner.invoke(app, ["info", "580857"])
    assert result.exit_code == 0
    assert result.stdout.count("Realistic Skin Texture Style") == 1


@respx.mock
def test_dry_run_output_not_duplicated(monkeypatch, tmp_path, model_payload):
    _env(monkeypatch, tmp_path)
    respx.get(f"{BASE_URL}/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    result = runner.invoke(app, ["download", "580857", "--dry-run"])
    assert result.exit_code == 0
    assert result.stdout.count("Will download") == 1
