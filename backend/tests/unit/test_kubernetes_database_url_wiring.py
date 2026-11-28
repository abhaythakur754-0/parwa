"""Production Kubernetes manifests must give every database client its real DB URL."""
from pathlib import Path

import yaml


def test_backend_worker_and_mcp_use_database_url_secret():
    backend_root = Path(__file__).resolve().parents[2]
    for workload in ("backend", "worker", "mcp"):
        manifest_path = backend_root.parent / "infra" / "k8s" / workload / "deployment.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        containers = manifest["spec"]["template"]["spec"]["containers"]
        env = {item["name"]: item for item in containers[0].get("env", [])}
        assert env["DATABASE_URL"]["valueFrom"]["secretKeyRef"] == {
            "name": "parwa-secrets",
            "key": "DATABASE_URL",
        }
