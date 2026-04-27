# syntax=docker/dockerfile:1.7
#
# Lighter MCP runtime image.
#
# The image ships ``lighter-mcp`` plus a pre-cloned ``lighter-agent-kit`` so
# the in-container ``lighter-mcp init`` skips the network step. The kit's own
# Python dependencies still self-install into ``<kit>/.vendor/pyX.Y/`` on
# first call, which keeps the image small (~80 MB compressed) at the cost of
# a ~10 second warm-up on the first request.
#
# Default entrypoint is ``lighter-mcp serve --host 0.0.0.0 --port 8791
# --allow-remote`` so the container is usable behind a reverse proxy out of
# the box. For stdio (one-shot, agent-side) usage, override:
#
#     docker run --rm -i ghcr.io/iamgoatedaf/lighter-mcp \
#       lighter-mcp stdio
#
# The image runs as a non-root ``lighter`` user.

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------------------
# Stage 1: build the wheel from the repo source. Keeps build deps out of the
# final image.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS build

WORKDIR /src
RUN python -m pip install --no-cache-dir --upgrade build

COPY . /src
RUN python -m build --wheel --outdir /dist

# ---------------------------------------------------------------------------
# Stage 2: runtime. Slim Python + git (so the kit can still ``git pull`` if
# the operator wants to refresh in-place).
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim

ARG KIT_REF=main

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LIGHTER_MCP_CONFIG=/data/config.toml

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates curl tini \
 && rm -rf /var/lib/apt/lists/*

# Non-root user that owns /data. Image is otherwise read-only.
RUN useradd --system --create-home --uid 1001 --shell /usr/sbin/nologin lighter \
 && mkdir -p /data /opt/lighter-agent-kit \
 && chown -R lighter:lighter /data /opt/lighter-agent-kit

# Pre-clone the kit so the first call doesn't hit the network. Pin to ${KIT_REF}.
RUN git clone --depth 1 --branch ${KIT_REF} \
        https://github.com/elliottech/lighter-agent-kit /opt/lighter-agent-kit \
 && chown -R lighter:lighter /opt/lighter-agent-kit

# Install the wheel built in stage 1, plus the http transport extra.
COPY --from=build /dist/lighter_mcp-*.whl /tmp/
RUN pip install --no-cache-dir "/tmp/$(ls /tmp | grep '^lighter_mcp-')[http]" \
 && rm -f /tmp/lighter_mcp-*.whl

# Default config. Operators can mount ``/data`` to override.
RUN printf 'mode = "readonly"\nkit_path = "/opt/lighter-agent-kit"\npython_executable = "/usr/local/bin/python"\naudit_log = "/data/audit.jsonl"\nhost = "https://mainnet.zklighter.elliot.ai"\n' > /data/config.toml \
 && chown lighter:lighter /data/config.toml

USER lighter
WORKDIR /data
VOLUME ["/data"]
EXPOSE 8791

ENTRYPOINT ["/usr/bin/tini", "--", "lighter-mcp"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8791", "--allow-remote"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:8791/health" || exit 1
