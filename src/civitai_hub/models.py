"""Pydantic models for CivitAI responses. Lenient: every optional API field
defaults, because metadata/hashes/primary are inconsistent across responses."""
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

_CFG = ConfigDict(extra="ignore", populate_by_name=True, protected_namespaces=())


class FileMetadata(BaseModel):
    model_config = _CFG

    format: str | None = None
    size: str | None = None
    fp: str | None = None


class ModelFile(BaseModel):
    model_config = _CFG

    id: int
    name: str
    size_kb: float | None = Field(default=None, alias="sizeKB")
    type: str | None = None
    metadata: FileMetadata = Field(default_factory=FileMetadata)
    primary: bool = False
    hashes: dict[str, str] = Field(default_factory=dict)
    download_url: str | None = Field(default=None, alias="downloadUrl")
    pickle_scan_result: str | None = Field(default=None, alias="pickleScanResult")
    virus_scan_result: str | None = Field(default=None, alias="virusScanResult")

    @property
    def sha256(self) -> str | None:
        for key, value in self.hashes.items():
            if key.upper() == "SHA256":
                return value.upper()
        return None

    @property
    def size_bytes(self) -> int | None:
        return round(self.size_kb * 1024) if self.size_kb is not None else None

    @property
    def is_safetensor(self) -> bool:
        return (self.metadata.format or "") == "SafeTensor"


class ModelVersion(BaseModel):
    model_config = _CFG

    id: int
    model_id: int | None = Field(default=None, alias="modelId")
    name: str | None = None
    base_model: str | None = Field(default=None, alias="baseModel")
    base_model_type: str | None = Field(default=None, alias="baseModelType")
    trained_words: list[str] = Field(default_factory=list, alias="trainedWords")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    status: str | None = None
    availability: str | None = None
    early_access_ends_at: datetime | None = Field(default=None, alias="earlyAccessEndsAt")
    download_url: str | None = Field(default=None, alias="downloadUrl")
    files: list[ModelFile] = Field(default_factory=list)

    @property
    def primary_file(self) -> ModelFile | None:
        return next((f for f in self.files if f.primary), None)


class Model(BaseModel):
    model_config = _CFG

    id: int
    name: str
    type: str | None = None
    nsfw: bool = False
    creator: dict | None = None
    tags: list[str] = Field(default_factory=list)
    stats: dict | None = None
    model_versions: list[ModelVersion] = Field(default_factory=list, alias="modelVersions")


@dataclass
class ModelInfo:
    """Return value of the public model_info()."""

    model: Model
    version: ModelVersion
    files: list[ModelFile]


@dataclass
class PlanItem:
    """One line of a --dry-run plan."""

    file_name: str
    size_bytes: int | None
    cached: bool


@dataclass
class BaseModelMatches:
    """Candidate base checkpoints for a model's baseModel family."""

    source: Model
    version: ModelVersion
    base_model: str | None
    candidates: list[Model]
