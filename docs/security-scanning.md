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
