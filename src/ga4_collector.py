"""
ga4_collector.py — Pulls website analytics from Google Analytics 4 (GA4)
via the Google Analytics Data API.

Produces one dataset:
  web_pulse — weekly website metrics (one row per week)

Metrics collected:
  Users:       totalUsers, newUsers, returningUsers
  Sessions:    sessions
  Acquisition: organic search, direct, social, referral user counts
  Engagement:  engagementRate, averageSessionDuration
  Top pages:   top landing page by sessions + its engagement rate
  Devices:     mobile, desktop, tablet user counts
  Location:    top US states by users (filters out non-US traffic)

Auth note:
  Uses the same Google service account as the Sheets integration.
  The service account must be added as a Viewer in GA4 Admin.
"""

from datetime import datetime
from typing import Any

from google.oauth2.service_account import Credentials
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Metric,
    Dimension,
    FilterExpression,
    Filter,
)

import config


def _get_client() -> BetaAnalyticsDataClient:
    creds = Credentials.from_service_account_info(
        config.GOOGLE_SERVICE_ACCOUNT_JSON,
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
    )
    return BetaAnalyticsDataClient(credentials=creds)


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Core report runner
# ---------------------------------------------------------------------------

def _run_report(
    client: BetaAnalyticsDataClient,
    start: datetime,
    end: datetime,
    metrics: list[str],
    dimensions: list[str] | None = None,
    dimension_filter: FilterExpression | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Run a GA4 report and return rows as a list of dicts.
    Results are returned in GA4's default order then sorted in Python.
    """
    request = RunReportRequest(
        property=f"properties/{config.GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=_date_str(start), end_date=_date_str(end))],
        metrics=[Metric(name=m) for m in metrics],
        dimensions=[Dimension(name=d) for d in (dimensions or [])],
        dimension_filter=dimension_filter,
        limit=limit,
    )
    response = client.run_report(request)

    rows = []
    for row in response.rows:
        r = {}
        for i, dim in enumerate(response.dimension_headers):
            r[dim.name] = row.dimension_values[i].value
        for i, met in enumerate(response.metric_headers):
            r[met.name] = row.metric_values[i].value
        rows.append(r)
    return rows


def _sort_by(rows: list[dict], metric: str) -> list[dict]:
    """Sort rows by a metric descending — done in Python to avoid OrderBy API quirks."""
    return sorted(rows, key=lambda r: float(r.get(metric, 0)), reverse=True)


# ---------------------------------------------------------------------------
# Individual metric collectors
# ---------------------------------------------------------------------------

def _get_user_metrics(client, start, end) -> dict:
    """Total, new, and returning users plus session/engagement metrics."""
    rows = _run_report(
        client, start, end,
        metrics=["totalUsers", "newUsers", "sessions",
                 "engagementRate", "averageSessionDuration"],
    )
    if not rows:
        return {}
    r = rows[0]
    total = int(float(r.get("totalUsers", 0)))
    new = int(float(r.get("newUsers", 0)))
    returning = max(0, total - new)
    eng_rate = round(float(r.get("engagementRate", 0)) * 100, 1)
    avg_duration = round(float(r.get("averageSessionDuration", 0)))

    return {
        "total_users": total,
        "new_users": new,
        "returning_users": returning,
        "sessions": int(float(r.get("sessions", 0))),
        "engagement_rate_pct": eng_rate,
        "avg_session_duration_sec": avg_duration,
    }


def _get_acquisition(client, start, end) -> dict:
    """Users by traffic source (organic, direct, social, referral)."""
    rows = _run_report(
        client, start, end,
        metrics=["totalUsers"],
        dimensions=["sessionDefaultChannelGroup"],
        limit=20,
    )
    rows = _sort_by(rows, "totalUsers")

    source_map = {
        "organic search": "organic_users",
        "direct": "direct_users",
        "organic social": "social_users",
        "referral": "referral_users",
    }
    result = {v: 0 for v in source_map.values()}
    top_source = None
    top_source_users = 0

    for row in rows:
        channel = row.get("sessionDefaultChannelGroup", "").lower()
        users = int(float(row.get("totalUsers", 0)))
        for key, col in source_map.items():
            if key in channel:
                result[col] += users
                break
        if users > top_source_users:
            top_source_users = users
            top_source = row.get("sessionDefaultChannelGroup", "")

    result["top_traffic_source"] = top_source
    return result


def _get_top_page(client, start, end) -> dict:
    """Top landing page by sessions with its engagement rate."""
    rows = _run_report(
        client, start, end,
        metrics=["sessions", "engagementRate"],
        dimensions=["landingPage"],
        limit=10,
    )
    rows = _sort_by(rows, "sessions")

    if not rows:
        return {
            "top_landing_page": None,
            "top_page_sessions": None,
            "top_page_engagement_rate_pct": None,
        }
    r = rows[0]
    return {
        "top_landing_page": r.get("landingPage"),
        "top_page_sessions": int(float(r.get("sessions", 0))),
        "top_page_engagement_rate_pct": round(float(r.get("engagementRate", 0)) * 100, 1),
    }


def _get_device_breakdown(client, start, end) -> dict:
    """Users by device category."""
    rows = _run_report(
        client, start, end,
        metrics=["totalUsers"],
        dimensions=["deviceCategory"],
        limit=10,
    )
    result = {"mobile_users": 0, "desktop_users": 0, "tablet_users": 0}
    for row in rows:
        device = row.get("deviceCategory", "").lower()
        users = int(float(row.get("totalUsers", 0)))
        if device == "mobile":
            result["mobile_users"] = users
        elif device == "desktop":
            result["desktop_users"] = users
        elif device == "tablet":
            result["tablet_users"] = users
    return result


def _get_top_locations(client, start, end, limit: int = 5) -> list[dict]:
    """Top US regions by users."""
    us_filter = FilterExpression(
        filter=Filter(
            field_name="country",
            string_filter=Filter.StringFilter(value="United States"),
        )
    )
    rows = _run_report(
        client, start, end,
        metrics=["totalUsers"],
        dimensions=["region"],
        dimension_filter=us_filter,
        limit=20,
    )
    rows = _sort_by(rows, "totalUsers")[:limit]
    return [
        {"region": r.get("region"), "users": int(float(r.get("totalUsers", 0)))}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Main collector
# ---------------------------------------------------------------------------

def collect_web_pulse(week_start: datetime, week_end: datetime) -> dict[str, Any]:
    """Collect weekly website metrics for web_pulse tab."""
    print("  Fetching GA4 metrics...")
    client = _get_client()

    user_metrics = _get_user_metrics(client, week_start, week_end)
    acquisition = _get_acquisition(client, week_start, week_end)
    top_page = _get_top_page(client, week_start, week_end)
    devices = _get_device_breakdown(client, week_start, week_end)
    locations = _get_top_locations(client, week_start, week_end)

    top_locations_str = ", ".join(
        f"{l['region']} ({l['users']})" for l in locations if l.get("region")
    ) or None

    return {
        "week_end_date": week_end.strftime("%Y-%m-%d"),
        **user_metrics,
        **acquisition,
        **top_page,
        **devices,
        "top_us_regions": top_locations_str,
    }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

WEB_PULSE_HEADERS = [
    "week_end_date",
    "total_users",
    "new_users",
    "returning_users",
    "sessions",
    "engagement_rate_pct",
    "avg_session_duration_sec",
    "organic_users",
    "direct_users",
    "social_users",
    "referral_users",
    "top_traffic_source",
    "top_landing_page",
    "top_page_sessions",
    "top_page_engagement_rate_pct",
    "mobile_users",
    "desktop_users",
    "tablet_users",
    "top_us_regions",
]


def row_to_list(data: dict, headers: list[str]) -> list[Any]:
    return [data.get(h) for h in headers]