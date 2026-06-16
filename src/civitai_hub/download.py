"""Download a single file: availability + scan gates, stream+resume, verify,
store, materialize."""
import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .cache import CacheStore, link_or_copy
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
    link_or_copy(blob, dest, use_symlinks)
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

    if force or not store.is_cached(model_id, file):
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
