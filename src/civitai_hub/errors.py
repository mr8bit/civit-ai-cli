"""Exception hierarchy. Each maps to a distinct CLI exit code."""


class CivitaiError(Exception):
    exit_code = 1


class InvalidURLError(CivitaiError):
    exit_code = 2


class AuthRequiredError(CivitaiError):
    exit_code = 3


class NotFoundError(CivitaiError):
    exit_code = 4


class ForbiddenError(CivitaiError):
    exit_code = 5


class EarlyAccessError(ForbiddenError):
    exit_code = 5


class NoMatchingFileError(CivitaiError):
    exit_code = 6


class AmbiguousFileError(CivitaiError):
    exit_code = 6


class HashMismatchError(CivitaiError):
    exit_code = 7


class OfflineError(CivitaiError):
    exit_code = 8


class RateLimitError(CivitaiError):
    exit_code = 9
