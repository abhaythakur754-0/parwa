use std::collections::HashMap;

use once_cell::sync::Lazy;
use pyo3::prelude::*;
use regex::Regex;
use sha2::{Digest, Sha256};

// ── PII Pattern Definitions ────────────────────────────────────────────

struct PiiPattern {
    pii_type: &'static str,
    regex: &'static Regex,
    confidence: f64,
    pattern_desc: &'static str,
}

macro_rules! lazy_regex {
    ($re:expr) => {{
        static RE: Lazy<Regex> = Lazy::new(|| Regex::new($re).unwrap());
        &*RE
    }};
}

/// All 15 PII type detectors, ordered roughly by specificity.
static PII_PATTERNS: Lazy<Vec<PiiPattern>> = Lazy::new(|| {
    vec![
        // 1. SSN — base pattern; invalid combos (000, 666, 9xx area; 00 group; 0000 serial)
        // are filtered out in post-match validation below.
        PiiPattern {
            pii_type: "SSN",
            regex: lazy_regex!(r"\b(\d{3})[-\s](\d{2})[-\s](\d{4})\b"),
            confidence: 0.95,
            pattern_desc: "SSN: NNN-NN-NNNN",
        },
        // 2. CREDIT_CARD (Visa 4x, MC 5x, Amex 3x)
        PiiPattern {
            pii_type: "CREDIT_CARD",
            regex: lazy_regex!(r"\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|3[47]\d{13})\b"),
            confidence: 0.85,
            pattern_desc: "Visa/MC/Amex card number",
        },
        // 3. EMAIL
        PiiPattern {
            pii_type: "EMAIL",
            regex: lazy_regex!(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
            confidence: 0.97,
            pattern_desc: "Email address",
        },
        // 4. PHONE — US formats
        PiiPattern {
            pii_type: "PHONE",
            regex: lazy_regex!(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
            confidence: 0.85,
            pattern_desc: "US phone number",
        },
        // 4b. PHONE — International
        PiiPattern {
            pii_type: "PHONE",
            regex: lazy_regex!(r"\b\+\d{1,3}[-.\s]?\d{2,4}[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b"),
            confidence: 0.75,
            pattern_desc: "International phone number",
        },
        // 5. IP_ADDRESS — IPv4
        PiiPattern {
            pii_type: "IP_ADDRESS",
            regex: lazy_regex!(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"),
            confidence: 0.90,
            pattern_desc: "IPv4 address",
        },
        // 5b. IP_ADDRESS — IPv6 (simplified)
        PiiPattern {
            pii_type: "IP_ADDRESS",
            regex: lazy_regex!(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"),
            confidence: 0.90,
            pattern_desc: "IPv6 address (full)",
        },
        // 6. DATE_OF_BIRTH — multiple formats
        PiiPattern {
            pii_type: "DATE_OF_BIRTH",
            regex: lazy_regex!(r"\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/]\d{4})\b"),
            confidence: 0.60,
            pattern_desc: "Date (various formats)",
        },
        // 7. PASSPORT — US passport number (9 digits)
        PiiPattern {
            pii_type: "PASSPORT",
            regex: lazy_regex!(r"\b\d{9}\b"),
            confidence: 0.50,
            pattern_desc: "Possible passport number (9 digits)",
        },
        // 7b. PASSPORT — UK passport (8 digits)
        PiiPattern {
            pii_type: "PASSPORT",
            regex: lazy_regex!(r"\b\d{8}\b"),
            confidence: 0.45,
            pattern_desc: "Possible passport number (8 digits)",
        },
        // 8. DRIVERS_LICENSE — generic US pattern
        PiiPattern {
            pii_type: "DRIVERS_LICENSE",
            regex: lazy_regex!(r"\b[A-Z][A-Z0-9]{5,12}\b"),
            confidence: 0.40,
            pattern_desc: "Possible US driver's license",
        },
        // 9. IBAN
        PiiPattern {
            pii_type: "IBAN",
            regex: lazy_regex!(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b"),
            confidence: 0.75,
            pattern_desc: "IBAN number",
        },
        // 10. MEDICAL_RECORD_NUMBER
        PiiPattern {
            pii_type: "MEDICAL_RECORD_NUMBER",
            regex: lazy_regex!(r"\b(?:MRN|MR|PT)\s*[-:]?\s*\d{4,12}\b"),
            confidence: 0.80,
            pattern_desc: "Medical record number (MRN/MR/PT prefix)",
        },
        // 11. HEALTH_INSURANCE_ID — Medicare MBI format
        PiiPattern {
            pii_type: "HEALTH_INSURANCE_ID",
            regex: lazy_regex!(r"\b[1-9A-CEGHJ-MPR-TVW-Y]\d[A-CEGHJ-NPR-TV-Z]\d{2}[A-CEGHJ-NPR-TV-Z]\d[A-CEGHJ-NPR-TV-Z]\d{2}\b"),
            confidence: 0.70,
            pattern_desc: "Medicare MBI",
        },
        // 12. STREET_ADDRESS
        PiiPattern {
            pii_type: "STREET_ADDRESS",
            regex: lazy_regex!(r"\b\d{1,5}\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Road|Rd|Court|Ct|Place|Pl|Way|Circle|Cir|Trail|Trl|Parkway|Pkwy)\b"),
            confidence: 0.50,
            pattern_desc: "Street address",
        },
        // 13. API_KEY
        PiiPattern {
            pii_type: "API_KEY",
            regex: lazy_regex!(r"\b(?:sk-[a-zA-Z0-9]{20,}|key_[a-zA-Z0-9]{16,}|ghp_[a-zA-Z0-9]{36}|xox[bpras]-[a-zA-Z0-9-]{20,})\b"),
            confidence: 0.95,
            pattern_desc: "API key (sk-, key_, ghp_, xox*)",
        },
        // 14. AADHAAR — 12 digits
        PiiPattern {
            pii_type: "AADHAAR",
            regex: lazy_regex!(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
            confidence: 0.80,
            pattern_desc: "Aadhaar number (12 digits)",
        },
        // 15. PAN — 5 letters + 4 digits + 1 letter (Indian)
        PiiPattern {
            pii_type: "PAN",
            regex: lazy_regex!(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
            confidence: 0.85,
            pattern_desc: "PAN (Indian permanent account number)",
        },
    ]
});

// ── Luhn Check ─────────────────────────────────────────────────────────

fn luhn_check(digits: &str) -> bool {
    let digits: Vec<u32> = digits
        .chars()
        .filter_map(|c| c.to_digit(10))
        .collect();
    if digits.is_empty() {
        return false;
    }
    let mut sum: u32 = 0;
    let mut double = false;
    for &d in digits.iter().rev() {
        if double {
            let doubled = d * 2;
            sum += if doubled > 9 { doubled - 9 } else { doubled };
        } else {
            sum += d;
        }
        double = !double;
    }
    sum % 10 == 0
}

// ── SHA-256 Deterministic Token ────────────────────────────────────────

fn deterministic_token(value: &str, pii_type: &str, company_id: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(value.as_bytes());
    hasher.update(pii_type.as_bytes());
    hasher.update(company_id.as_bytes());
    let result = hasher.finalize();
    let hex = hex::encode(result);
    format!("{{{{{}}}_{}}}", pii_type, &hex[..8])
}

// Small hex encoding helper (avoid pulling in another crate).
mod hex {
    pub fn encode(bytes: impl AsRef<[u8]>) -> String {
        bytes
            .as_ref()
            .iter()
            .map(|b| format!("{:02x}", b))
            .collect()
    }
}

// ── Detection ──────────────────────────────────────────────────────────

/// A single PII match.
#[derive(Debug, Clone)]
struct PiiMatch {
    pii_type: String,
    value: String,
    start: usize,
    end: usize,
    confidence: f64,
    pattern: String,
}

fn detect_pii_inner(text: &str, pii_types: Option<&[String]>) -> Vec<PiiMatch> {
    let patterns = &*PII_PATTERNS;
    let mut all_matches: Vec<PiiMatch> = Vec::new();

    let type_filter: Option<Vec<&str>> = pii_types.map(|types| types.iter().map(|s| s.as_str()).collect());

    for pp in patterns.iter() {
        // Filter by requested types
        if let Some(ref filter) = type_filter {
            if !filter.contains(&pp.pii_type) {
                continue;
            }
        }

        for cap in pp.regex.find_iter(text) {
            let value = cap.as_str().to_string();
            let start = cap.start();
            let end = cap.end();

            // Special handling: boost confidence for credit cards that pass Luhn
            let confidence = if pp.pii_type == "CREDIT_CARD" {
                let digits_only: String = value.chars().filter(|c| c.is_ascii_digit()).collect();
                if luhn_check(&digits_only) {
                    0.93
                } else {
                    pp.confidence
                }
            } else {
                pp.confidence
            };

            // Post-match validation for SSN: reject invalid combos
            if pp.pii_type == "SSN" {
                let parts: Vec<&str> = value.split(|c: char| c == '-' || c == ' ').collect();
                if parts.len() == 3 {
                    let area = parts[0];
                    let group = parts[1];
                    let serial = parts[2];
                    // Reject 000, 666, 9xx area codes
                    if area == "000" || area == "666" || area.starts_with('9') {
                        continue;
                    }
                    // Reject 00 group
                    if group == "00" {
                        continue;
                    }
                    // Reject 0000 serial
                    if serial == "0000" {
                        continue;
                    }
                }
            }

            all_matches.push(PiiMatch {
                pii_type: pp.pii_type.to_string(),
                value,
                start,
                end,
                confidence,
                pattern: pp.pattern_desc.to_string(),
            });
        }
    }

    // Deduplicate overlapping matches — keep highest confidence at each position.
    // Strategy: sort by start, then by confidence descending. Walk through and
    // remove any match that overlaps with a previously accepted higher-confidence match.
    all_matches.sort_by(|a, b| {
        a.start.cmp(&b.start).then_with(|| b.confidence.partial_cmp(&a.confidence).unwrap())
    });

    let mut deduped: Vec<PiiMatch> = Vec::new();
    let mut last_end: usize = 0;

    for m in &all_matches {
        if m.start >= last_end {
            deduped.push(m.clone());
            last_end = m.end;
        }
        // If overlapping, skip (the earlier higher-confidence one wins)
    }

    // Re-sort by position
    deduped.sort_by_key(|m| m.start);
    deduped
}

// ── Python-exposed functions ───────────────────────────────────────────

/// Detect PII in the given text.
///
/// Returns a list of dicts, each with keys:
///   pii_type, value, start, end, confidence, pattern
#[pyfunction]
#[pyo3(signature = (text, pii_types = None))]
pub fn detect_pii(text: &str, pii_types: Option<Vec<String>>) -> Vec<HashMap<String, String>> {
    let matches = detect_pii_inner(text, pii_types.as_deref());
    matches
        .into_iter()
        .map(|m| {
            let mut d = HashMap::new();
            d.insert("pii_type".to_string(), m.pii_type);
            d.insert("value".to_string(), m.value);
            d.insert("start".to_string(), m.start.to_string());
            d.insert("end".to_string(), m.end.to_string());
            d.insert("confidence".to_string(), format!("{:.2}", m.confidence));
            d.insert("pattern".to_string(), m.pattern);
            d
        })
        .collect()
}

/// Redact all detected PII by replacing with the given replacement string.
#[pyfunction]
#[pyo3(signature = (text, replacement, pii_types = None))]
pub fn redact_pii(text: &str, replacement: &str, pii_types: Option<Vec<String>>) -> String {
    let matches = detect_pii_inner(text, pii_types.as_deref());
    if matches.is_empty() {
        return text.to_string();
    }

    let mut result = text.to_string();
    // Process from end to start so indices remain valid
    for m in matches.iter().rev() {
        result.replace_range(m.start..m.end, replacement);
    }
    result
}

/// Redact PII deterministically: same input + same company_id → same tokens.
///
/// Returns (redacted_text, redaction_map_json).
#[pyfunction]
#[pyo3(signature = (text, company_id, pii_types = None))]
pub fn redact_pii_deterministic(
    text: &str,
    company_id: &str,
    pii_types: Option<Vec<String>>,
) -> (String, String) {
    let matches = detect_pii_inner(text, pii_types.as_deref());

    if matches.is_empty() {
        return (text.to_string(), "{}".to_string());
    }

    let mut result = text.to_string();
    let mut redaction_map: HashMap<String, String> = HashMap::new();

    // Process from end to start
    for m in matches.iter().rev() {
        let token = deterministic_token(&m.value, &m.pii_type, company_id);
        redaction_map.insert(m.value.clone(), token.clone());
        result.replace_range(m.start..m.end, &token);
    }

    let json_map =
        serde_json::to_string(&redaction_map).unwrap_or_else(|_| "{}".to_string());

    (result, json_map)
}

#[cfg(test)]
mod tests {
    use super::*;

    // Helper: run detect and convert to HashMap format (same as Python sees)
    fn detect(text: &str) -> Vec<HashMap<String, String>> {
        detect_pii_inner(text, None)
            .into_iter()
            .map(|m| {
                let mut d = HashMap::new();
                d.insert("pii_type".to_string(), m.pii_type);
                d.insert("value".to_string(), m.value);
                d.insert("start".to_string(), m.start.to_string());
                d.insert("end".to_string(), m.end.to_string());
                d.insert("confidence".to_string(), format!("{:.2}", m.confidence));
                d.insert("pattern".to_string(), m.pattern);
                d
            })
            .collect()
    }

    #[test]
    fn test_detect_ssn() {
        let results = detect("My SSN is 123-45-6789.");
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].get("pii_type").unwrap(), "SSN");
        assert_eq!(results[0].get("value").unwrap(), "123-45-6789");
    }

    #[test]
    fn test_detect_credit_card_with_luhn() {
        // 4539 1488 0343 6467 — valid Visa (passes Luhn)
        let results = detect("Card: 4539148803436467");
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].get("pii_type").unwrap(), "CREDIT_CARD");
        // Luhn-valid cards get 0.93
        assert_eq!(results[0].get("confidence").unwrap(), "0.93");
    }

    #[test]
    fn test_detect_email() {
        let results = detect("Contact me at alice@example.com please.");
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].get("pii_type").unwrap(), "EMAIL");
        assert_eq!(results[0].get("value").unwrap(), "alice@example.com");
    }

    #[test]
    fn test_detect_phone() {
        let results = detect("Call me at (555) 123-4567.");
        assert!(!results.is_empty());
        let phones: Vec<_> = results
            .iter()
            .filter(|r| r.get("pii_type").unwrap() == "PHONE")
            .collect();
        assert!(!phones.is_empty());
    }

    #[test]
    fn test_detect_multiple_pii_types() {
        let text = "Alice (alice@test.com) has SSN 123-45-6789 and card 4539148803436467.";
        let results = detect(text);
        let types: Vec<_> = results.iter().map(|r| r.get("pii_type").unwrap().clone()).collect();
        assert!(types.contains(&"EMAIL".to_string()));
        assert!(types.contains(&"SSN".to_string()));
        assert!(types.contains(&"CREDIT_CARD".to_string()));
    }

    #[test]
    fn test_redact_simple() {
        let text = "SSN: 123-45-6789 and email alice@example.com";
        let redacted = redact_pii(text, "[REDACTED]", None);
        assert!(!redacted.contains("123-45-6789"));
        assert!(!redacted.contains("alice@example.com"));
        assert!(redacted.contains("[REDACTED]"));
    }

    #[test]
    fn test_redact_deterministic_same_input_same_token() {
        let text = "SSN is 123-45-6789";
        let (r1, _) = redact_pii_deterministic(text, "company_abc", None);
        let (r2, _) = redact_pii_deterministic(text, "company_abc", None);
        assert_eq!(r1, r2);
    }

    #[test]
    fn test_redact_deterministic_different_company_different_token() {
        let text = "SSN is 123-45-6789";
        let (r1, _) = redact_pii_deterministic(text, "company_a", None);
        let (r2, _) = redact_pii_deterministic(text, "company_b", None);
        assert_ne!(r1, r2);
    }

    #[test]
    fn test_no_false_positives_on_clean_text() {
        let text = "Hello, this is a clean paragraph with no personal data.";
        let results = detect(text);
        assert!(
            results.is_empty(),
            "Expected no PII detections, got: {:?}",
            results
        );
    }

    #[test]
    fn test_overlapping_matches_deduplicated() {
        // "123456789" could match PASSPORT (9 digits) and AADHAAR (12 digits won't match)
        // But "123456789012" could match AADHAAR (12 digits) — let's test a scenario
        // where an email-like pattern could overlap with other matches.
        // Simpler: "1234567890123456" — could match CREDIT_CARD (16 digits) and AADHAAR (12 digits)
        let text = "1234567890123456";
        let results = detect(text);
        // It should detect something but not duplicate overlapping regions
        // Verify no two results have overlapping ranges
        for i in 0..results.len() {
            let start_i: usize = results[i].get("start").unwrap().parse().unwrap();
            let end_i: usize = results[i].get("end").unwrap().parse().unwrap();
            for j in (i + 1)..results.len() {
                let start_j: usize = results[j].get("start").unwrap().parse().unwrap();
                let end_j: usize = results[j].get("end").unwrap().parse().unwrap();
                assert!(
                    !(start_i < end_j && start_j < end_i),
                    "Overlapping matches: {:?} and {:?}",
                    results[i],
                    results[j]
                );
            }
        }
    }

    #[test]
    fn test_detect_api_key() {
        let results = detect("Use key sk-abc123def456ghi789jkl012mno345");
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].get("pii_type").unwrap(), "API_KEY");
    }

    #[test]
    fn test_detect_aadhaar() {
        let results = detect("Aadhaar: 1234 5678 9012");
        assert!(!results.is_empty());
        let aadhaar: Vec<_> = results
            .iter()
            .filter(|r| r.get("pii_type").unwrap() == "AADHAAR")
            .collect();
        assert!(!aadhaar.is_empty());
    }
}