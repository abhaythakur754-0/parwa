# Known Issues - PARWA Week 19

**Last Updated:** 2026-03-23

---

## Active Issues

### HIGH Priority

#### 1. Tracking Number Confusion
- **ID:** ISSUE-001
- **Status:** Open
- **Severity:** High
- **Description:** AI confuses similar tracking numbers when multiple packages exist
- **Workaround:** Verify tracking numbers manually for multi-package orders
- **Fix Timeline:** Week 20
- **Affected Components:** Shipping module

#### 2. Inventory Sync Delays
- **ID:** ISSUE-002
- **Status:** Open
- **Severity:** High
- **Description:** Stock status shows incorrect for recently sold-out items
- **Workaround:** Check product page for real-time availability
- **Fix Timeline:** Week 20
- **Affected Components:** Product catalog, Knowledge base

### MEDIUM Priority

#### 3. Return Policy Edge Cases
- **ID:** ISSUE-003
- **Status:** Open
- **Severity:** Medium
- **Description:** AI misses 30-day window exceptions for damaged items
- **Workaround:** Escalate damaged item returns to human agent
- **Fix Timeline:** Week 21
- **Affected Components:** Policy handler

#### 4. Order Modification Confusion
- **ID:** ISSUE-004
- **Status:** Open
- **Severity:** Medium
- **Description:** Incorrect information about modifying orders after shipment
- **Workaround:** Check order status before providing modification info
- **Fix Timeline:** Week 21
- **Affected Components:** Order handler

### LOW Priority

#### 5. International Shipping Coverage
- **ID:** ISSUE-005
- **Status:** Open
- **Severity:** Low
- **Description:** FAQ lacks international shipping details
- **Workaround:** Add FAQ entries manually
- **Fix Timeline:** Week 22
- **Affected Components:** Knowledge base

---

## Resolved Issues

#### R1. Cross-Tenant Data Leak (FIXED)
- **ID:** ISSUE-R1
- **Status:** Resolved
- **Severity:** Critical
- **Description:** Potential cross-tenant data exposure in shadow mode
- **Resolution:** Added tenant isolation checks
- **Resolved Date:** 2026-03-22

#### R2. Memory Leak in Long Sessions (FIXED)
- **ID:** ISSUE-R2
- **Status:** Resolved
- **Severity:** High
- **Description:** Memory usage grew during extended shadow mode sessions
- **Resolution:** Implemented periodic cleanup
- **Resolved Date:** 2026-03-21

---

## Known Limitations

1. **Gift Card Support:** Not yet implemented
2. **Loyalty Program:** Knowledge base missing
3. **Voice Support:** Disabled for this client
4. **Multi-language:** English only currently

---

## Reporting New Issues

To report a new issue:
1. Use the error tracker: `clients/error_tracker.py`
2. Include severity, context, and reproduction steps
3. Submit to GitHub issues with label `bug`

---

## Issue Metrics

| Metric | Value |
|--------|-------|
| Total Active Issues | 5 |
| High Severity | 2 |
| Medium Severity | 2 |
| Low Severity | 1 |
| Resolved This Week | 2 |
