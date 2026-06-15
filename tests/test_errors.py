import pytest

from civitai_hub import errors


def test_all_errors_subclass_base_and_have_exit_codes():
    classes = [
        errors.InvalidURLError, errors.AuthRequiredError, errors.NotFoundError,
        errors.ForbiddenError, errors.EarlyAccessError, errors.NoMatchingFileError,
        errors.AmbiguousFileError, errors.HashMismatchError, errors.OfflineError,
        errors.RateLimitError,
    ]
    for cls in classes:
        assert issubclass(cls, errors.CivitaiError)
        assert isinstance(cls.exit_code, int)


def test_exit_codes_are_distinct_per_category():
    assert errors.AuthRequiredError.exit_code == 3
    assert errors.NotFoundError.exit_code == 4
    assert errors.HashMismatchError.exit_code == 7
    assert errors.EarlyAccessError.exit_code == errors.ForbiddenError.exit_code


def test_raising_carries_message():
    with pytest.raises(errors.NotFoundError, match="missing"):
        raise errors.NotFoundError("missing model")
