import os
import unittest
from unittest.mock import patch

import psycopg

from app import app


class APITests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        self.token = patch.dict(os.environ, {"API_TOKEN": "unit-test-token"})
        self.token.start()
        self.addCleanup(self.token.stop)
        self.headers = {"Authorization": "Bearer unit-test-token"}

    def test_liveness_does_not_depend_on_database(self):
        with patch("app.connect", side_effect=psycopg.OperationalError):
            self.assertEqual(self.client.get("/health").status_code, 200)
            self.assertEqual(self.client.get("/ready").status_code, 503)

    def test_missing_and_wrong_tokens(self):
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            self.assertEqual(
                self.client.post("/incidents", json={"title": "test"}, headers=headers).status_code,
                401,
            )

    def test_missing_server_token_fails_closed(self):
        with patch.dict(os.environ, {"API_TOKEN": ""}):
            self.assertEqual(
                self.client.post(
                    "/incidents", json={"title": "test"}, headers=self.headers
                ).status_code,
                401,
            )

    def test_invalid_title(self):
        for title in ("", "   ", "x" * 201, None, 10):
            with self.subTest(title=title):
                self.assertEqual(
                    self.client.post(
                        "/incidents", json={"title": title}, headers=self.headers
                    ).status_code,
                    400,
                )

    def test_invalid_severity(self):
        self.assertEqual(
            self.client.post(
                "/incidents", json={"title": "test", "severity": "critical"}, headers=self.headers
            ).status_code,
            400,
        )

    def test_json_object_required(self):
        self.assertEqual(
            self.client.post("/incidents", json=["test"], headers=self.headers).status_code, 400
        )

    def test_update_requires_version_and_status(self):
        for body in (
            {},
            {"status": "resolved", "version": True},
            {"status": "resolved", "version": 0},
            {"status": "gone", "version": 1},
        ):
            self.assertEqual(
                self.client.patch("/incidents/1", json=body, headers=self.headers).status_code, 400
            )

    def test_database_errors_are_not_exposed(self):
        with patch(
            "app.connect", side_effect=psycopg.OperationalError("secret connection details")
        ):
            response = self.client.get("/incidents")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("secret", response.text)


if __name__ == "__main__":
    unittest.main()
