# Repository security scanning

`Repository security` runs on every push and pull request, manually, and each Monday at 06:17 UTC. Scheduled runs begin after the workflow reaches the default branch. Reports are retained as workflow artifacts for 14 days.

| Check | Coverage | Failure policy |
| --- | --- | --- |
| Gitleaks | All fetched Git history, with redacted logs and reports | Any detected secret |
| pip-audit | Resolved runtime, test, quality, and audit-tool Python dependencies | Any known vulnerability |
| CodeQL | Python with security-extended queries | Security severity 7.0 or higher; missing report also fails |
| Trivy configuration | Repository Terraform and supported container configuration | High or critical misconfiguration |
| Trivy images | Built API, recovery worker, database; deployed Grafana and Prometheus images | High or critical vulnerability, including unfixed findings |

`Security gate` fails if any scanner fails, is cancelled, or is skipped. Lower-severity CodeQL findings remain available in GitHub code scanning. Container and configuration JSON reports contain the high/critical findings used by the gate. The recovery image's installed Python dependencies are covered by its image scan. The database base also covers the isolated restore database. Tests run in a disposable CI environment; no live AWS resources are deployed.

A passing scan is limited to known vulnerabilities and the rules supported by each tool. It is not a guarantee that the repository or deployed infrastructure is secure. Copilot review complements these deterministic checks.

## Handling findings

Fix the dependency, image, source, or configuration and rerun the failed job. If a real credential is detected, revoke and rotate it first; deleting the current file does not remove it from Git history. Never paste credentials into an issue or PR. Do not introduce blanket exclusions or `continue-on-error` to get a green gate. An unavoidable exception needs a narrow identifier, documented justification, owner, and expiry reviewed by a human.

Pinned scanner/action versions are intentional. Dependabot checks dependencies weekly, including nested Dockerfiles and the S3 Terraform root. Updating a base image can affect availability; run the complete restore, S3, and dashboard integration suite before merging. Roll back through a reviewed revert, preserving the security gate and documenting any vulnerability reintroduced by the rollback.

These workflows consume GitHub Actions minutes and download public vulnerability databases. They do not create AWS resources or introduce AWS usage charges.

## Initial scan findings (2026-09-29)

The first real Actions run passed secret scanning, CodeQL, dependency auditing, and Python quality tests. It exposed existing high/critical container findings in all five image groups. Some Debian findings have no published fix; other findings are in bundled Go binaries/plugins that require upstream image updates. No vulnerability exclusions were added. The Flask finding was fixed by upgrading to 3.1.3.

Configuration findings require deliberate review:

- `DS-0002`, `db/Dockerfile`: the official PostgreSQL entrypoint starts as root to initialize/chown its volume before dropping to postgres. Blindly adding `USER postgres` can break volume initialization. A reviewed, narrowly scoped exception or tested volume-initialization redesign is needed.
- `AWS-0132`, `infra/backup-storage/main.tf`: backups currently use S3 AES256 server-side encryption. The rule requires a customer-managed KMS key. Adopting KMS changes key lifecycle, permissions, cost, and restore dependencies, and must be designed explicitly. No live AWS change was made.

The active required-check ruleset covers `main` and `codex/backup-recovery-lab`: `Python quality and security`, `recovery`, and `Security gate`. Existing PRs need these workflow definitions before they can satisfy the checks. GitHub native secret scanning, secret push protection, vulnerability alerts, and Dependabot security updates are enabled. CI scanner installation is complete, but the security gate intentionally remains red until the reported findings are remediated or individually reviewed under the exception policy above.
