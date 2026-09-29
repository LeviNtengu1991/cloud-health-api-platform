"""Small incident log used as the workload for the recovery lab."""

import hmac
import os
from datetime import datetime, timezone

import psycopg
from flask import Flask, jsonify, request
from psycopg.rows import dict_row

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


def connect():
    return psycopg.connect(connect_timeout=3, row_factory=dict_row)


def authorized():
    token = os.environ.get("API_TOKEN", "")
    return bool(token) and hmac.compare_digest(
        request.headers.get("Authorization", ""), "Bearer " + token
    )


@app.get("/")
def index():
    return jsonify(service="cloud-health-api", endpoints=["/health", "/ready", "/incidents"])


@app.get("/health")
def health():
    return jsonify(status="healthy", checked_at=datetime.now(timezone.utc).isoformat())


@app.get("/ready")
def ready():
    try:
        with connect() as db:
            db.execute("SELECT 1 FROM incidents LIMIT 1")
        return jsonify(status="ready")
    except psycopg.Error:
        return jsonify(status="not_ready"), 503


@app.errorhandler(psycopg.Error)
def database_error(_error):
    return jsonify(error="Database unavailable; retry later"), 503


@app.get("/incidents")
def incidents():
    with connect() as db:
        rows = db.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify(items=rows)


@app.post("/incidents")
def create_incident():
    if not authorized():
        return jsonify(error="A valid bearer token is required"), 401
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="Expected a JSON object"), 400
    title, severity = body.get("title"), body.get("severity", "low")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
        return jsonify(error="title must contain 1 to 200 characters"), 400
    if severity not in ("low", "medium", "high"):
        return jsonify(error="severity must be low, medium, or high"), 400
    with connect() as db:
        row = db.execute(
            "INSERT INTO incidents (title, severity) VALUES (%s, %s) RETURNING *",
            (title.strip(), severity),
        ).fetchone()
    return jsonify(row), 201


@app.patch("/incidents/<int:incident_id>")
def update_incident(incident_id):
    if not authorized():
        return jsonify(error="A valid bearer token is required"), 401
    body = request.get_json(silent=True)
    if (
        not isinstance(body, dict)
        or body.get("status") not in ("open", "resolved")
        or type(body.get("version")) is not int
        or body["version"] < 1
    ):
        return jsonify(error="Supply status (open/resolved) and a positive integer version"), 400
    with connect() as db:
        row = db.execute(
            "UPDATE incidents SET status=%s, version=version+1, updated_at=now() "
            "WHERE id=%s AND version=%s RETURNING *",
            (body["status"], incident_id, body["version"]),
        ).fetchone()
        if row is None:
            exists = db.execute("SELECT 1 FROM incidents WHERE id=%s", (incident_id,)).fetchone()
            return jsonify(
                error="Version conflict" if exists else "Not found"
            ), 409 if exists else 404
    return jsonify(row)
