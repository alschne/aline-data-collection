"""
main.py — Entry point for the weekly analytics pipeline (B2B business).

Collects Instagram + Google Analytics 4 data, writes to Google Sheets,
and sends a weekly email digest.

Run manually:  python src/main.py
Scheduled via: .github/workflows/weekly_pipeline.yml
"""

import sys
import argparse
from datetime import datetime, timedelta, timezone

import config
import sheets
import ig_collector
import ga4_collector
import email_digest


def get_week_window() -> tuple[datetime, datetime]:
    """Returns (week_start, week_end) for the most recently completed Mon–Sun week."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    days_since_sunday = today.weekday() + 1
    week_end = today - timedelta(days=days_since_sunday)
    week_start = week_end - timedelta(days=6)
    return week_start, week_end


def get_previous_row(sheet, date_col: str = "week_end_date") -> dict | None:
    """Read the second-to-last row for week-over-week comparisons."""
    try:
        all_rows = sheet.get_all_records()
        if len(all_rows) >= 2:
            return all_rows[-2]
        elif len(all_rows) == 1:
            return all_rows[0]
    except Exception:
        pass
    return None


def run():
    week_start, week_end = get_week_window()
    week_end_str = week_end.strftime("%Y-%m-%d")
    print(f"\n{'='*55}")
    print(f"  Analytics pipeline — week ending {week_end_str}")
    print(f"{'='*55}\n")

    errors = []
    ig_pulse_data = {}
    post_rows = []
    web_pulse_data = {}
    prev_ig = None
    prev_web = None

    # ------------------------------------------------------------------
    # Instagram — ig_pulse
    # ------------------------------------------------------------------
    print("[1/4] IG Pulse (account-level weekly metrics)")
    try:
        ig_pulse_sheet = sheets.get_sheet(config.SHEET_IG_PULSE)
        sheets.ensure_headers(ig_pulse_sheet, ig_collector.IG_PULSE_HEADERS)
        prev_ig = get_previous_row(ig_pulse_sheet)

        ig_pulse_data = ig_collector.collect_ig_pulse(week_start, week_end)
        row = ig_collector.row_to_list(ig_pulse_data, ig_collector.IG_PULSE_HEADERS)
        sheets.upsert_row(ig_pulse_sheet, row, key_col_index=0)
        print("  ✓ ig_pulse updated\n")
    except Exception as e:
        print(f"  ✗ ig_pulse failed: {e}")
        errors.append(("ig_pulse", str(e)))

    # ------------------------------------------------------------------
    # Instagram — ig_stars (per-post)
    # ------------------------------------------------------------------
    print("[2/4] IG Stars (per-post metrics)")
    try:
        ig_stars_sheet = sheets.get_sheet(config.SHEET_IG_STARS)
        sheets.ensure_headers(ig_stars_sheet, ig_collector.IG_STARS_HEADERS)
        existing_permalinks = sheets.get_existing_keys(
            ig_stars_sheet,
            key_col_index=ig_collector.IG_STARS_HEADERS.index("permalink"),
        )

        post_rows = ig_collector.collect_ig_stars(week_start, week_end)
        # Sort oldest to newest so the sheet stays in chronological order
        post_rows = sorted(post_rows, key=lambda p: (p.get("post_date", ""), p.get("post_time", "")))
        new_posts = 0
        for post in post_rows:
            permalink = post.get("permalink", "")
            if permalink and permalink in existing_permalinks:
                print(f"  Skipping existing post: {permalink}")
                continue
            row = ig_collector.row_to_list(post, ig_collector.IG_STARS_HEADERS)
            sheets.append_row(ig_stars_sheet, row)
            new_posts += 1

        print(f"  ✓ ig_stars updated — {new_posts} new post(s) added\n")
    except Exception as e:
        print(f"  ✗ ig_stars failed: {e}")
        errors.append(("ig_stars", str(e)))

    # ------------------------------------------------------------------
    # Google Analytics 4 — web_pulse
    # ------------------------------------------------------------------
    print("[3/4] Web Pulse (GA4 weekly website metrics)")
    try:
        web_pulse_sheet = sheets.get_sheet(config.SHEET_WEB_PULSE)
        sheets.ensure_headers(web_pulse_sheet, ga4_collector.WEB_PULSE_HEADERS)
        prev_web = get_previous_row(web_pulse_sheet)

        web_pulse_data = ga4_collector.collect_web_pulse(week_start, week_end)
        row = ga4_collector.row_to_list(web_pulse_data, ga4_collector.WEB_PULSE_HEADERS)
        sheets.upsert_row(web_pulse_sheet, row, key_col_index=0)
        print("  ✓ web_pulse updated\n")
    except Exception as e:
        print(f"  ✗ web_pulse failed: {e}")
        errors.append(("web_pulse", str(e)))

    # ------------------------------------------------------------------
    # Email digest
    # ------------------------------------------------------------------
    print("[4/4] Sending email digest")
    try:
        email_digest.send_digest(
            week_end=week_end_str,
            ig_pulse=ig_pulse_data,
            post_rows=post_rows,
            web_pulse=web_pulse_data,
            prev_ig_pulse=prev_ig,
            prev_web_pulse=prev_web,
        )
        print("  ✓ Email sent\n")
    except Exception as e:
        print(f"  ✗ Email failed: {e}")
        errors.append(("email", str(e)))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"{'='*55}")
    if errors:
        print(f"  Pipeline finished with {len(errors)} error(s):")
        for step, msg in errors:
            print(f"    • {step}: {msg}")
        sys.exit(1)
    else:
        print("  Pipeline finished successfully ✓")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    run()