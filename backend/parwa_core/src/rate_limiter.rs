use std::collections::{HashMap, VecDeque};
use std::time::{SystemTime, UNIX_EPOCH};

use parking_lot::RwLock;
use pyo3::prelude::*;

/// Per-identifier sliding window state.
struct SlidingWindow {
    timestamps: VecDeque<u64>,
    violation_count: u32,
    lockout_until: Option<u64>,
}

impl SlidingWindow {
    fn new() -> Self {
        Self {
            timestamps: VecDeque::new(),
            violation_count: 0,
            lockout_until: None,
        }
    }
}

/// Thread-safe sliding-window rate limiter with progressive lockout.
#[pyclass]
pub struct RateLimiter {
    max_requests: u32,
    window_secs: u64,
    lockout_steps: Vec<u64>,
    buckets: RwLock<HashMap<String, SlidingWindow>>,
}

#[pymethods]
impl RateLimiter {
    #[new]
    fn new(max_requests: u32, window_secs: u64) -> Self {
        Self {
            max_requests,
            window_secs,
            lockout_steps: vec![0, 2, 4, 8, 900],
            buckets: RwLock::new(HashMap::new()),
        }
    }

    /// Check whether the given identifier is allowed.
    /// Returns (allowed: bool, reason: str).
    fn check(&self, identifier: &str) -> (bool, String) {
        check_inner(
            identifier,
            self.max_requests,
            self.window_secs,
            &self.lockout_steps,
            &self.buckets,
        )
    }
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time went backwards")
        .as_secs()
}

fn check_inner(
    identifier: &str,
    max_requests: u32,
    window_secs: u64,
    lockout_steps: &[u64],
    buckets: &RwLock<HashMap<String, SlidingWindow>>,
) -> (bool, String) {
    let now = now_secs();

    let mut map = buckets.write();
    let bucket = map.entry(identifier.to_string()).or_insert_with(SlidingWindow::new);

    // If currently locked out
    if let Some(lock_until) = bucket.lockout_until {
        if now < lock_until {
            let remaining = lock_until - now;
            return (
                false,
                format!("Locked out for {} more seconds", remaining),
            );
        }
        // Lockout expired – reset violation count so the user gets a fresh window
        bucket.lockout_until = None;
        bucket.violation_count = 0;
    }

    // Prune timestamps outside the sliding window
    let window_start = now.saturating_sub(window_secs);
    while bucket
        .timestamps
        .front()
        .map_or(false, |&ts| ts < window_start)
    {
        bucket.timestamps.pop_front();
    }

    // Check count
    if (bucket.timestamps.len() as u32) >= max_requests {
        bucket.violation_count += 1;
        // Determine lockout duration from steps
        let step_idx = (bucket.violation_count as usize).min(lockout_steps.len() - 1);
        let lockout_secs = lockout_steps[step_idx];
        if lockout_secs > 0 {
            bucket.lockout_until = Some(now + lockout_secs);
            return (
                false,
                format!(
                    "Rate limit exceeded. Locked out for {} seconds (violation #{})",
                    lockout_secs, bucket.violation_count
                ),
            );
        }
        return (
            false,
            format!(
                "Rate limit exceeded ({} requests in {}s window, violation #{})",
                bucket.timestamps.len(),
                window_secs,
                bucket.violation_count
            ),
        );
    }

    // Record this request
    bucket.timestamps.push_back(now);
    (true, "Allowed".to_string())
}

