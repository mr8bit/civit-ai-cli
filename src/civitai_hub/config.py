"""Resolve settings with precedence: explicit arg > environment > default."""
import os
from dataclasses import dataclass
from pathlib import Path

import platformdirs


@dataclass
class Settings:
    token: str | None
    cache_dir: Path
    offline: bool
    use_symlinks: bool
    progress: bool


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_settings(
    *,
    token: str | None = None,
    cache_dir: str | os.PathLike | None = None,
    offline: bool | None = None,
    use_symlinks: bool | None = None,
    progress: bool | None = None,
) -> Settings:
    resolved_token = token or os.environ.get("CIVITAI_TOKEN") or read_stored_token()
    resolved_cache = (
        cache_dir
        or os.environ.get("CIVITAI_HOME")
        or platformdirs.user_cache_dir("civitai")
    )
    return Settings(
        token=resolved_token,
        cache_dir=Path(resolved_cache).expanduser(),
        offline=offline if offline is not None else _env_bool("CIVITAI_OFFLINE"),
        use_symlinks=(
            use_symlinks
            if use_symlinks is not None
            else not _env_bool("CIVITAI_DISABLE_SYMLINKS")
        ),
        progress=progress if progress is not None else not _env_bool("CIVITAI_NO_PROGRESS"),
    )


# --- token store (the `login` command) --------------------------------------
# Precedence: --token flag > CIVITAI_TOKEN env > this stored file > anonymous.

def token_file() -> Path:
    return Path(platformdirs.user_config_dir("civitai")) / "token"


def read_stored_token() -> str | None:
    try:
        return token_file().read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def store_token(token: str) -> Path:
    path = token_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token.strip(), encoding="utf-8")
    path.chmod(0o600)  # token is a secret
    return path


def delete_token() -> bool:
    path = token_file()
    existed = path.exists()
    path.unlink(missing_ok=True)
    return existed
