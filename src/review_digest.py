"""
review_digest.py — Quarterly and annual review emails for the B2B pipeline.
Covers Instagram + Google Analytics 4 website data.
"""

import smtplib
import json
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from typing import Any

import config
import sheets


QUARTER_RANGES = {
    1: ("01-01", "03-31"),
    2: ("04-01", "06-30"),
    3: ("07-01", "09-30"),
    4: ("10-01", "12-31"),
}

def get_current_quarter() -> int:
    return (datetime.now(timezone.utc).month - 1) // 3 + 1

def get_current_year() -> int:
    return datetime.now(timezone.utc).year

def filter_rows_by_period(
    rows: list[dict], start: str, end: str, date_key: str = "week_end_date"
) -> list[dict]:
    return [r for r in rows if start <= str(r.get(date_key, "")) <= end]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def safe_float(val) -> float:
    if val in (None, "", "--"):
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def aggregate_ig_pulse(rows: list[dict]) -> dict:
    if not rows:
        return {}

    def s(key): return sum(safe_float(r.get(key)) for r in rows)
    def avg(key):
        vals = [safe_float(r.get(key)) for r in rows if r.get(key) not in (None, "")]
        return round(sum(vals) / len(vals), 1) if vals else None

    try:
        follower_start = int(safe_float(rows[0].get("followers")))
        follower_end = int(safe_float(rows[-1].get("followers")))
        follower_growth = follower_end - follower_start
    except Exception:
        follower_start = follower_end = follower_growth = None

    best_week = max(rows, key=lambda r: safe_float(r.get("account_reach")), default={})

    return {
        "weeks": len(rows),
        "total_reach": int(s("account_reach")),
        "total_views": int(s("total_views")),
        "total_interactions": int(s("total_interactions")),
        "total_saves": int(s("saves")),
        "total_shares": int(s("shares")),
        "total_profile_visits": int(s("profile_visits")),
        "avg_weekly_reach": avg("account_reach"),
        "follower_start": follower_start,
        "follower_end": follower_end,
        "follower_growth": follower_growth,
        "best_week_reach": int(safe_float(best_week.get("account_reach"))),
        "best_week_date": best_week.get("week_end_date"),
    }


def aggregate_ig_stars(rows: list[dict]) -> dict:
    if not rows:
        return {}

    posts = [r for r in rows if str(r.get("format", "")).lower() != "reel"]
    reels = [r for r in rows if str(r.get("format", "")).lower() == "reel"]

    def avg(items, key):
        vals = [safe_float(r.get(key)) for r in items if r.get(key) not in (None, "")]
        return round(sum(vals) / len(vals), 1) if vals else None

    top_posts = sorted(rows, key=lambda r: safe_float(r.get("views")), reverse=True)[:3]

    return {
        "total_posts": len(rows),
        "total_image_posts": len(posts),
        "total_reels": len(reels),
        "avg_views_posts": avg(posts, "views"),
        "avg_views_reels": avg(reels, "views"),
        "top_posts": [
            {
                "date": r.get("post_date"),
                "format": r.get("format"),
                "views": r.get("views"),
                "saves": r.get("saves"),
                "shares": r.get("shares"),
                "permalink": r.get("permalink"),
            }
            for r in top_posts
        ],
    }


