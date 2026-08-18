# Copilot repository instructions

This project demonstrates DevOps and cloud-engineering practices around Terraform, AWS, containers, CI/CD, security, and reliability.

- Prefer small, reviewable changes with explicit operational outcomes.
- Treat Terraform as production infrastructure code: format it, validate it, use typed variables, tag resources, and avoid hard-coded credentials or account-specific identifiers.
- Keep containers non-root, minimal, health-checked, and compatible with a read-only filesystem.
- Use least-privilege GitHub Actions permissions and avoid long-lived AWS credentials; recommend OIDC for deployment workflows.
- Do not execute deployments or destructive Terraform commands automatically.
- Include validation commands and rollback notes in proposed changes.
- Update README documentation when behavior, prerequisites, architecture, or runbooks change.
