"""Pure selection logic: which version, which file(s)."""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .errors import AmbiguousFileError, NoMatchingFileError, NotFoundError
from .models import Model, ModelFile, ModelVersion

logger = logging.getLogger(__name__)
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


@dataclass
class FileSelectors:
    file_name: str | None = None
    type: str | None = None
    format: str | None = None
    size: str | None = None
    fp: str | None = None
    all: bool = False

    @property
    def has_selectors(self) -> bool:
        return any([self.file_name, self.type, self.format, self.size, self.fp])


def _sort_key(version: ModelVersion):
    dt = version.published_at
    if dt is None:
        return (_EPOCH, version.id)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt, version.id)


def pick_version(model: Model, version_id: int | None = None) -> ModelVersion:
    versions = model.model_versions
    if not versions:
        raise NotFoundError(f"Model {model.id} has no versions.")
    if version_id is not None:
        for v in versions:
            if v.id == version_id:
                return v
        raise NotFoundError(f"Version {version_id} not found in model {model.id}.")
    published = [v for v in versions if (v.status or "Published") == "Published"]
    pool = published or versions
    return max(pool, key=_sort_key)


def _matches(file: ModelFile, sel: FileSelectors) -> bool:
    def eq(value: str | None, want: str | None) -> bool:
        return want is None or (value or "").lower() == want.lower()

    return (
        eq(file.name, sel.file_name)
        and eq(file.type, sel.type)
        and eq(file.metadata.format, sel.format)
        and eq(file.metadata.size, sel.size)
        and eq(file.metadata.fp, sel.fp)
    )


def _describe(files: list[ModelFile]) -> str:
    return "; ".join(
        f"{f.name} (type={f.type}, fp={f.metadata.fp}, size={f.metadata.size})"
        for f in files
    )


def pick_files(version: ModelVersion, selectors: FileSelectors) -> list[ModelFile]:
    candidates = [f for f in version.files if _matches(f, selectors)]

    if not candidates:
        if selectors.has_selectors:
            raise NoMatchingFileError(
                f"No file in version {version.id} matches the given filters. "
                f"Available: {_describe(version.files)}"
            )
        raise NoMatchingFileError(f"Version {version.id} has no files.")

    if selectors.all:
        return candidates
    if len(candidates) == 1:
        return candidates

    if not selectors.has_selectors:
        primary = version.primary_file
        if primary is not None:
            return [primary]
        for f in candidates:
            if (f.type or "") == "Model" and f.is_safetensor:
                logger.warning("No primary file; defaulting to %s", f.name)
                return [f]
        logger.warning("No primary file; defaulting to %s", candidates[0].name)
        return [candidates[0]]

    raise AmbiguousFileError(
        f"Multiple files match in version {version.id}; narrow with "
        f"--file/--format/--fp/--size or use --all. Candidates: {_describe(candidates)}"
    )
