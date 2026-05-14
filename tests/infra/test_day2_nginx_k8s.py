#!/usr/bin/env python3
"""
PARWA Day 2 — Nginx Consolidation & K8s Hardening Tests
Tests: nginx config, ssl-setup.sh, deployments, HPAs, PDBs,
       kustomization, ingress, namespace resources
"""
import unittest
import yaml
import os

K8S_DIR = "/home/z/my-project/download/parwa/infra/k8s"
NGINX_DIR = "/home/z/my-project/download/parwa/nginx"


def load_yaml(path):
    with open(path) as f:
        return list(yaml.safe_load_all(f))


def load_yaml_first(path):
    docs = load_yaml(path)
    return docs[0] if docs else None


def load_file(path):
    with open(path) as f:
        return f.read()


class TestNginxConsolidated(unittest.TestCase):
    """#119-#135: Consolidated nginx config"""

    def test_worker_connections_4096(self):
        """#119: worker_connections must be 4096"""
        config = load_file(f"{NGINX_DIR}/nginx.conf")
        self.assertIn("worker_connections 4096", config)

    def test_server_tokens_off(self):
        """#120: server_tokens must be off"""
        config = load_file(f"{NGINX_DIR}/nginx.conf")
        self.assertIn("server_tokens off", config)

    def test_no_unsafe_eval_in_csp(self):
        """#125, #126: CSP must NOT contain unsafe-eval in active directives"""
        config = load_file(f"{NGINX_DIR}/conf.d/default.conf")
        # Check each add_header Content-Security-Policy line
        for line in config.split('\n'):
            if 'add_header Content-Security-Policy' in line:
                # Remove the comment about "Removed 'unsafe-eval'" before checking
                clean = line.split('#')[0]  # Strip comments
                self.assertNotIn("unsafe-eval", clean)

    def test_limit_req_status_429(self):
        """#123, #129: Rate limiting returns 429, not 503"""
        config = load_file(f"{NGINX_DIR}/nginx.conf")
        self.assertIn("limit_req_status 429", config)

    def test_client_body_buffer_size(self):
        """#124: client_body_buffer_size 16k"""
        config = load_file(f"{NGINX_DIR}/nginx.conf")
        self.assertIn("client_body_buffer_size 16k", config)

    def test_docs_blocked_in_production(self):
        """#128: /docs and /openapi.json must return 403"""
        config = load_file(f"{NGINX_DIR}/conf.d/default.conf")
        self.assertIn("location /docs", config)
        self.assertIn("return 403", config)
        self.assertIn("location /openapi.json", config)

    def test_ssl_trusted_certificate(self):
        """#131: ssl_trusted_certificate for OCSP"""
        config = load_file(f"{NGINX_DIR}/nginx.conf")
        self.assertIn("ssl_trusted_certificate", config)

    def test_ssl_dhparam(self):
        """#135: ssl_dhparam must be configured"""
        config = load_file(f"{NGINX_DIR}/nginx.conf")
        self.assertIn("ssl_dhparam", config)

    def test_ipv6_listening(self):
        """IPv6 support on both 80 and 443"""
        config = load_file(f"{NGINX_DIR}/conf.d/default.conf")
        self.assertIn("listen [::]:80", config)
        self.assertIn("listen [::]:443", config)

    def test_login_burst_increased(self):
        """#122: login rate limit burst=10 nodelay"""
        config = load_file(f"{NGINX_DIR}/conf.d/default.conf")
        self.assertIn("burst=10 nodelay", config)

    def test_general_rate_limit(self):
        """General rate limit zone exists"""
        config = load_file(f"{NGINX_DIR}/nginx.conf")
        self.assertIn("zone=general:", config)

    def test_security_headers_in_api_location(self):
        """#121, #133: security headers repeated in /api/ location"""
        config = load_file(f"{NGINX_DIR}/conf.d/default.conf")
        # Find the /api/ location block - find all text between location /api/ and next location
        lines = config.split('\n')
        in_api = False
        api_lines = []
        brace_count = 0
        for line in lines:
            if 'location /api/' in line and 'auth' not in line:
                in_api = True
                brace_count += line.count('{') - line.count('}')
                continue
            if in_api:
                api_lines.append(line)
                brace_count += line.count('{') - line.count('}')
                if brace_count <= 0:
                    break
        api_block = '\n'.join(api_lines)
        self.assertIn("X-Frame-Options", api_block)
        self.assertIn("X-Content-Type-Options", api_block)
        self.assertIn("Content-Security-Policy", api_block)

    def test_sensitive_files_blocked(self):
        """#127, #49: .env, .git, wp-admin blocked"""
        config = load_file(f"{NGINX_DIR}/conf.d/default.conf")
        # The nginx config uses regex: \\.(env|git)
        self.assertIn("env|git", config)
        self.assertIn("wp-admin", config)

    def test_least_conn_upstream(self):
        """least_conn upstream strategy"""
        config = load_file(f"{NGINX_DIR}/nginx.conf")
        self.assertIn("least_conn", config)


