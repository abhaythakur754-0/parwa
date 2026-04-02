import { useState, useRef, useEffect } from "react";

const SYSTEM_PROMPT = `You are a senior software testing engineer. Your job is to find loopholes, bugs, and missing test cases in any software project.

You think in 4 layers:
1. UNIT GAPS — individual functions with edge cases
2. INTEGRATION GAPS — two systems talking to each other, what breaks at the seams
3. FLOW GAPS — full user journeys nobody tested end to end
4. BREAK TESTS — adversarial scenarios where users do unexpected things

You know these failure patterns:
- Race conditions (two things at same time)
- Idempotency failures (same request sent twice)
- Tenant isolation leaks (one customer sees another's data)
- Webhook double-fires (payment systems sending same event twice)
- State loss (in-memory data gone on restart)
- Missing rollback (partial success leaving broken state)
- Silent failures (errors swallowed, never surfaced)
- Cascade failures (one system down takes others down)

RESPOND IN THIS EXACT FORMAT — no deviation:

GAPS FOUND: [number]

GAP 1
Severity: CRITICAL
Title: [short title]
What breaks: [one sentence]
Real scenario: [concrete example with actual data]
AI agent prompt: [exact prompt to paste into coding AI to write this test]

GAP 2
Severity: HIGH
Title: [short title]
What breaks: [one sentence]
Real scenario: [concrete example]
AI agent prompt: [exact prompt]

[continue for all gaps]

Keep it tight and actionable. Every gap needs an AI agent prompt they can copy paste directly.`;

const STARTERS = [
  { icon: "💳", label: "Payment + webhook", prompt: "I use Paddle for payments. Customer pays, Paddle sends a webhook to my backend, backend activates their subscription. What gaps should I test?" },
  { icon: "🤖", label: "AI approval gate", prompt: "My AI analyzes support tickets and sends recommendations to a human manager who clicks approve or reject. What could go wrong that I haven't tested?" },
  { icon: "🏢", label: "Multi-tenant database", prompt: "Multiple business clients share one PostgreSQL database separated by company_id. What are the loopholes in my data isolation?" },
  { icon: "📨", label: "Background job / worker", prompt: "I have a Celery worker that runs daily, calculates ticket overages and charges customers $0.10 per ticket via Paddle API. What can go wrong?" },
  { icon: "⚡", label: "Real-time Socket.io", prompt: "I use Socket.io for real-time updates — approval queue, activity feed, live metrics. Server restarts on every deploy. What gaps exist?" },
  { icon: "🔐", label: "Auth + sessions", prompt: "I have JWT auth with Google OAuth. Users can have multiple active sessions. What security loopholes exist?" },
];

function parseGaps(text) {
  const lines = text.split("\n").map(l => l.trim()).filter(Boolean);
  const gaps = [];
  let current = null;
  let foundCount = null;

  for (const line of lines) {
    if (line.startsWith("GAPS FOUND:")) {
      foundCount = line.replace("GAPS FOUND:", "").trim();
      continue;
    }
    if (/^GAP\s+\d+/i.test(line)) {
      if (current) gaps.push(current);
      current = { severity: "MEDIUM", title: "", breaks: "", scenario: "", prompt: "" };
      continue;
    }
    if (!current) continue;
    if (line.startsWith("Severity:")) current.severity = line.replace("Severity:", "").trim().toUpperCase();
    else if (line.startsWith("Title:")) current.title = line.replace("Title:", "").trim();
    else if (line.startsWith("What breaks:")) current.breaks = line.replace("What breaks:", "").trim();
    else if (line.startsWith("Real scenario:")) current.scenario = line.replace("Real scenario:", "").trim();
    else if (line.startsWith("AI agent prompt:")) current.prompt = line.replace("AI agent prompt:", "").trim();
  }
  if (current) gaps.push(current);
  return { foundCount, gaps };
}

