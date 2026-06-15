from civitai_hub.models import Model, ModelInfo, PlanItem
from civitai_hub.render import render_dry_run, render_model_info


def test_render_model_info_mentions_key_facts(model_payload):
    model = Model.model_validate(model_payload)
    version = model.model_versions[1]
    info = ModelInfo(model=model, version=version, files=list(version.files))
    text = render_model_info(info)
    assert "Realistic Skin Texture Style" in text
    assert "LORA" in text
    assert "Pony" in text  # base model
    assert "580857" in text  # parent model id
    assert "2 files" in text
    assert "someone" in text  # creator
    assert "1234" in text  # download count


def test_render_dry_run_lists_files_and_total():
    plan = [
        PlanItem("a.safetensors", 1024 * 1024, cached=False),
        PlanItem("b.safetensors", None, cached=True),
    ]
    text = render_dry_run(plan)
    assert "a.safetensors" in text
    assert "b.safetensors" in text
    assert "cached" in text.lower()


def test_download_progress_disabled_yields_none():
    from civitai_hub.render import download_progress

    with download_progress(False) as cb:
        assert cb is None


def test_download_progress_enabled_yields_callable():
    from civitai_hub.render import download_progress

    with download_progress(True) as cb:
        assert callable(cb)
        cb(10, 100)   # must not raise
        cb(0, None)   # new file / indeterminate total must not raise
