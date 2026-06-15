"""Live test against the real CivitAI API. Opt-in only:
    CIVITAI_LIVE=1 pytest tests/test_live.py -v
Never runs in normal/CI runs."""
import os

import pytest

import civitai_hub

pytestmark = pytest.mark.skipif(
    os.environ.get("CIVITAI_LIVE") != "1", reason="set CIVITAI_LIVE=1 to run live"
)


def test_real_model_info():
    info = civitai_hub.model_info("https://civitai.com/models/580857")
    assert info.model.id == 580857
    assert info.files  # at least one file