class TestSSLSetup(unittest.TestCase):
    """#140-#144: ssl-setup.sh fixes"""

    def test_dh_params_4096(self):
        """#141: DH params default should be 4096"""
        content = load_file(f"{NGINX_DIR}/ssl-setup.sh")
        self.assertIn("4096", content)

    def test_dns_nginx_removed(self):
        """#140: --dns-nginx must be replaced in active code"""
        content = load_file(f"{NGINX_DIR}/ssl-setup.sh")
        # Check it's only in comments, not in active code
        for line in content.split('\n'):
            stripped = line.strip()
            # Skip comment lines
            if stripped.startswith('#'):
                continue
            self.assertNotIn('--dns-nginx', stripped)

    def test_dns_cloudflare_option(self):
        """#140: DNS cloudflare option added"""
        content = load_file(f"{NGINX_DIR}/ssl-setup.sh")
        self.assertIn("--dns-cloudflare", content)

    def test_docker_support(self):
        """#142: Docker container support for nginx reload"""
        content = load_file(f"{NGINX_DIR}/ssl-setup.sh")
        self.assertIn(".dockerenv", content)

    def test_cron_heredoc(self):
        """#143: Cron job uses heredoc, not broken escaping"""
        content = load_file(f"{NGINX_DIR}/ssl-setup.sh")
        self.assertIn("CRON_EOF", content)


class TestDeploymentHardening(unittest.TestCase):
    """#68-#84: K8s deployment hardening"""

    def test_backend_has_startup_probe(self):
        """#68"""
        dep = load_yaml_first(f"{K8S_DIR}/backend/deployment.yaml")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        self.assertIn("startupProbe", container)

    def test_frontend_has_startup_probe(self):
        dep = load_yaml_first(f"{K8S_DIR}/frontend/deployment.yaml")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        self.assertIn("startupProbe", container)

    def test_worker_has_startup_probe(self):
        dep = load_yaml_first(f"{K8S_DIR}/worker/deployment.yaml")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        self.assertIn("startupProbe", container)

    def test_mcp_has_startup_probe(self):
        dep = load_yaml_first(f"{K8S_DIR}/mcp/deployment.yaml")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        self.assertIn("startupProbe", container)

    def test_frontend_liveness_uses_api_health(self):
        """#77: frontend liveness probe uses /api/health"""
        dep = load_yaml_first(f"{K8S_DIR}/frontend/deployment.yaml")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["livenessProbe"]["httpGet"]["path"], "/api/health")

    def test_frontend_has_serviceaccount(self):
        """#75"""
        dep = load_yaml_first(f"{K8S_DIR}/frontend/deployment.yaml")
        self.assertEqual(dep["spec"]["template"]["spec"]["serviceAccountName"], "parwa-frontend")

    def test_worker_has_serviceaccount(self):
        """#83"""
        dep = load_yaml_first(f"{K8S_DIR}/worker/deployment.yaml")
        self.assertEqual(dep["spec"]["template"]["spec"]["serviceAccountName"], "parwa-worker")

    def test_mcp_has_serviceaccount(self):
        """#83"""
        dep = load_yaml_first(f"{K8S_DIR}/mcp/deployment.yaml")
        self.assertEqual(dep["spec"]["template"]["spec"]["serviceAccountName"], "parwa-mcp")

    def test_worker_has_celery_queues(self):
        """#79: worker has CELERY_QUEUES env"""
        dep = load_yaml_first(f"{K8S_DIR}/worker/deployment.yaml")
        envs = dep["spec"]["template"]["spec"]["containers"][0]["env"]
        queues_env = next((e for e in envs if e.get("name") == "CELERY_QUEUES"), None)
        self.assertIsNotNone(queues_env)
        self.assertIn("email_queue", queues_env["value"])

    def test_mcp_replicas_2(self):
        """#84: MCP scaled to 2 replicas"""
        dep = load_yaml_first(f"{K8S_DIR}/mcp/deployment.yaml")
        self.assertEqual(dep["spec"]["replicas"], 2)

    def test_mcp_has_scrape_annotations(self):
        """#69"""
        dep = load_yaml_first(f"{K8S_DIR}/mcp/deployment.yaml")
        annotations = dep["spec"]["template"]["metadata"].get("annotations", {})
        self.assertEqual(annotations.get("prometheus.io/scrape"), "true")
        self.assertEqual(annotations.get("prometheus.io/port"), "8080")

    def test_frontend_has_tolerations(self):
        """#76"""
        dep = load_yaml_first(f"{K8S_DIR}/frontend/deployment.yaml")
        self.assertIn("tolerations", dep["spec"]["template"]["spec"])

    def test_mcp_has_tolerations(self):
        """#84"""
        dep = load_yaml_first(f"{K8S_DIR}/mcp/deployment.yaml")
        self.assertIn("tolerations", dep["spec"]["template"]["spec"])

    def test_all_deployments_have_topology_spread(self):
        """#70: topologySpreadConstraints"""
        for svc in ["backend", "frontend", "worker", "mcp"]:
            dep = load_yaml_first(f"{K8S_DIR}/{svc}/deployment.yaml")
            self.assertIn("topologySpreadConstraints", dep["spec"]["template"]["spec"],
                          f"{svc} missing topologySpreadConstraints")

    def test_startup_probe_failure_threshold_30(self):
        """startupProbe failureThreshold should be 30"""
        for svc in ["backend", "frontend", "mcp"]:
            dep = load_yaml_first(f"{K8S_DIR}/{svc}/deployment.yaml")
            container = dep["spec"]["template"]["spec"]["containers"][0]
            self.assertEqual(container["startupProbe"]["failureThreshold"], 30,
                             f"{svc} startupProbe failureThreshold wrong")


