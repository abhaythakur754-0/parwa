use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use parking_lot::Mutex;
use pyo3::prelude::*;

#[derive(Debug, Clone, Copy, PartialEq)]
enum State {
    Closed,
    Open,
    HalfOpen,
}

impl State {
    fn as_str(&self) -> &'static str {
        match self {
            State::Closed => "CLOSED",
            State::Open => "OPEN",
            State::HalfOpen => "HALF_OPEN",
        }
    }
}

struct CircuitState {
    state: State,
    failure_count: u32,
    success_count: u32,
    half_open_calls: u32,
    failure_threshold: u32,
    recovery_timeout_secs: u64,
    half_open_max_calls: u32,
    opened_at: Option<u64>,          // timestamp when circuit went OPEN
    last_failure_time: Option<u64>,
    last_state_change: Option<u64>,
}

/// Thread-safe circuit breaker with CLOSED / OPEN / HALF_OPEN states.
#[pyclass]
pub struct CircuitBreaker {
    name: String,
    inner: Mutex<CircuitState>,
}

#[pymethods]
impl CircuitBreaker {
    #[new]
    #[pyo3(signature = (name, failure_threshold, recovery_timeout_secs, half_open_max_calls))]
    fn new(
        name: &str,
        failure_threshold: u32,
        recovery_timeout_secs: u64,
        half_open_max_calls: u32,
    ) -> Self {
        let now = now_secs();
        Self {
            name: name.to_string(),
            inner: Mutex::new(CircuitState {
                state: State::Closed,
                failure_count: 0,
                success_count: 0,
                half_open_calls: 0,
                failure_threshold,
                recovery_timeout_secs,
                half_open_max_calls,
                opened_at: None,
                last_failure_time: None,
                last_state_change: Some(now),
            }),
        }
    }

    /// Returns true if the circuit is currently OPEN (rejecting calls).
    fn is_open(&self) -> bool {
        let mut state = self.inner.lock();

        match state.state {
            State::Open => {
                let now = now_secs();
                if let Some(opened_at) = state.opened_at {
                    if now.saturating_sub(opened_at) >= state.recovery_timeout_secs {
                        // Transition to HALF_OPEN
                        state.state = State::HalfOpen;
                        state.half_open_calls = 0;
                        state.last_state_change = Some(now);
                        return false; // HALF_OPEN allows calls
                    }
                }
                true
            }
            State::HalfOpen => false,
            State::Closed => false,
        }
    }

    /// Record a successful call.
    fn record_success(&self) {
        let mut state = self.inner.lock();
        let now = now_secs();

        state.success_count += 1;

        match state.state {
            State::Closed => {
                // Reset failure count on success in CLOSED state
                state.failure_count = 0;
            }
            State::HalfOpen => {
                state.half_open_calls += 1;
                if state.half_open_calls >= state.half_open_max_calls {
                    // All probe calls succeeded → close the circuit
                    state.state = State::Closed;
                    state.failure_count = 0;
                    state.half_open_calls = 0;
                    state.last_state_change = Some(now);
                }
            }
            State::Open => {
                // Shouldn't normally happen (calls are rejected when OPEN),
                // but handle gracefully
            }
        }
    }

    /// Record a failed call.
    fn record_failure(&self) {
        let mut state = self.inner.lock();
        let now = now_secs();

        state.failure_count += 1;
        state.last_failure_time = Some(now);

        match state.state {
            State::Closed => {
                if state.failure_count >= state.failure_threshold {
                    state.state = State::Open;
                    state.opened_at = Some(now);
                    state.last_state_change = Some(now);
                }
            }
            State::HalfOpen => {
                // Any failure in HALF_OPEN → back to OPEN
                state.state = State::Open;
                state.opened_at = Some(now);
                state.half_open_calls = 0;
                state.last_state_change = Some(now);
            }
            State::Open => {
                // Already open, just update timestamp
            }
        }
    }

