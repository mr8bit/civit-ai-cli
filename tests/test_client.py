import httpx
import pytest
import respx

from civitai_hub.client import BASE_URL, CivitaiClient
from civitai_hub.errors import (
    AuthRequiredError,
    ForbiddenError,
    NetworkError,
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
def test_transport_error_wrapped_as_network_error():
    respx.get(f"{BASE_URL}/models/9").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(NetworkError):
        CivitaiClient(max_retries=1, backoff_base=0).get_model(9)


@respx.mock
def test_search_models_parses_items_and_sends_params(model_payload):
    listing = {"items": [model_payload], "metadata": {}}
    route = respx.get(f"{BASE_URL}/models").mock(
        return_value=httpx.Response(200, json=listing)
    )
    results = CivitaiClient().search_models(
        types="Checkpoint", base_models="Pony", sort="Most Downloaded", limit=5
    )
    assert [m.id for m in results] == [580857]
    url = str(route.calls.last.request.url)
    assert "types=Checkpoint" in url
    assert "baseModels=Pony" in url
    assert "limit=5" in url


@respx.mock
def test_search_models_empty_items():
    respx.get(f"{BASE_URL}/models").mock(
        return_value=httpx.Response(200, json={"items": [], "metadata": {}})
    )
    assert CivitaiClient().search_models(query="nothing") == []
