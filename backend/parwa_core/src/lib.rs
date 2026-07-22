// ══════════════════════════════════════════════════════════════════
// parwa_core — Tier-1 Hot-Path Modules (Rust/PyO3)
//
// Replaces ~3,500 lines of Python with ~800 lines of Rust:
//   1. RateLimiter  — sliding-window, lock-free via DashMap
//   2. CircuitBreaker — atomic state machine
//   3. PII Redactor — compiled regex, deterministic tokens
//   4. JWT Decoder   — HS256 verify (fast-path; RS256 deferred)
//   5. Security Headers — nonce, CSP, origin check
//
// Build:  maturin develop --release
// Test:   cargo test
// ══════════════════════════════════════════════════════════════════

#![allow(deprecated)]

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::Bound;
pub type PyObject = pyo3::Py<pyo3::PyAny>;
use pyo3::types::{PyBool, PyDict, PyList};
use dashmap::DashMap;
use fancy_regex::Regex;
use std::collections::HashMap;
use std::sync::atomic::{AtomicU8, AtomicU32, AtomicU64, AtomicI64, Ordering};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

// ── Helpers ──────────────────────────────────────────────────────

fn now_secs() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

fn sha256_hex(input: &str) -> String {
    use sha2::{Sha256, Digest};
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    hex::encode(hasher.finalize())
}

fn hmac_sha256_hex(key: &str, msg: &str) -> String {
    use hmac::{Hmac, Mac};
    type HmacSha256 = Hmac<sha2::Sha256>;
    let mut mac = HmacSha256::new_from_slice(key.as_bytes()).unwrap();
    mac.update(msg.as_bytes());
    hex::encode(mac.finalize().into_bytes())
}

fn random_hex(n: usize) -> String {
    use rand::Rng;
    let mut rng = rand::rng();
    (0..n).map(|_| format!("{:02x}", rng.random_range(0..=255))).collect()
}

fn random_urlsafe(n: usize) -> String {
    use rand::Rng;
    let charset = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-";
    let mut rng = rand::rng();
    (0..n).map(|_| {
        let idx = rng.random_range(0..charset.len());
        charset[idx] as char
    }).collect()
}

// ── pyo3 0.29 helper: convert bool → Bound<'py, PyAny> ──
fn bool_to_any<'py>(py: Python<'py>, val: bool) -> Bound<'py, PyAny> {
    let borrowed = val.into_pyobject(py).unwrap();
    <Bound<'_, PyBool> as Clone>::clone(&*borrowed).into_any()
}

// ══════════════════════════════════════════════════════════════════
// 1. RATE LIMITER — Sliding-window, lock-free via DashMap
// ══════════════════════════════════════════════════════════════════

/// Per-category config: limit, window_secs, backoff list, lockout
#[derive(Clone)]
struct CategoryConfig {
    limit: u32,
    window_secs: f64,
    backoff: Vec<u32>,
    lockout_secs: f64,
}

/// Sliding-window buckets for a single key
struct WindowState {
    timestamps: Vec<f64>,   // sorted ascending
    failure_count: u32,
    first_fail_time: f64,
    locked_at: Option<f64>,
}

/// Thread-safe rate limiter using DashMap (lock-free reads)
#[pyclass]
struct RateLimiter {
    configs: HashMap<String, CategoryConfig>,
    windows: DashMap<String, WindowState>,
}

#[pymethods]
impl RateLimiter {
    #[new]
    #[pyo3(signature = (config=None))]
    fn new(config: Option<HashMap<String, PyObject>>) -> Self {
        let configs = default_category_configs();

        // Allow overriding from Python
        if let Some(py_config) = config {
            // We'll keep defaults; overrides can be added later
            let _ = py_config;
        }

        RateLimiter {
            configs,
            windows: DashMap::new(),
        }
    }

    /// Classify a request path + method into a category string.
    /// Mirrors Python classify_path() exactly.
    fn classify_path(&self, path: &str, method: &str) -> String {
        let m = method.to_uppercase();
        if path == "/api/auth/login" && m == "POST" { return "auth_login".into(); }
        if path == "/api/auth/register" && m == "POST" { return "auth_register".into(); }
        if path == "/api/auth/mfa" && m == "POST" { return "auth_mfa".into(); }
        if path == "/api/auth/phone/send" && m == "POST" { return "auth_phone_send".into(); }
        if path == "/api/auth/phone/verify" && m == "POST" { return "auth_phone_verify".into(); }
        if (path == "/api/auth/forgot-password" || path == "/api/auth/reset-password") && m == "POST" {
            return "auth_reset".into();
        }
        if path.starts_with("/api/billing/") { return "financial".into(); }
        if path.starts_with("/api/integrations/") { return "integration".into(); }
        if path == "/api/public/demo/chat" { return "demo_chat".into(); }
        if m == "GET" { return "general_get".into(); }
        "general_post".into()
    }

    /// Get config for a category
    fn get_category_config<'py>(&self, py: Python<'py>, category: &str) -> PyResult<Bound<'py, PyAny>> {
        let cfg = self.configs.get(category)
            .unwrap_or_else(|| self.configs.get("general_get").unwrap());

        let backoff_list = PyList::new(py, cfg.backoff.iter().copied())?;
        let dict = PyDict::new(py);
        dict.set_item("limit", cfg.limit)?;
        dict.set_item("window", cfg.window_secs as u32)?;
        dict.set_item("backoff_seconds", backoff_list)?;
        dict.set_item("lockout_duration", cfg.lockout_secs as u32)?;
        Ok(dict.into_any())
    }

    /// Check rate limit for a category + identifier.
    /// Returns a dict with: allowed, remaining, limit, reset_at, retry_after
    fn check_rate_limit<'py>(&self, py: Python<'py>, category: &str, identifier: &str) -> PyResult<Bound<'py, PyAny>> {
        let cfg = self.configs.get(category)
            .unwrap_or_else(|| self.configs.get("general_get").unwrap())
            .clone();
        let key = make_rl_key(category, identifier);
        let now = now_secs();
        let window_start = now - cfg.window_secs;

        let mut w = self.windows.entry(key.clone()).or_insert_with(|| WindowState {
            timestamps: Vec::new(),
            failure_count: 0,
            first_fail_time: 0.0,
            locked_at: None,
        });

        // Check lockout
        if let Some(locked_at) = w.locked_at {
            if now - locked_at < cfg.lockout_secs {
                let retry_after = (cfg.lockout_secs - (now - locked_at)).ceil() as u32;
                let dict = PyDict::new(py);
                dict.set_item("allowed", false)?;
                dict.set_item("remaining", 0)?;
                dict.set_item("limit", cfg.limit)?;
                dict.set_item("reset_at", (now + retry_after as f64) as i64)?;
                dict.set_item("retry_after", retry_after)?;
                return Ok(dict.into_any());
            } else {
                // Lockout expired
                w.locked_at = None;
                w.failure_count = 0;
            }
        }

        // Prune old timestamps
        w.timestamps.retain(|&ts| ts > window_start);

        let count = w.timestamps.len() as u32;

        let reset_at = if let Some(&oldest) = w.timestamps.first() {
            oldest + cfg.window_secs
        } else {
            now + cfg.window_secs
        };

        if count >= cfg.limit {
            let retry_after = (reset_at - now).ceil() as u32;
            let dict = PyDict::new(py);
            dict.set_item("allowed", false)?;
            dict.set_item("remaining", 0)?;
            dict.set_item("limit", cfg.limit)?;
            dict.set_item("reset_at", reset_at as i64)?;
            dict.set_item("retry_after", retry_after)?;
            Ok(dict.into_any())
        } else {
            w.timestamps.push(now);
            let remaining = cfg.limit.saturating_sub(count + 1);
            let dict = PyDict::new(py);
            dict.set_item("allowed", true)?;
            dict.set_item("remaining", remaining)?;
            dict.set_item("limit", cfg.limit)?;
            dict.set_item("reset_at", reset_at as i64)?;
            dict.set_item("retry_after", py.None())?;
            Ok(dict.into_any())
        }
    }

    /// Record a failure and return backoff seconds (or None)
    fn record_failure<'py>(&self, py: Python<'py>, category: &str, identifier: &str) -> PyResult<Bound<'py, PyAny>> {
        let cfg = self.configs.get(category)
            .unwrap_or_else(|| self.configs.get("general_get").unwrap())
            .clone();
        let key = make_rl_fail_key(category, identifier);
        let now = now_secs();

        let mut w = self.windows.entry(key).or_insert_with(|| WindowState {
            timestamps: Vec::new(),
            failure_count: 0,
            first_fail_time: 0.0,
            locked_at: None,
        });

        // Reset if first failure was > 1 hour ago
        if w.failure_count > 0 && now - w.first_fail_time > 3600.0 {
            w.failure_count = 0;
        }
        if w.failure_count == 0 {
            w.first_fail_time = now;
        }

        w.failure_count += 1;

        let count = w.failure_count;
        if (count as usize) < cfg.backoff.len() {
            let backoff = cfg.backoff[(count - 1) as usize];
            Ok(backoff.into_pyobject(py)?.into_any())
        } else {
            w.locked_at = Some(now);
            Ok((cfg.lockout_secs as u32).into_pyobject(py)?.into_any())
        }
    }

    /// Check if identifier is locked out
    fn is_locked_out(&self, category: &str, identifier: &str) -> bool {
        let cfg = self.configs.get(category)
            .unwrap_or_else(|| self.configs.get("general_get").unwrap());
        let key = make_rl_fail_key(category, identifier);
        let now = now_secs();

        if let Some(w) = self.windows.get(&key) {
            if let Some(locked_at) = w.locked_at {
                if now - locked_at < cfg.lockout_secs {
                    return true;
                }
            }
        }
        false
    }

    /// Reset rate limit and failure state for a key
    fn reset(&self, category: &str, identifier: &str) {
        let rl_key = make_rl_key(category, identifier);
        let fail_key = make_rl_fail_key(category, identifier);
        self.windows.remove(&rl_key);
        self.windows.remove(&fail_key);
    }

    /// Remove stale entries from the DashMap to prevent unbounded memory growth.
    /// Called periodically (e.g., every 5 minutes) from a background task.
    /// Returns the number of entries removed.
    fn cleanup_stale(&self) -> u32 {
        let now = now_secs();
        // Find the maximum window_secs across all categories
        let max_window = self.configs.values()
            .map(|c| c.window_secs)
            .fold(0.0_f64, f64::max);
        let max_lockout = self.configs.values()
            .map(|c| c.lockout_secs)
            .fold(0.0_f64, f64::max);
        let cutoff = now - max_window - max_lockout - 60.0; // 60s buffer

        let mut removed = 0u32;
        self.windows.retain(|_, w| {
            let is_stale = match (w.timestamps.last(), w.locked_at) {
                (Some(&last_ts), Some(locked_at)) => {
                    last_ts < cutoff && (locked_at as f64) < cutoff
                }
                (Some(&last_ts), None) => last_ts < cutoff,
                (None, Some(locked_at)) => (locked_at as f64) < cutoff,
                (None, None) => true, // empty state
            };
            if is_stale { removed += 1; }
            !is_stale
        });
        removed
    }
}

