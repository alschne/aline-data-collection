"""
email_digest.py — Weekly HTML email digest for the B2B business.
Covers Instagram performance + website analytics with AI-generated insights.
"""

import smtplib
import json
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import config


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt(value: Any, prefix: str = "", suffix: str = "", decimals: int = 0) -> str:
    if value is None or value == "":
        return "—"
    try:
        f = float(value)
        return f"{prefix}{f:,.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _pct_change(current: Any, previous: Any) -> str:
    try:
        c, p = float(current), float(previous)
        if p == 0:
            return ""
        change = (c - p) / p * 100
        arrow = "▲" if change >= 0 else "▼"
        colour = "#2e7d32" if change >= 0 else "#c62828"
        return f'<span style="color:{colour};font-size:12px;font-weight:600">{arrow} {abs(change):.1f}%</span>'
    except (TypeError, ValueError):
        return ""


def _ms_to_mmss(ms: Any) -> str:
    if ms is None or ms == "" or ms == 0:
        return "—"
    try:
        total_seconds = int(float(ms)) // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds:02d}s"
    except (TypeError, ValueError):
        return "—"


def _sec_to_mmss(sec: Any) -> str:
    """Convert seconds to m:ss string for GA4 session duration."""
    if sec is None or sec == "" or sec == 0:
        return "—"
    try:
        total = int(float(sec))
        minutes = total // 60
        seconds = total % 60
        return f"{minutes}m {seconds:02d}s"
    except (TypeError, ValueError):
        return "—"


# ---------------------------------------------------------------------------
# AI insights
# ---------------------------------------------------------------------------

def _get_ai_insights(
    week_end: str,
    ig_pulse: dict,
    prev_ig_pulse: dict | None,
    post_rows: list[dict],
    web_pulse: dict,
    prev_web_pulse: dict | None,
) -> str:
    """Generate AI insights covering both Instagram and website performance."""

    posts_summary = [
        {
            "format": p.get("format"),
            "views": p.get("views"),
            "reach": p.get("accounts_reached"),
            "saves": p.get("saves"),
            "shares": p.get("shares"),
            "avg_watch_time": _ms_to_mmss(p.get("avg_watch_time_ms")),
        }
        for p in post_rows
    ]

    prev_ig = ""
    if prev_ig_pulse:
        prev_ig = f"Last week IG: reach={prev_ig_pulse.get('account_reach')}, followers={prev_ig_pulse.get('followers')}"

    prev_web = ""
    if prev_web_pulse:
        prev_web = f"Last week web: users={prev_web_pulse.get('total_users')}, sessions={prev_web_pulse.get('sessions')}, engagement={prev_web_pulse.get('engagement_rate_pct')}%"

    prompt = f"""You are an expert digital marketing coach helping a B2B service business owner review their weekly performance.

This is a B2B service business with a website. The owner's goals are:
1. Get potential clients to contact them / fill out a form
2. Build credibility and showcase services
3. Drive traffic to book a discovery call
4. Grow Instagram following to build brand awareness

Week ending: {week_end}

INSTAGRAM METRICS:
- Reach: {ig_pulse.get('account_reach')}
- Total views: {ig_pulse.get('total_views')}
- Followers: {ig_pulse.get('followers')}
- Profile visits: {ig_pulse.get('profile_visits')}
- Saves: {ig_pulse.get('saves')}
- Shares: {ig_pulse.get('shares')}
- Total interactions: {ig_pulse.get('total_interactions')}
- Views from posts: {ig_pulse.get('views_from_posts')} ({ig_pulse.get('pct_views_from_posts')}%)
- Views from reels: {ig_pulse.get('views_from_reels')} ({ig_pulse.get('pct_views_from_reels')}%)
{prev_ig}

POSTS THIS WEEK:
{json.dumps(posts_summary, indent=2)}

WEBSITE METRICS:
- Total users: {web_pulse.get('total_users')}
- New users: {web_pulse.get('new_users')}
- Returning users: {web_pulse.get('returning_users')}
- Sessions: {web_pulse.get('sessions')}
- Engagement rate: {web_pulse.get('engagement_rate_pct')}%
- Avg session duration: {_sec_to_mmss(web_pulse.get('avg_session_duration_sec'))}
- Organic users: {web_pulse.get('organic_users')}
- Direct users: {web_pulse.get('direct_users')}
- Social users: {web_pulse.get('social_users')}
- Top traffic source: {web_pulse.get('top_traffic_source')}
- Top landing page: {web_pulse.get('top_landing_page')}
- Mobile users: {web_pulse.get('mobile_users')} / Desktop: {web_pulse.get('desktop_users')}
- Top US regions: {web_pulse.get('top_us_regions')}
{prev_web}

Background knowledge:
- For B2B service businesses, returning users and long session duration signal genuine interest
- Engagement rate above 50% is good for B2B; below 40% suggests content/UX issues
- Direct traffic often means people already know the brand — good sign
- Organic search traffic = SEO working, long-term valuable
- Social traffic from Instagram to website is the direct link between your two channels
- If mobile users dominate a B2B site, check that the site is optimised for mobile
- Saves and shares on IG posts signal content worth bookmarking — valuable for B2B credibility content
- Watch time under 3 seconds on reels = hook problem, not CTA problem

Write exactly 3 short paragraphs in plain HTML only (no headers, bullets, markdown, preamble):
1. ONE sentence on the most important signal across both Instagram and website this week. Lead with something positive. Reference a specific number.
2. ONE sentence identifying the most interesting connection or contrast between Instagram and website performance.
3. ONE specific, actionable thing to do next week — could be Instagram OR website, whichever has the higher leverage opportunity right now.

Total under 100 words. Be warm, direct, specific. Never lead with what went wrong.
Return only the 3 HTML paragraphs, nothing else."""

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
# HTML helpers
# ---------------------------------------------------------------------------

