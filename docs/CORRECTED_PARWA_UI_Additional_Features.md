# PARWA Additional Features from UI Documentation
## Features in UI PDF v3.4 - NOT in Main Documentation

> **Correction Notice:** This document has been corrected to align with the locked decisions in `loopwholws.md` (48 decisions). Key changes applied:
> - All references to the old name "Trivya" replaced with "PARWA"
> - "Stripe checkout" replaced with "Paddle checkout" (D1)
> - "Mini" variant renamed to "Starter", "Junior" renamed to "Growth" (D12)
> - Specific wording corrections per source-of-truth decisions

---

## Overview

The UI PDF (v3.4) contains several **client-facing features** that are **NOT mentioned in the Main Documentation v6.0**. These are primarily UX/UI enhancements focused on improving customer experience, trust-building, and conversion optimization.

---

## 1. Dogfooding Banner

### Description
A gold banner displayed on the landing page that demonstrates the product by using it ourselves.

### UI Specification
```
┌─────────────────────────────────────────────────────────┐
│ 🏆 Our support is powered by PARWA AI. Try it yourself. │
└─────────────────────────────────────────────────────────┘
```

### Purpose
- Builds instant trust through transparency
- Shows "we eat our own dog food" - we use our product
- Encourages visitors to test the AI

### Implementation Location
- **Page:** Landing page (Hero section)
- **Style:** Gold background, subtle animation
- **Action:** Links to Live AI Demo Widget

### Files to Create
| File | Purpose |
|------|---------|
| `frontend/src/components/landing/DogfoodingBanner.tsx` | Banner component |
| `frontend/src/components/landing/DogfoodingBanner.module.css` | Styling |

---

## 2. First Victory Celebration

### Description
An animated celebration that appears when a client logs in after activation, showing their AI's first successful ticket resolution.

### UI Specification
```
🎉 Your AI just resolved its first ticket!

Ticket #12847: "Where's my order?"
→ AI responded in 4 seconds
→ Customer satisfied (no reply needed)
→ Your team saved 8 minutes

[Animated counter starts]
"You've saved $3.47 in labor costs so far today.
At this rate, PARWA pays for itself in 23 days."
```

### Behavior
- Shows on **first login after activation**
- **Loops for first 7 days**
- Shows **cumulative savings in real-time**
- Updates with each new resolved ticket

### Purpose
- Immediate value demonstration
- Psychological reinforcement of ROI
- Reduces buyer's remorse
- Increases engagement

### Implementation Location
- **Page:** Dashboard (first login)
- **Trigger:** First ticket resolved after activation
- **Storage:** Track in user onboarding progress

### Files to Create
| File | Purpose |
|------|---------|
| `frontend/src/components/dashboard/FirstVictoryCelebration.tsx` | Main celebration component |
| `frontend/src/components/dashboard/SavingsCounter.tsx` | Animated counter |
| `frontend/src/hooks/useFirstVictory.ts` | Logic hook |
| `backend/api/routes/first_victory.py` | API endpoint |
| `backend/services/first_victory_tracker.py` | Tracking service |

---

## 3. Growth Nudge Alert

### Description
A usage-based notification that appears when the client is approaching their plan limits, suggesting an upgrade.

### UI Specification
```
┌────────────────────────────────────────────────────────┐
│ 📈 You're growing faster than your AI can handle       │
├────────────────────────────────────────────────────────┤
│ Last weekend: 340 tickets/day (your plan: 300)         │
│                                                        │
│ [Cyan button] "Add 1 Starter Agent for Black Friday:    │
│ +$400 (prorated, active instantly)"                    │
│                                                        │
│ [Subtle text] Or let PARWA auto-scale for you?         │
└────────────────────────────────────────────────────────┘
```

### Trigger Conditions
- Shows when usage is **>90% of plan** for **3 consecutive days**
- Only shows once per week maximum
- Different messages for different thresholds

### Purpose
- Proactive upselling
- Prevent service degradation
- Show we're monitoring their success

### Implementation Location
- **Page:** Dashboard (top of activity feed)
- **Trigger:** Backend monitoring job
- **Dismissal:** Can be dismissed, resurfaces after 7 days

### Files to Create
| File | Purpose |
|------|---------|
| `frontend/src/components/dashboard/GrowthNudge.tsx` | Alert component |
| `frontend/src/components/dashboard/GrowthNudgeCard.tsx` | Card variant |
| `backend/services/growth_nudge_monitor.py` | Monitoring service |
| `backend/workers/growth_nudge_worker.py` | Background worker |

---

## 4. Feature Discovery Teaser

### Description
A targeted upgrade prompt for Starter users showing how much time they could save by upgrading.

### UI Specification
```
┌────────────────────────────────────────────────────────┐
│ PARWA detected 47 refund requests this week            │
│ Your team reviewed all 47 manually.                    │
│                                                        │
│ Upgrade to PARWA Growth and let AI pre-approve 80%     │
│                                                        │
│ [Gold button] "See How Much Time I'd Save"             │
│                                                        │
│ [Shows calculator: 47 reviews × 5 min = 3.9 hrs/week]  │
└────────────────────────────────────────────────────────┘
```

### Trigger Conditions
- **Only for Starter users**
- Shows when refund review count exceeds threshold (e.g., 20+/week)
- Only shows once per week

### Purpose
- Tier upgrade conversion
- Show value before asking for money
- Educational about higher tier benefits

### Implementation Location
- **Page:** Dashboard
- **Position:** Below activity feed
- **Trigger:** Weekly analytics job

