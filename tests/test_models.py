from civitai_hub.models import Model, ModelVersion


def test_model_parses_and_aliases(model_payload):
    model = Model.model_validate(model_payload)
    assert model.id == 580857
    assert model.type == "LORA"
    assert len(model.model_versions) == 2


def test_file_helper_properties(model_payload):
    model = Model.model_validate(model_payload)
    v1 = model.model_versions[0]
    f = v1.files[0]
    assert f.sha256 == "A" * 64  # uppercased
    assert f.size_bytes == round(223232.0 * 1024)
    assert f.is_safetensor is True
    assert v1.primary_file is f


def test_missing_primary_defaults_false_and_metadata_safe(model_payload):
    v2 = Model.model_validate(model_payload).model_versions[1]
    fp32_file = v2.files[1]
    assert fp32_file.primary is False
    assert fp32_file.metadata.fp == "fp32"
    # file with absent metadata keys still parses
    assert v2.files[0].metadata.size == "pruned"


def test_version_endpoint_shape_carries_model_id(version_payload):
    v = ModelVersion.model_validate(version_payload)
    assert v.model_id == 580857
    assert v.base_model == "Pony"