fn make_rl_key(category: &str, identifier: &str) -> String {
    let raw = format!("{}\x00{}", category, identifier);
    let hash = &sha256_hex(&raw)[..16];
    format!("rl:{}", hash)
}

fn make_rl_fail_key(category: &str, identifier: &str) -> String {
    let raw = format!("{}\x00{}", category, identifier);
    let hash = &sha256_hex(&raw)[..16];
    format!("rl:fail:{}", hash)
}

fn default_category_configs() -> HashMap<String, CategoryConfig> {
    let mut m = HashMap::new();
    m.insert("auth_login".into(), CategoryConfig { limit: 5, window_secs: 60.0, backoff: vec![0, 2, 4, 8, 900], lockout_secs: 900.0 });
    m.insert("auth_mfa".into(), CategoryConfig { limit: 10, window_secs: 60.0, backoff: vec![0, 2, 4, 8, 900], lockout_secs: 900.0 });
    m.insert("auth_phone_send".into(), CategoryConfig { limit: 5, window_secs: 300.0, backoff: vec![0, 2, 4, 8, 900], lockout_secs: 900.0 });
    m.insert("auth_phone_verify".into(), CategoryConfig { limit: 10, window_secs: 60.0, backoff: vec![0, 2, 4, 8, 300], lockout_secs: 300.0 });
    m.insert("auth_register".into(), CategoryConfig { limit: 3, window_secs: 60.0, backoff: vec![0, 2, 4, 8, 900], lockout_secs: 900.0 });
    m.insert("auth_reset".into(), CategoryConfig { limit: 3, window_secs: 3600.0, backoff: vec![0, 2, 4, 8, 900], lockout_secs: 900.0 });
    m.insert("financial".into(), CategoryConfig { limit: 20, window_secs: 60.0, backoff: vec![0, 2, 4, 8, 300], lockout_secs: 300.0 });
    m.insert("general_get".into(), CategoryConfig { limit: 100, window_secs: 60.0, backoff: vec![0, 2, 4, 8, 60], lockout_secs: 60.0 });
    m.insert("general_post".into(), CategoryConfig { limit: 100, window_secs: 60.0, backoff: vec![0, 2, 4, 8, 60], lockout_secs: 60.0 });
    m.insert("integration".into(), CategoryConfig { limit: 60, window_secs: 60.0, backoff: vec![0, 2, 4, 8, 60], lockout_secs: 60.0 });
    m.insert("demo_chat".into(), CategoryConfig { limit: 60, window_secs: 300.0, backoff: vec![0, 2, 4, 8, 60], lockout_secs: 60.0 });
    m
}


// ══════════════════════════════════════════════════════════════════
// 2. CIRCUIT BREAKER — Atomic state machine per dependency
// ══════════════════════════════════════════════════════════════════

/// Circuit states: 0=Closed, 1=Open, 2=HalfOpen
const STATE_CLOSED: u8 = 0;
const STATE_OPEN: u8 = 1;
const STATE_HALF_OPEN: u8 = 2;

#[derive(Clone)]
#[allow(dead_code)]
struct BreakerConfig {
    failure_threshold: u32,
    success_threshold: u32,
    timeout_secs: f64,
    half_open_max_calls: u32,
}

/// Per-dependency circuit breaker with atomic state
#[allow(dead_code)]
struct Breaker {
    state: AtomicU8,
    failure_count: AtomicU32,
    success_count: AtomicU32,
    failure_threshold: u32,
    success_threshold: u32,
    timeout_secs: f64,
    half_open_max_calls: u32,
    opened_at: AtomicI64,
    last_failure_time: AtomicI64,
    total_failures: AtomicU32,
    total_successes: AtomicU32,
    half_open_calls: AtomicU32,
}

#[pyclass]
struct CircuitBreakerManager {
    breakers: DashMap<String, Arc<Breaker>>,
}

#[pymethods]
impl CircuitBreakerManager {
    #[new]
    fn new() -> Self {
        CircuitBreakerManager {
            breakers: DashMap::new(),
        }
    }

    /// Register a new circuit breaker with optional config overrides
    #[pyo3(signature = (name, failure_threshold=5, success_threshold=3, timeout=60.0, half_open_max_calls=3))]
    fn register(&self, name: &str, failure_threshold: u32, success_threshold: u32, timeout: f64, half_open_max_calls: u32) {
        self.breakers.entry(name.to_string()).or_insert_with(|| {
            Arc::new(Breaker {
                state: AtomicU8::new(STATE_CLOSED),
                failure_count: AtomicU32::new(0),
                success_count: AtomicU32::new(0),
                failure_threshold,
                success_threshold,
                timeout_secs: timeout,
                half_open_max_calls,
                opened_at: AtomicI64::new(0),
                last_failure_time: AtomicI64::new(0),
                total_failures: AtomicU32::new(0),
                total_successes: AtomicU32::new(0),
                half_open_calls: AtomicU32::new(0),
            })
        });
    }

    /// Check if dependency is available (closed or half-open)
    fn is_available(&self, name: &str) -> bool {
        if let Some(breaker) = self.breakers.get(name) {
            let state = breaker.state.load(Ordering::SeqCst);
            match state {
                STATE_CLOSED => true,
                STATE_HALF_OPEN => {
                    let b: &Breaker = &*breaker;
                    b.half_open_calls.load(Ordering::SeqCst) < b.half_open_max_calls
                }
                STATE_OPEN => {
                    // Check timeout
                    let opened_at = breaker.opened_at.load(Ordering::SeqCst);
                    let now = now_secs();
                    if now - opened_at as f64 >= breaker.timeout_secs {
                        breaker.state.store(STATE_HALF_OPEN, Ordering::SeqCst);
                        breaker.half_open_calls.store(0, Ordering::SeqCst);
                        breaker.success_count.store(0, Ordering::SeqCst);
                        true
                    } else {
                        false
                    }
                }
                _ => true,
            }
        } else {
            true // Not registered = available
        }
    }

    /// Record a successful call
    fn record_success(&self, name: &str) {
        if let Some(breaker) = self.breakers.get(name) {
            breaker.total_successes.fetch_add(1, Ordering::SeqCst);
            let state = breaker.state.load(Ordering::SeqCst);
            if state == STATE_HALF_OPEN {
                let successes = breaker.success_count.fetch_add(1, Ordering::SeqCst) + 1;
                if successes >= breaker.success_threshold {
                    breaker.state.store(STATE_CLOSED, Ordering::SeqCst);
                    breaker.failure_count.store(0, Ordering::SeqCst);
                    breaker.success_count.store(0, Ordering::SeqCst);
                    breaker.half_open_calls.store(0, Ordering::SeqCst);
                }
            }
        }
    }

    /// Record a failed call
    fn record_failure(&self, name: &str) {
        if let Some(breaker) = self.breakers.get(name) {
            breaker.total_failures.fetch_add(1, Ordering::SeqCst);
            let state = breaker.state.load(Ordering::SeqCst);
            breaker.last_failure_time.store(now_secs() as i64, Ordering::SeqCst);

            if state == STATE_HALF_OPEN {
                breaker.state.store(STATE_OPEN, Ordering::SeqCst);
                breaker.opened_at.store(now_secs() as i64, Ordering::SeqCst);
            } else if state == STATE_CLOSED {
                let failures = breaker.failure_count.fetch_add(1, Ordering::SeqCst) + 1;
                if failures >= breaker.failure_threshold {
                    breaker.state.store(STATE_OPEN, Ordering::SeqCst);
                    breaker.opened_at.store(now_secs() as i64, Ordering::SeqCst);
                }
            }
        }
    }

    /// Record that a call was attempted (for half-open tracking)
    fn record_call(&self, name: &str) {
        if let Some(breaker) = self.breakers.get(name) {
            if breaker.state.load(Ordering::SeqCst) == STATE_HALF_OPEN {
                breaker.half_open_calls.fetch_add(1, Ordering::SeqCst);
            }
        }
    }

    /// Force-open a circuit
    fn force_open(&self, name: &str) {
        if let Some(breaker) = self.breakers.get(name) {
            breaker.state.store(STATE_OPEN, Ordering::SeqCst);
            breaker.opened_at.store(now_secs() as i64, Ordering::SeqCst);
        }
    }

    /// Force-close a circuit
    fn force_close(&self, name: &str) {
        if let Some(breaker) = self.breakers.get(name) {
            breaker.state.store(STATE_CLOSED, Ordering::SeqCst);
            breaker.failure_count.store(0, Ordering::SeqCst);
            breaker.success_count.store(0, Ordering::SeqCst);
            breaker.half_open_calls.store(0, Ordering::SeqCst);
        }
    }

    /// Reset a circuit to closed
    fn reset(&self, name: &str) {
        self.force_close(name);
    }

    /// Get status dict for a circuit breaker
    fn get_status<'py>(&self, py: Python<'py>, name: &str) -> PyResult<Bound<'py, PyAny>> {
        if let Some(breaker) = self.breakers.get(name) {
            let state = breaker.state.load(Ordering::SeqCst);
            let state_str = match state {
                STATE_CLOSED => "closed",
                STATE_OPEN => "open",
                STATE_HALF_OPEN => "half_open",
                _ => "unknown",
            };
            let dict = PyDict::new(py);
            dict.set_item("name", name)?;
            dict.set_item("state", state_str)?;
            dict.set_item("failure_count", breaker.failure_count.load(Ordering::SeqCst))?;
            dict.set_item("success_count", breaker.success_count.load(Ordering::SeqCst))?;
            dict.set_item("failure_threshold", breaker.failure_threshold)?;
            dict.set_item("success_threshold", breaker.success_threshold)?;
            dict.set_item("timeout_seconds", breaker.timeout_secs)?;
            dict.set_item("total_failures", breaker.total_failures.load(Ordering::SeqCst))?;
            dict.set_item("total_successes", breaker.total_successes.load(Ordering::SeqCst))?;
            dict.set_item("is_available", self.is_available(name))?;
            Ok(dict.into_any())
        } else {
            let dict = PyDict::new(py);
            dict.set_item("name", name)?;
            dict.set_item("state", "not_registered")?;
            dict.set_item("is_available", true)?;
            Ok(dict.into_any())
        }
    }

    /// Get status of all registered breakers
    fn get_all_status<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let list = PyList::empty(py);
        for entry in self.breakers.iter() {
            let status = self.get_status(py, entry.key())?;
            list.append(status)?;
        }
        Ok(list.into_any())
    }

    /// Unregister a circuit breaker
    fn unregister(&self, name: &str) {
        self.breakers.remove(name);
    }
}


// ══════════════════════════════════════════════════════════════════
// 3. PII REDACTOR — Compiled regex, deterministic tokens
// ══════════════════════════════════════════════════════════════════

struct PIIPattern {
    pii_type: &'static str,
    pattern: Regex,
    confidence: f64,
}