/// Standalone rate-limit check (uses a process-global map for shared state).
#[pyfunction]
pub fn check_rate_limit(
    identifier: &str,
    max_requests: u32,
    window_secs: u64,
    lockout_steps: Vec<u64>,
) -> (bool, String) {
    // Use a process-global map so the standalone function also carries state
    // across calls (matching the Python-level expectation of a stateful limiter).
    static BUCKETS: once_cell::sync::Lazy<RwLock<HashMap<String, SlidingWindow>>> =
        once_cell::sync::Lazy::new(|| RwLock::new(HashMap::new()));

    let steps = if lockout_steps.is_empty() {
        vec![0, 2, 4, 8, 900]
    } else {
        lockout_steps
    };

    check_inner(identifier, max_requests, window_secs, &steps, &BUCKETS)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_allows_within_limit() {
        let rl = RateLimiter::new(5, 60);
        for _ in 0..5 {
            let (allowed, reason) = rl.check("user1");
            assert!(allowed, "should be allowed: {}", reason);
        }
    }

    #[test]
    fn test_denies_over_limit() {
        let rl = RateLimiter::new(3, 60);
        for _ in 0..3 {
            let (allowed, _) = rl.check("user2");
            assert!(allowed);
        }
        let (allowed, reason) = rl.check("user2");
        assert!(!allowed);
        assert!(reason.contains("Rate limit exceeded"));
    }

    #[test]
    fn test_progressive_lockout_increases() {
        let rl = RateLimiter::new(1, 60);
        // First request allowed
        let (allowed, _) = rl.check("user3");
        assert!(allowed);
        // Second denied – violation 1, lockout step[1] = 2s
        let (allowed, r1) = rl.check("user3");
        assert!(!allowed);
        assert!(r1.contains("2 seconds"));

        // Simulate lockout expiry to allow next violation to be counted
        {
            let mut map = rl.buckets.write();
            if let Some(b) = map.get_mut("user3") {
                b.lockout_until = None;
            }
        }
        // Third denied – violation 2, lockout step[2] = 4s
        let (allowed, r2) = rl.check("user3");
        assert!(!allowed);
        assert!(r2.contains("4 seconds"));

        // Simulate lockout expiry again
        {
            let mut map = rl.buckets.write();
            if let Some(b) = map.get_mut("user3") {
                b.lockout_until = None;
            }
        }
        // Fourth denied – violation 3, lockout step[3] = 8s
        let (allowed, r3) = rl.check("user3");
        assert!(!allowed);
        assert!(r3.contains("8 seconds"));
    }

    #[test]
    fn test_lockout_expires() {
        // Use a very short window so we can test expiration naturally.
        // We'll manually manipulate the lockout_until to simulate expiration.
        let rl = RateLimiter::new(1, 60);
        let (allowed, _) = rl.check("user_expire");
        assert!(allowed);

        // Exhaust
        let (allowed, _) = rl.check("user_expire");
        assert!(!allowed);

        // Manually clear the lockout to simulate expiration
        {
            let mut map = rl.buckets.write();
            if let Some(b) = map.get_mut("user_expire") {
                b.lockout_until = None;
                b.violation_count = 0;
                b.timestamps.clear();
            }
        }

        // Next request should be allowed again
        let (allowed, _) = rl.check("user_expire");
        assert!(allowed);
    }

    #[test]
    fn test_different_identifiers_independent() {
        let rl = RateLimiter::new(1, 60);
        let (a1, _) = rl.check("id_a");
        assert!(a1);
        let (a2, _) = rl.check("id_a");
        assert!(!a2);
        // Different identifier should be independent
        let (b1, _) = rl.check("id_b");
        assert!(b1);
    }

    #[test]
    fn test_standalone_function() {
        // The standalone function uses a global static, so results carry across
        // calls within the same process. Use a unique identifier.
        let unique_id = format!("standalone_test_{}", std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos());

        let (allowed, _) = check_rate_limit(&unique_id, 2, 60, vec![0, 5, 10]);
        assert!(allowed);
        let (allowed, _) = check_rate_limit(&unique_id, 2, 60, vec![0, 5, 10]);
        assert!(allowed);
        let (allowed, reason) = check_rate_limit(&unique_id, 2, 60, vec![0, 5, 10]);
        assert!(!allowed);
        assert!(reason.contains("5 seconds"));
    }
}