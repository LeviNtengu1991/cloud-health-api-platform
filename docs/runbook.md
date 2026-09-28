# Recovery lab runbook

## A short demonstration

1. Start the stack from the README and create two incidents.
2. Run `make backup` and note the snapshot name.
3. Create another incident after the backup.
4. Run `docker compose run --rm ops drill --snapshot SNAPSHOT_NAME`.
5. Read the report. The restored row count should match the earlier snapshot, while `GET /incidents` still contains the later record.
6. Open Prometheus and query `recovery_restore_last_attempt_success` and `recovery_restore_duration_seconds`.
7. Explain what this test does not prove: off-host recovery, point-in-time recovery, or traffic cutover.

## BackupStale or BackupFailed

Check `docker compose logs --tail=100 backup-scheduler` and `make metrics`. Confirm the source is healthy with `docker compose ps` and `/ready`. Check disk space on the Docker host. A stale alert can mean a stopped scheduler; a failed-attempt metric means an operation ran and failed.

Stop the scheduler before manual troubleshooting: `docker compose stop backup-scheduler`. Run `make backup` to reproduce the failure. Resume with `docker compose up -d backup-scheduler` after fixing it. Do not remove the last verified backup just to make disk space; copy it somewhere safe first.

If interrupted during a backup, a `.partial_` folder may remain. It is never selected as a completed backup. Inspect and remove stale partial folders only when no backup process is running.

## RestoreFailed

Run `make report`. A checksum mismatch means the archive no longer matches its manifest; choose another backup and investigate the storage. An expired backup can restore correctly but still fail the age target. A fingerprint mismatch means recovered records differ from the source snapshot. Keep that archive and report for investigation.

If `cleanup_failed` is true, the report includes the generated scratch database name. Inspect it on the recovery server, not the source. The CLI never needs permission to drop a source database.

## Database outage exercise

Run only in the disposable lab:

```bash
docker compose stop db
curl -i http://localhost:8080/health
curl -i http://localhost:8080/ready
docker compose start db
```

Expect health 200 and readiness 503 during the outage. Wait for readiness 200 after restart. Restarting PostgreSQL preserves the named data volume.

## Rebuild and reset

Schema initialization runs only when the source database volume is empty. Changing `db/schema.sql` will not migrate an existing database. For this lab, preserve any evidence you want, then use the explicit `make clean CONFIRM=delete-lab-data` command and start again. A deployed service would use versioned migrations instead.

## Interview discussion

Useful topics to walk through with the code open:

- Why a successful `pg_dump` exit code is insufficient evidence of recovery.
- Why a consistent snapshot matters when writes continue during a backup.
- How the drill avoids touching the live database.
- How backup age differs from a true RPO measurement.
- What changes before storing customer data or running this outside a laptop.

Run the exercise yourself and record your observations. Do not claim production availability, business savings, or a team rollout from this lab.
