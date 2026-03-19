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

Conversion metrics are intentionally excluded until GA4 conversions
are configured. Add them here once set up — see SETUP.md.

Auth note:
  Uses the same Google service account as the Sheets integration.
  The service account must be added as a Viewer in GA4 Admin — see SETUP.md.
"""

from datetime import datetime, timedelta, timezone
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
    OrderBy,
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
    order_bys: list[OrderBy] | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Run a GA4 report and return rows as a list of dicts.
    Keys are dimension/metric names, values are strings (GA4 always returns strings).
    """
    request = RunReportRequest(
        property=f"properties/{config.GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=_date_str(start), end_date=_date_str(end))],
        metrics=[Metric(name=m) for m in metrics],
        dimensions=[Dimension(name=d) for d in (dimensions or [])],
        dimension_filter=dimension_filter,
        order_bys=order_bys or [],
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


# ---------------------------------------------------------------------------
# Individual metric collectors
# ---------------------------------------------------------------------------

def _get_user_metrics(client, start, end) -> dict:
    """Total, new, and returning users."""
    rows = _run_report(
        client, start, end,
        metrics=["totalUsers", "newUsers", "sessions", "engagementRate",
                 "averageSessionDuration"],
    )
    if not rows:
        return {}
    r = rows[0]
    total = int(r.get("totalUsers", 0))
    new = int(r.get("newUsers", 0))
    returning = max(0, total - new)
    eng_rate = round(float(r.get("engagementRate", 0)) * 100, 1)
    avg_duration = round(float(r.get("averageSessionDuration", 0)))

    return {
        "total_users": total,
        "new_users": new,
        "returning_users": returning,
        "sessions": int(r.get("sessions", 0)),
        "engagement_rate_pct": eng_rate,
        "avg_session_duration_sec": avg_duration,
    }


def _get_acquisition(client, start, end) -> dict:
    """Users by traffic source (organic, direct, social, referral)."""
    rows = _run_report(
        client, start, end,
        metrics=["totalUsers"],
        dimensions=["sessionDefaultChannelGroup"],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="totalUsers"), descending=True)],
        limit=10,
    )

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
        users = int(row.get("totalUsers", 0))
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
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), descending=True)],
        limit=1,
    )
    if not rows:
        return {"top_landing_page": None, "top_page_sessions": None,
                "top_page_engagement_rate_pct": None}
    r = rows[0]
    return {
        "top_landing_page": r.get("landingPage"),
        "top_page_sessions": int(r.get("sessions", 0)),
        "top_page_engagement_rate_pct": round(float(r.get("engagementRate", 0)) * 100, 1),
    }


def _get_device_breakdown(client, start, end) -> dict:
    """Users by device category (mobile, desktop, tablet)."""
    rows = _run_report(
        client, start, end,
        metrics=["totalUsers"],
        dimensions=["deviceCategory"],
        limit=10,
    )
    result = {"mobile_users": 0, "desktop_users": 0, "tablet_users": 0}
    for row in rows:
        device = row.get("deviceCategory", "").lower()
        users = int(row.get("totalUsers", 0))
        if device == "mobile":
            result["mobile_users"] = users
        elif device == "desktop":
            result["desktop_users"] = users
        elif device == "tablet":
            result["tablet_users"] = users
    return result


def _get_top_locations(client, start, end, limit: int = 5) -> list[dict]:
    """Top US regions by users. Filters to US only."""
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
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="totalUsers"), descending=True)],
        limit=limit,
    )
    return [
        {"region": r.get("region"), "users": int(r.get("totalUsers", 0))}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Main collector
# ---------------------------------------------------------------------------

def collect_web_pulse(week_start: datetime, week_end: datetime) -> dict[str, Any]:
    """
    Collect weekly website metrics for web_pulse tab.
    Returns a flat dict of metric_name -> value.
    """
    print("  Fetching GA4 metrics...")
    client = _get_client()

    user_metrics = _get_user_metrics(client, week_start, week_end)
    acquisition = _get_acquisition(client, week_start, week_end)
    top_page = _get_top_page(client, week_start, week_end)
    devices = _get_device_breakdown(client, week_start, week_end)
    locations = _get_top_locations(client, week_start, week_end)

    # Format top locations as a readable string for the sheet
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
    # Users
    "total_users",
    "new_users",
    "returning_users",
    "sessions",
    # Engagement
    "engagement_rate_pct",
    "avg_session_duration_sec",
    # Acquisition
    "organic_users",
    "direct_users",
    "social_users",
    "referral_users",
    "top_traffic_source",
    # Top page
    "top_landing_page",
    "top_page_sessions",
    "top_page_engagement_rate_pct",
    # Devices
    "mobile_users",
    "desktop_users",
    "tablet_users",
    # Location
    "top_us_regions",
]


def row_to_list(data: dict, headers: list[str]) -> list[Any]:
    return [data.get(h) for h in headers]