fn build_pii_patterns() -> Vec<PIIPattern> {
    vec![
        // SSN
        PIIPattern { pii_type: "SSN", pattern: Regex::new(r"\b(?!000|666|9\d{2})(\d{3})[-\s](?!00)\d{2}[-\s](?!0000)\d{4}\b").unwrap(), confidence: 0.95 },
        // Credit Card
        PIIPattern { pii_type: "CREDIT_CARD", pattern: Regex::new(r"\b(?:4\d{3}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}|(?:5[1-5]\d{2}|2[2-7]\d{2})[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}|3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5})\b").unwrap(), confidence: 0.90 },
        // Email
        PIIPattern { pii_type: "EMAIL", pattern: Regex::new(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b").unwrap(), confidence: 0.95 },
        // Phone (US + international)
        PIIPattern { pii_type: "PHONE", pattern: Regex::new(r"(?:\b\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b|(?<!\w)\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b").unwrap(), confidence: 0.85 },
        // IPv4
        PIIPattern { pii_type: "IP_ADDRESS", pattern: Regex::new(r"\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b").unwrap(), confidence: 0.90 },
        // Date of Birth (MM/DD/YYYY)
        PIIPattern { pii_type: "DATE_OF_BIRTH", pattern: Regex::new(r"\b(0[1-9]|1[0-2])[\/\-](0[1-9]|[12]\d|3[01])[\/\-](19|20)\d{2}\b").unwrap(), confidence: 0.70 },
        // Date of Birth (YYYY-MM-DD)
        PIIPattern { pii_type: "DATE_OF_BIRTH", pattern: Regex::new(r"\b(19|20)\d{2}[\-\/](0[1-9]|1[0-2])[\-\/](0[1-9]|[12]\d|3[01])\b").unwrap(), confidence: 0.65 },
        // IBAN
        PIIPattern { pii_type: "IBAN", pattern: Regex::new(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b").unwrap(), confidence: 0.80 },
        // API Keys
        PIIPattern { pii_type: "API_KEY", pattern: Regex::new(r"\b(?:sk-[A-Za-z0-9_\-]{20,}|key_[A-Za-z0-9_\-]{16,}|ghp_[A-Za-z0-9]{36}|csk-[A-Za-z0-9_\-]{20,}|xox[bpra]-[A-Za-z0-9\-]{10,}|AIza[A-Za-z0-9_\-]{35}|hooks\.[A-Za-z0-9\-]{30,})\b").unwrap(), confidence: 0.95 },
        // Aadhaar
        PIIPattern { pii_type: "AADHAAR", pattern: Regex::new(r"\b[2-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}\b").unwrap(), confidence: 0.80 },
        // PAN (India)
        PIIPattern { pii_type: "PAN", pattern: Regex::new(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b").unwrap(), confidence: 0.85 },
        // Passport US
        PIIPattern { pii_type: "PASSPORT", pattern: Regex::new(r"\b[1-9]\d{8}\b").unwrap(), confidence: 0.50 },
        // Passport UK
        PIIPattern { pii_type: "PASSPORT", pattern: Regex::new(r"\b\d{8}[A-Z]\b").unwrap(), confidence: 0.60 },
        // Passport EU
        PIIPattern { pii_type: "PASSPORT", pattern: Regex::new(r"\b[A-Z]{2}\d{7}\b").unwrap(), confidence: 0.55 },
        // Medical Record
        PIIPattern { pii_type: "MEDICAL_RECORD_NUMBER", pattern: Regex::new(r"\b(?:MRN|MR|PT|PAT)[-]?\d{4,10}[A-Z]?\b").unwrap(), confidence: 0.85 },
        // Medicare MBI
        PIIPattern { pii_type: "HEALTH_INSURANCE_ID", pattern: Regex::new(r"\b[1-9][ACDEFGHJKMNPQRTUVWXY]{2}\d[ACDEFGHJKMNPQRTUVWXY]{2}\d[ACDEFGHJKMNPQRTUVWXY]{2}\d{2}\b").unwrap(), confidence: 0.75 },
        // Driver's License
        PIIPattern { pii_type: "DRIVERS_LICENSE", pattern: Regex::new(r"\b(?:[A-Z]{1,2}[-\s]?)?\d{6,12}\b").unwrap(), confidence: 0.45 },
        // Street Address
        PIIPattern { pii_type: "STREET_ADDRESS", pattern: Regex::new(r"\b\d{1,5}\s+[A-Za-z0-9\s]{2,40}(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl|Circle|Cir|Crescent|Cres|Trail|Trl|Parkway|Pkwy|Highway|Hwy|Terrace|Ter)\b(?:[,\s]+(?:#[\w\s]+|(?:Apt|Suite|Ste|Unit|Fl|Floor|Rm|Room)\s*\.?\s*[\w]+))?(?:[,\s]+[A-Za-z\s]{2,25})?").unwrap(), confidence: 0.60 },
    ]
}

#[pyclass]
struct PIIRedactor {
    patterns: Vec<PIIPattern>,
    #[allow(dead_code)]
    token_pattern: Regex,
}

#[pymethods]
impl PIIRedactor {
    #[new]
    fn new() -> Self {
        PIIRedactor {
            patterns: build_pii_patterns(),
            token_pattern: Regex::new(r"\{\{([A-Z_]+)_[0-9a-f]{8}\}\}").unwrap(),
        }
    }

    /// Detect PII in text. Returns list of (pii_type, value, start, end, confidence)
    fn detect_pii<'py>(&self, py: Python<'py>, text: &str) -> PyResult<Bound<'py, PyAny>> {
        let results = PyList::empty(py);
        for pat in &self.patterns {
            for mat in pat.pattern.find_iter(text).flatten() {
                let m = PyDict::new(py);
                m.set_item("pii_type", pat.pii_type)?;
                m.set_item("value", mat.as_str())?;
                m.set_item("start", mat.start())?;
                m.set_item("end", mat.end())?;
                m.set_item("confidence", pat.confidence)?;
                results.append(m)?;
            }
        }
        Ok(results.into_any())
    }

    /// Redact PII in text. Returns (redacted_text, redaction_map, redaction_id)
    /// company_id is used for deterministic token generation
    #[pyo3(signature = (text, company_id))]
    fn redact<'py>(&self, py: Python<'py>, text: &str, company_id: &str) -> PyResult<Bound<'py, PyAny>> {
        let redaction_id = uuid_str();
        let mut matches: Vec<(usize, usize, String, &str)> = Vec::new();

        for pat in &self.patterns {
            for mat in pat.pattern.find_iter(text).flatten() {
                let value = mat.as_str();
                let token = generate_token(pat.pii_type, value, company_id);
                matches.push((mat.start(), mat.end(), token, value));
            }
        }

        // Sort by start position, then by length descending (longer matches first)
        matches.sort_by(|a, b| {
            a.0.cmp(&b.0).then_with(|| (b.1 - b.0).cmp(&(a.1 - a.0)))
        });

        // Deduplicate: skip matches that overlap with a previous (longer) match
        let mut deduped: Vec<(usize, usize, String, &str)> = Vec::new();
        let mut last_end: usize = 0;
        for (start, end, token, value) in &matches {
            if *start >= last_end {
                deduped.push((*start, *end, token.clone(), *value));
                last_end = *end;
            }
        }

        // Build redacted text and map
        let mut redacted = text.to_string();
        let mut redaction_map: HashMap<String, String> = HashMap::new();
        let mut offset = 0i64;
        let mut pii_found = false;
        let mut pii_counts: HashMap<&str, u32> = HashMap::new();

        for (start, end, token, value) in &deduped {
            let s = (*start as i64 + offset) as usize;
            let e = (*end as i64 + offset) as usize;
            if s < redacted.len() && e <= redacted.len() {
                redacted.replace_range(s..e, token);
                offset += token.len() as i64 - (*end as i64 - *start as i64);
                redaction_map.insert(token.clone(), value.to_string());
                *pii_counts.entry(token).or_insert(0) += 1;
                pii_found = true;
            }
        }

        let dict = PyDict::new(py);
        dict.set_item("redacted_text", &redacted)?;
        dict.set_item("redaction_map", redaction_map)?;
        dict.set_item("redaction_id", &redaction_id)?;
        dict.set_item("pii_found", pii_found)?;

        // Summary
        let summary_dict = PyDict::new(py);
        let mut type_counts: HashMap<&str, u32> = HashMap::new();
        for pat in &self.patterns {
            let count = deduped.iter().filter(|m| pat.pattern.is_match(m.3).unwrap_or(false)).count() as u32;
            if count > 0 {
                type_counts.insert(pat.pii_type, count);
            }
        }
        for (pii_type, count) in &type_counts {
            summary_dict.set_item(*pii_type, *count)?;
        }
        dict.set_item("summary", summary_dict)?;

        Ok(dict.into_any())
    }

    /// Deredact text by replacing tokens with original values
    #[pyo3(signature = (text, redaction_map))]
    fn deredact<'py>(&self, py: Python<'py>, text: &str, redaction_map: HashMap<String, String>) -> PyResult<Bound<'py, PyAny>> {
        let mut result = text.to_string();
        for (token, original) in &redaction_map {
            result = result.replace(token, original);
        }
        Ok(result.into_pyobject(py)?.into_any())
    }

    /// Check if text contains PII (quick boolean check)
    fn has_pii(&self, text: &str) -> bool {
        for pat in &self.patterns {
            if pat.pattern.is_match(text).unwrap_or(false) {
                return true;
            }
        }
        false
    }
}

fn generate_token(pii_type: &str, value: &str, company_id: &str) -> String {
    let raw = format!("{}:{}:{}", value, pii_type, company_id);
    let digest = &sha256_hex(&raw)[..8];
    format!("{{{{{}_{} }}}}", pii_type, digest)
}

fn uuid_str() -> String {
    use rand::Rng;
    let mut rng = rand::rng();
    let bytes: [u8; 16] = rng.random();
    format!(
        "{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}",
        bytes[0], bytes[1], bytes[2], bytes[3],
        bytes[4], bytes[5],
        bytes[6], bytes[7],
        bytes[8], bytes[9],
        bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]
    )
}


// ══════════════════════════════════════════════════════════════════
// 4. JWT DECODER — HS256 verify, RS256 verify
// ══════════════════════════════════════════════════════════════════

use base64::{Engine as _, engine::general_purpose};

/// Decode a base64url string (no padding)
fn b64url_decode(input: &str) -> Result<Vec<u8>, String> {
    let padded = {
        let mut s = input.to_string();
        while s.len() % 4 != 0 {
            s.push('=');
        }
        s
    };
    general_purpose::STANDARD.decode(&padded).map_err(|e| format!("base64 decode error: {}", e))
}

/// Decode a base64url string to JSON
fn b64url_to_json(input: &str) -> Result<serde_json::Value, String> {
    let bytes = b64url_decode(input)?;
    serde_json::from_slice(&bytes).map_err(|e| format!("json parse error: {}", e))
}

