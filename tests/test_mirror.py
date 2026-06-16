"""civitai.red mirror support: host config, URL routing, download trust."""
import httpx
import pytest
import respx

import civitai_hub
from civitai_hub.client import CivitaiClient
from civitai_hub.config import resolve_settings
from civitai_hub.download import _require_trusted_host
from civitai_hub.errors import CivitaiError


def test_host_config_precedence_and_validation(monkeypatch):
    monkeypatch.delenv("CIVITAI_HOST", raising=False)
    assert resolve_settings().host == "civitai.com"
    monkeypatch.setenv("CIVITAI_HOST", "civitai.red")
    assert resolve_settings().host == "civitai.red"
    assert resolve_settings(host="civitai.com").host == "civitai.com"  # flag beats env
    monkeypatch.setenv("CIVITAI_HOST", "evil.example")
    with pytest.raises(CivitaiError, match="Unsupported host"):
        resolve_settings()


def test_client_base_url_follows_host():
    assert CivitaiClient().base_url == "https://civitai.com/api/v1"
    assert CivitaiClient(host="civitai.red").base_url == "https://civitai.red/api/v1"


def test_download_trusts_both_mirrors():
    _require_trusted_host("https://civitai.com/api/download/models/5")
    _require_trusted_host("https://civitai.red/api/download/models/5")
    _require_trusted_host("https://image.civitai.red/x")  # subdomain ok
    with pytest.raises(CivitaiError, match="untrusted host"):
        _require_trusted_host("https://attacker.example/grab")


@respx.mock
def test_red_url_routes_to_red_api(monkeypatch, tmp_path, model_payload):
    monkeypatch.setenv("CIVITAI_HOME", str(tmp_path))
    for var in ["CIVITAI_TOKEN", "CIVITAI_HOST"]:
        monkeypatch.delenv(var, raising=False)
    route = respx.get("https://civitai.red/api/v1/models/580857").mock(
        return_value=httpx.Response(200, json=model_payload)
    )
    info = civitai_hub.model_info("https://civitai.red/models/580857/x")
    assert info.model.id == 580857
    assert route.called  # the .red URL hit the .red API, not civitai.com
