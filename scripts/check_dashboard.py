#!/usr/bin/env python3
"""Check that Grafana loaded the committed dashboard and can query Prometheus."""
import base64
import json
from pathlib import Path
import time
import urllib.request

values = dict(line.split('=', 1) for line in Path('.env').read_text().splitlines() if '=' in line)
auth = base64.b64encode(('admin:' + values['GRAFANA_ADMIN_PASSWORD']).encode()).decode()

def get(path):
    request = urllib.request.Request('http://127.0.0.1:3000' + path, headers={'Authorization': 'Basic ' + auth})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)

for attempt in range(30):
    try:
        result = get('/api/dashboards/uid/recovery-lab')
        assert len(result['dashboard']['panels']) == 11
        assert get('/api/datasources/uid/recovery-prometheus/health')['status'] == 'OK'
        break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(1)
print('Grafana provisioned all 11 panels and reached Prometheus.')