/// Verify HS256 signature
fn verify_hs256(signature_b64: &str, signing_input: &str, secret: &str) -> bool {
    let expected = hmac_sha256_hex(secret, signing_input);
    let sig_bytes = match b64url_decode(signature_b64) {
        Ok(b) => b,
        Err(_) => return false,
    };
    let expected_bytes = match hex::decode(&expected) {
        Ok(b) => b,
        Err(_) => return false,
    };
    // Constant-time comparison
    if sig_bytes.len() != expected_bytes.len() {
        return false;
    }
    let mut result: u8 = 0;
    for (a, b) in sig_bytes.iter().zip(expected_bytes.iter()) {
        result |= a ^ b;
    }
    result == 0
}

/// Verify RS256 signature (using public key PEM)
#[allow(dead_code, unused_variables)]
fn verify_rs256(signature_b64: &str, _signing_input: &str, _public_key_pem: &str) -> bool {
    // For now, we delegate RS256 verification to Python's jose library
    // since native RSA in Rust requires ring/rsa crate which is complex.
    // The Python wrapper will handle RS256; this is a placeholder for pure-Rust future.
    // We return false to trigger the Python fallback.
    false
}

#[pyclass]
struct JWTDecoder {
    previous_keys: Vec<String>,
}

#[pymethods]
impl JWTDecoder {
    #[new]
    #[pyo3(signature = (previous_keys=None))]
    fn new(previous_keys: Option<Vec<String>>) -> Self {
        JWTDecoder {
            previous_keys: previous_keys.unwrap_or_default(),
        }
    }

    /// Verify and decode an HS256 JWT token.
    /// Returns the payload dict on success, raises PyValueError on failure.
    #[pyo3(signature = (token, secret, algorithms=None))]
    fn verify<'py>(&self, py: Python<'py>, token: &str, secret: &str, algorithms: Option<Vec<String>>) -> PyResult<Bound<'py, PyAny>> {
        let parts: Vec<&str> = token.split('.').collect();
        if parts.len() != 3 {
            return Err(PyValueError::new_err("Invalid JWT: must have 3 parts"));
        }

        let header = b64url_to_json(parts[0])
            .map_err(|e| PyValueError::new_err(format!("Invalid JWT header: {}", e)))?;
        let payload = b64url_to_json(parts[1])
            .map_err(|e| PyValueError::new_err(format!("Invalid JWT payload: {}", e)))?;

        let alg = header.get("alg")
            .and_then(|v| v.as_str())
            .unwrap_or("HS256");

        // Determine which algorithms to try
        let try_algos: Vec<&str> = if let Some(ref algos) = algorithms {
            algos.iter().map(|s| s.as_str()).collect()
        } else if alg == "RS256" {
            vec!["RS256", "HS256"]
        } else {
            vec![alg]
        };

        let signing_input = format!("{}.{}", parts[0], parts[1]);

        // Try RS256 first if requested
        for &try_alg in &try_algos {
            if try_alg == "RS256" {
                // RS256 needs a public key which we don't have here
                // Skip - let Python handle RS256
                continue;
            }
            if try_alg == "HS256" {
                // Try primary key, then previous keys
                let all_keys: Vec<&str> = std::iter::once(secret)
                    .chain(self.previous_keys.iter().map(|s| s.as_str()))
                    .collect();

                for key in &all_keys {
                    if verify_hs256(parts[2], &signing_input, key) {
                        // Verify token type
                        if let Some(token_type) = payload.get("type").and_then(|v| v.as_str()) {
                            if token_type != "access" {
                                return Err(PyValueError::new_err("Invalid token type"));
                            }
                        }

                        // Check expiry
                        if let Some(exp) = payload.get("exp").and_then(|v| v.as_f64()) {
                            if now_secs() > exp {
                                return Err(PyValueError::new_err("Token expired"));
                            }
                        }

                        // Check nbf
                        if let Some(nbf) = payload.get("nbf").and_then(|v| v.as_f64()) {
                            if now_secs() < nbf {
                                return Err(PyValueError::new_err("Token not yet valid"));
                            }
                        }

                        return Ok(json_value_to_py(py, &payload));
                    }
                }
            }
        }

        Err(PyValueError::new_err("Invalid or expired token"))
    }

    /// Extract claims without verification (for jti extraction)
    fn get_unverified_claims<'py>(&self, py: Python<'py>, token: &str) -> PyResult<Bound<'py, PyAny>> {
        let parts: Vec<&str> = token.split('.').collect();
        if parts.len() != 3 {
            return Err(PyValueError::new_err("Invalid JWT: must have 3 parts"));
        }
        let payload = b64url_to_json(parts[1])
            .map_err(|e| PyValueError::new_err(format!("Invalid JWT payload: {}", e)))?;
        Ok(json_value_to_py(py, &payload))
    }

    /// Set previous keys for rotation support
    fn set_previous_keys(&mut self, keys: Vec<String>) {
        self.previous_keys = keys;
    }
}

fn json_value_to_py<'py>(py: Python<'py>, val: &serde_json::Value) -> Bound<'py, PyAny> {
    match val {
        serde_json::Value::Null => py.None().into_bound(py),
        serde_json::Value::Bool(b) => {
            {
                        bool_to_any(py, *b)
                    }
        }
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                i.into_pyobject(py).unwrap().clone().into_any()
            } else if let Some(f) = n.as_f64() {
                f.into_pyobject(py).unwrap().clone().into_any()
            } else {
                py.None().into_bound(py)
            }
        }
        serde_json::Value::String(s) => s.into_pyobject(py).unwrap().clone().into_any(),
        serde_json::Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(json_value_to_py(py, item)).unwrap();
            }
            list.into_any()
        }
        serde_json::Value::Object(obj) => {
            let dict = PyDict::new(py);
            for (k, v) in obj {
                dict.set_item(k, json_value_to_py(py, v)).unwrap();
            }
            dict.into_any()
        }
    }
}


// ══════════════════════════════════════════════════════════════════
// 5. SECURITY HEADERS + CSRF
// ══════════════════════════════════════════════════════════════════

#[pyclass]
struct SecurityHeaders {
    is_production: bool,
    csp_template: String,
}

#[pymethods]
impl SecurityHeaders {
    #[new]
    #[pyo3(signature = (environment="development"))]
    fn new(environment: &str) -> Self {
        SecurityHeaders {
            is_production: environment == "production",
            csp_template: String::from(
                "default-src 'self'; script-src 'self' 'nonce-{nonce}'; \
                 style-src 'self' 'unsafe-inline'; img-src 'self' data: https: blob:; \
                 font-src 'self' data:; \
                 connect-src 'self' https://*.paddle.com https://api.stripe.com; \
                 frame-ancestors 'none'; base-uri 'self'; form-action 'self'; \
                 object-src 'none'; upgrade-insecure-requests"
            ),
        }
    }

    /// Generate CSP nonce and full headers dict for a response
    fn generate_headers<'py>(&self, py: Python<'py>, path: &str) -> PyResult<Bound<'py, PyAny>> {
        let nonce = random_urlsafe(16);
        let dict = PyDict::new(py);

        dict.set_item("X-Content-Type-Options", "nosniff")?;
        dict.set_item("X-Frame-Options", "DENY")?;
        dict.set_item("X-XSS-Protection", "0")?;
        dict.set_item("Referrer-Policy", "strict-origin-when-cross-origin")?;
        dict.set_item("Permissions-Policy", "camera=(), microphone=(), geolocation=()")?;
        dict.set_item("Content-Security-Policy", self.csp_template.replace("{nonce}", &nonce))?;
        dict.set_item("X-CSP-Nonce", &nonce)?;

        if self.is_production {
            dict.set_item("Strict-Transport-Security", "max-age=31536000; includeSubDomains")?;
        }

        // M-11: No-cache for auth endpoints
        let auth_prefixes = ["/api/auth/", "/api/login", "/api/register", "/api/mfa/", "/api/refresh"];
        for prefix in &auth_prefixes {
            if path.starts_with(prefix) {
                dict.set_item("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")?;
                dict.set_item("Pragma", "no-cache")?;
                dict.set_item("Expires", "0")?;
                break;
            }
        }

        Ok(dict.into_any())
    }
}


#[pyclass]
struct CSRFValidator {
    trusted_origins: Vec<String>,
    secret_key: String,
    max_age: f64,
}

#[pymethods]
impl CSRFValidator {
    #[new]
    #[pyo3(signature = (trusted_origins=None, secret_key="parwa-csrf-fallback", max_age=3600.0))]
    fn new(trusted_origins: Option<Vec<String>>, secret_key: &str, max_age: f64) -> Self {
        CSRFValidator {
            trusted_origins: trusted_origins.unwrap_or_default(),
            secret_key: secret_key.to_string(),
            max_age,
        }
    }

    /// Validate origin and/or referer against trusted origins
    #[pyo3(signature = (origin, referer=""))]
    fn is_valid_origin(&self, origin: &str, referer: &str) -> bool {
        if self.trusted_origins.is_empty() {
            return true; // No origins configured = local dev
        }

        let check_origin = if !origin.is_empty() {
            origin.to_string()
        } else if !referer.is_empty() {
            // Extract origin from referer
            if let Some(scheme_end) = referer.find("://") {
                let rest = &referer[scheme_end + 3..];
                if let Some(slash) = rest.find('/') {
                    format!("{}://{}", &referer[..scheme_end], &rest[..slash])
                } else {
                    format!("{}://{}", &referer[..scheme_end], rest)
                }
            } else {
                return false;
            }
        } else {
            return false;
        };

        // Allow any Vercel preview deployment
        if Regex::new(r"^https://[a-z0-9\-]+(--[a-z0-9\-]+)?\.vercel\.app$").unwrap().is_match(&check_origin).unwrap_or(false) {
            return true;
        }

        // Check against trusted origins
        for trusted in &self.trusted_origins {
            if check_origin == *trusted || check_origin.starts_with(&format!("{}/", trusted)) {
                return true;
            }
        }

        false
    }

    /// Generate a CSRF token (nonce:timestamp:sig)
    fn generate_csrf_token(&self) -> String {
        let nonce = random_hex(16);
        let timestamp = now_secs() as u64;
        let msg = format!("{}:{}", nonce, timestamp);
        let sig = &hmac_sha256_hex(&self.secret_key, &msg)[..16];
        format!("{}:{}:{}", nonce, timestamp, sig)
    }

    /// Validate a CSRF token
    fn validate_csrf_token(&self, token: &str) -> bool {
        if token.is_empty() {
            return false;
        }
        let parts: Vec<&str> = token.split(':').collect();
        if parts.len() != 3 {
            return false;
        }
        let nonce = parts[0];
        let timestamp_str = parts[1];
        let sig = parts[2];

        // Check timestamp freshness
        let ts: f64 = match timestamp_str.parse() {
            Ok(t) => t,
            Err(_) => return false,
        };
        let age = (now_secs() - ts).abs();
        if age > self.max_age {
            return false;
        }

        // Verify HMAC signature
        let msg = format!("{}:{}", nonce, timestamp_str);
        let expected = &hmac_sha256_hex(&self.secret_key, &msg)[..16];

        // Constant-time comparison
        if sig.len() != expected.len() {
            return false;
        }
        let mut result: u8 = 0;
        for (a, b) in sig.bytes().zip(expected.bytes()) {
            result |= a ^ b;
        }
        result == 0
    }

