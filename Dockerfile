FROM python:3.12-alpine AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-alpine

ENV TZ=Asia/Shanghai
ENV PATH="/app/.venv/bin:$PATH"

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

CMD ["smzdm-scheduler"]
