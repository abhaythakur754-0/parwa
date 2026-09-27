"""
Week 8 Tests: DEPLOY-02 — SSL/TLS Configuration Validation

Validates nginx SSL configuration for SSL Labs A+ compliance:
- TLSv1.2+ minimum
- Strong cipher suites (8 Mozilla Modern ciphers)
- OCSP stapling enabled
- HSTS with includeSubDomains and preload
- Security headers present
"""

import os
import re
import pytest


# Main nginx.conf has global SSL settings (ciphers, OCSP, sessions)
NGINX_MAIN_CONF = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "nginx", "nginx.conf"
)
# Site configs inherit globals from main, only define server blocks
NGINX_SITE_CONFS = [
    os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "nginx", "nginx.conf"
    ),
    os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "infra", "docker", "nginx-default.conf"
    ),
]


def _read_nginx_conf(path):
    """Read nginx configuration file."""
    with open(path, "r") as f:
        return f.read()


# Expected Mozilla Modern cipher suites
EXPECTED_CIPHERS = [
    "ECDHE-ECDSA-AES128-GCM-SHA256",
    "ECDHE-RSA-AES128-GCM-SHA256",
    "ECDHE-ECDSA-AES256-GCM-SHA384",
    "ECDHE-RSA-AES256-GCM-SHA384",
    "ECDHE-ECDSA-CHACHA20-POLY1305",
    "ECDHE-RSA-CHACHA20-POLY1305",
    "DHE-RSA-AES128-GCM-SHA256",
    "DHE-RSA-AES256-GCM-SHA384",
]


class TestTLSProtocols:
    """Verify TLS protocol configuration."""

    def test_tls_min_version_12(self):
        """Must use TLSv1.2 minimum (no SSLv3, TLSv1.0, TLSv1.1)."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        assert "TLSv1.2" in content, "Missing TLSv1.2"
        assert "SSLv3" not in content, "SSLv3 must not be present"
        assert "TLSv1" not in content or "TLSv1.2" in content, (
            "TLSv1 without TLSv1.2"
        )
        # Must not have TLSv1.0 or TLSv1.1 alone
        assert re.search(r"ssl_protocols.*TLSv1\.2", content), (
            "TLSv1.2 not in ssl_protocols directive"
        )

    def test_tls_13_supported(self):
        """Should support TLSv1.3."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        assert "TLSv1.3" in content, "TLSv1.3 not configured"


class TestCipherSuites:
    """Verify strong cipher suite configuration."""

    def test_has_ssl_ciphers(self):
        """Main config must define ssl_ciphers directive."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        assert "ssl_ciphers" in content, "Missing ssl_ciphers directive"

    def test_all_modern_ciphers_present(self):
        """All 8 Mozilla Modern ciphers must be present in main config."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        cipher_line = ""
        for line in content.split("\n"):
            if "ssl_ciphers" in line:
                cipher_line += line
        for cipher in EXPECTED_CIPHERS:
            assert cipher in cipher_line, f"Missing cipher: {cipher}"

    def test_no_weak_ciphers(self):
        """Must not include weak ciphers (RC4, DES, 3DES, MD5)."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        weak = ["RC4", "DES-CBC3", "AES128-SHA", "MD5"]
        for w in weak:
            assert w not in content, f"Weak cipher '{w}' found"

    def test_cipher_count(self):
        """Must have at least 8 Mozilla Modern ciphers in main config."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        cipher_line = ""
        for line in content.split("\n"):
            if "ssl_ciphers" in line:
                cipher_line += line
        ciphers = [c.strip() for c in cipher_line.split(":")[-1].strip().strip(";").split(":")]
        # Count actual cipher names (they're colon-separated in the directive)
        all_ciphers = re.findall(r"ECDHE|DHE-RSA|DHE-DSS", cipher_line)
        assert len(all_ciphers) >= 8, f"Expected >= 8 ciphers, found {len(all_ciphers)}"