function GapCard({ gap }) {
  const [copied, setCopied] = useState(false);
  const sev = {
    CRITICAL: { bg: "#1a0808", border: "#7f1d1d", dot: "#ef4444", label: "🔴 CRITICAL" },
    HIGH:     { bg: "#1a1008", border: "#78350f", dot: "#f97316", label: "🟡 HIGH" },
    MEDIUM:   { bg: "#08101a", border: "#1e3a5f", dot: "#38bdf8", label: "🟢 MEDIUM" },
  }[gap.severity] || { bg: "#08101a", border: "#1e3a5f", dot: "#38bdf8", label: "🟢 MEDIUM" };

  return (
    <div style={{ background: sev.bg, border: `1px solid ${sev.border}`, borderRadius: 10, padding: 16, marginBottom: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        <span style={{ background: sev.dot, color: "#fff", fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4, fontFamily: "monospace", letterSpacing: 0.8 }}>
          {sev.label}
        </span>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#f1f5f9" }}>{gap.title}</span>
      </div>
      {gap.breaks && (
        <p style={{ fontSize: 12, color: "#94a3b8", marginBottom: 5, lineHeight: 1.5 }}>
          <span style={{ color: "#475569" }}>Breaks: </span>{gap.breaks}
        </p>
      )}
      {gap.scenario && (
        <p style={{ fontSize: 12, color: "#94a3b8", marginBottom: 10, lineHeight: 1.5 }}>
          <span style={{ color: "#475569" }}>Scenario: </span>{gap.scenario}
        </p>
      )}
      {gap.prompt && (
        <div style={{ background: "#050508", border: "1px solid #1e2030", borderRadius: 6, padding: "10px 12px" }}>
          <div style={{ fontSize: 10, color: "#475569", marginBottom: 6, fontFamily: "monospace", letterSpacing: 1 }}>AI AGENT PROMPT</div>
          <p style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.6, fontFamily: "monospace" }}>{gap.prompt}</p>
          <button
            onClick={() => { navigator.clipboard.writeText(gap.prompt); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
            style={{
              marginTop: 8, padding: "4px 12px",
              background: copied ? "#14532d" : "#1e2030",
              border: `1px solid ${copied ? "#16a34a" : "#334155"}`,
              borderRadius: 4, fontSize: 11,
              color: copied ? "#4ade80" : "#64748b",
              cursor: "pointer", fontFamily: "monospace", transition: "all 0.15s",
            }}
          >{copied ? "✓ Copied!" : "Copy prompt"}</button>
        </div>
      )}
    </div>
  );
}

function AssistantMessage({ content }) {
  const { foundCount, gaps } = parseGaps(content);
  if (gaps.length === 0) {
    return (
      <div style={{ background: "#0f1117", border: "1px solid #1e2030", borderRadius: 10, padding: "14px 16px", fontSize: 13, color: "#cbd5e1", lineHeight: 1.7, whiteSpace: "pre-wrap", fontFamily: "monospace" }}>
        {content}
      </div>
    );
  }
  return (
    <div>
      <div style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "linear-gradient(135deg,#f97316,#ef4444)", borderRadius: 20, padding: "5px 14px", marginBottom: 14 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "#fff", fontFamily: "monospace" }}>
          ⚡ {foundCount || gaps.length} GAPS FOUND
        </span>
      </div>
      {gaps.map((g, i) => <GapCard key={i} gap={g} />)}
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);
  const taRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  const send = async (text) => {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput("");
    setError("");
    if (taRef.current) taRef.current.style.height = "auto";

    const history = [...messages, { role: "user", content: msg }];
    setMessages(history);
    setLoading(true);

    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          system: SYSTEM_PROMPT,
          messages: history.map(m => ({ role: m.role, content: m.content })),
        }),
      });
      const data = await res.json();
      const reply = data?.content?.[0]?.text;
      if (!reply) throw new Error("Empty response");
      setMessages([...history, { role: "assistant", content: reply }]);
    } catch (e) {
      setError("Could not reach the API. Please try again.");
      setMessages(history);
    }
    setLoading(false);
  };

  const isEmpty = messages.length === 0;

  return (
    <div style={{ fontFamily: "'DM Mono','Fira Code',monospace", background: "#0a0a0f", minHeight: "100vh", display: "flex", flexDirection: "column", color: "#e2e8f0", maxWidth: 820, margin: "0 auto" }}>

      {/* Header */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid #1e2030", display: "flex", alignItems: "center", gap: 12, position: "sticky", top: 0, background: "#0a0a0f", zIndex: 10 }}>
        <div style={{ width: 36, height: 36, background: "linear-gradient(135deg,#f97316,#ef4444)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>⚡</div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#f1f5f9", letterSpacing: -0.3 }}>Testing Gap Finder</div>
          <div style={{ fontSize: 11, color: "#475569", marginTop: 1 }}>describe any feature → get exact gaps + AI agent prompts</div>
        </div>
        <div style={{ marginLeft: "auto", fontSize: 10, padding: "3px 8px", background: "#1e2030", border: "1px solid #2d3748", borderRadius: 4, color: "#f97316", letterSpacing: 1 }}>ANY PROJECT</div>
      </div>

      {/* Empty state */}
      {isEmpty && (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "32px 24px", gap: 28 }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 21, fontWeight: 700, color: "#f1f5f9", letterSpacing: -0.5, lineHeight: 1.3 }}>What are you building?</div>
            <div style={{ fontSize: 12, color: "#475569", marginTop: 6 }}>describe a feature or system — get every gap you haven't tested</div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, width: "100%", maxWidth: 580 }}>
            {STARTERS.map(s => (
              <button key={s.label} onClick={() => send(s.prompt)}
                style={{ background: "#0f1117", border: "1px solid #1e2030", borderRadius: 8, padding: "12px 14px", textAlign: "left", cursor: "pointer", display: "flex", alignItems: "center", gap: 10 }}
                onMouseEnter={e => e.currentTarget.style.borderColor = "#f97316"}
                onMouseLeave={e => e.currentTarget.style.borderColor = "#1e2030"}
              >
                <span style={{ fontSize: 16 }}>{s.icon}</span>
                <span style={{ fontSize: 12, color: "#94a3b8" }}>{s.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      {!isEmpty && (
        <div style={{ flex: 1, padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
          {messages.map((m, i) => (
            <div key={i}>
              {m.role === "user" ? (
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <div style={{ background: "#1e2030", border: "1px solid #2d3748", borderRadius: 10, padding: "10px 14px", maxWidth: "75%", fontSize: 13, color: "#e2e8f0", lineHeight: 1.6 }}>
                    {m.content}
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <div style={{ width: 28, height: 28, background: "linear-gradient(135deg,#f97316,#ef4444)", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, flexShrink: 0, marginTop: 2 }}>⚡</div>
                  <div style={{ flex: 1 }}><AssistantMessage content={m.content} /></div>
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <div style={{ width: 28, height: 28, background: "linear-gradient(135deg,#f97316,#ef4444)", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, flexShrink: 0 }}>⚡</div>
              <div style={{ background: "#0f1117", border: "1px solid #1e2030", borderRadius: 10, padding: "12px 16px", display: "flex", gap: 5, alignItems: "center" }}>
                {[0, 1, 2].map(i => (
                  <div key={i} style={{ width: 5, height: 5, background: "#f97316", borderRadius: "50%", animation: `bounce 1.2s ${i * 0.2}s ease-in-out infinite` }} />
                ))}
              </div>
            </div>
          )}

          {error && (
            <div style={{ background: "#1a0808", border: "1px solid #7f1d1d", borderRadius: 8, padding: "10px 14px", fontSize: 12, color: "#f87171" }}>
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      )}

      {/* Input */}
      <div style={{ padding: "14px 24px 20px", borderTop: "1px solid #1e2030", background: "#0a0a0f" }}>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end", background: "#0f1117", border: "1px solid #1e2030", borderRadius: 10, padding: "10px 12px" }}>
          <textarea
            ref={taRef}
            rows={1}
            placeholder="Describe any feature, system, or flow you're building..."
            value={input}
            onChange={e => {
              setInput(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
            }}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            disabled={loading}
            style={{ flex: 1, background: "transparent", border: "none", outline: "none", resize: "none", fontSize: 13, color: "#e2e8f0", fontFamily: "'DM Mono',monospace", lineHeight: 1.5, minHeight: 20, maxHeight: 120 }}
          />
          <button
            onClick={() => send()}
            disabled={!input.trim() || loading}
            style={{ width: 32, height: 32, background: !input.trim() || loading ? "#1e2030" : "linear-gradient(135deg,#f97316,#ef4444)", border: "none", borderRadius: 6, cursor: !input.trim() || loading ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 16, color: "#fff", transition: "all 0.15s" }}
          >↑</button>
        </div>
        <div style={{ fontSize: 10, color: "#334155", marginTop: 6, textAlign: "center", fontFamily: "monospace" }}>
          Enter to send · Shift+Enter for new line · Works for any tech stack
        </div>
      </div>

      <style>{`@keyframes bounce { 0%,80%,100%{transform:scale(0.6);opacity:0.4} 40%{transform:scale(1);opacity:1} }`}</style>
    </div>
  );
}