class TestHPA(unittest.TestCase):
    """#73, #80, #81: HPA fixes"""

    def test_backend_hpa_has_memory(self):
        """#73: backend HPA has memory metric"""
        hpa = load_yaml_first(f"{K8S_DIR}/backend/hpa.yaml")
        metrics = hpa["spec"]["metrics"]
        mem_metrics = [m for m in metrics if m.get("resource", {}).get("name") == "memory"]
        self.assertTrue(len(mem_metrics) > 0, "Backend HPA missing memory metric")

    def test_worker_hpa_has_memory(self):
        """#80: worker HPA has memory metric"""
        hpa = load_yaml_first(f"{K8S_DIR}/worker/hpa.yaml")
        metrics = hpa["spec"]["metrics"]
        mem_metrics = [m for m in metrics if m.get("resource", {}).get("name") == "memory"]
        self.assertTrue(len(mem_metrics) > 0, "Worker HPA missing memory metric")

    def test_mcp_hpa_exists(self):
        """#81: MCP HPA created"""
        path = f"{K8S_DIR}/mcp/hpa.yaml"
        self.assertTrue(os.path.exists(path))

    def test_mcp_hpa_min_replicas(self):
        hpa = load_yaml_first(f"{K8S_DIR}/mcp/hpa.yaml")
        self.assertEqual(hpa["spec"]["minReplicas"], 2)
        self.assertEqual(hpa["spec"]["maxReplicas"], 5)


class TestPDB(unittest.TestCase):
    """#57, #58, #59: PDB fixes"""

    def test_pdb_uses_max_unavailable(self):
        """#59: PDB uses maxUnavailable, not minAvailable"""
        pdbs = load_yaml(f"{K8S_DIR}/pdb.yaml")
        for pdb in pdbs:
            if pdb:
                self.assertIn("maxUnavailable", pdb["spec"],
                               f"PDB {pdb['metadata']['name']} uses minAvailable instead of maxUnavailable")
                self.assertNotIn("minAvailable", pdb["spec"])

    def test_mcp_pdb_exists(self):
        """#57"""
        pdbs = load_yaml(f"{K8S_DIR}/pdb.yaml")
        names = [p["metadata"]["name"] for p in pdbs if p]
        self.assertIn("mcp-pdb", names)

    def test_postgres_pdb_exists(self):
        """#58"""
        pdbs = load_yaml(f"{K8S_DIR}/pdb.yaml")
        names = [p["metadata"]["name"] for p in pdbs if p]
        self.assertIn("postgres-pdb", names)

    def test_redis_pdb_exists(self):
        """#58"""
        pdbs = load_yaml(f"{K8S_DIR}/pdb.yaml")
        names = [p["metadata"]["name"] for p in pdbs if p]
        self.assertIn("redis-pdb", names)


