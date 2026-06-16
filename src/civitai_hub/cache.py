"""Content-addressed cache: blobs/<sha256> + snapshots/<versionId>/<name> links."""
import hashlib
import os
import shutil
from pathlib import Path

from .models import ModelFile

_SHA_RE = set("0123456789abcdefABCDEF")


def sha256_file(path) -> str:
    """Streamed SHA256 of a file as uppercase hex."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()

_CACHEDIR_TAG = (
    "Signature: 8a477f597d28d172789f06886806bc55\n"
    "# This file marks this directory as a cache for civitai-hub.\n"
)


def link_or_copy(src: Path, dest: Path, use_symlinks: bool) -> None:
    """Replace `dest` with a relative symlink to `src`, or a copy when symlinks
    are disabled or unsupported (Windows without privilege, some NAS)."""
    if dest.is_symlink() or dest.exists():
        dest.unlink()
    if use_symlinks:
        try:
            dest.symlink_to(os.path.relpath(src, dest.parent))
            return
        except (OSError, ValueError):  # ValueError: relpath across Windows drives
            pass
    shutil.copy2(src, dest)


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

    def is_cached(self, model_id: int, file: ModelFile) -> bool:
        return self.blob_path(model_id, file).exists()

    def store(self, tmp_path, model_id: int, version_id: int, file: ModelFile) -> Path:
        self.ensure_root()
        blob = self.blob_path(model_id, file)
        blob.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp_path, blob)
        snap = self.snapshot_path(model_id, version_id, file.name)
        snap.parent.mkdir(parents=True, exist_ok=True)
        link_or_copy(blob, snap, self.use_symlinks)
        return snap

    def _models_root(self) -> Path:
        return self.root / "models"

    def iter_entries(self) -> list[dict]:
        """One row per cached file (snapshot), with its blob sha and size."""
        out = []
        if not self._models_root().exists():
            return out
        for model_dir in sorted(self._models_root().iterdir()):
            if not model_dir.name.isdigit():
                continue
            snaps = model_dir / "snapshots"
            if not snaps.exists():
                continue
            for ver_dir in sorted(snaps.iterdir()):
                for f in sorted(ver_dir.iterdir()):
                    out.append({
                        "model_id": int(model_dir.name),
                        "version_id": ver_dir.name,
                        "filename": f.name,
                        "size_bytes": f.stat().st_size if f.exists() else 0,
                        "sha": f.resolve().name if f.is_symlink() else "(copy)",
                    })
        return out

    def total_size(self) -> int:
        return sum(
            b.stat().st_size
            for b in self._models_root().glob("*/blobs/*")
            if b.is_file() and not b.name.endswith(".incomplete")
        )

    def verify(self) -> list[tuple[Path, bool]]:
        """Re-hash every sha256-named blob; ok when content matches the name."""
        results = []
        for blob in self._models_root().glob("*/blobs/*"):
            name = blob.name
            if len(name) != 64 or not set(name) <= _SHA_RE:
                continue  # skip file-<id> (hashless) blobs and .incomplete temps
            results.append((blob, sha256_file(blob) == name.upper()))
        return results

    def remove_model(self, model_id: int) -> bool:
        model_dir = self._model_dir(model_id)
        if model_dir.exists():
            shutil.rmtree(model_dir)
            return True
        return False

    def prune(self) -> dict:
        """Remove leftover .incomplete temps and dangling snapshot symlinks."""
        temps = snaps = 0
        for tmp in self._models_root().glob("*/blobs/*.incomplete"):
            tmp.unlink(missing_ok=True)
            temps += 1
        for snap in self._models_root().glob("*/snapshots/*/*"):
            if snap.is_symlink() and not snap.resolve().exists():
                snap.unlink()
                snaps += 1
        return {"temps": temps, "dangling_snapshots": snaps}
