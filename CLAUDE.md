# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Status: starter / not yet implemented.** This directory is currently empty — there is no source code, build system, or test suite yet. The sections below describe the *intended* project. Replace the `TODO` placeholders with real commands and architecture details as code is added, and delete this banner once the project is scaffolded.

## What this project is

`civit-ai-cli` is intended to be a command-line tool for [CivitAI](https://civitai.com) — browsing, searching, and downloading models, LoRAs, checkpoints, and images via CivitAI's public REST API.

The technology stack has **not been chosen yet**. Before scaffolding, decide on:
- Language/runtime (e.g. Node/TypeScript, Python, Go, Rust)
- CLI framework (e.g. commander/oclif, click/typer, cobra, clap)
- HTTP client and how API responses are typed/modeled

Once chosen, document the concrete decisions here so future sessions don't have to re-derive them.

## Commands

Fill these in once the stack and tooling exist. Keep them runnable and specific (include how to run a *single* test).

- Install deps: `TODO`
- Build: `TODO`
- Run the CLI locally: `TODO`
- Lint / format: `TODO`
- Run all tests: `TODO`
- Run a single test: `TODO`

## Architecture (intended)

A CLI for an external API typically separates these concerns — keep them in distinct modules so the boundaries stay clear as the tool grows:

- **CLI / command layer** — argument parsing, subcommands (e.g. `search`, `show`, `download`), output formatting (table/JSON). Should contain no HTTP logic.
- **API client layer** — a thin typed wrapper over the CivitAI REST API: builds requests, attaches auth, handles pagination and rate limits, maps JSON responses to internal types. This is the only layer that talks to the network.
- **Domain/model types** — shared shapes for models, model versions, files, and images returned by the API.
- **Config & auth** — resolves the API token (env var / config file / flag) and base URL; keeps secrets out of source and out of committed config.
- **Download/IO** — streaming file downloads with progress, resumable where possible, and safe destination-path handling.

Document the *actual* module boundaries and data flow here once they exist, focusing on the cross-cutting pieces (auth resolution, pagination, error handling) that require reading multiple files to understand.

## CivitAI API reference

The CLI targets CivitAI's public REST API. Verify details against the current docs at <https://developer.civitai.com> / <https://github.com/civitai/civitai/wiki/REST-API-Reference> before relying on them — the API evolves.

- **Base URL:** `https://civitai.com/api/v1`
- **Common endpoints:** `/models`, `/models/{id}`, `/model-versions/{id}`, `/model-versions/by-hash/{hash}`, `/images`, `/creators`, `/tags`
- **Model download:** `https://civitai.com/api/download/models/{modelVersionId}`
- **Auth:** an API key (created in CivitAI account settings) sent as `Authorization: Bearer <token>` header (or `?token=` query param). Some downloads/endpoints require it. Never hardcode the token — read it from env/config.
- **Pagination:** list endpoints are paginated; responses include `metadata` with `nextPage`/cursor info to follow.
