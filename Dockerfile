FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

RUN groupadd --system --gid 10001 redops \
    && useradd --system --uid 10001 --gid redops --home-dir /app --shell /usr/sbin/nologin redops \
    && mkdir -p /app/instance \
    && chown redops:redops /app/instance

COPY --chown=redops:redops . .

USER 10001:10001

EXPOSE 5000

# Keep one process because RedOps Vault runs its backup scheduler in-process.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "3600", "--no-control-socket", "--access-logfile", "-", "wsgi:app"]
