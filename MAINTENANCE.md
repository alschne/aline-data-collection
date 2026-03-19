# Maintenance Guide

---

## Regular maintenance

### Instagram access token
Auto-refreshes on every run. No action needed as long as pipeline runs at least
once every 60 days.

If expired: re-run `scripts/ig_auth.py` and update `IG_ACCESS_TOKEN` in GitHub Secrets.

### Google service account / GA4 access
Never expires unless manually revoked.

### Gmail App Password
Never expires unless you change your Google password or revoke it.

---

## Changing the schedule

Edit `.github/workflows/weekly_pipeline.yml`:
```yaml
schedule:
  - cron: "0 8 * * 1"   # Monday 8AM UTC = 1AM Mountain
```
- Monday 9AM Mountain (summer): `0 15 * * 1`
- Monday 9AM Mountain (winter): `0 16 * * 1`

---

## Adding GA4 conversions

Once you've set up conversions in GA4 (contact form, CTA clicks), add them
to the pipeline:

1. In GA4, confirm the conversion event name (e.g. `generate_lead`)
2. In `src/ga4_collector.py`, add a new function:

```python
def _get_conversions(client, start, end) -> dict:
    rows = _run_report(
        client, start, end,
        metrics=["conversions", "conversionRate"],
        dimensions=["eventName"],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="eventName",
                string_filter=Filter.StringFilter(value="generate_lead"),
            )
        ),
    )
    if not rows:
        return {"total_conversions": 0, "conversion_rate_pct": 0}
    r = rows[0]
    return {
        "total_conversions": int(r.get("conversions", 0)),
        "conversion_rate_pct": round(float(r.get("conversionRate", 0)) * 100, 2),
    }
```

3. Call it in `collect_web_pulse()` and add the keys to `WEB_PULSE_HEADERS`
4. Update `email_digest.py` to display the new metrics in the website section

---

## Troubleshooting

### `403 Permission denied` on GA4
The service account hasn't been added as a Viewer in GA4.
Go to GA4 → Admin → Account Access Management → add service account email as Viewer.

### `404 Property not found` on GA4
Your `GA4_PROPERTY_ID` is wrong. Verify it in GA4 → Admin → Property Settings.
It should be just the number — no "properties/" prefix.

### GA4 returns empty data
- Check that GA4 has been tracking for the date range you're querying
- New GA4 properties can take 24-48 hours to start showing data
- Verify the service account has Viewer access

### Instagram errors
See repo 1 MAINTENANCE.md — the Instagram setup is identical.

### Email not arriving
Check spam. Verify App Password is correct (no spaces). Confirm 2-Step
Verification is still enabled on your Gmail.

### AI insights missing
Non-fatal — email sends without insights section. Check logs for:
`Warning: AI insights unavailable: ...`
Common causes: rate limit (429) or invalid API key.

---

## Manually triggering

GitHub → Actions → Weekly Analytics Pipeline → Run workflow.

If data already exists for the week, the pipeline skips writing it again.
Delete the relevant rows first if you need to force a rewrite.
