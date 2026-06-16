# syntax=docker/dockerfile:1

# --- build the wheel in an isolated stage ---------------------------------
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /dist

# --- minimal runtime image ------------------------------------------------
FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/mr8bit/civit-ai-cli" \
      org.opencontainers.image.description="huggingface_hub, but for CivitAI" \
      org.opencontainers.image.licenses="MIT"

# Non-root user with a writable, persistent cache directory.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data \
    && chown app:app /data

COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

USER app
ENV CIVITAI_HOME=/data
VOLUME ["/data"]

ENTRYPOINT ["civitai"]
CMD ["--help"]
