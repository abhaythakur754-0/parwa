# Shadow Mode Day 7 Gap Analysis — Onboarding Stage 0 Enforcer

> **Analysis Date:** April 17, 2026
> **Part:** Part 11 (Shadow Mode) - Day 7
> **Focus:** Stage 0 Enforcement, Onboarding Step, Graduation Celebration, Safety Floor UI

---

## Executive Summary

Day 7 of Shadow Mode implementation focuses on forcing new clients into Shadow Mode for their first N actions and providing onboarding UI components for the shadow mode experience.

| Component | Status | Notes |
|-----------|--------|-------|
| B7.1 — Stage 0 Shadow Enforcement | ✅ Complete | Backend logic in shadow_mode_service.py |
| B7.2 — Onboarding Flow Updates | ⏳ Partial | Need ShadowModeStep component |
| B7.3 — Shadow Mode Onboarding Component | ❌ Missing | Need ShadowModeStep.tsx |
| B7.4 — Graduation Celebration Modal | ❌ Missing | Need ShadowGraduationModal.tsx |
| B7.5 — Safety Floor UI Indicator | ✅ Complete | Already implemented |

**Overall Day 7 Status: 60% Complete (2 of 5 components missing)**

---

## Component Analysis

### B7.1 — Stage 0 Shadow Enforcement

**File:** `backend/app/services/shadow_mode_service.py`

**Status: ✅ Complete**

The Stage 0 enforcement is fully implemented:

```python
# Lines 277-293: Stage 0 check in evaluate_action_risk()
shadow_remaining = getattr(company, "shadow_actions_remaining", None)
if shadow_remaining and shadow_remaining > 0:
    # Force shadow mode for Stage 0 onboarding
    return {
        "mode": "shadow",
        "requires_approval": True,
        "reason": f"Stage 0 onboarding: {shadow_remaining} shadow actions remaining",
        "layers": {
            "layer1_heuristic": {"score": 0.5, "reason": "Stage 0 forced"},
            "layer2_preference": {"mode": None, "reason": "Stage 0 override"},
            "layer3_historical": {"avg_risk": None, "reason": "Stage 0 override"},
            "layer4_safety_floor": {"hard_safety": True, "reason": "Stage 0 override"},
        },
    }
```

**Decrement Logic (Lines 668-677):**
```python
# Decrement shadow_actions_remaining for Stage 0
remaining = getattr(company, "shadow_actions_remaining", None)
if remaining and remaining > 0:
    company.shadow_actions_remaining = remaining - 1
```

**Database Field:** `database/models/core.py` line 60:
```python
shadow_actions_remaining = Column(Integer, default=10)
```

**Migration:** `database/alembic/versions/027_shadow_mode_config.py` adds the column.

---

### B7.2 — Onboarding Flow Updates

**Status: ⏳ Partial**

Current onboarding wizard has 5 steps:
1. Welcome
2. LegalCompliance
3. IntegrationSetup
4. KnowledgeUpload
5. AIConfig

**Missing:** A dedicated Shadow Mode explanation step should be added after AI activation.

---

### B7.3 — Shadow Mode Onboarding Component

**File:** `frontend/src/components/onboarding/ShadowModeStep.tsx`

**Status: ❌ Missing**

**Required Features:**
- [ ] Animated explanation of Shadow Mode
- [ ] Visual: "You're in the driver's seat" metaphor
- [ ] Progress bar: "X actions until graduation"
- [ ] Sample actions preview (what you'll approve)
- [ ] "Skip explanation" option
- [ ] Real-time shadow_actions_remaining display

---

### B7.4 — Graduation Celebration Modal

**File:** `frontend/src/components/onboarding/ShadowGraduationModal.tsx`

**Status: ❌ Missing**

**Required Features:**
- [ ] Confetti animation
- [ ] "You've graduated to Supervised mode!" message
- [ ] Explanation of what changed
- [ ] Option to stay in Shadow mode longer
- [ ] "Continue" button

---

### B7.5 — Safety Floor UI Indicator

**Status: ✅ Complete**

Safety floor indicators are already implemented in multiple locations:

**1. ApprovalDetailModal.tsx (Lines 447-458):**
```tsx
{/* Layer 4: Safety Floor */}
<span className="text-xs font-medium text-zinc-400">Layer 4: Safety Floor</span>
<span className={
  riskEvaluation.layers.layer4_safety_floor.hard_safety ? 'text-red-400' : 'text-emerald-400'
}>
  {riskEvaluation.layers.layer4_safety_floor.hard_safety ? 'BLOCKED' : 'PASSED'}
</span>
```

**2. ShadowModeSettings.tsx (Lines 461-462):**
```tsx
<SectionCard title="Hard Safety Floor" icon={<ExclamationTriangleIcon />}>
  {/* Lists actions that are ALWAYS supervised */}
</SectionCard>
```

**3. WhatIfSimulator.tsx (Line 386):**
```tsx
<p className="text-[10px] font-semibold text-[#FF7F11] uppercase tracking-wider mb-1">
  Layer 4: Safety Floor
</p>
<p className="text-xs text-zinc-400">
  Hard safety rules are always enforced regardless of mode...
</p>
```

---

## Database Schema

| Table | Column | Type | Default | Status |
|-------|--------|------|---------|--------|
| companies | shadow_actions_remaining | Integer | 10 | ✅ Exists |
| companies | system_mode | String(15) | 'supervised' | ✅ Exists |

---

## Gap Summary

| Gap | Severity | Resolution |
|-----|----------|------------|
| Missing ShadowModeStep.tsx | High | Create new component |
| Missing ShadowGraduationModal.tsx | Medium | Create new component |
| No integration in OnboardingWizard | Medium | Add step after AI activation |

---

## Implementation Plan

### 1. Create ShadowModeStep.tsx
- Add as optional Step 6 in onboarding (or integrate into Welcome step)
- Show shadow mode explanation with animations
- Display shadow_actions_remaining counter
- Add "Learn More" link to docs

### 2. Create ShadowGraduationModal.tsx
- Trigger when shadow_actions_remaining reaches 0
- Show confetti celebration
- Explain graduation to Supervised mode
- Allow user to opt-out and stay in Shadow

### 3. Update OnboardingWizard.tsx
- Integrate ShadowModeStep after AIConfig
- Handle graduation modal trigger
- Add WebSocket listener for graduation event

---

## Files to Create

1. `frontend/src/components/onboarding/ShadowModeStep.tsx`
2. `frontend/src/components/onboarding/ShadowGraduationModal.tsx`

## Files to Modify

1. `frontend/src/components/onboarding/OnboardingWizard.tsx` - Add shadow step
2. `frontend/src/components/onboarding/index.ts` - Export new components

---

*End of Day 7 Gap Analysis*
