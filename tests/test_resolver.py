import pytest

from civitai_hub.errors import AmbiguousFileError, NoMatchingFileError, NotFoundError
from civitai_hub.models import Model
from civitai_hub.resolver import FileSelectors, pick_files, pick_version


def test_pick_latest_version_by_published_at(model_payload):
    model = Model.model_validate(model_payload)
    v = pick_version(model)
    assert v.id == 649002  # newer publishedAt than 649001


def test_pick_pinned_version(model_payload):
    model = Model.model_validate(model_payload)
    assert pick_version(model, version_id=649001).id == 649001


def test_pick_unknown_version_raises(model_payload):
    model = Model.model_validate(model_payload)
    with pytest.raises(NotFoundError):
        pick_version(model, version_id=999)


def test_default_picks_primary_file(model_payload):
    v = Model.model_validate(model_payload).model_versions[0]
    files = pick_files(v, FileSelectors())
    assert len(files) == 1 and files[0].id == 11


def test_fp_selector(model_payload):
    v = Model.model_validate(model_payload).model_versions[1]
    files = pick_files(v, FileSelectors(fp="fp32"))
    assert [f.id for f in files] == [23]


def test_all_returns_every_file(model_payload):
    v = Model.model_validate(model_payload).model_versions[1]
    files = pick_files(v, FileSelectors(all=True))
    assert {f.id for f in files} == {22, 23}


def test_no_match_raises(model_payload):
    v = Model.model_validate(model_payload).model_versions[1]
    with pytest.raises(NoMatchingFileError):
        pick_files(v, FileSelectors(fp="bf16"))


def test_ambiguous_selector_raises(model_payload):
    v = Model.model_validate(model_payload).model_versions[1]
    with pytest.raises(AmbiguousFileError):
        pick_files(v, FileSelectors(type="Model"))


def test_no_primary_falls_back_to_first_safetensor(model_payload):
    # Build a version where no file is primary.
    model = Model.model_validate(model_payload)
    v = model.model_versions[1]
    for f in v.files:
        f.primary = False
    files = pick_files(v, FileSelectors())
    assert files[0].id == 22  # first Model-type safetensor


def test_no_files_no_selectors_raises(model_payload):
    v = Model.model_validate(model_payload).model_versions[0]
    v.files = []
    with pytest.raises(NoMatchingFileError):
        pick_files(v, FileSelectors())
