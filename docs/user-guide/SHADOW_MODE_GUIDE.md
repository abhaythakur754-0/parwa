# Shadow Mode User Guide

> **PARWA AI Customer Support Platform**
> **Last Updated:** April 17, 2026

---

## What is Shadow Mode?

Shadow Mode is a safety feature that gives you control over how your AI assistant (Jarvis) handles actions. Think of it as a "trust but verify" system that lets you decide how much autonomy Jarvis has.

### Why Shadow Mode?

When you deploy an AI to handle customer support, you want confidence that it won't make mistakes. Shadow Mode provides:

- **Safety Net**: Catch potential mistakes before they happen
- **Learning Period**: See what Jarvis wants to do before fully automating
- **Flexibility**: Different rules for different types of actions
- **Audit Trail**: Complete history of all AI decisions

---

## The Three Modes

### 🔴 Shadow Mode (Full Oversight)

**"I want to approve everything first"**

- **Every action** requires your approval before execution
- Best for: New deployments, high-stakes situations, building trust
- What happens: Jarvis drafts actions → You review → You approve/reject

### 🟡 Supervised Mode (Balanced)

**"Let me review the risky ones"**

- High-risk actions require approval
- Low-risk actions execute automatically
- Best for: Established deployments with some confidence
- What happens: Jarvis handles routine tasks → Flags risky actions for review

### 🟢 Graduated Mode (High Trust)

**"Handle routine tasks, I'll undo if needed"**

- Most actions execute automatically
- You can undo actions within a time window (default: 30 minutes)
- Best for: Mature deployments with high confidence
- What happens: Jarvis executes → You can undo within window

---

## Quick Start

### Understanding Your Current Mode

1. Open the **Dashboard**
2. Look for the **Shadow Mode** indicator in the header
3. Click to see details and change mode

### Changing Modes

**Via Dashboard:**
1. Go to **Settings → Shadow Mode**
2. Select your preferred mode
3. Changes take effect immediately

**Via Jarvis:**
```
You: "switch to supervised mode"
Jarvis: "Done. Your system is now in supervised mode."

You: "put refunds in shadow mode"
Jarvis: "Understood. Refunds will now require your approval."
```

---

## The Approvals Queue

### Accessing the Queue

Navigate to **Dashboard → Approvals** to see all pending actions.

### Understanding Queue Items

Each item shows:

| Field | Description |
|-------|-------------|
| **Action Type** | What Jarvis wants to do (Send Email, Process Refund, etc.) |
| **Risk Score** | How risky (0-100%, higher = riskier) |
| **AI Recommendation** | Why Jarvis thinks this is okay |
| **Time** | When the action was queued |
| **Mode** | Which mode triggered this review |

### Risk Score Colors

| Color | Risk Level | Meaning |
|-------|------------|---------|
| 🟢 Green | 0-30% | Low risk, routine action |
| 🟡 Yellow | 30-70% | Moderate risk, needs attention |
| 🔴 Red | 70-100% | High risk, careful review needed |

### Reviewing an Action

1. Click on an item to see full details
2. Review the action payload (what will happen)
3. Check the AI's reasoning
4. Make your decision:

**Approve**: Action executes immediately
**Reject**: Action is cancelled
**View Details**: See more context (customer history, related tickets)

### Batch Actions

Select multiple items and approve/reject all at once:

1. Check the boxes next to items
2. Click **Approve Selected** or **Reject Selected**
3. Optionally add a note

**Pro tip:** Use "Approve All Low Risk" to quickly approve items with risk < 30%

---

## Configuring Preferences

### Per-Action Settings

You can set different modes for different action types:

1. Go to **Settings → Shadow Mode → Preferences**
2. Click **Add Preference**
3. Choose:
   - **Action Category** (e.g., Refunds, Email, SMS)
   - **Preferred Mode** (Shadow, Supervised, Graduated)
4. Save

### Example Configurations

| Action Category | Mode | Why |
|-----------------|------|-----|
| Refunds | Shadow | Money is involved, want full control |
| Email Replies | Graduated | Comfortable with routine emails |
| SMS | Supervised | Most are fine, flag risky ones |
| Account Changes | Shadow | Security-sensitive |

### Via Jarvis

```
You: "always ask me before processing refunds"
Jarvis: "Done. Refunds will now require your approval."

You: "let email replies go through automatically"
Jarvis: "Understood. Email replies are now in graduated mode."
```

---

## The Undo Queue

### What Can Be Undone?

Actions that were **auto-executed** in Graduated mode can be undone within the time window (default: 30 minutes).

### Accessing Undo Queue

Go to **Dashboard → Undo Queue** to see actions available for undo.

### How Undo Works

1. Find the action you want to undo
2. Click **Undo**
3. Provide a reason
4. The action is reversed (if possible)

### What Happens When You Undo

| Action Type | Undo Behavior |
|-------------|---------------|
| Email | Email is already sent, but logged as undone for audit |
| SMS | SMS is already sent, logged as undone |
| Refund | May trigger reversal transaction (depends on payment processor) |
| Ticket Close | Ticket reopens |

---

## The Shadow Log

### What It Is

Complete audit trail of all AI actions and your decisions.

### Accessing the Log

Go to **Dashboard → Shadow Log**

### Filtering

Filter by:
- **Action Type**: Email, SMS, Refund, etc.
- **Mode**: Shadow, Supervised, Graduated
- **Decision**: Pending, Approved, Rejected, Undone
- **Date Range**: When the action occurred

### Exporting

