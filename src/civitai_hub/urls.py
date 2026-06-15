"""Parse CivitAI URLs / ids into a ModelRef."""
import re
from dataclasses import dataclass

from .errors import InvalidURLError

_DOWNLOAD_RE = re.compile(r"civitai\.com/api/download/models/(\d+)")
_MODEL_RE = re.compile(r"civitai\.com/models/(\d+)")
_VERSION_QS_RE = re.compile(r"[?&]modelVersionId=(\d+)")


@dataclass(frozen=True)
class ModelRef:
    """A reference to a model and (optionally) a pinned version.

    model_id is None only for api/download URLs that carry just a version id.
    """

    model_id: int | None
    version_id: int | None = None


def parse_model_url(value: str) -> ModelRef:
    s = (value or "").strip()
    if not s:
        raise InvalidURLError("Empty model reference")

    if s.isdigit():
        return ModelRef(model_id=int(s))

    m = _DOWNLOAD_RE.search(s)
    if m:
        return ModelRef(model_id=None, version_id=int(m.group(1)))

    m = _MODEL_RE.search(s)
    if m:
        vq = _VERSION_QS_RE.search(s)
        version_id = int(vq.group(1)) if vq else None
        return ModelRef(model_id=int(m.group(1)), version_id=version_id)

    raise InvalidURLError(f"Not a CivitAI model URL or id: {s!r}")
