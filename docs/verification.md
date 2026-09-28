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
