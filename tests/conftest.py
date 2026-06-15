"""Sample CivitAI payloads using real (sometimes messy) response shapes."""
import pytest


@pytest.fixture
def model_payload():
    # A LoRA model with one version; primary flag present, lean metadata.
    return {
        "id": 580857,
        "name": "Realistic Skin Texture Style",
        "type": "LORA",
        "nsfw": False,
        "creator": {"username": "someone", "image": None},
        "tags": ["style", "skin"],
        "stats": {"downloadCount": 1234, "thumbsUpCount": 56},
        "modelVersions": [
            {
                "id": 649001,
                "name": "v1.0",
                "baseModel": "SDXL 1.0",
                "baseModelType": "Standard",
                "status": "Published",
                "publishedAt": "2024-06-01T10:00:00.000Z",
                "trainedWords": ["detailed skin"],
                "downloadUrl": "https://civitai.com/api/download/models/649001",
                "files": [
                    {
                        "id": 11,
                        "name": "skin-v1.safetensors",
                        "sizeKB": 223232.0,
                        "type": "Model",
                        "metadata": {"format": "SafeTensor"},
                        "primary": True,
                        "hashes": {"SHA256": "a" * 64, "AutoV2": "b" * 10},
                        "downloadUrl": "https://civitai.com/api/download/models/649001",
                        "pickleScanResult": "Success",
                        "virusScanResult": "Success",
                    }
                ],
            },
            {
                "id": 649002,
                "name": "v2.0",
                "baseModel": "Pony",
                "status": "Published",
                "publishedAt": "2024-08-01T10:00:00.000Z",
                "trainedWords": [],
                "downloadUrl": "https://civitai.com/api/download/models/649002",
                "files": [
                    {
                        "id": 22,
                        "name": "skin-v2-fp16.safetensors",
                        "sizeKB": 100000.0,
                        "type": "Model",
                        "metadata": {"format": "SafeTensor", "size": "pruned", "fp": "fp16"},
                        "primary": True,
                        "hashes": {"SHA256": "c" * 64},
                        "downloadUrl": "https://civitai.com/api/download/models/649002",
                        "pickleScanResult": "Success",
                        "virusScanResult": "Success",
                    },
                    {
                        "id": 23,
                        "name": "skin-v2-fp32.safetensors",
                        "sizeKB": 200000.0,
                        "type": "Model",
                        "metadata": {"format": "SafeTensor", "size": "full", "fp": "fp32"},
                        # no 'primary' key at all (must default to False)
                        "hashes": {"SHA256": "d" * 64},
                        "downloadUrl": "https://civitai.com/api/download/models/649002",
                        "pickleScanResult": "Success",
                        "virusScanResult": "Success",
                    },
                ],
            },
        ],
    }


@pytest.fixture
def version_payload():
    # Shape returned by /model-versions/{id}: richer, carries modelId.
    return {
        "id": 649002,
        "modelId": 580857,
        "name": "v2.0",
        "baseModel": "Pony",
        "status": "Published",
        "publishedAt": "2024-08-01T10:00:00.000Z",
        "trainedWords": [],
        "model": {"name": "Realistic Skin Texture Style", "type": "LORA", "nsfw": False},
        "downloadUrl": "https://civitai.com/api/download/models/649002",
        "files": [
            {
                "id": 22,
                "name": "skin-v2-fp16.safetensors",
                "sizeKB": 100000.0,
                "type": "Model",
                "metadata": {"format": "SafeTensor", "size": "pruned", "fp": "fp16"},
                "primary": True,
                "hashes": {"SHA256": "c" * 64},
                "downloadUrl": "https://civitai.com/api/download/models/649002",
                "pickleScanResult": "Success",
                "virusScanResult": "Success",
            }
        ],
    }
