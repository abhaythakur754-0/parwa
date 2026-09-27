use std::collections::HashMap;

use pyo3::prelude::*;

/// Generate a dict of recommended security response headers.
#[pyfunction]
pub fn generate_security_headers() -> HashMap<String, String> {
    let nonce = uuid::Uuid::new_v4()
        .to_string()
        .replace('-', ""); // 32 hex chars

    let mut headers = HashMap::new();
    headers.insert(
        "X-Content-Type-Options".to_string(),
        "nosniff".to_string(),
    );
    headers.insert("X-Frame-Options".to_string(), "DENY".to_string());
    headers.insert("X-XSS-Protection".to_string(), "0".to_string());
    headers.insert(
        "Referrer-Policy".to_string(),
        "strict-origin-when-cross-origin".to_string(),
    );
    headers.insert(
        "Content-Security-Policy".to_string(),
        format!(
            "default-src 'self'; script-src 'self' 'nonce-{}'",
            nonce
        ),
    );
    headers.insert(
        "Strict-Transport-Security".to_string(),
        "max-age=31536000; includeSubDomains".to_string(),
    );
    headers
}

/// Generate a 32-byte hex nonce (64 hex characters).
#[pyfunction]
pub fn generate_csrf_nonce() -> String {
    uuid::Uuid::new_v4()
        .to_string()
        .replace('-', "") // 32 hex chars from UUID (128 bits = 32 hex chars)
        + &uuid::Uuid::new_v4().to_string().replace('-', "") // another 32 = 64 total
}

/// Verify whether the given `origin` matches any of the `allowed_origins`.
///
/// Simple string matching (exact or prefix with wildcard `*`).
#[pyfunction]
pub fn verify_csrf_origin(origin: &str, allowed_origins: Vec<String>) -> bool {
    for allowed in &allowed_origins {
        if allowed == "*" {
            return true;
        }
        if origin == allowed {
            return true;
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_headers_contain_required_keys() {
        let headers = generate_security_headers();
        assert_eq!(headers.get("X-Content-Type-Options").unwrap(), "nosniff");
        assert_eq!(headers.get("X-Frame-Options").unwrap(), "DENY");
        assert_eq!(headers.get("X-XSS-Protection").unwrap(), "0");
        assert_eq!(
            headers.get("Referrer-Policy").unwrap(),
            "strict-origin-when-cross-origin"
        );
        assert!(headers
            .get("Content-Security-Policy")
            .unwrap()
            .contains("default-src 'self'"));
        assert!(headers
            .get("Content-Security-Policy")
            .unwrap()
            .contains("script-src 'self' 'nonce-"));
        assert_eq!(
            headers.get("Strict-Transport-Security").unwrap(),
            "max-age=31536000; includeSubDomains"
        );
    }

    #[test]
    fn test_nonce_is_64_chars() {
        let nonce = generate_csrf_nonce();
        assert_eq!(nonce.len(), 64, "Expected 64-char nonce, got: {}", nonce);
        // Should be all hex
        assert!(
            nonce.chars().all(|c| c.is_ascii_hexdigit()),
            "Nonce should be hex: {}",
            nonce
        );
    }

    #[test]
    fn test_verify_allowed_origin() {
        assert!(verify_csrf_origin(
            "https://app.example.com",
            vec!["https://app.example.com".to_string()]
        ));
        assert!(verify_csrf_origin(
            "https://app.example.com",
            vec![
                "https://other.com".to_string(),
                "https://app.example.com".to_string()
            ]
        ));
    }

    #[test]
    fn test_verify_rejected_origin() {
        assert!(!verify_csrf_origin(
            "https://evil.com",
            vec!["https://app.example.com".to_string()]
        ));
    }
}