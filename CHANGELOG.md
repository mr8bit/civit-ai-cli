# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- GitHub Actions: CI (`ruff` + `pytest` on Python 3.10–3.13), PyPI publish (trusted publishing),
  and a multi-arch Docker image published to `ghcr.io`.

[Unreleased]: https://github.com/mr8bit/civit-ai-cli/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mr8bit/civit-ai-cli/releases/tag/v0.1.0
