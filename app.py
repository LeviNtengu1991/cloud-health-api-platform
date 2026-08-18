from datetime import datetime, timezone

from flask import Flask, jsonify


app = Flask(__name__)


@app.get("/")
def index():
    return jsonify(
        service="cloud-health-api",
        message="DevOps portfolio service is running",
        endpoints=["/", "/health", "/ready"],
    )


@app.get("/health")
def health():
    return jsonify(status="healthy", checked_at=datetime.now(timezone.utc).isoformat())


@app.get("/ready")
def ready():
    return jsonify(status="ready"), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