Click **Export to CSV** to download the log for external analysis.

---

## What-If Simulator

### Purpose

Test how Jarvis would handle a hypothetical action without actually executing it.

### Using the Simulator

1. Go to **Settings → Shadow Mode → What-If**
2. Enter:
   - Action Type
   - Payload (details of the action)
3. Click **Simulate**
4. See:
   - Predicted mode
   - Risk score
   - Why this decision
   - Layer-by-layer breakdown

### Example

```
Action Type: refund
Payload: {"amount": 250, "customer_id": "vip_001"}

Result:
Mode: Supervised
Risk Score: 65%
Reason: "Moderate refund amount for VIP customer"
Layer 1: Base risk 0.8, amount adds +0.1
Layer 2: No preference set
Layer 3: Historical avg 0.5 for refunds
Layer 4: Hard safety floor - always requires approval
```

---

## Stage 0: New User Onboarding

### What Is Stage 0?

When you first start using PARWA, your account is in "Stage 0" - a learning period where **all actions require approval**.

### How It Works

1. New accounts start with **10 shadow actions remaining**
2. Each approved action decrements the counter
3. After 10 approvals, you **graduate** to Supervised mode
4. Rejected actions don't count (you're learning!)

### Why Stage 0?

- **Learn the system**: See what Jarvis wants to do
- **Build confidence**: Understand risk scores and decisions
- **Set preferences**: Decide which actions need oversight

### Your Progress

See your progress in:
- Dashboard header: "7 of 10 shadow actions remaining"
- Onboarding modal: Progress bar with explanations

---

## Jarvis Commands Reference

### Mode Commands

| Command | Action |
|---------|--------|
| "switch to shadow mode" | Set global mode to Shadow |
| "switch to supervised mode" | Set global mode to Supervised |
| "switch to graduated mode" | Set global mode to Graduated |
| "what is my current shadow mode?" | Show current mode and preferences |

### Preference Commands

| Command | Action |
|---------|--------|
| "put [action] in shadow mode" | Set preference: [action] → Shadow |
| "put [action] in supervised mode" | Set preference: [action] → Supervised |
| "put [action] in graduated mode" | Set preference: [action] → Graduated |
| "always ask me before [action]" | Same as "put [action] in shadow mode" |

### Approval Commands

| Command | Action |
|---------|--------|
| "show me pending approvals" | List pending actions |
| "approve the last [action]" | Approve most recent [action] |
| "reject the last [action]" | Reject most recent [action] |
| "why was this action put in shadow?" | Explain decision layers |

### Undo Commands

| Command | Action |
|---------|--------|
| "undo the last [action]" | Undo most recent [action] |
| "show me the undo queue" | List undoable actions |

---

## Safety Floor

Some actions ALWAYS require approval, regardless of your settings:

| Action | Why Always Approved |
|--------|---------------------|
| Refunds | Financial impact |
| Account Deletion | Irreversible |
| Data Export | Privacy concern |
| Password Reset | Security sensitive |
| API Key Creation | Security sensitive |

These actions show a **"Safety Floor"** badge in the approvals queue.

---

## Best Practices

### For New Deployments

1. **Start in Shadow mode** for at least 50-100 actions
2. **Review every decision** - learn Jarvis's patterns
3. **Set preferences** for action types you trust
4. **Gradually move to Supervised** as confidence grows

### For Production

1. **Use Graduated for routine actions** (simple replies, acknowledgments)
2. **Keep Shadow for sensitive actions** (refunds, account changes)
3. **Regularly review the Shadow Log** for patterns
4. **Adjust risk thresholds** based on your risk tolerance

### For Teams

1. **Document your preferences** so all managers are aligned
2. **Use batch approvals** for efficiency
3. **Add notes** when approving/rejecting for audit trail
4. **Train new managers** on Shadow Mode before giving access

---

## Troubleshooting

### "Too many pending approvals"

- Check if preferences are set correctly
- Consider moving more action types to Graduated
- Use batch approve for low-risk items

### "Action was auto-approved when I wanted to review it"

- Check if the action has a preference set to Graduated
- Verify the global mode isn't set to Graduated
- Safety Floor actions should always require approval

### "I can't undo an action"

- Check if you're within the undo window (default: 30 minutes)
- Only auto-executed actions (Graduated mode) can be undone
- Some actions may not be reversible (already sent emails)

### "Jarvis isn't following my preferences"

- Verify preferences are saved in Settings
- Check if a conflicting global mode is set
- Safety Floor always overrides preferences

---

## FAQ

### Q: What happens if I reject an action?
**A:** The action is cancelled and logged. No further action is taken. The customer is not notified.

### Q: Can I change back to Shadow mode after graduating?
**A:** Yes! You can change modes anytime via Settings or Jarvis.

### Q: Do rejected actions count toward Stage 0 graduation?
**A:** No, only approved actions decrement the counter.

### Q: What's the difference between Supervised and Shadow?
**A:** In Shadow, ALL actions require approval. In Supervised, only high-risk actions require approval based on risk scores.

### Q: How is risk score calculated?
**A:** Risk score combines: action type (base risk), payload details (amount, content), historical patterns, and safety rules.

### Q: Can I set different modes for different team members?
**A:** Currently, Shadow Mode is company-wide. All managers see the same approvals queue.

---

## Getting Help

- **In-app**: Click the help icon in the Shadow Mode settings
- **Jarvis**: Ask "help with shadow mode"
- **Documentation**: docs.parwa.ai/shadow-mode

---

*End of Shadow Mode User Guide*
