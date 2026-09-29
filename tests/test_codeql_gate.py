"""Regression tests for the CodeQL merge gate."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_codeql import check


class CodeQLGateTests(unittest.TestCase):
    def test_missing_output_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                check(directory)

    def test_severity_threshold(self):
        for severity, blocked in [("6.9", False), ("7.0", True), ("9.8", True)]:
            with self.subTest(severity=severity), tempfile.TemporaryDirectory() as directory:
                report = {
                    "runs": [
                        {
                            "tool": {
                                "driver": {
                                    "rules": [
                                        {
                                            "id": "test",
                                            "properties": {"security-severity": severity},
                                        }
                                    ]
                                }
                            },
                            "results": [{"ruleId": "test"}],
                        }
                    ]
                }
                Path(directory, "python.sarif").write_text(json.dumps(report))
                if blocked:
                    with self.assertRaises(ValueError):
                        check(directory)
                else:
                    check(directory)

    def test_clean_scan_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "python.sarif").write_text(
                json.dumps({"runs": [{"tool": {"driver": {"rules": []}}, "results": []}]})
            )
            check(directory)
