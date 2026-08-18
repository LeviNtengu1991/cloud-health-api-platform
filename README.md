# Cloud Health API — DevOps Portfolio Project

A production-minded DevOps demonstration by **Levi N**. This repository combines a small health-check API with container security, infrastructure as code, and repeatable validation workflows.

## What this demonstrates

- **Containers:** multi-layer-conscious Docker image, non-root runtime, health check, immutable filesystem support
- **Infrastructure as Code:** versioned AWS resources using Terraform and reusable variables
- **Cloud operations:** Amazon ECR, ECS cluster, CloudWatch logs, image scanning, retention policies, and consistent tags
- **Reliability:** liveness and readiness endpoints plus automatic container restarts
- **Security:** least-privilege container user, `no-new-privileges`, immutable ECR tags, encrypted images

## Architecture

```text
Developer -> Docker build -> Amazon ECR -> Amazon ECS
                                      \-> CloudWatch Logs & Container Insights
```

Terraform provisions the cloud foundation. The Flask service exists to provide a realistic workload for container build, health-check, and deployment automation.

## Run locally

```bash
docker compose up --build
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

## Validate the infrastructure

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan
```

`terraform plan` and `terraform apply` require AWS credentials. No cloud resources are created automatically.

## Repository map

| File | Purpose |
|---|---|
| `app.py` | Health and readiness API |
| `Dockerfile` | Hardened production container |
| `docker-compose.yml` | Reproducible local runtime |
| `main.tf` | AWS ECR, ECS, and CloudWatch resources |
| `variables.tf` | Typed and validated configuration |
| `outputs.tf` | Useful infrastructure outputs |

## Next improvements

- Add an ECS task definition, service, and Application Load Balancer
- Add OIDC-based GitHub-to-AWS authentication
- Add Trivy image scanning and Checkov policy checks
- Add Prometheus metrics and an operational dashboard

## Author

**Levi N** — DevOps & Cloud Engineer
