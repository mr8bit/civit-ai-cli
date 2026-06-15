"""Content-addressed cache: blobs/<sha256> + snapshots/<versionId>/<name> links."""
import os
import shutil
from pathlib import Path

from .models import ModelFile

_CACHEDIR_TAG = (
    "Signature: 8a477f597d28d172789f06886806bc55\n"
    "# This file marks this directory as a cache for civitai-hub.\n"
)


class CacheStore:
    def __init__(self, root, use_symlinks: bool = True):
        self.root = Path(root).expanduser()
        self.use_symlinks = use_symlinks

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tag = self.root / "CACHEDIR.TAG"
        if not tag.exists():
            tag.write_text(_CACHEDIR_TAG)

    def _model_dir(self, model_id: int) -> Path:
        return self.root / "models" / str(model_id)

    def blob_path(self, model_id: int, file: ModelFile) -> Path:
        key = file.sha256 or f"file-{file.id}"
        return self._model_dir(model_id) / "blobs" / key

    def incomplete_path(self, model_id: int, file: ModelFile) -> Path:
        blob = self.blob_path(model_id, file)
        return blob.parent / (blob.name + ".incomplete")

    def snapshot_path(self, model_id: int, version_id: int, filename: str) -> Path:
        return self._model_dir(model_id) / "snapshots" / str(version_id) / filename

    def is_cached(self, model_id: int, version_id: int, file: ModelFile) -> bool:
        return self.blob_path(model_id, file).exists()

    def store(self, tmp_path, model_id: int, version_id: int, file: ModelFile) -> Path:
        self.ensure_root()
        blob = self.blob_path(model_id, file)
        blob.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp_path, blob)
        snap = self.snapshot_path(model_id, version_id, file.name)
        snap.parent.mkdir(parents=True, exist_ok=True)
        self._link(blob, snap)
        return snap

    def _link(self, blob: Path, snap: Path) -> None:
        if snap.is_symlink() or snap.exists():
            snap.unlink()
        if self.use_symlinks:
            try:
                snap.symlink_to(os.path.relpath(blob, snap.parent))
                return
            except OSError:
                pass
        shutil.copy2(blob, snap)