def aggregate_web_pulse(rows: list[dict]) -> dict:
    if not rows:
        return {}

    def s(key): return sum(safe_float(r.get(key)) for r in rows)
    def avg(key):
        vals = [safe_float(r.get(key)) for r in rows if r.get(key) not in (None, "")]
        return round(sum(vals) / len(vals), 1) if vals else None

    weeks = len(rows)

    # Top traffic source by total users across period
    source_totals = {}
    for r in rows:
        src = r.get("top_traffic_source")
        if src:
            source_totals[src] = source_totals.get(src, 0) + 1
    top_source = max(source_totals, key=source_totals.get) if source_totals else None

    return {
        "weeks": weeks,
        "total_users": int(s("total_users")),
        "total_new_users": int(s("new_users")),
        "total_returning_users": int(s("returning_users")),
        "total_sessions": int(s("sessions")),
        "avg_engagement_rate_pct": avg("engagement_rate_pct"),
        "avg_session_duration_sec": avg("avg_session_duration_sec"),
        "total_organic_users": int(s("organic_users")),
        "total_direct_users": int(s("direct_users")),
        "total_social_users": int(s("social_users")),
        "total_referral_users": int(s("referral_users")),
        "top_traffic_source": top_source,
        "avg_weekly_users": round(s("total_users") / weeks, 1) if weeks else None,
    }


# ---------------------------------------------------------------------------
# AI insights
# ---------------------------------------------------------------------------

def _sec_to_mmss(sec) -> str:
    if not sec:
        return "—"
    try:
        total = int(float(sec))
        return f"{total // 60}m {total % 60:02d}s"
    except Exception:
        return "—"