def _post_row_html(post: dict) -> str:
    is_reel = str(post.get("format", "")).lower() == "reel"
    badge = (
        '<span style="background:#e91e63;color:white;padding:2px 6px;border-radius:10px;font-size:11px">Reel</span>'
        if is_reel else
        '<span style="background:#1976d2;color:white;padding:2px 6px;border-radius:10px;font-size:11px">Post</span>'
    )
    permalink = post.get("permalink", "")
    link = f'<a href="{permalink}" style="color:#aaa;font-size:11px">View ↗</a>' if permalink else ""
    watch = _ms_to_mmss(post.get("avg_watch_time_ms")) if is_reel else "—"

    return (
        f'<tr style="border-bottom:1px solid #f0f0f0">'
        f'<td style="padding:10px 8px;font-size:13px">{badge}<br>'
        f'<span style="color:#aaa;font-size:11px">{post.get("post_date","")}</span><br>{link}</td>'
        f'<td style="padding:10px 8px;text-align:right;font-size:13px"><strong>{_fmt(post.get("views"))}</strong><br>'
        f'<span style="color:#aaa;font-size:11px">reach: {_fmt(post.get("accounts_reached"))}</span></td>'
        f'<td style="padding:10px 8px;text-align:right;font-size:13px">🔖 {_fmt(post.get("saves"))}<br>'
        f'<span style="color:#aaa;font-size:11px">↗ {_fmt(post.get("shares"))}</span></td>'
        f'<td style="padding:10px 8px;text-align:right;font-size:13px">'
        f'{"⏱ " + watch if is_reel else "👍 " + _fmt(post.get("likes"))}</td>'
        f'</tr>'
    )


