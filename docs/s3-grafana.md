# S3 backups and Grafana

## Start the dashboard

For an existing checkout that already has `.env`, add only the new Grafana password:

```bash
python3 scripts/configure.py --grafana
```

New checkouts get this password from the normal `scripts/configure.py` setup. Then:

```bash
make build
make up
make dashboard
```

Open http://localhost:3000/d/recovery-lab and sign in as `admin` with `GRAFANA_ADMIN_PASSWORD` from your local `.env`. Do not paste that password into issues or commit it. Grafana stores its initial password in its database: editing `.env` after first start does not rotate it. Use Grafana's password-change UI for an existing installation.

The provisioned dashboard shows metrics availability, local backup age, local restore outcome, retained snapshot count, S3 enablement, S3 snapshot age, upload outcome, S3 restore outcome, restore durations, and firing alerts. S3 panels show no evidence until enabled. Zero status means failure or no previous attempt. Missing metrics means unknown health, not success. The S3 age panel uses the snapshot creation time, so re-uploading an old backup cannot make it look fresh.

Dashboard definitions and the Prometheus data source are committed under `monitoring/grafana`. Edit those files to make durable dashboard changes. Anonymous access and sign-ups are disabled; the port binds only to localhost. Grafana uses a named data volume and a non-root process. Startup plugin auto-updates are disabled because the bundled plugin directory is read-only; update the pinned Grafana image through review to update its bundled plugins. `make stop` and `make clean` include the dashboard and test profiles; clean deletes the Grafana database as well as lab data.

## Prepare off-host storage

The separate Terraform root in `infra/backup-storage` describes only backup storage. It does not change the existing ECS/ECR foundation. It creates a private S3 bucket with public access blocked, ACLs disabled, versioning, AES-256 server-side encryption (SSE-S3), HTTPS-only access, and lifecycle retention. The default policy expires current objects under `recovery/` after 30 days and noncurrent versions after seven days. Expiration is asynchronous; objects and delete markers can persist beyond these periods. This is not immutable Object Lock storage.

Review locally:

```bash
terraform -chdir=infra/backup-storage init -backend=false
terraform -chdir=infra/backup-storage fmt -check
terraform -chdir=infra/backup-storage validate
terraform -chdir=infra/backup-storage plan -var='bucket_name=YOUR-GLOBALLY-UNIQUE-BUCKET'
```

Provisioning requires an AWS account, a chosen region and bucket name, and an approved Terraform apply. No apply is performed by the repository's CI. The bucket has `prevent_destroy` and `force_destroy=false`; intentionally removing it needs a separate reviewed retention and deletion decision. Store Terraform state securely; it is excluded from Git.

The module outputs separate writer and reader policy documents for review. It creates no IAM users, access keys, or role attachments. A scheduler needs only `PutObject` under `recovery/*`; a recovery operator needs `ListBucket` restricted to that prefix plus `GetObject`. A combined demo identity needs both. Neither needs delete privileges. Use a dedicated profile with temporary credentials. For real workloads, prefer IAM roles and the SDK credential chain. Changing the default prefix requires matching changes to lifecycle rules and policy resources.

## Configure and run S3 operations

Add the nonsecret settings below to `.env` after provisioning your bucket (or choosing an existing compatible SSE-S3 bucket):

```dotenv
S3_BUCKET=YOUR-BUCKET
S3_PREFIX=recovery
AWS_DEFAULT_REGION=us-east-1
```

Export a dedicated credentials/config directory and profile in your shell:

```bash
export AWS_CONFIG_DIR=/absolute/path/to/dedicated-aws-config
export AWS_PROFILE=recovery-lab
```

The directory should contain AWS `credentials` and optionally `config` files readable by the non-root container user. Use a dedicated directory containing only this lab profile. `docker-compose.s3.yml` mounts it read-only into the operations and scheduler containers; the API and dashboard receive no AWS credentials. It supports profiles backed by temporary credentials in the credentials file. Host `credential_process` executables and interactive SSO login inside containers are not provided. Refresh expired temporary credentials on the host. Never loosen file permissions broadly or bake credentials into an image.

