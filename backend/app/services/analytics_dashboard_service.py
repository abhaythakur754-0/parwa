"""
PARWA Analytics Dashboard Service (F-115, F-116, F-119)

Service functions for dashboard analytics endpoints:
- F-115: Confidence Trend — AI confidence score tracking
- F-116: Drift Reports — Model performance drift detection
- F-119: QA Scores — Response quality assessment scores

Building Codes: BC-001 (multi-tenant), BC-007 (AI model), BC-012 (error handling)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from database.models.analytics import DriftReport, QAScore
from database.models.tickets import TicketMessage

logger = get_logger("analytics_dashboard_service")

# ══════════════════════════════════════════════════════════════════
# DEFAULTS
# ══════════════════════════════════════════════════════════════════

LOW_CONFIDENCE_THRESHOLD = 0.6
CRITICAL_THRESHOLD = 0.4
QA_PASS_THRESHOLD = 0.7

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "low": 3}


# ══════════════════════════════════════════════════════════════════
# F-115: CONFIDENCE TREND
# ══════════════════════════════════════════════════════════════════


def get_confidence_trend(
    company_id: str,
    db: Session,
    days: int = 30,
) -> Dict[str, Any]:
    """Get AI confidence trend over time.

    Aggregates TicketMessage.ai_confidence scores grouped by day,
    calculates distribution buckets, and determines trend direction.

    F-115: Confidence Trend
    BC-001: Scoped by company_id.
    BC-007: AI confidence metrics.
    """
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        # Fetch all AI messages with confidence in the period
        rows = (
            db.query(
                func.date(TicketMessage.created_at).label("day"),
                TicketMessage.ai_confidence,
            )
            .filter(
                TicketMessage.company_id == company_id,
                TicketMessage.role == "ai",
                TicketMessage.ai_confidence.isnot(None),
                TicketMessage.created_at >= start,
                TicketMessage.created_at < now,
            )
            .all()
        )

        # Group by day
        day_map: Dict[str, List[float]] = {}
        for row in rows:
            day_str = str(row.day)
            conf_val = float(row.ai_confidence)
            if day_str not in day_map:
                day_map[day_str] = []
            day_map[day_str].append(conf_val)

        # Build daily trend
        daily_trend: List[Dict[str, Any]] = []
        all_confidences: List[float] = []

        for i in range(days):
            day_date = (start + timedelta(days=i)).date()
            day_str = str(day_date)
            scores = day_map.get(day_str, [])

            if scores:
                avg_conf = round(sum(scores) / len(scores), 2)
                min_conf = round(min(scores), 2)
                max_conf = round(max(scores), 2)
                low_count = sum(1 for s in scores if s < LOW_CONFIDENCE_THRESHOLD)
            else:
                avg_conf = 0.0
                min_conf = 0.0
                max_conf = 0.0
                low_count = 0

            daily_trend.append(
                {
                    "date": day_date.strftime("%Y-%m-%d"),
                    "avg_confidence": avg_conf,
                    "min_confidence": min_conf,
                    "max_confidence": max_conf,
                    "total_predictions": len(scores),
                    "low_confidence_count": low_count,
                }
            )

            all_confidences.extend(scores)

        # Overall stats
        total_predictions = len(all_confidences)
        overall_avg = (
            round(sum(all_confidences) / total_predictions, 2)
            if total_predictions > 0
            else 0.0
        )
        current_avg = 0.0
        for entry in reversed(daily_trend):
            if entry["avg_confidence"] > 0:
                current_avg = entry["avg_confidence"]
                break

        # Distribution buckets
        distribution = _compute_confidence_distribution(
            all_confidences, total_predictions
        )

        # Trend direction: compare second half vs first half
        trend_direction, change_vs_previous = _compute_trend(
            daily_trend, days, "avg_confidence"
        )

        return {
            "daily_trend": daily_trend,
            "current_avg": current_avg,
            "overall_avg": overall_avg,
            "trend_direction": trend_direction,
            "change_vs_previous_period": change_vs_previous,
            "distribution": distribution,
            "low_confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
            "critical_threshold": CRITICAL_THRESHOLD,
            "total_predictions": total_predictions,
        }

    except Exception as exc:
        logger.error(
            "confidence_trend_error",
            company_id=company_id,
            error=str(exc),
        )
        return _empty_confidence_response()


def _compute_confidence_distribution(
    confidences: List[float],
    total: int,
) -> List[Dict[str, Any]]:
    """Compute confidence distribution into buckets."""
    buckets = [
        ("0-20", 0),
        ("20-40", 0),
        ("40-60", 0),
        ("60-80", 0),
        ("80-100", 0),
    ]

    for c in confidences:
        # c is 0.0 to 1.0; convert to 0-100
        pct = c * 100
        if pct < 20:
            buckets[0] = (buckets[0][0], buckets[0][1] + 1)
        elif pct < 40:
            buckets[1] = (buckets[1][0], buckets[1][1] + 1)
        elif pct < 60:
            buckets[2] = (buckets[2][0], buckets[2][1] + 1)
        elif pct < 80:
            buckets[3] = (buckets[3][0], buckets[3][1] + 1)
        else:
            buckets[4] = (buckets[4][0], buckets[4][1] + 1)

    return [
        {
            "range": label,
            "count": count,
            "percentage": round((count / total) * 100, 1) if total > 0 else 0.0,
        }
        for label, count in buckets
    ]


def _empty_confidence_response() -> Dict[str, Any]:
    """Return an empty confidence trend response."""
    return {
        "daily_trend": [],
        "current_avg": 0.0,
        "overall_avg": 0.0,
        "trend_direction": "stable",
        "change_vs_previous_period": 0.0,
        "distribution": [
            {"range": "0-20", "count": 0, "percentage": 0.0},
            {"range": "20-40", "count": 0, "percentage": 0.0},
            {"range": "40-60", "count": 0, "percentage": 0.0},
            {"range": "60-80", "count": 0, "percentage": 0.0},
            {"range": "80-100", "count": 0, "percentage": 0.0},
        ],
        "low_confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
        "critical_threshold": CRITICAL_THRESHOLD,
        "total_predictions": 0,
    }


# ══════════════════════════════════════════════════════════════════
# F-116: DRIFT REPORTS
# ══════════════════════════════════════════════════════════════════


def get_drift_reports(
    company_id: str,
    db: Session,
    limit: int = 20,
) -> Dict[str, Any]:
    """Get drift detection reports for model performance monitoring.

    Queries the DriftReport table and maps DB fields to the
    frontend-expected response format.

    F-116: Drift Reports
    BC-001: Scoped by company_id.
    BC-007: AI model drift metrics.
    """
    try:
        # Fetch recent drift reports
        reports = (
            db.query(DriftReport)
            .filter(
                DriftReport.company_id == company_id,
            )
            .order_by(
                desc(DriftReport.report_date),
            )
            .limit(limit)
            .all()
        )

        mapped_reports: List[Dict[str, Any]] = []
        active_count = 0
        last_detected_at: Optional[str] = None
        most_severe_rank = 999
        most_severe: Optional[str] = None

        for r in reports:
            # Map DB fields to frontend-expected names
            severity = str(r.severity or "info").lower()
            if severity == "low":
                severity = "info"

            report_date = r.report_date or r.created_at
            if report_date:
                detected_at = report_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                detected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            mapped_reports.append(
                {
                    "report_id": str(r.id),
                    "detected_at": detected_at,
                    "severity": severity,
                    "metric_name": str(r.metric_type or ""),
                    "metric_value": (
                        float(r.current_value) if r.current_value is not None else 0.0
                    ),
                    "baseline_value": (
                        float(r.baseline_value) if r.baseline_value is not None else 0.0
                    ),
                    "drift_pct": float(r.drift_pct) if r.drift_pct is not None else 0.0,
                    "description": f"Drift detected in {r.metric_type or 'unknown metric'} "
                    f"(current: {r.current_value or 0}, baseline: {r.baseline_value or 0})",
                    "status": "active",
                    "resolved_at": None,
                    "recovery_action": None,
                }
            )

            # Track active count (all reports without resolved status are
            # "active")
            active_count += 1

            # Track last detected
            if last_detected_at is None or detected_at > last_detected_at:
                last_detected_at = detected_at

            # Track most severe
            rank = SEVERITY_ORDER.get(severity, 99)
            if rank < most_severe_rank:
                most_severe_rank = rank
                most_severe = severity

        total = len(mapped_reports)

        return {
            "reports": mapped_reports,
            "total": total,
            "active_count": active_count,
            "last_detected_at": last_detected_at,
            "most_severe": most_severe,
        }

    except Exception as exc:
        logger.error(
            "drift_reports_error",
            company_id=company_id,
            error=str(exc),
        )
        return _empty_drift_response()


def _empty_drift_response() -> Dict[str, Any]:
    """Return an empty drift reports response."""
    return {
        "reports": [],
        "total": 0,
        "active_count": 0,
        "last_detected_at": None,
        "most_severe": None,
    }


# ══════════════════════════════════════════════════════════════════
# F-119: QA SCORES
# ══════════════════════════════════════════════════════════════════


def get_qa_scores(
    company_id: str,
    db: Session,
    days: int = 30,
) -> Dict[str, Any]:
    """Get QA scores — response quality assessment over time.

    Queries QAScore table grouped by day, computes dimension
    averages and pass rates, and determines trend direction.

    F-119: QA Scores
    BC-001: Scoped by company_id.
    BC-007: AI quality metrics.
    """
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        # Fetch all QA scores in the period
        rows = (
            db.query(
                func.date(QAScore.created_at).label("day"),
                QAScore.accuracy,
                QAScore.tone,
                QAScore.completeness,
                QAScore.overall,
            )
            .filter(
                QAScore.company_id == company_id,
                QAScore.created_at >= start,
                QAScore.created_at < now,
            )
            .all()
        )

        # Group by day
        day_map: Dict[str, List[Dict[str, Optional[float]]]] = {}
        for row in rows:
            day_str = str(row.day)
            if day_str not in day_map:
                day_map[day_str] = []
            day_map[day_str].append(
                {
                    "accuracy": (
                        float(row.accuracy) if row.accuracy is not None else None
                    ),
                    "tone": float(row.tone) if row.tone is not None else None,
                    "completeness": (
                        float(row.completeness)
                        if row.completeness is not None
                        else None
                    ),
                    "overall": float(row.overall) if row.overall is not None else None,
                }
            )

        # Build daily trend
        daily_trend: List[Dict[str, Any]] = []
        total_evaluated = 0
        total_pass_count = 0
        all_accuracy: List[float] = []
        all_tone: List[float] = []
        all_completeness: List[float] = []
        all_overall: List[float] = []

        for i in range(days):
            day_date = (start + timedelta(days=i)).date()
            day_str = str(day_date)
            entries = day_map.get(day_str, [])

            if entries:
                acc_scores = [
                    e["accuracy"] for e in entries if e["accuracy"] is not None
                ]
                tone_scores = [e["tone"] for e in entries if e["tone"] is not None]
                comp_scores = [
                    e["completeness"] for e in entries if e["completeness"] is not None
                ]
                overall_scores = [
                    e["overall"] for e in entries if e["overall"] is not None
                ]

                acc_avg = (
                    round(sum(acc_scores) / len(acc_scores), 2) if acc_scores else 0.0
                )
                tone_avg = (
                    round(sum(tone_scores) / len(tone_scores), 2)
                    if tone_scores
                    else 0.0
                )
                comp_avg = (
                    round(sum(comp_scores) / len(comp_scores), 2)
                    if comp_scores
                    else 0.0
                )
                overall_avg = (
                    round(sum(overall_scores) / len(overall_scores), 2)
                    if overall_scores
                    else 0.0
                )
                pass_count = sum(1 for o in overall_scores if o >= QA_PASS_THRESHOLD)

                all_accuracy.extend(acc_scores)
                all_tone.extend(tone_scores)
                all_completeness.extend(comp_scores)
                all_overall.extend(overall_scores)
            else:
                acc_avg = 0.0
                tone_avg = 0.0
                comp_avg = 0.0
                overall_avg = 0.0
                pass_count = 0

            day_count = len(entries)
            total_evaluated += day_count
            total_pass_count += pass_count

            daily_trend.append(
                {
                    "date": day_date.strftime("%Y-%m-%d"),
                    "overall_score": overall_avg,
                    "accuracy_score": acc_avg,
                    "completeness_score": comp_avg,
                    "tone_score": tone_avg,
                    "relevance_score": 0.0,  # No relevance field in DB model
                    "total_evaluated": day_count,
                    "pass_count": pass_count,
                }
            )

        # Overall averages
        overall_avg_score = (
            round(sum(all_overall) / len(all_overall), 2) if all_overall else 0.0
        )
        current_overall = 0.0
        for entry in reversed(daily_trend):
            if entry["overall_score"] > 0:
                current_overall = entry["overall_score"]
                break

        pass_rate = (
            round(total_pass_count / total_evaluated, 2) if total_evaluated > 0 else 0.0
        )

        # Dimension summaries
        dimensions = [
            {
                "dimension_name": "Accuracy",
                "avg_score": (
                    round(sum(all_accuracy) / len(all_accuracy), 2)
                    if all_accuracy
                    else 0.0
                ),
                "pass_rate": (
                    round(
                        sum(1 for s in all_accuracy if s >= QA_PASS_THRESHOLD)
                        / len(all_accuracy),
                        2,
                    )
                    if all_accuracy
                    else 0.0
                ),
                "trend": _dimension_trend(daily_trend, "accuracy_score"),
            },
            {
                "dimension_name": "Completeness",
                "avg_score": (
                    round(sum(all_completeness) / len(all_completeness), 2)
                    if all_completeness
                    else 0.0
                ),
                "pass_rate": (
                    round(
                        sum(1 for s in all_completeness if s >= QA_PASS_THRESHOLD)
                        / len(all_completeness),
                        2,
                    )
                    if all_completeness
                    else 0.0
                ),
                "trend": _dimension_trend(daily_trend, "completeness_score"),
            },
            {
                "dimension_name": "Tone",
                "avg_score": (
                    round(sum(all_tone) / len(all_tone), 2) if all_tone else 0.0
                ),
                "pass_rate": (
                    round(
                        sum(1 for s in all_tone if s >= QA_PASS_THRESHOLD)
                        / len(all_tone),
                        2,
                    )
                    if all_tone
                    else 0.0
                ),
                "trend": _dimension_trend(daily_trend, "tone_score"),
            },
            {
                "dimension_name": "Relevance",
                "avg_score": 0.0,
                "pass_rate": 0.0,
                "trend": "stable",
            },
        ]

        # Overall trend direction
        trend_direction, change_vs_previous = _compute_trend(
            daily_trend, days, "overall_score"
        )

        return {
            "daily_trend": daily_trend,
            "current_overall": current_overall,
            "overall_avg": overall_avg_score,
            "pass_rate": pass_rate,
            "total_evaluated": total_evaluated,
            "dimensions": dimensions,
            "trend_direction": trend_direction,
            "change_vs_previous_period": change_vs_previous,
            "threshold_pass": QA_PASS_THRESHOLD,
        }

    except Exception as exc:
        logger.error(
            "qa_scores_error",
            company_id=company_id,
            error=str(exc),
        )
        return _empty_qa_response()


def _dimension_trend(
    daily_trend: List[Dict[str, Any]],
    score_key: str,
) -> str:
    """Determine trend direction for a specific dimension.

    Compares the average of the second half of the period
    against the first half.
    """
    valid_entries = [e for e in daily_trend if e.get(score_key, 0) > 0]
    if len(valid_entries) < 4:
        return "stable"

    mid = len(valid_entries) // 2
    first_half = valid_entries[:mid]
    second_half = valid_entries[mid:]

    first_avg = sum(e[score_key] for e in first_half) / len(first_half)
    second_avg = sum(e[score_key] for e in second_half) / len(second_half)

    if first_avg == 0:
        return "stable"

    change = (second_avg - first_avg) / first_avg
    if change > 0.02:
        return "improving"
    elif change < -0.02:
        return "declining"
    return "stable"


def _compute_trend(
    daily_trend: List[Dict[str, Any]],
    days: int,
    score_key: str,
) -> tuple:
    """Compute overall trend direction and change percentage.

    Compares the second half of the period against the first half.
    Returns (trend_direction, change_vs_previous_period).
    """
    valid_entries = [e for e in daily_trend if e.get(score_key, 0) > 0]
    if len(valid_entries) < 4:
        return "stable", 0.0

    mid = len(valid_entries) // 2
    first_half = valid_entries[:mid]
    second_half = valid_entries[mid:]

    first_avg = sum(e[score_key] for e in first_half) / len(first_half)
    second_avg = sum(e[score_key] for e in second_half) / len(second_half)

    if first_avg == 0:
        return "stable", 0.0

    change = round((second_avg - first_avg) / first_avg, 2)

    if change > 0.02:
        return "improving", change
    elif change < -0.02:
        return "declining", change
    return "stable", change


def _empty_qa_response() -> Dict[str, Any]:
    """Return an empty QA scores response."""
    return {
        "daily_trend": [],
        "current_overall": 0.0,
        "overall_avg": 0.0,
        "pass_rate": 0.0,
        "total_evaluated": 0,
        "dimensions": [
            {
                "dimension_name": "Accuracy",
                "avg_score": 0.0,
                "pass_rate": 0.0,
                "trend": "stable",
            },
            {
                "dimension_name": "Completeness",
                "avg_score": 0.0,
                "pass_rate": 0.0,
                "trend": "stable",
            },
            {
                "dimension_name": "Tone",
                "avg_score": 0.0,
                "pass_rate": 0.0,
                "trend": "stable",
            },
            {
                "dimension_name": "Relevance",
                "avg_score": 0.0,
                "pass_rate": 0.0,
                "trend": "stable",
            },
        ],
        "trend_direction": "stable",
        "change_vs_previous_period": 0.0,
        "threshold_pass": QA_PASS_THRESHOLD,
    }
