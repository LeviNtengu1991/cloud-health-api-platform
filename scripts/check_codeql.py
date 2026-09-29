"""Fail CI on high/critical SARIF security findings or missing scan output."""

import json
import sys
from pathlib import Path


def check(directory):
    reports = list(Path(directory).glob("*.sarif"))
    if not reports:
        raise ValueError("CodeQL did not produce a SARIF report")
    findings = []
    for report in reports:
        for run in json.loads(report.read_text())["runs"]:
            rules = {rule["id"]: rule for rule in run["tool"]["driver"]["rules"]}
            for result in run.get("results", []):
                rule = rules[result["ruleId"]]
                severity = float(rule.get("properties", {}).get("security-severity", 0))
                if severity >= 7:
                    findings.append(result["ruleId"])
    if findings:
        raise ValueError("High/critical CodeQL findings: " + ", ".join(findings))


if __name__ == "__main__":
    try:
        check(sys.argv[1])
    except ValueError as error:
        raise SystemExit(str(error)) from None
