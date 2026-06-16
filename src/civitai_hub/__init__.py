"""civitai_hub — huggingface_hub, but for CivitAI."""
from .cache import CacheStore
from .client import CivitaiClient
from .config import resolve_settings
from .download import download_file
from .errors import NotFoundError
from .models import BaseModelMatches, Model, ModelInfo, ModelVersion, PlanItem
from .resolver import FileSelectors, pick_files, pick_version
from .urls import parse_model_url

__version__ = "0.1.0"
__all__ = ["model_info", "download", "find_base_models", "ModelInfo", "PlanItem", "BaseModelMatches", "__version__"]


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


def find_base_models(
    url_or_id, *, version_id=None, limit=10, token=None, cache_dir=None
) -> BaseModelMatches:
    settings = resolve_settings(token=token, cache_dir=cache_dir)
    ref = parse_model_url(str(url_or_id))
    client = CivitaiClient(token=settings.token)
    model, version = _resolve(client, ref, version_id)
    family = version.base_model
    candidates = []
    if family:
        candidates = client.search_models(
            types="Checkpoint", base_models=family, sort="Most Downloaded", limit=limit
        )
    return BaseModelMatches(
        source=model, version=version, base_model=family, candidates=candidates
    )
