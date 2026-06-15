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
