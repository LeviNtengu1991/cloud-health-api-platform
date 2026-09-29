# Code quality and DevOps review

## Automated checks

The `Code quality` workflow scans every push and pull request, and supports a manual run. A weekly schedule runs on the default branch once this workflow is merged there.

- Ruff catches Python errors, unused imports/variables, import ordering, and common bug patterns.
- Ruff format enforces consistent formatting without changing files in CI.
- Bandit scans application/recovery runtime code and credential configuration, and uploads a JSON report. It intentionally excludes test harnesses that execute disposable failure scenarios. It is not a dependency vulnerability scanner.
- The regression suite tests the API and recovery/S3 behavior. The separate `Backup and recovery` workflow builds containers and exercises real PostgreSQL restores, S3 emulation, monitoring rules, and Grafana on PRs.
- Existing Security and IaC Quality and Dependabot configurations remain available. They cover different checks; a passing Python scan does not prove infrastructure is secure.

Run locally from a virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-test.txt -r requirements-quality.txt
make quality
make test-python
```

To apply style corrections: `ruff check --fix .` followed by `ruff format .`. Review the diff and rerun checks. Runtime Bandit suppressions are limited to documented PostgreSQL subprocess calls and the container-internal metrics listener. Any new suppression needs a specific justification.

## Continuous Copilot review

The repository's automatic Copilot rule requests review for PRs targeting any branch, including drafts and new pushes. Direct pushes without a PR receive CI checks but not a Copilot PR review. Copilot availability depends on the author's eligible subscription and remaining quota; enabling a ruleset does not buy a subscription or guarantee a review.

Copilot uses `.github/copilot-instructions.md` for review guidance. A separate read-only `devops-reviewer` profile is available in `.github/agents/devops-reviewer.md` for manually selected agent sessions in supported Copilot interfaces. The custom profile is not the automatic-review trigger.

The rule requests reviews; it does not automatically merge or approve infrastructure changes. Existing repository rules are preserved. These checks are visible CI results, not mandatory merge gates unless configured as required status checks. Review the PR, its CI results, and Copilot findings before merging.

References: [automatic Copilot review](https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-code-review), [custom agents](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/create-custom-agents), [Ruff](https://docs.astral.sh/ruff/), [Bandit](https://bandit.readthedocs.io/).
