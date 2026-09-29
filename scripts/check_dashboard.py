#!/usr/bin/env python3
"""Check that Grafana loaded the committed dashboard and can query Prometheus."""

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

values = dict(line.split("=", 1) for line in Path(".env").read_text().splitlines() if "=" in line)
auth = base64.b64encode(("admin:" + values["GRAFANA_ADMIN_PASSWORD"]).encode()).decode()


def get(path, payload=None):
    request = urllib.request.Request(
        "http://127.0.0.1:3000" + path,
        headers={"Authorization": "Basic " + auth, "Content-Type": "application/json"},
        data=json.dumps(payload).encode() if payload is not None else None,
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read(4096).decode(errors="replace")
        raise RuntimeError(f"{path}: HTTP {error.code}: {body}") from error


print("Provisioned data sources:", json.dumps(get("/api/datasources")), flush=True)

for attempt in range(30):
    try:
        result = get("/api/dashboards/uid/recovery-lab")
        assert len(result["dashboard"]["panels"]) == 11
        query = get(
            "/api/ds/query",
            {
                "from": "now-5m",
                "to": "now",
                "queries": [
                    {
                        "refId": "A",
                        "datasource": {"type": "prometheus", "uid": "recovery-prometheus"},
                        "expr": 'up{job="recovery"}',
                        "instant": True,
                        "range": False,
                        "format": "time_series",
                        "intervalMs": 15000,
                        "maxDataPoints": 1,
                    }
                ],
            },
        )["results"]["A"]
        assert not query.get("error"), query.get("error")
        samples = [
            value
            for frame in query.get("frames", [])
            for field, values in zip(
                frame["schema"]["fields"], frame["data"]["values"], strict=True
            )
            if field["type"] == "number"
            for value in values
        ]
        assert samples and all(value == 1 for value in samples), (
            "Recovery scrape is not healthy yet"
        )
        break
    except Exception as error:
        print(f"Grafana check attempt {attempt + 1}/30: {error}", flush=True)
        if attempt == 29:
            raise
        time.sleep(1)
print("Grafana provisioned all 11 panels and reached Prometheus.")