class TestKustomization(unittest.TestCase):
    """#60-#63: Kustomization fixes"""

    def test_no_common_labels(self):
        """#60: commonLabels replaced with labels"""
        content = load_file(f"{K8S_DIR}/kustomization.yaml")
        self.assertNotIn("commonLabels:", content)

    def test_has_labels_with_include_selectors(self):
        content = load_file(f"{K8S_DIR}/kustomization.yaml")
        self.assertIn("includeSelectors: true", content)

    def test_has_images_section(self):
        """#61: images section with pinned tags"""
        kustomization = load_yaml_first(f"{K8S_DIR}/kustomization.yaml")
        self.assertIn("images", kustomization)

    def test_no_latest_tags_in_images(self):
        """No :latest tags in images section"""
        kustomization = load_yaml_first(f"{K8S_DIR}/kustomization.yaml")
        for img in kustomization.get("images", []):
            tag = img.get("newTag", "")
            self.assertNotEqual(tag, "latest", f"Image {img.get('name')} uses :latest")

    def test_no_orphaned_pvc_resources(self):
        """#63, #94: orphaned PVCs removed from active resources"""
        content = load_file(f"{K8S_DIR}/kustomization.yaml")
        # Check that postgres/pvc.yaml and redis/pvc.yaml are NOT listed as active resources
        # (they should only appear in comments)
        lines = content.split('\n')
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                continue  # Skip comments
            self.assertNotEqual(stripped, '- postgres/pvc.yaml')
            self.assertNotEqual(stripped, '- redis/pvc.yaml')

    def test_mcp_hpa_in_resources(self):
        content = load_file(f"{K8S_DIR}/kustomization.yaml")
        self.assertIn("mcp/hpa.yaml", content)

    def test_limitrange_in_resources(self):
        content = load_file(f"{K8S_DIR}/kustomization.yaml")
        self.assertIn("limitrange.yaml", content)

    def test_resourcequota_in_resources(self):
        content = load_file(f"{K8S_DIR}/kustomization.yaml")
        self.assertIn("resourcequota.yaml", content)


class TestIngress(unittest.TestCase):
    """#46-#50: Ingress fixes"""

    def test_monitoring_host_exists(self):
        """#46"""
        ingresses = load_yaml(f"{K8S_DIR}/ingress.yaml")
        hosts = []
        for ing in ingresses:
            if ing:
                for rule in ing["spec"].get("rules", []):
                    hosts.append(rule["host"])
        self.assertIn("monitoring.parwa.ai", hosts)

    def test_proxy_body_size_10m(self):
        """#48: proxy-body-size lowered to 10m"""
        content = load_file(f"{K8S_DIR}/ingress.yaml")
        self.assertIn("proxy-body-size", content)
        self.assertIn("\"10m\"", content)

    def test_sensitive_files_blocked(self):
        """#49: server-snippet blocks .env, .git"""
        content = load_file(f"{K8S_DIR}/ingress.yaml")
        self.assertIn("env|git", content)  # Regex pattern blocking .env/.git
        self.assertIn("wp-admin", content)

    def test_www_redirect(self):
        """#50: www → non-www redirect"""
        content = load_file(f"{K8S_DIR}/ingress.yaml")
        self.assertIn("from-to-www-redirect", content)

    def test_monitoring_auth(self):
        """#46: monitoring ingress has basic auth"""
        content = load_file(f"{K8S_DIR}/ingress.yaml")
        self.assertIn("auth-type: basic", content)
        self.assertIn("monitoring-basic-auth", content)


class TestNamespaceResources(unittest.TestCase):
    """#37, #38: LimitRange and ResourceQuota"""

    def test_limitrange_exists(self):
        lr = load_yaml_first(f"{K8S_DIR}/limitrange.yaml")
        self.assertEqual(lr["kind"], "LimitRange")

    def test_limitrange_has_defaults(self):
        lr = load_yaml_first(f"{K8S_DIR}/limitrange.yaml")
        limits = lr["spec"]["limits"][0]
        self.assertIn("default", limits)
        self.assertIn("defaultRequest", limits)
        self.assertIn("max", limits)

    def test_resourcequota_exists(self):
        rq = load_yaml_first(f"{K8S_DIR}/resourcequota.yaml")
        self.assertEqual(rq["kind"], "ResourceQuota")

    def test_resourcequota_has_cpu_memory_pods(self):
        rq = load_yaml_first(f"{K8S_DIR}/resourcequota.yaml")
        hard = rq["spec"]["hard"]
        self.assertIn("limits.cpu", hard)
        self.assertIn("limits.memory", hard)
        self.assertIn("pods", hard)


if __name__ == "__main__":
    unittest.main()
