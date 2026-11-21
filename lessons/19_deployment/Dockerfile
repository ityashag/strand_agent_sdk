# Container for lessons/19_deployment/agentcore_app.py
# Build from the REPO ROOT:
#   docker build --platform linux/arm64 -f lessons/19_deployment/Dockerfile -t strands-lesson19 .
#   docker run --rm -p 8080:8080 -e MODEL_PROVIDER=fake strands-lesson19
#
# AgentCore Runtime needs: linux/arm64, an HTTP server on port 8080, POST /invocations, GET /ping.
# The capstone has a leaner image that installs only the service package (capstone/Dockerfile).

FROM python:3.13-slim AS build
# Pin uv; copy the static binary from its official image.
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# 1) dependencies only (cached layer): lock file + local package sources
COPY pyproject.toml uv.lock ./
COPY course_common ./course_common
COPY capstone ./capstone
RUN uv sync --frozen --no-dev --no-install-project
# 2) the app code
COPY lessons/19_deployment ./app_code

FROM python:3.13-slim
# Run as a non-root user.
RUN useradd --create-home --uid 10001 agent
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/app_code /app/app_code
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 OTEL_SERVICE_NAME=strands-lesson19
USER agent
EXPOSE 8080
CMD ["python", "app_code/agentcore_app.py"]
