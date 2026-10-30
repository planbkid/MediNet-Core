FROM python:3.14-alpine AS builder
WORKDIR /build
RUN apk add --no-cache build-base libffi-dev openssl-dev postgresql-dev cargo
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.14-alpine AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apk add --no-cache libpq libffi libstdc++ openssl
RUN addgroup -S -g 10001 pac && adduser -S -D -H -u 10001 -G pac pac
WORKDIR /srv/pac
COPY --from=builder /install /usr/local
COPY --chown=pac:pac app ./app
COPY --chown=pac:pac migrations ./migrations
COPY --chown=pac:pac alembic.ini ./alembic.ini
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
