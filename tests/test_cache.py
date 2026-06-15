from civitai_hub.cache import CacheStore
from civitai_hub.models import ModelFile


def _file(file_id, name, sha):
    return ModelFile.model_validate(
        {"id": file_id, "name": name, "hashes": {"SHA256": sha}}
    )


def test_store_creates_blob_and_symlink(tmp_path):
    store = CacheStore(tmp_path)
    f = _file(1, "a.safetensors", "A" * 64)
    src = tmp_path / "incoming.bin"
    src.write_bytes(b"weights")

    snap = store.store(src, model_id=10, version_id=100, file=f)

    assert snap.read_bytes() == b"weights"
    blob = store.blob_path(10, f)
    assert blob.exists()
    assert store.is_cached(10, 100, f) is True
    assert (tmp_path / "CACHEDIR.TAG").exists()


def test_dedup_same_blob_across_versions(tmp_path):
    store = CacheStore(tmp_path)
    f = _file(1, "a.safetensors", "A" * 64)
    src1 = tmp_path / "v1.bin"
    src1.write_bytes(b"same")
    store.store(src1, 10, 100, f)
    # second version, identical content/hash -> reuse blob, new snapshot
    src2 = tmp_path / "v2.bin"
    src2.write_bytes(b"same")
    snap2 = store.store(src2, 10, 200, f)

    blobs = list((tmp_path / "models" / "10" / "blobs").iterdir())
    assert len(blobs) == 1
    assert snap2.read_bytes() == b"same"


def test_copy_fallback_when_symlinks_disabled(tmp_path):
    store = CacheStore(tmp_path, use_symlinks=False)
    f = _file(1, "a.safetensors", "A" * 64)
    src = tmp_path / "incoming.bin"
    src.write_bytes(b"data")
    snap = store.store(src, 10, 100, f)
    assert snap.is_symlink() is False
    assert snap.read_bytes() == b"data"


def test_not_cached_before_store(tmp_path):
    store = CacheStore(tmp_path)
    f = _file(1, "a.safetensors", "A" * 64)
    assert store.is_cached(10, 100, f) is False
