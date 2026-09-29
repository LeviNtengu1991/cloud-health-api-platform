FROM postgres:17.11-bookworm
COPY db/init.sh /docker-entrypoint-initdb.d/01-init.sh
COPY db/schema.sql /schema.sql
RUN chmod 0644 /docker-entrypoint-initdb.d/01-init.sh /schema.sql