### Files to Create
| File | Purpose |
|------|---------|
| `frontend/src/components/dashboard/FeatureDiscoveryTeaser.tsx` | Teaser component |
| `frontend/src/components/dashboard/TimeSavingsCalculator.tsx` | Calculator popup |
| `backend/services/feature_discovery.py` | Detection logic |

---

## 5. Contextual Help System

### Description
A persistent help button that shows contextual GIF demos for the exact feature the user is viewing.

### UI Specification
```
[?]  ← Persistent cyan question mark in bottom-left corner

Hover: "Confused? Ask me anything."
Click: Shows 3-second GIF demo of current feature
```

### Example for "Add Call Slot"
```
┌─────────────────────────────────────────────────────────┐
│ [Looping GIF: Click "Add Slot" → Paddle checkout →       │
│  AI makes test call]                                    │
│                                                         │
│ "Adding a call line takes 45 seconds. No engineers      │
│  needed."                                               │
└─────────────────────────────────────────────────────────┘
```

### Behavior
- **Persistent:** Always visible in bottom-left
- **Contextual:** Shows help for current page/feature
- **Interactive:** Can open chat with AI trainer

### Purpose
- Reduce support tickets
- Self-service onboarding
- Immediate help without leaving page

### Implementation Location
- **Page:** All dashboard pages
- **Position:** Fixed bottom-left
- **Content:** Pre-recorded GIFs per feature

### Files to Create
| File | Purpose |
|------|---------|
| `frontend/src/components/help/ContextualHelp.tsx` | Main help widget |
| `frontend/src/components/help/HelpGifViewer.tsx` | GIF display |
| `frontend/src/hooks/useContextualHelp.ts` | Context detection |
| `frontend/src/data/helpContent.ts` | Help content & GIF URLs |
| `public/help-gifs/*.gif` | GIF demos for each feature |

---

## 6. Graceful Cancellation Flow

### Description
A multi-option cancellation flow that attempts to retain customers by addressing their specific concerns.

### UI Specification
```
We're sad to see you go. Before you cancel:

[ ] "PARWA is too expensive"
    → [Show ROI summary: "You've saved $8,400 this month"]

[ ] "My team wasn't using it"
    → [Offer 30-min training call, free]

[ ] "It didn't integrate with our tools"
    → [Show upcoming integrations roadmap]

[ ] "It made mistakes"
    → [Offer to dial back autonomy, add human approvals]

[Cancel Anyway] [Pause for 30 Days] [Get Help]
```

### Key Insight
> "40% of cancellations are reversible if you show them their own success data."

### Purpose
- Reduce churn rate
- Address specific pain points
- Offer alternatives to cancellation
- Gather feedback for improvement

### Implementation Location
- **Page:** Settings → Billing → Cancel Subscription
- **Trigger:** Cancel button click
- **Actions:** Show relevant alternatives based on selection

### Files to Create
| File | Purpose |
|------|---------|
| `frontend/src/components/settings/CancellationFlow.tsx` | Main flow component |
| `frontend/src/components/settings/CancellationOption.tsx` | Individual option |
| `frontend/src/components/settings/ROIDisplay.tsx` | ROI summary display |
| `frontend/src/components/settings/TrainingOffer.tsx` | Free training offer |
| `frontend/src/components/settings/IntegrationsRoadmap.tsx` | Roadmap display |
| `backend/api/routes/cancellation.py` | Cancellation API |
| `backend/services/churn_prevention.py` | Retention logic |

---

## Summary: Files to Create

### Frontend Components
| # | File | Feature |
|---|------|---------|
| 1 | `DogfoodingBanner.tsx` | Dogfooding Banner |
| 2 | `FirstVictoryCelebration.tsx` | First Victory |
| 3 | `SavingsCounter.tsx` | Animated savings counter |
| 4 | `GrowthNudge.tsx` | Growth nudge alert |
| 5 | `GrowthNudgeCard.tsx` | Card variant |
| 6 | `FeatureDiscoveryTeaser.tsx` | Feature teaser |
| 7 | `TimeSavingsCalculator.tsx` | Time calculator |
| 8 | `ContextualHelp.tsx` | Help widget |
| 9 | `HelpGifViewer.tsx` | GIF viewer |
| 10 | `CancellationFlow.tsx` | Cancellation flow |
| 11 | `CancellationOption.tsx` | Cancel option |
| 12 | `ROIDisplay.tsx` | ROI display |
| 13 | `TrainingOffer.tsx` | Training offer |
| 14 | `IntegrationsRoadmap.tsx` | Roadmap |

### Backend Services
| # | File | Feature |
|---|------|---------|
| 1 | `first_victory_tracker.py` | First victory tracking |
| 2 | `growth_nudge_monitor.py` | Growth monitoring |
| 3 | `growth_nudge_worker.py` | Background worker |
| 4 | `feature_discovery.py` | Discovery detection |
| 5 | `churn_prevention.py` | Retention logic |

### Backend API Routes
| # | File | Feature |
|---|------|---------|
| 1 | `first_victory.py` | First victory API |
| 2 | `cancellation.py` | Cancellation API |

### Hooks
| # | File | Feature |
|---|------|---------|
| 1 | `useFirstVictory.ts` | First victory logic |
| 2 | `useContextualHelp.ts` | Help context |

### Data Files
| # | File | Feature |
|---|------|---------|
| 1 | `helpContent.ts` | Help content config |
| 2 | `public/help-gifs/*.gif` | GIF demos |

---

## Total: 26 New Files

- **Frontend Components:** 14 files
- **Backend Services:** 5 files
- **Backend API Routes:** 2 files
- **Hooks:** 2 files
- **Data/Assets:** 3+ files