def _mini_bar(value: Any, max_value: Any, color: str = "#1976d2") -> str:
    try:
        pct = min(100, int(float(value) / float(max_value) * 100)) if float(max_value) > 0 else 0
    except (TypeError, ValueError, ZeroDivisionError):
        pct = 0
    return (
        f'<div style="background:#f5f5f5;border-radius:3px;height:6px;width:80px;display:inline-block">'
        f'<div style="background:{color};border-radius:3px;height:6px;width:{pct}%"></div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Main HTML builder
# ---------------------------------------------------------------------------

def build_html(
    week_end: str,
    ig_pulse: dict[str, Any],
    post_rows: list[dict[str, Any]],
    web_pulse: dict[str, Any],
    prev_ig_pulse: dict[str, Any] | None = None,
    prev_web_pulse: dict[str, Any] | None = None,
) -> str:
    ig = ig_pulse
    p = prev_ig_pulse or {}
    wp = web_pulse
    pw = prev_web_pulse or {}

    # AI insights
    ai_html = _get_ai_insights(week_end, ig_pulse, prev_ig_pulse, post_rows, web_pulse, prev_web_pulse)
    ai_section = ""
    if ai_html:
        ai_section = f"""
  <div style="background:#f8f4ff;border-left:4px solid #7c4dff;padding:14px 16px;margin-bottom:24px;border-radius:0 6px 6px 0">
    <p style="margin:0 0 6px 0;font-size:12px;color:#7c4dff;font-weight:600;text-transform:uppercase;letter-spacing:0.5px">✦ Weekly Insights</p>
    <div style="font-size:13px;color:#333;line-height:1.6">{ai_html}</div>
  </div>"""

    # IG format breakdown
    post_views = ig.get('views_from_posts') or 0
    reel_views = ig.get('views_from_reels') or 0
    max_views = max(float(post_views), float(reel_views), 1)
    format_section = f"""
  <div style="margin-bottom:20px">
    <p style="font-size:12px;color:#555;margin-bottom:6px;font-weight:600">Views by format</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <tr>
        <td style="padding:3px 0;width:60px;color:#1976d2;font-weight:600">Posts</td>
        <td style="padding:3px 8px">{_mini_bar(post_views, max_views, '#1976d2')}</td>
        <td style="padding:3px 0;text-align:right;color:#555">{_fmt(post_views)} ({_fmt(ig.get('pct_views_from_posts'))}%)</td>
      </tr>
      <tr>
        <td style="padding:3px 0;color:#e91e63;font-weight:600">Reels</td>
        <td style="padding:3px 8px">{_mini_bar(reel_views, max_views, '#e91e63')}</td>
        <td style="padding:3px 0;text-align:right;color:#555">{_fmt(reel_views)} ({_fmt(ig.get('pct_views_from_reels'))}%)</td>
      </tr>
    </table>
  </div>"""

    # Posts table
    post_rows_html = ""
    if post_rows:
        for post in sorted(post_rows, key=lambda x: float(x.get('views') or 0), reverse=True):
            post_rows_html += _post_row_html(post)
    else:
        post_rows_html = '<tr><td colspan="4" style="padding:16px;text-align:center;color:#aaa">No posts this week</td></tr>'

    # Acquisition breakdown
    total_acq = sum([
        float(wp.get('organic_users') or 0),
        float(wp.get('direct_users') or 0),
        float(wp.get('social_users') or 0),
        float(wp.get('referral_users') or 0),
    ])
    acq_section = f"""
  <div style="margin-bottom:20px">
    <p style="font-size:12px;color:#555;margin-bottom:6px;font-weight:600">Traffic sources</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <tr>
        <td style="padding:3px 0;width:80px;color:#2e7d32;font-weight:600">Organic</td>
        <td style="padding:3px 8px">{_mini_bar(wp.get('organic_users'), total_acq or 1, '#2e7d32')}</td>
        <td style="padding:3px 0;text-align:right;color:#555">{_fmt(wp.get('organic_users'))} users</td>
      </tr>
      <tr>
        <td style="padding:3px 0;color:#1565c0;font-weight:600">Direct</td>
        <td style="padding:3px 8px">{_mini_bar(wp.get('direct_users'), total_acq or 1, '#1565c0')}</td>
        <td style="padding:3px 0;text-align:right;color:#555">{_fmt(wp.get('direct_users'))} users</td>
      </tr>
      <tr>
        <td style="padding:3px 0;color:#e91e63;font-weight:600">Social</td>
        <td style="padding:3px 8px">{_mini_bar(wp.get('social_users'), total_acq or 1, '#e91e63')}</td>
        <td style="padding:3px 0;text-align:right;color:#555">{_fmt(wp.get('social_users'))} users</td>
      </tr>
      <tr>
        <td style="padding:3px 0;color:#6a1b9a;font-weight:600">Referral</td>
        <td style="padding:3px 8px">{_mini_bar(wp.get('referral_users'), total_acq or 1, '#6a1b9a')}</td>
        <td style="padding:3px 0;text-align:right;color:#555">{_fmt(wp.get('referral_users'))} users</td>
      </tr>
    </table>
  </div>"""

    # Device breakdown
    total_devices = sum([
        float(wp.get('mobile_users') or 0),
        float(wp.get('desktop_users') or 0),
        float(wp.get('tablet_users') or 0),
    ])
    device_section = f"""
  <div style="margin-bottom:24px">
    <p style="font-size:12px;color:#555;margin-bottom:6px;font-weight:600">Devices</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <tr>
        <td style="padding:3px 0;width:80px;font-weight:600">Desktop</td>
        <td style="padding:3px 8px">{_mini_bar(wp.get('desktop_users'), total_devices or 1, '#1565c0')}</td>
        <td style="padding:3px 0;text-align:right;color:#555">{_fmt(wp.get('desktop_users'))} users</td>
      </tr>
      <tr>
        <td style="padding:3px 0;font-weight:600">Mobile</td>
        <td style="padding:3px 8px">{_mini_bar(wp.get('mobile_users'), total_devices or 1, '#e91e63')}</td>
        <td style="padding:3px 0;text-align:right;color:#555">{_fmt(wp.get('mobile_users'))} users</td>
      </tr>
      <tr>
        <td style="padding:3px 0;font-weight:600">Tablet</td>
        <td style="padding:3px 8px">{_mini_bar(wp.get('tablet_users'), total_devices or 1, '#aaa')}</td>
        <td style="padding:3px 0;text-align:right;color:#555">{_fmt(wp.get('tablet_users'))} users</td>
      </tr>
    </table>
  </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;max-width:640px;margin:0 auto;color:#1a1a1a;padding:24px 16px">

  <table style="width:100%;margin-bottom:24px">
    <tr>
      <td>
        <h2 style="margin:0;font-size:22px">Weekly Analytics</h2>
        <p style="margin:4px 0 0 0;color:#aaa;font-size:13px">Week ending {week_end}</p>
      </td>
      <td style="text-align:right;vertical-align:top">
        <a href="https://docs.google.com/spreadsheets/d/{config.GOOGLE_SPREADSHEET_ID}"
           style="font-size:12px;color:#aaa;text-decoration:none">View full data ↗</a>
      </td>
    </tr>
  </table>

  {ai_section}

  <!-- INSTAGRAM -->
  <h3 style="color:#e91e63;margin:0 0 12px 0;font-size:15px;text-transform:uppercase;letter-spacing:0.5px">📸 Instagram</h3>
  <table style="width:100%;border-collapse:collapse;margin-bottom:16px">
    <tr style="background:#fce4ec">
      <th style="padding:8px;text-align:left;font-size:12px;color:#888;font-weight:600;text-transform:uppercase">Metric</th>
      <th style="padding:8px;text-align:right;font-size:12px;color:#888;font-weight:600;text-transform:uppercase">This Week</th>
      <th style="padding:8px;text-align:right;font-size:12px;color:#888;font-weight:600;text-transform:uppercase">vs Last Week</th>
    </tr>
    <tr>
      <td style="padding:9px 8px;font-size:13px">Reach</td>
      <td style="padding:9px 8px;text-align:right;font-size:14px;font-weight:700">{_fmt(ig.get('account_reach'))}</td>
      <td style="padding:9px 8px;text-align:right">{_pct_change(ig.get('account_reach'), p.get('account_reach'))}</td>
    </tr>
    <tr style="background:#fafafa">
      <td style="padding:9px 8px;font-size:13px">Total Views</td>
      <td style="padding:9px 8px;text-align:right;font-size:14px;font-weight:700">{_fmt(ig.get('total_views'))}</td>
      <td style="padding:9px 8px;text-align:right">{_pct_change(ig.get('total_views'), p.get('total_views'))}</td>
    </tr>
    <tr>
      <td style="padding:9px 8px;font-size:13px">Followers</td>
      <td style="padding:9px 8px;text-align:right;font-size:14px;font-weight:700">{_fmt(ig.get('followers'))}</td>
      <td style="padding:9px 8px;text-align:right">{_pct_change(ig.get('followers'), p.get('followers'))}</td>
    </tr>
    <tr style="background:#fafafa">
      <td style="padding:9px 8px;font-size:13px">Saves</td>
      <td style="padding:9px 8px;text-align:right;font-size:14px;font-weight:700">{_fmt(ig.get('saves'))}</td>
      <td style="padding:9px 8px;text-align:right">{_pct_change(ig.get('saves'), p.get('saves'))}</td>
    </tr>
    <tr>
      <td style="padding:9px 8px;font-size:13px">Profile Visits</td>
      <td style="padding:9px 8px;text-align:right;font-size:14px;font-weight:700">{_fmt(ig.get('profile_visits'))}</td>
      <td style="padding:9px 8px;text-align:right">{_pct_change(ig.get('profile_visits'), p.get('profile_visits'))}</td>
    </tr>
    <tr style="background:#fafafa">
      <td style="padding:9px 8px;font-size:13px">Total Interactions</td>
      <td style="padding:9px 8px;text-align:right;font-size:14px;font-weight:700">{_fmt(ig.get('total_interactions'))}</td>
      <td style="padding:9px 8px;text-align:right">{_pct_change(ig.get('total_interactions'), p.get('total_interactions'))}</td>
    </tr>
  </table>

  {format_section}

  <p style="font-size:13px;color:#555;margin-bottom:8px;font-weight:600">Posts this week <span style="color:#aaa;font-weight:400">(sorted by views)</span></p>
  <table style="width:100%;border-collapse:collapse;margin-bottom:28px;font-size:13px">
    <tr style="background:#fce4ec;font-size:11px;color:#888;text-transform:uppercase">
      <th style="padding:7px 8px;text-align:left;font-weight:600">Format</th>
      <th style="padding:7px 8px;text-align:right;font-weight:600">Views</th>
      <th style="padding:7px 8px;text-align:right;font-weight:600">Saves/Shares</th>
      <th style="padding:7px 8px;text-align:right;font-weight:600">Likes/Watch</th>
    </tr>
    {post_rows_html}
  </table>

  <!-- WEBSITE -->
  <h3 style="color:#1565c0;margin:0 0 12px 0;font-size:15px;text-transform:uppercase;letter-spacing:0.5px">🌐 Website</h3>
  <table style="width:100%;border-collapse:collapse;margin-bottom:16px">
    <tr style="background:#e3f2fd">
      <th style="padding:8px;text-align:left;font-size:12px;color:#888;font-weight:600;text-transform:uppercase">Metric</th>
      <th style="padding:8px;text-align:right;font-size:12px;color:#888;font-weight:600;text-transform:uppercase">This Week</th>
      <th style="padding:8px;text-align:right;font-size:12px;color:#888;font-weight:600;text-transform:uppercase">vs Last Week</th>
    </tr>
    <tr>
      <td style="padding:9px 8px;font-size:13px">Total Users</td>
      <td style="padding:9px 8px;text-align:right;font-size:14px;font-weight:700">{_fmt(wp.get('total_users'))}</td>
      <td style="padding:9px 8px;text-align:right">{_pct_change(wp.get('total_users'), pw.get('total_users'))}</td>
    </tr>
    <tr style="background:#fafafa">
      <td style="padding:9px 8px;font-size:13px">New / Returning</td>
      <td style="padding:9px 8px;text-align:right;font-size:13px">{_fmt(wp.get('new_users'))} new / {_fmt(wp.get('returning_users'))} returning</td>
      <td style="padding:9px 8px;text-align:right">{_pct_change(wp.get('new_users'), pw.get('new_users'))}</td>
    </tr>
    <tr>
      <td style="padding:9px 8px;font-size:13px">Sessions</td>
      <td style="padding:9px 8px;text-align:right;font-size:14px;font-weight:700">{_fmt(wp.get('sessions'))}</td>
      <td style="padding:9px 8px;text-align:right">{_pct_change(wp.get('sessions'), pw.get('sessions'))}</td>
    </tr>
    <tr style="background:#fafafa">
      <td style="padding:9px 8px;font-size:13px">Engagement Rate</td>
      <td style="padding:9px 8px;text-align:right;font-size:14px;font-weight:700">{_fmt(wp.get('engagement_rate_pct'))}%</td>
      <td style="padding:9px 8px;text-align:right">{_pct_change(wp.get('engagement_rate_pct'), pw.get('engagement_rate_pct'))}</td>
    </tr>
    <tr>
      <td style="padding:9px 8px;font-size:13px">Avg Session Duration</td>
      <td style="padding:9px 8px;text-align:right;font-size:14px;font-weight:700">{_sec_to_mmss(wp.get('avg_session_duration_sec'))}</td>
      <td style="padding:9px 8px;text-align:right">{_pct_change(wp.get('avg_session_duration_sec'), pw.get('avg_session_duration_sec'))}</td>
    </tr>
    <tr style="background:#fafafa">
      <td style="padding:9px 8px;font-size:13px">Top Landing Page</td>
      <td style="padding:9px 8px;text-align:right;font-size:13px" colspan="2">
        {wp.get('top_landing_page') or '—'}
        {f'<span style="color:#aaa;font-size:11px"> · {_fmt(wp.get("top_page_sessions"))} sessions · {_fmt(wp.get("top_page_engagement_rate_pct"))}% engaged</span>' if wp.get('top_landing_page') else ''}
      </td>
    </tr>
    <tr>
      <td style="padding:9px 8px;font-size:13px">Top US Regions</td>
      <td style="padding:9px 8px;text-align:right;font-size:12px;color:#555" colspan="2">{wp.get('top_us_regions') or '—'}</td>
    </tr>
  </table>

  {acq_section}
  {device_section}

  <p style="font-size:11px;color:#ccc;border-top:1px solid #f0f0f0;padding-top:12px;margin-top:8px">
    Auto-generated weekly analytics · {week_end}
  </p>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send_digest(
    week_end: str,
    ig_pulse: dict[str, Any],
    post_rows: list[dict[str, Any]],
    web_pulse: dict[str, Any],
    prev_ig_pulse: dict[str, Any] | None = None,
    prev_web_pulse: dict[str, Any] | None = None,
) -> None:
    print("  Sending weekly email digest...")
    html = build_html(week_end, ig_pulse, post_rows, web_pulse, prev_ig_pulse, prev_web_pulse)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Weekly Analytics — week ending {week_end}"
    msg["From"] = f"Analytics Pipeline <{config.EMAIL_SENDER}>"
    msg["To"] = config.EMAIL_RECIPIENT
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_SENDER, config.EMAIL_RECIPIENT, msg.as_string())

    print(f"  Email sent to {config.EMAIL_RECIPIENT}")