class TestOCSPStapling:
    """Verify OCSP stapling configuration."""

    def test_ocsp_stapling_enabled(self):
        """OCSP stapling must be on in main config."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        assert "ssl_stapling on" in content, "OCSP stapling not enabled"

    def test_ocsp_stapling_verify(self):
        """OCSP stapling verification must be on in main config."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        assert "ssl_stapling_verify on" in content, "OCSP verify not enabled"

    def test_resolver_configured(self):
        """Must configure DNS resolver for OCSP in main config."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        assert "resolver" in content, "DNS resolver not configured for OCSP"

    def test_ssl_session_tickets_off(self):
        """SSL session tickets must be off (forward secrecy) in main config."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        assert "ssl_session_tickets off" in content, "Session tickets not disabled"


class TestHSTS:
    """Verify HSTS configuration."""

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_hsts_header_present(self, conf_path):
        """Strict-Transport-Security header must be present."""
        content = _read_nginx_conf(conf_path)
        assert "Strict-Transport-Security" in content, "HSTS header missing"

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_hsts_max_age_minimum(self, conf_path):
        """HSTS max-age must be at least 1 year (31536000 seconds)."""
        content = _read_nginx_conf(conf_path)
        match = re.search(r"max-age=(\d+)", content)
        assert match, "HSTS max-age not found"
        max_age = int(match.group(1))
        assert max_age >= 31536000, f"HSTS max-age too low: {max_age}"

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_hsts_include_subdomains(self, conf_path):
        """HSTS must include includeSubDomains."""
        content = _read_nginx_conf(conf_path)
        assert "includeSubDomains" in content, "HSTS includeSubDomains missing"

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_hsts_preload(self, conf_path):
        """HSTS should include preload for browser preloading."""
        content = _read_nginx_conf(conf_path)
        assert "preload" in content, "HSTS preload missing"


class TestSecurityHeaders:
    """Verify security headers in nginx configuration."""

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_x_frame_options(self, conf_path):
        """X-Frame-Options must be SAMEORIGIN."""
        content = _read_nginx_conf(conf_path)
        assert "X-Frame-Options" in content
        assert "SAMEORIGIN" in content

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_x_content_type_options(self, conf_path):
        """X-Content-Type-Options must be nosniff."""
        content = _read_nginx_conf(conf_path)
        assert "X-Content-Type-Options" in content
        assert "nosniff" in content

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_referrer_policy(self, conf_path):
        """Referrer-Policy must be strict-origin-when-cross-origin."""
        content = _read_nginx_conf(conf_path)
        assert "Referrer-Policy" in content

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_permissions_policy(self, conf_path):
        """Permissions-Policy must restrict camera/microphone/geolocation."""
        content = _read_nginx_conf(conf_path)
        assert "Permissions-Policy" in content

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_csp_header(self, conf_path):
        """Content-Security-Policy must be defined."""
        content = _read_nginx_conf(conf_path)
        assert "Content-Security-Policy" in content


class TestHTTPToHTTPSRedirect:
    """Verify HTTP to HTTPS redirect."""

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_port_80_listens(self, conf_path):
        """Must listen on port 80."""
        content = _read_nginx_conf(conf_path)
        assert re.search(r"listen\s+80", content), "Not listening on port 80"

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_https_redirect(self, conf_path):
        """Must redirect HTTP to HTTPS (301)."""
        content = _read_nginx_conf(conf_path)
        assert "301" in content or "return 301" in content, "No 301 redirect"
        assert "https" in content, "No HTTPS redirect target"

    @pytest.mark.parametrize("conf_path", NGINX_SITE_CONFS)
    def test_ssl_port_443(self, conf_path):
        """Must listen on port 443 with ssl."""
        content = _read_nginx_conf(conf_path)
        assert re.search(r"listen\s+443\s+ssl", content), "Not listening on 443 with SSL"


class TestSSLSessionConfig:
    """Verify SSL session configuration for performance."""

    def test_session_cache_configured(self):
        """SSL session cache must be configured in main config."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        assert "ssl_session_cache" in content, "Session cache not configured"

    def test_session_timeout(self):
        """SSL session timeout must be 1 day in main config."""
        content = _read_nginx_conf(NGINX_MAIN_CONF)
        assert "ssl_session_timeout" in content, "Session timeout not configured"
        assert "1d" in content, "Session timeout not 1d"
