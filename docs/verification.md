# Verification notes

Local run on 2026-09-28T01:18:37.180519+00:00 using Docker Desktop on macOS (ARM64), PostgreSQL 17.6, and the containers in this branch.

- 21 unit tests passed.
- API, database initialization, and recovery images built successfully.
- The real database integration test passed all 11 checks listed below.
- A snapshot containing 24 sample incidents restored successfully. The source and restored SHA-256 fingerprints matched.
- Restore and verification took 0.115 seconds; the snapshot was 2.116 seconds old when checked. This small laptop test is not a production performance estimate.

Integration coverage: authorized API writes; optimistic update conflicts; restricted application database permissions; snapshot recovery after later source writes; source unchanged after a drill; scratch database cleanup; expired-backup refusal; same-server refusal; corrupted archive refusal; retention; liveness/readiness behavior during a database outage.

CI runs the same exercise on Ubuntu and uploads `restore-evidence` containing its own report. Generated credentials, backup archives, and live data are excluded from Git. Re-run the tests to get evidence for your own environment.

No AWS resources were deployed or modified for this project. The existing Terraform configuration was not changed.

Follow-up on 2026-09-28: all 21 unit tests and the recovery workflow's actionlint check passed again. Docker Desktop could not start on this host, so fresh container builds and database integration verification are delegated to the branch's GitHub Actions workflow. The measurements above remain from the earlier local run.

## S3 and Grafana extension — 2026-09-28

- 36 tests passed locally: the original 21 plus 15 S3/emulator and scheduler safety tests.
- Coverage includes SSE-S3 upload requests, verified download, incomplete-upload discovery, retry after interrupted manifest publication, corrupted/missing archives, invalid paths and metadata, local overwrite refusal, fresh-download drill behavior, separate failure reports, preserved snapshot age, and skipping local pruning after upload failure.
- The new standalone S3 Terraform root passed backend-free initialization, formatting, and validation with AWS provider 5.100.0. No plan or apply was run against AWS.
- Base Compose (including dashboard/testing profiles), the optional S3 overlay, workflow actionlint, monitoring YAML, dashboard JSON, and Git whitespace checks passed.
- Container builds were attempted but Docker's daemon is unavailable on this host. The new Grafana dashboard has not been rendered locally; container startup, Prometheus rule evaluation, the real PostgreSQL/S3-emulator integration, and Grafana API smoke checks await execution in Docker/CI.
- CI now contains the S3-emulator integration and Grafana provisioning checks. These are implemented, not claimed as passing remote runs. No real AWS round trip or GitHub CI run has been verified for this extension.
