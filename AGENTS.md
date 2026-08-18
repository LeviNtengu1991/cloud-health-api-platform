# Repository Agent Instructions

This repository is an AWS-focused DevOps portfolio project. Prioritize secure, reviewable, production-minded infrastructure changes.

## Working rules

- Run `terraform fmt -check`, `terraform init -backend=false`, and `terraform validate` after Terraform changes.
- Build the Docker image after application, dependency, or Dockerfile changes.
- Preserve the non-root container user, health check, read-only runtime compatibility, and least-privilege defaults.
- Never add cloud credentials, tokens, private keys, state files, or generated Terraform directories.
- Do not run `terraform apply`, modify live infrastructure, or broaden IAM permissions without explicit human approval.
- Pin third-party actions and container dependencies to intentional versions.
- Explain security, cost, availability, and rollback implications in pull requests.

## Definition of done

A change is complete when formatting and validation pass, documentation reflects operational impact, no secrets are introduced, and a safe rollback path is clear.
