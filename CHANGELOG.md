# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Reject path-traversal / absolute filenames supplied by the API before building any path
  (could otherwise write outside the cache / `--local-dir`).
- Validate the download host (`civitai.com` only) before requesting — closes SSRF and stops the
  auth token from reaching an API-named third-party host.
- Send the token via the `Authorization` header instead of a `?token=` query param, so it never
  appears in a URL, log, or traceback.

### Fixed
- Wrap transport failures (`httpx` connect/read/protocol errors) as a catchable `NetworkError`
  (exit code 10) with transport-level retry, instead of leaking a raw traceback.
- `--force` now restarts the download from scratch instead of resuming a stale partial.
- `link_or_copy` falls back to copy on Windows cross-drive `ValueError`, not just `OSError`.

### Packaging
- Single-source the version from `__init__.py` (`[tool.hatch.version]`); the publish workflow
  guards that the package version matches the release tag.
- Trim dev files from the PyPI sdist; add Dependabot for GitHub Actions.

## [0.1.0] - 2026-06-16

### Added
- `civitai info <url|id>` — inspect a model: type, base/parent model, versions, and a
  table of every file (size, format, precision, hash, scan status); `--json` output.
- `civitai download <url|id>` — smart version/file selection (`--version-id`, `--fp16/--fp32`,
  `--pruned/--full`, `--format`, `--file`, `--all`), a content-addressed deduplicated cache,
  HTTP range-resume, SHA256 verification, a progress bar, `--local-dir` materialization, and `--dry-run`.
- `civitai base <url|id>` — find base checkpoints matching a model's base-model family,
  with `--download N` to fetch one.
- Importable library API: `civitai_hub.model_info`, `civitai_hub.download`, `civitai_hub.find_base_models`.
- Configuration via flags and `CIVITAI_TOKEN` / `CIVITAI_HOME` / `CIVITAI_OFFLINE` /
  `CIVITAI_DISABLE_SYMLINKS` / `CIVITAI_NO_PROGRESS`.
- GitHub Actions: CI (`ruff` + `pytest` on Python 3.10–3.13); on each release the wheel + sdist
  are attached to the GitHub release and published to PyPI (trusted publishing); a multi-arch
  Docker image is published to `ghcr.io`.

[Unreleased]: https://github.com/mr8bit/civit-ai-cli/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mr8bit/civit-ai-cli/releases/tag/v0.1.0