    /// Returns the current state as a string: "CLOSED", "OPEN", or "HALF_OPEN".
    fn get_state(&self) -> String {
        // Call is_open to trigger potential transition
        self.is_open();
        let state = self.inner.lock();
        state.state.as_str().to_string()
    }

    /// Returns a HashMap with circuit breaker statistics.
    fn get_stats(&self) -> HashMap<String, String> {
        // Trigger potential state transition
        self.is_open();

        let state = self.inner.lock();
        let mut map = HashMap::new();
        map.insert("name".to_string(), self.name.clone());
        map.insert("state".to_string(), state.state.as_str().to_string());
        map.insert(
            "failure_count".to_string(),
            state.failure_count.to_string(),
        );
        map.insert(
            "success_count".to_string(),
            state.success_count.to_string(),
        );
        map.insert(
            "last_failure_time".to_string(),
            state
                .last_failure_time
                .map_or("None".to_string(), |t| t.to_string()),
        );
        map.insert(
            "last_state_change".to_string(),
            state
                .last_state_change
                .map_or("None".to_string(), |t| t.to_string()),
        );
        map
    }
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time went backwards")
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_starts_closed() {
        let cb = CircuitBreaker::new("test", 3, 60, 2);
        assert_eq!(cb.get_state(), "CLOSED");
        assert!(!cb.is_open());
    }

    #[test]
    fn test_opens_after_threshold_failures() {
        let cb = CircuitBreaker::new("test", 3, 60, 2);
        cb.record_failure();
        assert_eq!(cb.get_state(), "CLOSED");
        cb.record_failure();
        assert_eq!(cb.get_state(), "CLOSED");
        cb.record_failure();
        assert_eq!(cb.get_state(), "OPEN");
    }

    #[test]
    fn test_rejects_when_open() {
        let cb = CircuitBreaker::new("test", 2, 60, 1);
        cb.record_failure();
        cb.record_failure();
        assert!(cb.is_open());
        assert_eq!(cb.get_state(), "OPEN");
    }

    #[test]
    fn test_transitions_to_half_open_after_timeout() {
        // Use a very short recovery timeout and manipulate time via the internal state.
        let cb = CircuitBreaker::new("test", 1, 1, 1);
        cb.record_failure();
        assert_eq!(cb.get_state(), "OPEN");

        // Manually set opened_at far enough in the past
        {
            let mut state = cb.inner.lock();
            state.opened_at = Some(now_secs() - 2); // 2 seconds ago, timeout is 1s
        }

        // is_open should transition to HALF_OPEN and return false
        assert!(!cb.is_open());
        assert_eq!(cb.get_state(), "HALF_OPEN");
    }

    #[test]
    fn test_closes_after_half_open_success() {
        let cb = CircuitBreaker::new("test", 1, 1, 2);

        // Trip the breaker
        cb.record_failure();
        assert_eq!(cb.get_state(), "OPEN");

        // Simulate timeout expiry
        {
            let mut state = cb.inner.lock();
            state.opened_at = Some(now_secs() - 2);
        }

        // Trigger transition to HALF_OPEN
        assert!(!cb.is_open());
        assert_eq!(cb.get_state(), "HALF_OPEN");

        // Record enough successes to close
        cb.record_success();
        cb.record_success();
        assert_eq!(cb.get_state(), "CLOSED");
    }

    #[test]
    fn test_reopens_on_half_open_failure() {
        let cb = CircuitBreaker::new("test", 1, 1, 3);

        // Trip the breaker
        cb.record_failure();
        assert_eq!(cb.get_state(), "OPEN");

        // Simulate timeout expiry
        {
            let mut state = cb.inner.lock();
            state.opened_at = Some(now_secs() - 2);
        }

        // Trigger transition to HALF_OPEN
        assert!(!cb.is_open());
        assert_eq!(cb.get_state(), "HALF_OPEN");

        // Record a success
        cb.record_success();
        assert_eq!(cb.get_state(), "HALF_OPEN");

        // Record a failure → back to OPEN
        cb.record_failure();
        assert_eq!(cb.get_state(), "OPEN");
    }
}