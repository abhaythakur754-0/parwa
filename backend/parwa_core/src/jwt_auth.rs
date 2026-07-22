use std::collections::HashMap;

use jsonwebtoken::{decode, encode, Algorithm, DecodingKey, EncodingKey, Header, Validation};
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub company_id: String,
    pub email: String,
    pub role: String,
    pub plan: String,
    #[serde(rename = "type")]
    pub token_type: String,
    pub exp: u64,
    pub iat: u64,
    pub nbf: u64,
    pub jti: String,
}

/// Create a JWT HS256 access token.
#[pyfunction]
pub fn create_access_token(
    user_id: &str,
    company_id: &str,
    email: &str,
    role: &str,
    plan: &str,
    secret: &str,
    expire_minutes: u64,
) -> PyResult<String> {
    let now = jsonwebtoken::get_current_timestamp();
    let claims = Claims {
        sub: user_id.to_string(),
        company_id: company_id.to_string(),
        email: email.to_string(),
        role: role.to_string(),
        plan: plan.to_string(),
        token_type: "access".to_string(),
        exp: now + expire_minutes * 60,
        iat: now,
        nbf: now,
        jti: uuid::Uuid::new_v4().to_string(),
    };

    let token = encode(
        &Header::new(Algorithm::HS256),
        &claims,
        &EncodingKey::from_secret(secret.as_bytes()),
    )
    .map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Failed to create token: {}", e))
    })?;

    Ok(token)
}

/// Verify a JWT HS256 access token.
///
/// Tries `secret` first, then each entry in `previous_secrets` (key rotation).
/// Returns a HashMap of claims on success, or raises a ValueError on failure.
#[pyfunction]
pub fn verify_access_token(
    token: &str,
    secret: &str,
    previous_secrets: Vec<String>,
) -> PyResult<HashMap<String, String>> {
    let mut validation = Validation::new(Algorithm::HS256);
    validation.leeway = 0;

    // Try the current secret first
    if let Ok(token_data) =
        decode::<Claims>(token, &DecodingKey::from_secret(secret.as_bytes()), &validation)
    {
        return Ok(claims_to_map(&token_data.claims));
    }

    // Try previous secrets
    for prev in &previous_secrets {
        if let Ok(token_data) =
            decode::<Claims>(token, &DecodingKey::from_secret(prev.as_bytes()), &validation)
        {
            return Ok(claims_to_map(&token_data.claims));
        }
    }

    Err(pyo3::exceptions::PyValueError::new_err(
        "Invalid or expired token",
    ))
}

fn claims_to_map(claims: &Claims) -> HashMap<String, String> {
    let mut map = HashMap::new();
    map.insert("sub".to_string(), claims.sub.clone());
    map.insert("company_id".to_string(), claims.company_id.clone());
    map.insert("email".to_string(), claims.email.clone());
    map.insert("role".to_string(), claims.role.clone());
    map.insert("plan".to_string(), claims.plan.clone());
    map.insert("type".to_string(), claims.token_type.clone());
    map.insert("exp".to_string(), claims.exp.to_string());
    map.insert("iat".to_string(), claims.iat.to_string());
    map.insert("nbf".to_string(), claims.nbf.to_string());
    map.insert("jti".to_string(), claims.jti.clone());
    map
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_and_verify() {
        let secret = "test_secret_key_123";
        let token = create_access_token(
            "user_1",
            "company_1",
            "user@example.com",
            "admin",
            "pro",
            secret,
            60,
        )
        .unwrap();

        let claims = verify_access_token(&token, secret, vec![]).unwrap();
        assert_eq!(claims.get("sub").unwrap(), "user_1");
        assert_eq!(claims.get("company_id").unwrap(), "company_1");
        assert_eq!(claims.get("email").unwrap(), "user@example.com");
    }

    #[test]
    fn test_expired_token_rejected() {
        pyo3::prepare_freethreaded_python();
        let secret = "test_secret_key_123";
        // Create a token that expires in 0 minutes (already expired by the time we verify)
        let token = create_access_token(
            "user_1",
            "company_1",
            "user@example.com",
            "admin",
            "pro",
            secret,
            0,
        )
        .unwrap();

        // Small sleep to ensure the token is truly expired
        std::thread::sleep(std::time::Duration::from_secs(1));

        let result = verify_access_token(&token, secret, vec![]);
        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(err.to_string().contains("Invalid or expired token"));
    }

    #[test]
    fn test_wrong_secret_rejected() {
        let secret_a = "secret_aaaa";
        let secret_b = "secret_bbbb";
        let token = create_access_token(
            "user_1",
            "company_1",
            "user@example.com",
            "admin",
            "pro",
            secret_a,
            60,
        )
        .unwrap();

        let result = verify_access_token(&token, secret_b, vec![]);
        assert!(result.is_err());
    }

    #[test]
    fn test_previous_secret_accepted() {
        let old_secret = "old_secret_key";
        let new_secret = "new_secret_key";
        let token = create_access_token(
            "user_1",
            "company_1",
            "user@example.com",
            "admin",
            "pro",
            old_secret,
            60,
        )
        .unwrap();

        // Verify with new secret (fails) but provide old as previous
        let result =
            verify_access_token(&token, new_secret, vec![old_secret.to_string()]).unwrap();
        assert_eq!(result.get("sub").unwrap(), "user_1");
    }

    #[test]
    fn test_claims_correct() {
        let secret = "test_secret_key";
        let token = create_access_token(
            "user_42",
            "corp_inc",
            "alice@corp.com",
            "editor",
            "enterprise",
            secret,
            30,
        )
        .unwrap();

        let claims = verify_access_token(&token, secret, vec![]).unwrap();
        assert_eq!(claims.get("sub").unwrap(), "user_42");
        assert_eq!(claims.get("company_id").unwrap(), "corp_inc");
        assert_eq!(claims.get("email").unwrap(), "alice@corp.com");
        assert_eq!(claims.get("role").unwrap(), "editor");
        assert_eq!(claims.get("plan").unwrap(), "enterprise");
        assert_eq!(claims.get("type").unwrap(), "access");
        assert!(claims.get("jti").unwrap().len() > 0);
        // exp > iat
        let exp: u64 = claims.get("exp").unwrap().parse().unwrap();
        let iat: u64 = claims.get("iat").unwrap().parse().unwrap();
        assert!(exp > iat);
    }
}