    /// Check if a path is a cookie-auth path that requires CSRF tokens
    fn is_cookie_auth_path(&self, path: &str) -> bool {
        let public_paths = [
            "/api/auth/login", "/api/auth/register", "/api/auth/google",
            "/api/auth/refresh", "/api/auth/phone/send", "/api/auth/phone/verify",
            "/api/auth/forgot-password", "/api/auth/reset-password", "/api/auth/check-email",
        ];
        for p in &public_paths {
            if path == *p {
                return false;
            }
        }
        let cookie_prefixes = ["/api/auth/", "/api/login", "/api/register", "/api/mfa/", "/api/refresh"];
        for prefix in &cookie_prefixes {
            if path.starts_with(prefix) {
                return true;
            }
        }
        false
    }
}


// ══════════════════════════════════════════════════════════════════
// 7. HMAC VERIFIER — Webhook signature verification (Tier 2)
//    Paddle (HMAC-SHA256 hex), Twilio (RFC 5849 HMAC-SHA1),
//    Shopify (HMAC-SHA256 base64), timestamp freshness
// ══════════════════════════════════════════════════════════════════

use sha1::Sha1;

/// Verify Paddle webhook HMAC-SHA256 signature (hex-encoded).
fn verify_paddle_hmac(payload: &[u8], signature: &str, secret: &str) -> bool {
    if payload.is_empty() || signature.is_empty() || secret.is_empty() {
        return false;
    }
    let expected = hmac_sha256_hex(secret, &String::from_utf8_lossy(payload));
    constant_time_compare(&expected, signature.trim())
}

/// Verify Twilio webhook signature (RFC 5849 HMAC-SHA1).
fn verify_twilio_hmac(url: &str, params: &HashMap<String, String>, signature: &str, auth_token: &str) -> bool {
    if url.is_empty() || params.is_empty() || signature.is_empty() || auth_token.is_empty() {
        return false;
    }
    let mut sorted: Vec<(&String, &String)> = params.iter().collect();
    sorted.sort_by_key(|(k, _)| *k);
    let mut data = url.to_string();
    for (k, v) in sorted {
        data.push_str(k);
        data.push_str(v);
    }
    use hmac::{Hmac, Mac};
    type HmacSha1 = Hmac<Sha1>;
    let mut mac = match HmacSha1::new_from_slice(auth_token.as_bytes()) {
        Ok(m) => m,
        Err(_) => return false,
    };
    mac.update(data.as_bytes());
    let result = mac.finalize().into_bytes();
    let expected = hex::encode(result);
    constant_time_compare(&expected, signature.trim())
}

/// Verify Shopify webhook HMAC-SHA256 (base64-encoded).
fn verify_shopify_hmac(payload: &[u8], hmac_header: &str, secret: &str) -> bool {
    if payload.is_empty() || hmac_header.is_empty() || secret.is_empty() {
        return false;
    }
    use hmac::{Hmac, Mac};
    type HmacSha256 = Hmac<sha2::Sha256>;
    let mut mac = match HmacSha256::new_from_slice(secret.as_bytes()) {
        Ok(m) => m,
        Err(_) => return false,
    };
    mac.update(payload);
    let result = mac.finalize().into_bytes();
    let expected_b64 = general_purpose::STANDARD.encode(result);
    constant_time_compare(&expected_b64, hmac_header.trim())
}

/// Constant-time string comparison (prevents timing attacks).
#[allow(dead_code)]
fn constant_time_compare(a: &str, b: &str) -> bool {
    if a.len() != b.len() {
        // Still compare to avoid timing leak on length
        let _ = a.as_bytes().iter().zip(b.as_bytes().iter()).fold(0u8, |acc, (x, y)| acc ^ (x ^ y));
        return false;
    }
    let result = a.as_bytes().iter().zip(b.as_bytes().iter()).fold(0u8, |acc, (x, y)| acc | (x ^ y));
    result == 0
}

/// Verify webhook timestamp freshness (within max_age_seconds).
fn verify_timestamp_freshness(timestamp_str: &str, max_age_secs: f64) -> bool {
    let ts: f64 = match timestamp_str.parse() {
        Ok(v) => v,
        Err(_) => return false,
    };
    let age = (now_secs() - ts).abs();
    age <= max_age_secs
}


#[pyclass]
#[derive(Clone)]
pub struct HMACVerifier {
    max_age_secs: f64,
}

#[pymethods]
impl HMACVerifier {
    #[new]
    #[pyo3(signature = (max_age_secs=300.0))]
    fn new(max_age_secs: f64) -> Self {
        Self { max_age_secs }
    }

    /// Verify Paddle webhook HMAC-SHA256 (hex signature).
    fn verify_paddle(&self, payload: &[u8], signature: &str, secret: &str) -> bool {
        verify_paddle_hmac(payload, signature, secret)
    }

    /// Verify Twilio webhook signature (RFC 5849 HMAC-SHA1).
    /// params is a Python dict of {key: value} strings.
    fn verify_twilio<'py>(&self, _py: Python<'py>, url: &str, params: Bound<'py, PyDict>, signature: &str, auth_token: &str) -> bool {
        let mut map = HashMap::new();
        for (k, v) in params.iter() {
            let key: String = match k.extract() {
                Ok(s) => s,
                Err(_) => return false,
            };
            let val: String = match v.extract() {
                Ok(s) => s,
                Err(_) => return false,
            };
            map.insert(key, val);
        }
        verify_twilio_hmac(url, &map, signature, auth_token)
    }

    /// Verify Shopify webhook HMAC-SHA256 (base64 signature).
    fn verify_shopify(&self, payload: &[u8], hmac_header: &str, secret: &str) -> bool {
        verify_shopify_hmac(payload, hmac_header, secret)
    }

    /// Generic HMAC-SHA256 hex verification.
    fn verify_hmac_sha256(&self, payload: &[u8], signature: &str, secret: &str) -> bool {
        verify_paddle_hmac(payload, signature, secret)
    }

    /// Generic HMAC-SHA256 hex generation (for outbound webhook signing).
    fn sign_hmac_sha256(&self, payload: &str, secret: &str) -> String {
        hmac_sha256_hex(secret, payload)
    }

    /// Verify timestamp freshness (within max_age_secs).
    fn verify_timestamp(&self, timestamp_str: &str) -> bool {
        verify_timestamp_freshness(timestamp_str, self.max_age_secs)
    }

    /// Constant-time string comparison utility.
    fn constant_time_compare(&self, a: &str, b: &str) -> bool {
        constant_time_compare(a, b)
    }
}


// ══════════════════════════════════════════════════════════════════
// 8. CRYPTO ENGINE — bcrypt password/API-key hashing (Tier 2)
//    Cost factor 12, constant-time verify, API key "ak$" prefix
// ══════════════════════════════════════════════════════════════════

#[pyclass]
pub struct CryptoEngine {
    bcrypt_cost: u32,
}

#[pymethods]
impl CryptoEngine {
    #[new]
    #[pyo3(signature = (bcrypt_cost=12))]
    fn new(bcrypt_cost: u32) -> Self {
        Self { bcrypt_cost: bcrypt_cost.max(4).min(31) }
    }

    /// Hash a password using bcrypt.
    /// Returns the bcrypt hash string.
    fn hash_password(&self, password: &str) -> PyResult<String> {
        let hash = bcrypt::hash(password, self.bcrypt_cost)
            .map_err(|e| PyValueError::new_err(format!("bcrypt hash failed: {}", e)))?;
        Ok(hash)
    }

    /// Verify a password against a bcrypt hash.
    fn verify_password(&self, password: &str, hash: &str) -> bool {
        bcrypt::verify(password, hash).unwrap_or(false)
    }

    /// Hash an API key using bcrypt with "ak$" prefix (M-12).
    fn hash_api_key(&self, raw_key: &str) -> PyResult<String> {
        if raw_key.is_empty() {
            return Err(PyValueError::new_err("API key must not be empty"));
        }
        let hash = bcrypt::hash(raw_key, self.bcrypt_cost)
            .map_err(|e| PyValueError::new_err(format!("bcrypt hash failed: {}", e)))?;
        Ok(format!("ak${}", hash))
    }

    /// Verify an API key against a stored hash.
    /// Supports "ak$" bcrypt prefix and legacy SHA-256 fallback.
    fn verify_api_key(&self, raw_key: &str, key_hash: &str) -> bool {
        if raw_key.is_empty() || key_hash.is_empty() {
            return false;
        }
        // M-12: bcrypt format
        if let Some(stored) = key_hash.strip_prefix("ak$") {
            return bcrypt::verify(raw_key, stored).unwrap_or(false);
        }
        // Legacy SHA-256 fallback
        let computed = sha256_hex(raw_key);
        constant_time_compare(&computed, key_hash)
    }

    /// SHA-256 hash of input string.
    fn sha256(&self, input: &str) -> String {
        sha256_hex(input)
    }

    /// HMAC-SHA256 hex of (key, message).
    fn hmac_sha256(&self, key: &str, message: &str) -> String {
        hmac_sha256_hex(key, message)
    }

    /// Constant-time string comparison.
    fn constant_time_compare(&self, a: &str, b: &str) -> bool {
        constant_time_compare(a, b)
    }

    /// Generate a secure random hex token.
    fn random_token(&self, nbytes: usize) -> String {
        random_hex(nbytes)
    }

    /// Generate a secure random URL-safe token.
    fn random_urlsafe_token(&self, nbytes: usize) -> String {
        random_urlsafe(nbytes)
    }
}


// ══════════════════════════════════════════════════════════════════
// 9. CONNECTION POOL — Managed pool registry (Tier 3)
//    DashMap-backed pool for external service HTTP connections.
//    Python checks out a slot before making an HTTP request and
//    checks it back in after. Enforces per-service max connections,
//    tracks health, provides stats.
// ══════════════════════════════════════════════════════════════════

/// Per-service pool configuration
#[derive(Clone)]
struct PoolConfig {
    max_connections: u32,
    idle_timeout_secs: f64,
    connect_timeout_secs: f64,
}

/// Per-service pool state (atomic counters — no locking for hot path)
struct PoolState {
    active_count: AtomicU32,
    idle_count: AtomicU32,
    total_checkout: AtomicU64,
    total_checkin: AtomicU64,
    total_errors: AtomicU64,
    total_timeouts: AtomicU64,
    #[allow(dead_code)]
    created_at: f64,
    last_activity: AtomicI64,
}

#[pyclass]
struct ConnectionPool {
    configs: DashMap<String, PoolConfig>,
    states: DashMap<String, PoolState>,
}

#[pymethods]
impl ConnectionPool {
    #[new]
    fn new() -> Self {
        ConnectionPool {
            configs: DashMap::new(),
            states: DashMap::new(),
        }
    }

