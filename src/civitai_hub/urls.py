"""Parse CivitAI URLs / ids into a ModelRef."""
import re
from dataclasses import dataclass

from .errors import InvalidURLError

# civitai.com and its transparent mirror civitai.red share the same paths/ids.
_DOWNLOAD_RE = re.compile(r"civitai\.(?:com|red)/api/download/models/(\d+)")
_MODEL_RE = re.compile(r"civitai\.(?:com|red)/models/(\d+)")
_HOST_RE = re.compile(r"\b(civitai\.(?:com|red))")
_VERSION_QS_RE = re.compile(r"[?&]modelVersionId=(\d+)")


@dataclass(frozen=True)
class ModelRef:
    """A reference to a model and (optionally) a pinned version.

    model_id is None only for api/download URLs that carry just a version id.
    host is the mirror the URL was on (civitai.com / civitai.red), or None for a
    bare id (which then falls back to the configured default host).
    """

    model_id: int | None
    version_id: int | None = None
    host: str | None = None


def parse_model_url(value: str) -> ModelRef:
    s = (value or "").strip()
    if not s:
        raise InvalidURLError("Empty model reference")

    if s.isdigit():
        return ModelRef(model_id=int(s))

    host_match = _HOST_RE.search(s)
    host = host_match.group(1) if host_match else None

    m = _DOWNLOAD_RE.search(s)
    if m:
        return ModelRef(model_id=None, version_id=int(m.group(1)), host=host)

    m = _MODEL_RE.search(s)
    if m:
        vq = _VERSION_QS_RE.search(s)
        version_id = int(vq.group(1)) if vq else None
        return ModelRef(model_id=int(m.group(1)), version_id=version_id, host=host)

    raise InvalidURLError(f"Not a CivitAI model URL or id: {s!r}")
