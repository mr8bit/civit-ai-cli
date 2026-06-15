# civitai-hub

`huggingface_hub`, but for [CivitAI](https://civitai.com). Inspect a model and
download its checkpoint / LoRA into a deduplicated managed cache.

## Install

    pipx install civitai-hub      # or: pip install -e ".[dev]" for development

## CLI

    civitai info  https://civitai.com/models/580857/realistic-skin
    civitai download https://civitai.com/models/580857 --fp16 -o ~/ComfyUI/models/loras
    civitai download 580857 --dry-run
    civitai download 580857 --all

Auth (for gated / NSFW): `export CIVITAI_TOKEN=<your key>` or pass `--token`.

## Library

```python
import civitai_hub

info = civitai_hub.model_info("https://civitai.com/models/580857")
path = civitai_hub.download("https://civitai.com/models/580857", fp="fp16",
                            local_dir="~/ComfyUI/models/loras")
```

## Configuration

| Env | Meaning |
|---|---|
| `CIVITAI_TOKEN` | API key |
| `CIVITAI_HOME` | cache root (default: platform cache dir) |
| `CIVITAI_OFFLINE` | serve cache only |
| `CIVITAI_DISABLE_SYMLINKS` | copy instead of symlink |
| `CIVITAI_NO_PROGRESS` | disable progress |

See `docs/superpowers/specs/` and `docs/superpowers/plans/` for design details.
