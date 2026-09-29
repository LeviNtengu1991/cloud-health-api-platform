FROM postgres:17.11-bookworm
# The client major matches the database. Debian supplies Python through apt.
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir 'psycopg[binary]==3.2.9' 'boto3==1.43.103' \
    && mkdir -p /backups && chown postgres:postgres /backups
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /ops
COPY recovery/ /ops/recovery/
USER postgres
ENTRYPOINT ["python", "-m", "recovery.cli"]
CMD ["--help"]
