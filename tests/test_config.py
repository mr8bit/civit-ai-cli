from pathlib import Path

from civitai_hub.config import resolve_settings


def test_flag_beats_env(monkeypatch):
    monkeypatch.setenv("CIVITAI_TOKEN", "from-env")
    s = resolve_settings(token="from-flag")
    assert s.token == "from-flag"


def test_env_used_when_no_flag(monkeypatch):
    monkeypatch.setenv("CIVITAI_TOKEN", "from-env")
    monkeypatch.setenv("CIVITAI_HOME", "/tmp/civ-cache")
    s = resolve_settings()
    assert s.token == "from-env"
    assert s.cache_dir == Path("/tmp/civ-cache")


def test_defaults(monkeypatch):
    for var in ["CIVITAI_TOKEN", "CIVITAI_HOME", "CIVITAI_OFFLINE",
                "CIVITAI_DISABLE_SYMLINKS", "CIVITAI_NO_PROGRESS"]:
        monkeypatch.delenv(var, raising=False)
    s = resolve_settings()
    assert s.token is None
    assert s.offline is False
    assert s.use_symlinks is True
    assert s.progress is True
    assert "civitai" in str(s.cache_dir).lower()


def test_bool_env_parsing(monkeypatch):
    monkeypatch.setenv("CIVITAI_OFFLINE", "1")
    monkeypatch.setenv("CIVITAI_DISABLE_SYMLINKS", "true")
    s = resolve_settings()
    assert s.offline is True
    assert s.use_symlinks is False