```bash
# Stop automatic work during a manual demonstration.
docker compose stop backup-scheduler
make backup
make s3-upload
make s3-drill

# Enable hourly off-host copies and refresh the metrics configuration.
docker compose -f docker-compose.yml -f docker-compose.s3.yml up -d backup-scheduler recovery-metrics
```

When S3_BUCKET is configured, the scheduler creates a local backup, uploads it, and only then prunes local snapshots. Failed uploads preserve local backups and set the S3 failure metric; the next scheduled run tries a new snapshot. An operator can retry a specific old snapshot with `s3-upload --snapshot snapshot_...`. Re-uploading a snapshot creates new object versions and may increase storage costs.

The archive is uploaded with an S3 SHA-256 checksum and SSE-S3 encryption. The manifest is uploaded last as the completion marker. Downloads discover only manifests under the configured prefix, check size and SHA-256, and publish a local snapshot only after validation. Incomplete archive uploads have no manifest and are ignored. A retry can finish an interrupted manifest upload. Checksums detect corruption; they are not a signature against an actor who can replace both files.

For a download without restoring, use a fresh backup directory in the container:

```bash
docker compose -f docker-compose.yml -f docker-compose.s3.yml run --rm \
  -e BACKUP_DIR=/backups/downloaded ops s3-download --snapshot snapshot_REPLACE_WITH_ID
```

Existing local snapshots are never overwritten. `s3-drill` always downloads into a new temporary directory, checks the archive, runs the existing isolated PostgreSQL drill, and saves `/backups/s3-restore-report.json`. It never uses the cached local archive. Download failures also produce a failed S3 report. The local restore report is independent.

## Demonstrate a failure

Use the local emulator for destructive corruption tests, never your retained S3 backups:

```bash
docker compose stop backup-scheduler
make integration
docker compose --profile testing up -d --build --wait s3-mock
python3 scripts/integration_s3.py
```

The S3 script creates a disposable `recovery-ci` bucket in Moto, uploads a real PostgreSQL dump, downloads and restores it, compares fingerprints, then corrupts the emulator's archive and verifies refusal. Restart the emulator with `docker compose --profile testing up -d --force-recreate s3-mock` before repeating, because its bucket lives in memory. No emulator ports are exposed to the host. CI runs this test and uploads both restore reports. Moto validates application behavior, not AWS IAM enforcement or real S3 availability.

For a dashboard walkthrough, create records, run backup and restore, and watch the age and outcome panels. Stop the metrics service and observe the metrics-unavailable alert; restart it after the demonstration. S3 alerts are gated on enablement and include stale snapshots, upload failure, restore failure, and overdue drills. Notifications still require an Alertmanager destination.

## Limits, cost, and rollback

- Real AWS round trips are unverified until you configure a bucket and credentials. The automated tests use an emulator.
- The existing drill still connects to the source server to compare PostgreSQL cluster identities. It proves recovery from off-host bytes into a separate running server; it is not a source-destroyed disaster-recovery procedure or a traffic cutover. Preserve the original backup's trust metadata and design a separate reviewed recovery procedure before handling total source loss.
- A single archive is limited to 5 GiB; downloads need enough free temporary disk space. Large multipart transfers and resumable downloads are outside this lab.
- Restore duration excludes the S3 download, scratch cleanup, failure detection, and traffic cutover. It is not production RTO. S3 evidence on the dashboard records this lab's last upload; it does not continuously verify that an object still exists remotely.
- S3 storage, object versions, PUT/GET/LIST requests, and downloads can incur charges. Estimate from dump size × retained backups and check the current regional AWS pricing. No fixed cost estimate is claimed. Grafana runs locally, not as a paid managed service.
- To disable remote copies, clear S3_BUCKET and recreate the scheduler and metrics containers using the base Compose file. Stop Grafana with `docker compose --profile dashboard stop grafana`. Preserve the S3 bucket and local volumes when rolling back code; do not destroy backups as part of rollback.

References: [AWS PutObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutObject.html), [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/), [Grafana Docker configuration](https://grafana.com/docs/grafana/latest/setup-grafana/configure-docker/).