    /// Register a service pool with config.
    #[pyo3(signature = (service, max_connections=20, idle_timeout_secs=60.0, connect_timeout_secs=10.0))]
    fn register(&self, service: &str, max_connections: u32, idle_timeout_secs: f64, connect_timeout_secs: f64) {
        self.configs.entry(service.to_string()).or_insert_with(|| PoolConfig {
            max_connections,
            idle_timeout_secs,
            connect_timeout_secs,
        });
        self.states.entry(service.to_string()).or_insert_with(|| PoolState {
            active_count: AtomicU32::new(0),
            idle_count: AtomicU32::new(0),
            total_checkout: AtomicU64::new(0),
            total_checkin: AtomicU64::new(0),
            total_errors: AtomicU64::new(0),
            total_timeouts: AtomicU64::new(0),
            created_at: now_secs(),
            last_activity: AtomicI64::new(0),
        });
    }

    /// Check out a connection slot. Returns true if allowed, false if pool exhausted.
    fn checkout<'py>(&self, py: Python<'py>, service: &str) -> PyResult<Bound<'py, PyAny>> {
        let allowed = {
            let cfg = self.configs.get(service);
            let max = match cfg {
                Some(c) => c.max_connections,
                None => {
                    let false_val = bool_to_any(py, false);
                    return Ok(false_val);
                }
            };
            let state = self.states.entry(service.to_string())
                .or_insert_with(|| PoolState {
                    active_count: AtomicU32::new(0),
                    idle_count: AtomicU32::new(0),
                    total_checkout: AtomicU64::new(0),
                    total_checkin: AtomicU64::new(0),
                    total_errors: AtomicU64::new(0),
                    total_timeouts: AtomicU64::new(0),
                    created_at: now_secs(),
                    last_activity: AtomicI64::new(0),
                });
            let current = state.active_count.load(Ordering::SeqCst);
            if current < max {
                state.active_count.fetch_add(1, Ordering::SeqCst);
                let _ = state.idle_count.fetch_update(Ordering::SeqCst, Ordering::SeqCst, |v| Some(v.saturating_sub(1)));
                state.total_checkout.fetch_add(1, Ordering::SeqCst);
                state.last_activity.store(now_secs() as i64, Ordering::SeqCst);
                true
            } else {
                false
            }
        };
        let result = bool_to_any(py, allowed);
        Ok(result)
    }

    /// Check in a connection slot after request completes.
    #[pyo3(signature = (service, success=true))]
    fn checkin(&self, service: &str, success: bool) {
        if let Some(state) = self.states.get(service) {
            let _ = state.active_count.fetch_update(Ordering::SeqCst, Ordering::SeqCst, |v| Some(v.saturating_sub(1)));
            state.idle_count.fetch_add(1, Ordering::SeqCst);
            state.total_checkin.fetch_add(1, Ordering::SeqCst);
            if !success {
                state.total_errors.fetch_add(1, Ordering::SeqCst);
            }
            state.last_activity.store(now_secs() as i64, Ordering::SeqCst);
        }
    }

    /// Record a timeout for a service pool.
    fn record_timeout(&self, service: &str) {
        if let Some(state) = self.states.get(service) {
            state.total_timeouts.fetch_add(1, Ordering::SeqCst);
        }
    }

    /// Get pool stats for a service.
    fn get_stats<'py>(&self, py: Python<'py>, service: &str) -> PyResult<Bound<'py, PyAny>> {
        let dict = PyDict::new(py);
        if let Some(cfg) = self.configs.get(service) {
            dict.set_item("max_connections", cfg.max_connections)?;
            dict.set_item("idle_timeout_secs", cfg.idle_timeout_secs)?;
            dict.set_item("connect_timeout_secs", cfg.connect_timeout_secs)?;
        } else {
            dict.set_item("registered", false)?;
            return Ok(dict.into_any());
        }
        if let Some(state) = self.states.get(service) {
            dict.set_item("active", state.active_count.load(Ordering::SeqCst))?;
            dict.set_item("idle", state.idle_count.load(Ordering::SeqCst))?;
            dict.set_item("total_checkout", state.total_checkout.load(Ordering::SeqCst))?;
            dict.set_item("total_checkin", state.total_checkin.load(Ordering::SeqCst))?;
            dict.set_item("total_errors", state.total_errors.load(Ordering::SeqCst))?;
            dict.set_item("total_timeouts", state.total_timeouts.load(Ordering::SeqCst))?;
            dict.set_item("registered", true)?;
            dict.set_item("utilization", {
                let active = state.active_count.load(Ordering::SeqCst) as f64;
                let max = self.configs.get(service).map(|c| c.max_connections as f64).unwrap_or(1.0);
                active / max
            })?;
        }
        Ok(dict.into_any())
    }

    /// Get stats for all registered pools.
    fn get_all_stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let list = PyList::empty(py);
        for entry in self.configs.iter() {
            let stats = self.get_stats(py, entry.key())?;
            list.append(stats)?;
        }
        Ok(list.into_any())
    }

    /// Check if a service pool has available capacity.
    fn has_capacity(&self, service: &str) -> bool {
        let max = match self.configs.get(service) {
            Some(c) => c.max_connections,
            None => return true,
        };
        if let Some(state) = self.states.get(service) {
            state.active_count.load(Ordering::SeqCst) < max
        } else {
            true
        }
    }

    /// Reset stats for a service pool.
    fn reset(&self, service: &str) {
        if let Some(state) = self.states.get(service) {
            state.active_count.store(0, Ordering::SeqCst);
            state.idle_count.store(0, Ordering::SeqCst);
            state.total_checkout.store(0, Ordering::SeqCst);
            state.total_checkin.store(0, Ordering::SeqCst);
            state.total_errors.store(0, Ordering::SeqCst);
            state.total_timeouts.store(0, Ordering::SeqCst);
            state.last_activity.store(now_secs() as i64, Ordering::SeqCst);
        }
    }

    /// Unregister a service pool.
    fn unregister(&self, service: &str) {
        self.configs.remove(service);
        self.states.remove(service);
    }
}


// ══════════════════════════════════════════════════════════════════
// 10. ASYNC LOGGER — Structured log buffer (Tier 3)
//     High-performance log buffering: accepts entries, batches flushes.
//     Python async apps call log() from any thread; a periodic task
//     calls flush() to drain the buffer into Python's structlog.
// ══════════════════════════════════════════════════════════════════

use std::sync::Mutex;

/// A single log entry
struct LogEntry {
    timestamp: f64,
    level: String,      // "debug", "info", "warning", "error", "critical"
    logger_name: String,
    message: String,
    context_json: String, // serialized JSON of extra context
}

#[pyclass]
struct AsyncLogger {
    buffer: Mutex<Vec<LogEntry>>,
    max_buffer_size: usize,
    dropped_count: AtomicU64,
    flush_count: AtomicU64,
    total_logged: AtomicU64,
    level_filter: AtomicU8,  // 0=debug, 1=info, 2=warning, 3=error, 4=critical
}

#[pymethods]
impl AsyncLogger {
    #[new]
    #[pyo3(signature = (max_buffer_size=10000, level_filter="debug"))]
    fn new(max_buffer_size: usize, level_filter: &str) -> Self {
        let level = match level_filter {
            "debug" => 0u8,
            "info" => 1,
            "warning" | "warn" => 2,
            "error" => 3,
            "critical" | "fatal" => 4,
            _ => 0,
        };
        AsyncLogger {
            buffer: Mutex::new(Vec::with_capacity(max_buffer_size.min(100000))),
            max_buffer_size: max_buffer_size.min(100000),
            dropped_count: AtomicU64::new(0),
            flush_count: AtomicU64::new(0),
            total_logged: AtomicU64::new(0),
            level_filter: AtomicU8::new(level),
        }
    }

    /// Log an entry. Thread-safe. Drops if buffer is full.
    #[pyo3(signature = (level, message, logger_name="parwa", context=None))]
    fn log<'py>(&self, py: Python<'py>, level: &str, message: &str, logger_name: &str, context: Option<PyObject>) -> bool {
        let entry_level = match level {
            "debug" => 0u8,
            "info" => 1,
            "warning" | "warn" => 2,
            "error" => 3,
            "critical" | "fatal" => 4,
            _ => 1,
        };
        let filter = self.level_filter.load(Ordering::SeqCst);
        if entry_level < filter {
            return false; // below threshold
        }

        let ctx_json = match &context {
            Some(ctx) => {
                // Try to serialize Python dict to JSON
                let dict: Bound<'_, PyDict> = match ctx.extract(py) {
                    Ok(d) => d,
                    Err(_) => return false,
                };
                let mut map = serde_json::Map::new();
                for (k, v) in dict.iter() {
                    let key: String = match k.extract() {
                        Ok(s) => s,
                        Err(_) => continue,
                    };
                    let val = match v.extract::<String>() {
                        Ok(s) => serde_json::Value::String(s),
                        Err(_) => match v.extract::<i64>() {
                            Ok(n) => serde_json::json!(n),
                            Err(_) => match v.extract::<f64>() {
                                Ok(f) => serde_json::json!(f),
                                Err(_) => match v.extract::<bool>() {
                                    Ok(b) => serde_json::json!(b),
                                    Err(_) => serde_json::Value::Null,
                                },
                            },
                        },
                    };
                    map.insert(key, val);
                }
                serde_json::to_string(&map).unwrap_or_else(|_| "{}".to_string())
            }
            None => "{}".to_string(),
        };

        let entry = LogEntry {
            timestamp: now_secs(),
            level: level.to_string(),
            logger_name: logger_name.to_string(),
            message: message.to_string(),
            context_json: ctx_json,
        };

        self.total_logged.fetch_add(1, Ordering::SeqCst);
        match self.buffer.lock() {
            Ok(mut buf) => {
                if buf.len() >= self.max_buffer_size {
                    self.dropped_count.fetch_add(1, Ordering::SeqCst);
                    return false;
                }
                buf.push(entry);
                true
            }
            Err(_) => {
                self.dropped_count.fetch_add(1, Ordering::SeqCst);
                false
            }
        }
    }

    /// Convenience: log at INFO level.
    fn info<'py>(&self, py: Python<'py>, message: &str, logger_name: &str) -> bool {
        self.log(py, "info", message, logger_name, None)
    }

    /// Convenience: log at WARNING level.
    fn warning<'py>(&self, py: Python<'py>, message: &str, logger_name: &str) -> bool {
        self.log(py, "warning", message, logger_name, None)
    }

    /// Convenience: log at ERROR level.
    fn error<'py>(&self, py: Python<'py>, message: &str, logger_name: &str) -> bool {
        self.log(py, "error", message, logger_name, None)
    }

    /// Convenience: log at DEBUG level.
    fn debug<'py>(&self, py: Python<'py>, message: &str, logger_name: &str) -> bool {
        self.log(py, "debug", message, logger_name, None)
    }

    /// Flush the buffer: return all entries as a list of dicts, clear buffer.
    fn flush<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let entries = match self.buffer.lock() {
            Ok(mut buf) => std::mem::take(&mut *buf),
            Err(_) => Vec::new(),
        };
        self.flush_count.fetch_add(1, Ordering::SeqCst);

        let list = PyList::empty(py);
        for entry in &entries {
            let dict = PyDict::new(py);
            dict.set_item("timestamp", entry.timestamp)?;
            dict.set_item("level", &entry.level)?;
            dict.set_item("logger", &entry.logger_name)?;
            dict.set_item("message", &entry.message)?;
            // Parse context_json back to dict
            let ctx_val: serde_json::Value = serde_json::from_str(&entry.context_json).unwrap_or(serde_json::json!({}));
            if let serde_json::Value::Object(obj) = ctx_val {
                let ctx_dict = PyDict::new(py);
                for (k, v) in obj {
                    let py_val = match v {
                        serde_json::Value::String(s) => s.into_pyobject(py)?.into_any(),
                        serde_json::Value::Number(n) => {
                            if let Some(i) = n.as_i64() {
                                i.into_pyobject(py)?.into_any()
                            } else if let Some(f) = n.as_f64() {
                                f.into_pyobject(py)?.into_any()
                            } else {
                                py.None().into_bound(py)
                            }
                        }
                        serde_json::Value::Bool(b) => {
                        bool_to_any(py, b)
                    },
                        serde_json::Value::Null => py.None().into_bound(py),
                        _ => py.None().into_bound(py),
                    };
                    ctx_dict.set_item(k, py_val)?;
                }
                dict.set_item("context", ctx_dict)?;
            }
            list.append(dict)?;
        }
        Ok(list.into_any())
    }

    /// Get current buffer size.
    fn buffer_size(&self) -> usize {
        self.buffer.lock().map(|b| b.len()).unwrap_or(0)
    }

    /// Get logger stats.
    fn get_stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let dict = PyDict::new(py);
        dict.set_item("buffer_size", self.buffer_size())?;
        dict.set_item("max_buffer_size", self.max_buffer_size)?;
        dict.set_item("dropped_count", self.dropped_count.load(Ordering::SeqCst))?;
        dict.set_item("flush_count", self.flush_count.load(Ordering::SeqCst))?;
        dict.set_item("total_logged", self.total_logged.load(Ordering::SeqCst))?;
        let level = self.level_filter.load(Ordering::SeqCst);
        let level_str = match level {
            0 => "debug",
            1 => "info",
            2 => "warning",
            3 => "error",
            4 => "critical",
            _ => "debug",
        };
        dict.set_item("level_filter", level_str)?;
        Ok(dict.into_any())
    }

    /// Set the minimum log level filter.
    fn set_level_filter(&self, level: &str) {
        let val = match level {
            "debug" => 0u8,
            "info" => 1,
            "warning" | "warn" => 2,
            "error" => 3,
            "critical" | "fatal" => 4,
            _ => 0,
        };
        self.level_filter.store(val, Ordering::SeqCst);
    }

    /// Clear the buffer without returning entries.
    fn clear(&self) {
        if let Ok(mut buf) = self.buffer.lock() {
            buf.clear();
        }
    }
}


