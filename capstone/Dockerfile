# Production image for the support agent. Build from the capstone folder:
#   cd capstone
#   docker build --platform linux/arm64 -t support-agent .
#   docker run --rm -p 8000:8000 -e SUPPORT_MODEL_PROVIDER=bedrock -e AWS_REGION=us-east-1 support-agent
#
# Regenerate the lock after changing dependencies (from the repo root):
#   uv pip compile capstone/pyproject.toml --python-version 3.13 \
#     --python-platform aarch64-unknown-linux-gnu --generate-hashes -o capstone/requirements.lock

FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /build
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv PATH="/opt/venv/bin:$PATH"
# 1) exact, hash-checked dependencies (cached layer)
COPY requirements.lock .
RUN uv pip install --require-hashes -r requirements.lock
# 2) the service package itself, without re-resolving dependencies
COPY pyproject.toml .
COPY support_agent ./support_agent
RUN uv pip install --no-deps .

FROM python:3.13-slim
RUN useradd --create-home --uid 10001 agent
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    OTEL_SERVICE_NAME=support-agent \
    SUPPORT_JSON_LOGS=true \
    SUPPORT_SESSION_DIR=/tmp/sessions
USER agent
WORKDIR /home/agent
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
# FastAPI service. For AgentCore Runtime use instead:
#   CMD ["python", "-m", "support_agent.agentcore_main"]   (port 8080)
CMD ["uvicorn", "support_agent.api:build_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