def _get_review_insights(
    period_label: str,
    ig_pulse_agg: dict,
    ig_stars_agg: dict,
    web_agg: dict,
    is_annual: bool = False,
) -> str:
    period_type = "year" if is_annual else "quarter"

    prompt = f"""You are an expert digital marketing coach reviewing a {period_type} of performance data for a B2B service business.

This is a B2B service business. The website is where conversions happen. Instagram is top-of-funnel awareness.
Primary goals: get potential clients to contact/book, build credibility, grow awareness.

Period: {period_label}
{"Annual review — look for year-long trends, seasonal patterns, and strategic direction for next year." if is_annual else "Quarterly review — what worked, what to prioritise next quarter."}

INSTAGRAM ({period_label}):
- Follower growth: {ig_pulse_agg.get('follower_start')} → {ig_pulse_agg.get('follower_end')} ({ig_pulse_agg.get('follower_growth'):+d} followers)
- Total reach: {ig_pulse_agg.get('total_reach')}
- Total saves: {ig_pulse_agg.get('total_saves')}
- Total shares: {ig_pulse_agg.get('total_shares')}
- Posts published: {ig_stars_agg.get('total_posts')} ({ig_stars_agg.get('total_image_posts')} images, {ig_stars_agg.get('total_reels')} reels)
- Avg views per image: {ig_stars_agg.get('avg_views_posts')}
- Avg views per reel: {ig_stars_agg.get('avg_views_reels')}

WEBSITE ({period_label}):
- Total users: {web_agg.get('total_users')}
- New users: {web_agg.get('total_new_users')}
- Returning users: {web_agg.get('total_returning_users')}
- Total sessions: {web_agg.get('total_sessions')}
- Avg engagement rate: {web_agg.get('avg_engagement_rate_pct')}%
- Avg session duration: {_sec_to_mmss(web_agg.get('avg_session_duration_sec'))}
- Organic users: {web_agg.get('total_organic_users')}
- Direct users: {web_agg.get('total_direct_users')}
- Social users: {web_agg.get('total_social_users')} (Instagram → website)
- Top traffic source: {web_agg.get('top_traffic_source')}

Write a {period_type} review in plain HTML paragraphs only (no headers, bullets, markdown):
{"4 paragraphs: (1) Overall story of the year — website performance first, then IG. (2) Biggest website win. (3) Biggest growth opportunity for next year. (4) One strategic priority — specific and actionable." if is_annual else "3 paragraphs: (1) Overall story of the quarter — lead with website, then IG. (2) What worked best. (3) One clear priority for next quarter, specific and actionable."}

Be warm, direct, specific. Reference actual numbers. Website insights first. Total {"under 200" if is_annual else "under 150"} words.
Return only the HTML paragraphs."""

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={config.GOOGLE_AI_API_KEY}",
            headers={"content-type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"  Warning: AI insights unavailable: {e}")
        return ""


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _fmt(value: Any, prefix: str = "", suffix: str = "", decimals: int = 0) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{prefix}{float(value):,.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def build_review_html(
    period_label: str,
    ig_pulse_agg: dict,
    ig_stars_agg: dict,
    web_agg: dict,
    insights_html: str,
    is_annual: bool = False,
) -> str:
    review_type = "Annual Review" if is_annual else "Quarterly Review"
    accent = "#4a148c" if is_annual else "#1565c0"

    follower_growth = ig_pulse_agg.get("follower_growth") or 0
    growth_color = "#2e7d32" if follower_growth >= 0 else "#c62828"
    growth_sign = "+" if follower_growth >= 0 else ""

    top_posts_html = ""
    for p in ig_stars_agg.get("top_posts", []):
        link = f'<a href="{p.get("permalink","")}" style="color:#aaa;font-size:11px">View ↗</a>' if p.get("permalink") else ""
        top_posts_html += (
            f'<tr style="border-bottom:1px solid #f5f5f5">'
            f'<td style="padding:7px 8px;font-size:13px">{p.get("format","")}<br>'
            f'<span style="color:#aaa;font-size:11px">{p.get("date","")}</span><br>{link}</td>'
            f'<td style="padding:7px 8px;text-align:right;font-size:13px;font-weight:700">{_fmt(p.get("views"))}</td>'
            f'<td style="padding:7px 8px;text-align:right;font-size:13px">🔖 {_fmt(p.get("saves"))}</td>'
            f'<td style="padding:7px 8px;text-align:right;font-size:13px">↗ {_fmt(p.get("shares"))}</td>'
            f'</tr>'
        )

    insights_block = ""
    if insights_html:
        insights_block = f"""
  <div style="background:#f3e5f5;border-left:4px solid {accent};padding:14px 16px;margin-bottom:24px;border-radius:0 6px 6px 0">
    <p style="margin:0 0 8px 0;font-size:12px;color:{accent};font-weight:600;text-transform:uppercase;letter-spacing:0.5px">✦ {"Year in Review" if is_annual else "Quarter in Review"}</p>
    <div style="font-size:13px;color:#333;line-height:1.7">{insights_html}</div>
  </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;max-width:640px;margin:0 auto;color:#1a1a1a;padding:24px 16px">

  <div style="border-bottom:3px solid {accent};padding-bottom:12px;margin-bottom:20px">
    <h2 style="margin:0;color:{accent};font-size:24px">{"🏆" if is_annual else "📅"} {review_type}</h2>
    <p style="margin:4px 0 0 0;color:#aaa;font-size:13px">{period_label}</p>
  </div>

  {insights_block}

  <!-- WEBSITE -->
  <h3 style="color:#1565c0;margin:0 0 12px 0;font-size:15px;text-transform:uppercase;letter-spacing:0.5px">🌐 Website — {period_label}</h3>
  <table style="width:100%;border-collapse:collapse;margin-bottom:16px">
    <tr style="background:#e3f2fd">
      <td style="padding:10px;text-align:center">
        <div style="font-size:22px;font-weight:700">{_fmt(web_agg.get('total_users'))}</div>
        <div style="font-size:12px;color:#888">Total Users</div>
      </td>
      <td style="padding:10px;text-align:center">
        <div style="font-size:22px;font-weight:700">{_fmt(web_agg.get('total_sessions'))}</div>
        <div style="font-size:12px;color:#888">Total Sessions</div>
      </td>
      <td style="padding:10px;text-align:center">
        <div style="font-size:22px;font-weight:700">{_fmt(web_agg.get('avg_engagement_rate_pct'))}%</div>
        <div style="font-size:12px;color:#888">Avg Engagement Rate</div>
      </td>
    </tr>
  </table>
  <table style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:13px">
    <tr style="background:#fafafa">
      <td style="padding:8px">New users</td>
      <td style="padding:8px;text-align:right;font-weight:600">{_fmt(web_agg.get('total_new_users'))}</td>
      <td style="padding:8px">Returning users</td>
      <td style="padding:8px;text-align:right;font-weight:600">{_fmt(web_agg.get('total_returning_users'))}</td>
    </tr>
    <tr>
      <td style="padding:8px">Avg session duration</td>
      <td style="padding:8px;text-align:right;font-weight:600">{_sec_to_mmss(web_agg.get('avg_session_duration_sec'))}</td>
      <td style="padding:8px">Top traffic source</td>
      <td style="padding:8px;text-align:right;font-weight:600">{web_agg.get('top_traffic_source') or '—'}</td>
    </tr>
    <tr style="background:#fafafa">
      <td style="padding:8px">Organic users</td>
      <td style="padding:8px;text-align:right;font-weight:600">{_fmt(web_agg.get('total_organic_users'))}</td>
      <td style="padding:8px">Social → website</td>
      <td style="padding:8px;text-align:right;font-weight:600">{_fmt(web_agg.get('total_social_users'))}</td>
    </tr>
    <tr>
      <td style="padding:8px">Direct users</td>
      <td style="padding:8px;text-align:right;font-weight:600">{_fmt(web_agg.get('total_direct_users'))}</td>
      <td style="padding:8px">Referral users</td>
      <td style="padding:8px;text-align:right;font-weight:600">{_fmt(web_agg.get('total_referral_users'))}</td>
    </tr>
  </table>

  <!-- INSTAGRAM -->
  <h3 style="color:#e91e63;margin:0 0 12px 0;font-size:15px;text-transform:uppercase;letter-spacing:0.5px">📸 Instagram — {period_label}</h3>
  <table style="width:100%;border-collapse:collapse;margin-bottom:16px">
    <tr style="background:#fce4ec">
      <td style="padding:10px;text-align:center">
        <div style="font-size:22px;font-weight:700">{_fmt(ig_pulse_agg.get('total_reach'))}</div>
        <div style="font-size:12px;color:#888">Total Reach</div>
      </td>
      <td style="padding:10px;text-align:center">
        <div style="font-size:22px;font-weight:700" style="color:{growth_color}">{growth_sign}{_fmt(follower_growth)}</div>
        <div style="font-size:12px;color:#888">Follower Growth</div>
      </td>
      <td style="padding:10px;text-align:center">
        <div style="font-size:22px;font-weight:700">{_fmt(ig_stars_agg.get('total_posts'))}</div>
        <div style="font-size:12px;color:#888">Posts Published</div>
      </td>
    </tr>
  </table>
  <table style="width:100%;border-collapse:collapse;margin-bottom:16px;font-size:13px">
    <tr style="background:#fafafa">
      <td style="padding:8px">Avg views / image post</td>
      <td style="padding:8px;text-align:right;font-weight:600">{_fmt(ig_stars_agg.get('avg_views_posts'))}</td>
      <td style="padding:8px">Avg views / reel</td>
      <td style="padding:8px;text-align:right;font-weight:600">{_fmt(ig_stars_agg.get('avg_views_reels'))}</td>
    </tr>
    <tr>
      <td style="padding:8px">Total saves</td>
      <td style="padding:8px;text-align:right;font-weight:600">{_fmt(ig_pulse_agg.get('total_saves'))}</td>
      <td style="padding:8px">Total shares</td>
      <td style="padding:8px;text-align:right;font-weight:600">{_fmt(ig_pulse_agg.get('total_shares'))}</td>
    </tr>
  </table>

  <p style="font-size:13px;color:#555;margin-bottom:8px;font-weight:600">Top performing posts</p>
  <table style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:13px">
    <tr style="background:#fce4ec;font-size:11px;color:#888;text-transform:uppercase">
      <th style="padding:7px 8px;text-align:left;font-weight:600">Post</th>
      <th style="padding:7px 8px;text-align:right;font-weight:600">Views</th>
      <th style="padding:7px 8px;text-align:right;font-weight:600">Saves</th>
      <th style="padding:7px 8px;text-align:right;font-weight:600">Shares</th>
    </tr>
    {top_posts_html or '<tr><td colspan="4" style="padding:12px;text-align:center;color:#aaa">No post data</td></tr>'}
  </table>

  <p style="font-size:11px;color:#ccc;border-top:1px solid #f0f0f0;padding-top:12px">
    Auto-generated {review_type.lower()} · {period_label} ·
    <a href="https://docs.google.com/spreadsheets/d/{config.GOOGLE_SPREADSHEET_ID}" style="color:#ccc">View full data ↗</a>
  </p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Send + entry points
# ---------------------------------------------------------------------------

def send_review(period_label: str, html: str, is_annual: bool = False) -> None:
    review_type = "Annual Review 🏆" if is_annual else "Quarterly Review 📅"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{review_type} — {period_label}"
    msg["From"] = f"AA Analytics Pipeline <{config.EMAIL_SENDER}>"
    msg["To"] = config.EMAIL_RECIPIENT
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_SENDER, config.EMAIL_RECIPIENT, msg.as_string())
    print(f"  {review_type} sent to {config.EMAIL_RECIPIENT}")


def run_quarterly_review(quarter: int | None = None, year: int | None = None) -> None:
    q = quarter or get_current_quarter()
    y = year or get_current_year()
    start_suffix, end_suffix = QUARTER_RANGES[q]
    start = f"{y}-{start_suffix}"
    end = f"{y}-{end_suffix}"
    period_label = f"Q{q} {y}"
    print(f"\n  Running quarterly review for {period_label}")

    ig_pulse_rows = filter_rows_by_period(sheets.get_sheet(config.SHEET_IG_PULSE).get_all_records(), start, end)
    ig_stars_rows = filter_rows_by_period(sheets.get_sheet(config.SHEET_IG_STARS).get_all_records(), start, end, date_key="post_date")
    web_rows = filter_rows_by_period(sheets.get_sheet(config.SHEET_WEB_PULSE).get_all_records(), start, end)

    ig_pulse_agg = aggregate_ig_pulse(ig_pulse_rows)
    ig_stars_agg = aggregate_ig_stars(ig_stars_rows)
    web_agg = aggregate_web_pulse(web_rows)

    insights = _get_review_insights(period_label, ig_pulse_agg, ig_stars_agg, web_agg)
    html = build_review_html(period_label, ig_pulse_agg, ig_stars_agg, web_agg, insights)
    send_review(period_label, html)
    print(f"  ✓ Quarterly review sent for {period_label}")


def run_annual_review(year: int | None = None) -> None:
    y = year or get_current_year()
    start = f"{y}-01-01"
    end = f"{y}-12-31"
    period_label = f"Full Year {y}"
    print(f"\n  Running annual review for {period_label}")

    ig_pulse_rows = filter_rows_by_period(sheets.get_sheet(config.SHEET_IG_PULSE).get_all_records(), start, end)
    ig_stars_rows = filter_rows_by_period(sheets.get_sheet(config.SHEET_IG_STARS).get_all_records(), start, end, date_key="post_date")
    web_rows = filter_rows_by_period(sheets.get_sheet(config.SHEET_WEB_PULSE).get_all_records(), start, end)

    ig_pulse_agg = aggregate_ig_pulse(ig_pulse_rows)
    ig_stars_agg = aggregate_ig_stars(ig_stars_rows)
    web_agg = aggregate_web_pulse(web_rows)

    insights = _get_review_insights(period_label, ig_pulse_agg, ig_stars_agg, web_agg, is_annual=True)
    html = build_review_html(period_label, ig_pulse_agg, ig_stars_agg, web_agg, insights, is_annual=True)
    send_review(period_label, html, is_annual=True)
    print(f"  ✓ Annual review sent for {period_label}")
