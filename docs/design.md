# Design choices

## One workload, one recovery question

The API stores a small incident log: title, severity, status, timestamps, and an optimistic-lock version. It gives recovery tests actual state to protect without turning the repository into a large application.

The question each drill answers is: can this backup recreate the incident data on another server, within the chosen time and backup-age limits?

## Snapshot consistency

`pg_dump` provides a consistent logical database dump. A row count taken in a separate transaction could disagree with that dump if the API were writing at the same time. The backup operation instead opens a read-only repeatable-read transaction and exports its snapshot. It passes the snapshot ID to `pg_dump` and computes the fingerprint from the same transaction.

The fingerprint streams incident rows in primary-key order and hashes a canonical JSON representation. Both connections use UTC for timestamps. The dump restores the schema and sequence; the drill also attempts an insert and rolls it back to verify that the restored identity sequence is usable.

Only the incidents table is fingerprinted. If the application gains tables, add them to the verification contract before claiming they are covered.

## Restore isolation

The source and recovery servers are separate containers and PostgreSQL clusters. Before creating a scratch database, the CLI rejects identical connection endpoints and compares PostgreSQL system identifiers to catch two DNS names pointing to the same cluster.

Scratch names are generated internally with a `recovery_` prefix. The command has no option to restore into an arbitrary live database. It creates one database, restores into it, verifies it, and drops exactly that database in a `finally` block. Cleanup failures mark the report as failed and preserve the scratch name for investigation.

A lab administrator connects to the source to export snapshots and identify the cluster. The HTTP app uses a different role with only SELECT/INSERT/UPDATE and sequence access. Production backup identities would need a more specific privilege design.

## Measurements

Default lab targets:

- Backup no older than 7,200 seconds when tested.
- Restore verification completes within 120 seconds, including checksum, isolation checks, database creation, restore and validation; scratch cleanup is outside the timer.

These are pass/fail targets, not measured service RPO/RTO. Backup age approximates the recovery point exposed by a logical snapshot. The drill does not measure failure detection, infrastructure provisioning, DNS changes, traffic cutover, or a full service outage. Never report its duration as a production RTO.

## Storage and retention

An archive and manifest are written into a private staging directory. A rename publishes the complete directory. SHA-256 detects accidental archive changes before restore. It is not a signature: someone who can replace both the archive and manifest can replace the expected checksum.

Retention is a count of complete snapshots, not a calendar policy. Before pruning old snapshots, the command verifies the retained archives. Seven hourly backups cover roughly seven successful intervals, but failures, manual backups, or a stopped scheduler change that window.

Docker volume persistence is enough for this exercise, not disaster recovery. The optional S3 extension implements encrypted off-host copies and restore tests after downloading them; see [S3 and Grafana](s3-grafana.md). Application identities do not need delete permissions. Bucket lifecycle, versioning, and dedicated AWS identities need deployment review.

## Availability and rollback

The API's liveness endpoint stays healthy when PostgreSQL is down; readiness returns 503. This avoids treating a database outage as a reason to continually restart the application. Writes return 503 instead of leaking database errors, and optimistic locking prevents one update from silently replacing another.

The branch changes readiness semantics and adds database requirements. Roll back by switching to the previous code and Compose definition. Do not delete the PostgreSQL volume as part of a code rollback. There are no live AWS changes to reverse.
