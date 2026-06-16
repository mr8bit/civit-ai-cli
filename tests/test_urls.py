import pytest

from civitai_hub.errors import InvalidURLError
from civitai_hub.urls import ModelRef, parse_model_url


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://civitai.com/models/580857/realistic-skin", ModelRef(580857, None, "civitai.com")),
        ("https://civitai.com/models/580857", ModelRef(580857, None, "civitai.com")),
        ("https://civitai.com/models/580857?modelVersionId=649002", ModelRef(580857, 649002, "civitai.com")),
        ("https://civitai.com/models/580857/slug?modelVersionId=649002&foo=1", ModelRef(580857, 649002, "civitai.com")),
        ("https://civitai.com/api/download/models/649002", ModelRef(None, 649002, "civitai.com")),
        ("580857", ModelRef(580857, None, None)),
        ("  https://civitai.com/models/580857  ", ModelRef(580857, None, "civitai.com")),
        # civitai.red mirror — same ids, host captured
        ("https://civitai.red/models/580857/x", ModelRef(580857, None, "civitai.red")),
        ("https://civitai.red/models/580857?modelVersionId=649002", ModelRef(580857, 649002, "civitai.red")),
        ("https://civitai.red/api/download/models/649002", ModelRef(None, 649002, "civitai.red")),
    ],
)
def test_parse_variants(url, expected):
    assert parse_model_url(url) == expected


@pytest.mark.parametrize("bad", ["", "   ", "https://example.com/x", "not a url"])
def test_parse_invalid(bad):
    with pytest.raises(InvalidURLError):
        parse_model_url(bad)