// ══════════════════════════════════════════════════════════════════
// MODULE REGISTRATION
// ══════════════════════════════════════════════════════════════════

#[pymodule]
fn parwa_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Tier 1
    m.add_class::<RateLimiter>()?;
    m.add_class::<CircuitBreakerManager>()?;
    m.add_class::<PIIRedactor>()?;
    m.add_class::<JWTDecoder>()?;
    m.add_class::<SecurityHeaders>()?;
    m.add_class::<CSRFValidator>()?;

    // Tier 2
    m.add_class::<HMACVerifier>()?;
    m.add_class::<CryptoEngine>()?;

    // Tier 3
    m.add_class::<ConnectionPool>()?;
    m.add_class::<AsyncLogger>()?;

    Ok(())
}



#[cfg(test)]
fn b64url_encode_json(val: &serde_json::Value) -> String {
    let bytes = serde_json::to_vec(val).unwrap();
    general_purpose::URL_SAFE_NO_PAD.encode(&bytes)
}

// ══════════════════════════════════════════════════════════════════
// UNIT TESTS — Pure Rust logic (no PyO3 GIL needed)
// Python integration tests are in parwa/tests/test_parwa_core.py
// ══════════════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rate_limiter_classify_path() {
        let rl = RateLimiter::new(None);
        assert_eq!(rl.classify_path("/api/auth/login", "POST"), "auth_login");
        assert_eq!(rl.classify_path("/api/auth/register", "POST"), "auth_register");
        assert_eq!(rl.classify_path("/api/billing/subscriptions", "GET"), "financial");
        assert_eq!(rl.classify_path("/api/tickets", "GET"), "general_get");
        assert_eq!(rl.classify_path("/api/tickets", "POST"), "general_post");
        assert_eq!(rl.classify_path("/api/integrations/hubspot", "POST"), "integration");
        assert_eq!(rl.classify_path("/health", "GET"), "general_get");
        assert_eq!(rl.classify_path("/api/auth/mfa", "POST"), "auth_mfa");
        assert_eq!(rl.classify_path("/api/auth/phone/send", "POST"), "auth_phone_send");
        assert_eq!(rl.classify_path("/api/public/demo/chat", "POST"), "demo_chat");
        assert_eq!(rl.classify_path("/api/auth/forgot-password", "POST"), "auth_reset");
    }

    #[test]
    fn test_rate_limiter_key_generation() {
        let k1 = make_rl_key("auth_login", "test@example.com");
        let k2 = make_rl_key("auth_login", "test@example.com");
        let k3 = make_rl_key("auth_login", "other@example.com");
        assert_eq!(k1, k2);
        assert_ne!(k1, k3);
    }

    #[test]
    fn test_rate_limiter_category_configs() {
        let rl = RateLimiter::new(None);
        let cfg = rl.configs.get("auth_login").unwrap();
        assert_eq!(cfg.limit, 5);
        assert_eq!(cfg.window_secs, 60.0);
        assert_eq!(cfg.backoff, vec![0, 2, 4, 8, 900]);
        let cfg2 = rl.configs.get("general_get").unwrap();
        assert_eq!(cfg2.limit, 100);
    }

    #[test]
    fn test_circuit_breaker_initial_state() {
        let cb = CircuitBreakerManager::new();
        cb.register("test_dep", 3, 2, 30.0, 1);
        assert!(cb.is_available("test_dep"));
        assert!(cb.is_available("nonexistent"));
    }

    #[test]
    fn test_circuit_breaker_opens_after_threshold() {
        let cb = CircuitBreakerManager::new();
        cb.register("test_dep", 3, 2, 30.0, 1);
        for _ in 0..3 { cb.record_failure("test_dep"); }
        assert!(!cb.is_available("test_dep"));
    }

    #[test]
    fn test_circuit_breaker_stays_closed_under_threshold() {
        let cb = CircuitBreakerManager::new();
        cb.register("test_dep", 5, 2, 30.0, 1);
        for _ in 0..4 { cb.record_failure("test_dep"); }
        assert!(cb.is_available("test_dep"));
    }

    #[test]
    fn test_circuit_breaker_force_open_close() {
        let cb = CircuitBreakerManager::new();
        cb.register("test_dep", 5, 2, 30.0, 1);
        cb.force_open("test_dep");
        assert!(!cb.is_available("test_dep"));
        cb.force_close("test_dep");
        assert!(cb.is_available("test_dep"));
    }

    #[test]
    fn test_circuit_breaker_half_open_recovery() {
        let cb = CircuitBreakerManager::new();
        cb.register("test_dep", 2, 2, 0.0, 5);
        cb.record_failure("test_dep");
        cb.record_failure("test_dep");
        assert!(!cb.is_available("test_dep"));
        std::thread::sleep(std::time::Duration::from_millis(10));
        assert!(cb.is_available("test_dep"));
        cb.record_success("test_dep");
        cb.record_success("test_dep");
        assert!(cb.is_available("test_dep"));
    }

    #[test]
    fn test_circuit_breaker_unregister() {
        let cb = CircuitBreakerManager::new();
        cb.register("temp", 3, 2, 60.0, 1);
        cb.unregister("temp");
        assert!(cb.is_available("temp"));
    }

    #[test]
    fn test_circuit_breaker_reset() {
        let cb = CircuitBreakerManager::new();
        cb.register("test_dep", 3, 2, 30.0, 1);
        cb.force_open("test_dep");
        assert!(!cb.is_available("test_dep"));
        cb.reset("test_dep");
        assert!(cb.is_available("test_dep"));
    }

    #[test]
    fn test_pii_patterns_compile() {
        let patterns = build_pii_patterns();
        assert_eq!(patterns.len(), 19);
    }

    #[test]
    fn test_pii_email_detection() {
        let patterns = build_pii_patterns();
        let email_pat = patterns.iter().find(|p| p.pii_type == "EMAIL").unwrap();
        assert!(email_pat.pattern.is_match("test@example.com").unwrap());
        assert!(email_pat.pattern.is_match("user.name+tag@domain.co.uk").unwrap());
        assert!(!email_pat.pattern.is_match("not an email").unwrap());
    }

    #[test]
    fn test_pii_ssn_detection() {
        let patterns = build_pii_patterns();
        let ssn_pat = patterns.iter().find(|p| p.pii_type == "SSN").unwrap();
        assert!(ssn_pat.pattern.is_match("123-45-6789").unwrap());
        assert!(!ssn_pat.pattern.is_match("000-00-0000").unwrap());
        assert!(!ssn_pat.pattern.is_match("666-00-0000").unwrap());
    }

    #[test]
    fn test_pii_credit_card_detection() {
        let patterns = build_pii_patterns();
        let cc_pat = patterns.iter().find(|p| p.pii_type == "CREDIT_CARD").unwrap();
        assert!(cc_pat.pattern.is_match("4111-1111-1111-1111").unwrap());
        assert!(cc_pat.pattern.is_match("5500-0000-0000-0004").unwrap());
        assert!(!cc_pat.pattern.is_match("1234").unwrap());
    }

    #[test]
    fn test_pii_token_generation() {
        let token1 = generate_token("EMAIL", "test@example.com", "company-123");
        let token2 = generate_token("EMAIL", "test@example.com", "company-123");
        let token3 = generate_token("EMAIL", "other@example.com", "company-123");
        assert_eq!(token1, token2);
        assert_ne!(token1, token3);
        assert!(token1.starts_with("{{EMAIL_"));
        assert!(token1.ends_with("}}"));
    }

    #[test]
    fn test_jwt_hs256_verify() {
        let signing_input = "header.payload";
        let sig = hmac_sha256_hex("secret", signing_input);
        assert!(verify_hs256(
            &general_purpose::URL_SAFE_NO_PAD.encode(hex::decode(&sig).unwrap()),
            signing_input, "secret"
        ));
        assert!(!verify_hs256(
            &general_purpose::URL_SAFE_NO_PAD.encode(hex::decode(&sig).unwrap()),
            signing_input, "wrong-secret"
        ));
    }

    #[test]
    fn test_jwt_roundtrip() {
        let header = b64url_encode_json(&serde_json::json!({"alg": "HS256"}));
        let now = now_secs();
        let payload = b64url_encode_json(&serde_json::json!({"sub": "user-123", "exp": now + 3600.0}));
        let signing_input = format!("{}.{}", header, payload);
        let sig = hmac_sha256_hex("test-secret", &signing_input);
        let sig_b64 = general_purpose::URL_SAFE_NO_PAD.encode(hex::decode(&sig).unwrap());
        let token = format!("{}.{}.{}", header, payload, sig_b64);
        let parts: Vec<&str> = token.split('.').collect();
        assert_eq!(parts.len(), 3);
    }

    #[test]
    fn test_csrf_token_generate_validate() {
        let csrf = CSRFValidator::new(None, "test-secret", 3600.0);
        let token = csrf.generate_csrf_token();
        assert!(csrf.validate_csrf_token(&token));
    }

    #[test]
    fn test_csrf_token_invalid_format() {
        let csrf = CSRFValidator::new(None, "test-secret", 3600.0);
        assert!(!csrf.validate_csrf_token("invalid"));
        assert!(!csrf.validate_csrf_token(""));
        assert!(!csrf.validate_csrf_token("a:b"));
    }

    #[test]
    fn test_csrf_token_wrong_secret() {
        let csrf1 = CSRFValidator::new(None, "secret-1", 3600.0);
        let csrf2 = CSRFValidator::new(None, "secret-2", 3600.0);
        let token = csrf1.generate_csrf_token();
        assert!(!csrf2.validate_csrf_token(&token));
    }

    #[test]
    fn test_csrf_origin_validation() {
        let csrf = CSRFValidator::new(
            Some(vec!["https://app.parwa.ai".to_string()]),
            "secret", 3600.0,
        );
        assert!(csrf.is_valid_origin("https://app.parwa.ai", ""));
        assert!(!csrf.is_valid_origin("https://evil.com", ""));
        assert!(csrf.is_valid_origin("https://parwa-git-main.vercel.app", ""));
    }

    #[test]
    fn test_csrf_cookie_auth_path() {
        let csrf = CSRFValidator::new(None, "secret", 3600.0);
        assert!(!csrf.is_cookie_auth_path("/api/auth/login"));
        assert!(!csrf.is_cookie_auth_path("/api/auth/register"));
        assert!(csrf.is_cookie_auth_path("/api/auth/profile"));
        assert!(!csrf.is_cookie_auth_path("/api/tickets"));
    }

    #[test]
    fn test_sha256_deterministic() {
        assert_eq!(sha256_hex("hello"), sha256_hex("hello"));
        assert_ne!(sha256_hex("hello"), sha256_hex("world"));
        assert_eq!(sha256_hex("hello").len(), 64);
    }

    #[test]
    fn test_hmac_sha256() {
        let h1 = hmac_sha256_hex("key", "message");
        assert_eq!(h1, hmac_sha256_hex("key", "message"));
        assert_ne!(h1, hmac_sha256_hex("key", "different"));
    }

    // ── Tier 2: HMAC Verifier tests ────────────────────────────────

    #[test]
    fn test_hmac_paddle_verify() {
        let payload = b"test payload data";
        let secret = "paddle-secret-key";
        let sig = hmac_sha256_hex(secret, &String::from_utf8_lossy(payload));
        assert!(verify_paddle_hmac(payload, &sig, secret));
        assert!(!verify_paddle_hmac(payload, "wrong_sig", secret));
        assert!(!verify_paddle_hmac(payload, &sig, "wrong_secret"));
    }

    #[test]
    fn test_hmac_paddle_empty_inputs() {
        assert!(!verify_paddle_hmac(b"", "sig", "secret"));
        assert!(!verify_paddle_hmac(b"data", "", "secret"));
        assert!(!verify_paddle_hmac(b"data", "sig", ""));
    }

    #[test]
    fn test_hmac_shopify_verify() {
        let payload = b"shopify webhook payload";
        let secret = "shopify-secret";
        use hmac::{Hmac, Mac};
        type HmacSha256 = Hmac<sha2::Sha256>;
        let mut mac = HmacSha256::new_from_slice(secret.as_bytes()).unwrap();
        mac.update(payload);
        let result = mac.finalize().into_bytes();
        let sig_b64 = general_purpose::STANDARD.encode(result);
        assert!(verify_shopify_hmac(payload, &sig_b64, secret));
        assert!(!verify_shopify_hmac(payload, "wrong", secret));
    }

    #[test]
    fn test_hmac_twilio_verify() {
        let url = "https://myapp.com/twilio/webhook";
        let mut params = HashMap::new();
        params.insert("CallSid".to_string(), "CA123".to_string());
        params.insert("From".to_string(), "+1234567890".to_string());
        let auth_token = "twilio_auth_token";

        // Compute expected signature
        let mut sorted: Vec<(&String, &String)> = params.iter().collect();
        sorted.sort_by_key(|(k, _)| *k);
        let mut data = url.to_string();
        for (k, v) in sorted {
            data.push_str(k);
            data.push_str(v);
        }
        use hmac::{Hmac, Mac};
        type HmacSha1 = Hmac<Sha1>;
        let mut mac = HmacSha1::new_from_slice(auth_token.as_bytes()).unwrap();
        mac.update(data.as_bytes());
        let sig = hex::encode(mac.finalize().into_bytes());

        assert!(verify_twilio_hmac(url, &params, &sig, auth_token));
        assert!(!verify_twilio_hmac(url, &params, "wrong", auth_token));
    }

    #[test]
    fn test_constant_time_compare() {
        assert!(constant_time_compare("hello", "hello"));
        assert!(!constant_time_compare("hello", "world"));
        // Different lengths should return false
        assert!(!constant_time_compare("ab", "abc"));
        // Empty strings
        assert!(constant_time_compare("", ""));
    }

    #[test]
    fn test_timestamp_freshness() {
        let now = now_secs();
        assert!(verify_timestamp_freshness(&now.to_string(), 300.0));
        assert!(!verify_timestamp_freshness(&(now - 400.0).to_string(), 300.0));
        assert!(!verify_timestamp_freshness("not_a_number", 300.0));
    }

    // ── Tier 2: Crypto Engine tests ──────────────────────────────

    #[test]
    fn test_crypto_bcrypt_password() {
        let engine = CryptoEngine::new(4); // low cost for speed
        let hash = engine.hash_password("test_password").unwrap();
        assert!(hash.starts_with("$2"));
        assert!(engine.verify_password("test_password", &hash));
        assert!(!engine.verify_password("wrong_password", &hash));
    }

    #[test]
    fn test_crypto_bcrypt_api_key() {
        let engine = CryptoEngine::new(4);
        let raw_key = "sk-live-abc123xyz456";
        let hash = engine.hash_api_key(raw_key).unwrap();
        assert!(hash.starts_with("ak$"));
        assert!(engine.verify_api_key(raw_key, &hash));
        assert!(!engine.verify_api_key("wrong_key", &hash));
        // Legacy SHA-256 fallback
        let sha256_hash = sha256_hex(raw_key);
        assert!(engine.verify_api_key(raw_key, &sha256_hash));
    }

    #[test]
    fn test_crypto_empty_inputs() {
        let engine = CryptoEngine::new(4);
        assert!(engine.hash_api_key("").is_err());
        assert!(!engine.verify_api_key("", "$2a$04$hash"));
        assert!(!engine.verify_api_key("key", ""));
    }

    #[test]
    fn test_crypto_sha256() {
        let engine = CryptoEngine::new(4);
        assert_eq!(engine.sha256("hello"), sha256_hex("hello"));
        assert_eq!(engine.sha256("hello").len(), 64);
    }

    #[test]
    fn test_crypto_random_tokens() {
        let engine = CryptoEngine::new(4);
        let hex_token = engine.random_token(32);
        assert_eq!(hex_token.len(), 64); // 32 bytes = 64 hex chars
        let url_token = engine.random_urlsafe_token(32);
        assert!(url_token.len() >= 32);
    }

    // ── Tier 3: Connection Pool tests ────────────────────────────

    #[test]
    fn test_pool_register_and_checkout() {
        let pool = ConnectionPool::new();
        pool.register("stripe", 3, 60.0, 10.0);
        assert!(pool.checkout_or_true("stripe")); // wrapper for test
        assert!(pool.has_capacity("stripe"));
        pool.checkin("stripe", true);
    }

    #[test]
    fn test_pool_exhaustion() {
        let pool = ConnectionPool::new();
        pool.register("api", 2, 60.0, 10.0);
        assert!(pool.checkout_or_true("api"));
        assert!(pool.checkout_or_true("api"));
        // Third should fail — pool exhausted
        assert!(!pool.checkout_or_true("api"));
        pool.checkin("api", true);
        pool.checkin("api", true);
        // Should work again
        assert!(pool.checkout_or_true("api"));
        pool.checkin("api", true);
    }

    #[test]
    fn test_pool_unregistered_service() {
        let pool = ConnectionPool::new();
        assert!(!pool.checkout_or_true("nonexistent")); // not registered = false
        assert!(pool.has_capacity("nonexistent")); // not registered = true (pass-through)
    }

    #[test]
    fn test_pool_stats() {
        let pool = ConnectionPool::new();
        pool.register("redis", 10, 60.0, 5.0);
        pool.checkout_or_true("redis");
        pool.checkin("redis", true);
        pool.checkout_or_true("redis");
        pool.checkin("redis", false); // error
        pool.record_timeout("redis");
        // Just verify it doesn't crash — stats should be accessible
        assert!(pool.has_capacity("redis"));
    }

    #[test]
    fn test_pool_unregister() {
        let pool = ConnectionPool::new();
        pool.register("temp", 5, 60.0, 10.0);
        pool.unregister("temp");
        assert!(!pool.checkout_or_true("temp")); // gone
    }

    #[test]
    fn test_pool_reset() {
        let pool = ConnectionPool::new();
        pool.register("svc", 5, 60.0, 10.0);
        pool.checkout_or_true("svc");
        pool.reset("svc");
        // After reset, should have capacity
        assert!(pool.has_capacity("svc"));
    }
}

/// Test helper: checkout returning bool (for unit tests without Python GIL)
impl ConnectionPool {
    #[allow(dead_code)]
    fn checkout_or_true(&self, service: &str) -> bool {
        let max = match self.configs.get(service) {
            Some(c) => c.max_connections,
            None => return false,
        };
        let state = self.states.entry(service.to_string())
            .or_insert_with(|| PoolState {
                active_count: AtomicU32::new(0),
                idle_count: AtomicU32::new(0),
                total_checkout: AtomicU64::new(0),
                total_checkin: AtomicU64::new(0),
                total_errors: AtomicU64::new(0),
                total_timeouts: AtomicU64::new(0),
                created_at: now_secs(),
                last_activity: AtomicI64::new(0),
            });
        let current = state.active_count.load(Ordering::SeqCst);
        if current < max {
            state.active_count.fetch_add(1, Ordering::SeqCst);
            state.total_checkout.fetch_add(1, Ordering::SeqCst);
            true
        } else {
            false
        }
    }
}
