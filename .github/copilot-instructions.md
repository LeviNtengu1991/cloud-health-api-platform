# Copilot repository instructions

This project demonstrates DevOps and cloud-engineering practices around Terraform, AWS, containers, CI/CD, security, and reliability.

- Prefer small, reviewable changes with explicit operational outcomes.
- Treat Terraform as production infrastructure code: format it, validate it, use typed variables, tag resources, and avoid hard-coded credentials or account-specific identifiers.
- Keep containers non-root, minimal, health-checked, and compatible with a read-only filesystem.
- Use least-privilege GitHub Actions permissions and avoid long-lived AWS credentials; recommend OIDC for deployment workflows.
- Do not execute deployments or destructive Terraform commands automatically.
- Include validation commands and rollback notes in proposed changes.
- Update README documentation when behavior, prerequisites, architecture, or runbooks change.

## Pull request review

Review changed code and its operational effects. Report concrete defects with file/line references, a triggering scenario, severity, and a suggested fix. Prioritize correctness and security over style already enforced by Ruff. Do not invent test results or production readiness claims.

- Python: parameterized SQL, authorization, exception handling, optimistic updates, resource cleanup, and bounded network/subprocess operations.
- Recovery: shared snapshot consistency, checksums, incomplete S3 uploads, no overwrite of local data, source/target isolation, scratch cleanup, and preserving local backups when remote upload fails.
- AWS/Terraform: private encrypted storage, HTTPS, narrow IAM, safe lifecycle policies, cost, state exclusion, and explicit deployment approval.
- Docker/Grafana: non-root execution, localhost-only published ports, read-only compatibility, writable volume boundaries, and pinned plugin behavior.
- GitHub Actions: minimum permissions, no secret access for untrusted PR code, pinned dependencies, useful failing checks, and preserved evidence.
- Require tests for changed failure behavior and matching runbook/rollback notes. Review inline Bandit suppressions individually; do not add blanket exclusions to make a scan pass.

Use the existing code-quality and recovery checks as evidence. Copilot review supplements these checks and human judgment; it does not authorize automatic merging or cloud changes.
