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

    def _get_json(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        for attempt in range(self.max_retries + 1):
            resp = self.http.get(url, params=params)
            retriable = resp.status_code == 429 or resp.status_code >= 500
            if retriable and attempt < self.max_retries:
                time.sleep(self.backoff_base * (2**attempt))
                continue
            self._raise_for_status(resp)  # the final retriable attempt raises here too
            return resp.json()
        raise CivitaiError("Request failed: max_retries must be >= 0.")

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

    def search_models(
        self,
        *,
        types: str | None = None,
        base_models: str | None = None,
        query: str | None = None,
        sort: str | None = None,
        limit: int | None = 20,
    ) -> list[Model]:
        params = {
            k: v
            for k, v in {
                "types": types,
                "baseModels": base_models,
                "query": query,
                "sort": sort,
                "limit": limit,
            }.items()
            if v is not None
        }
        data = self._get_json("/models", params=params)
        return [Model.model_validate(item) for item in data.get("items", [])]
