# B2B Analytics Pipeline

Automated weekly data collection for a B2B service business.
Pulls Instagram performance data and Google Analytics 4 website metrics,
appends to Google Sheets, and sends a weekly email digest with AI insights.

## What this does

Every Monday at 8AM UTC:
1. Pulls last week's Instagram account metrics → `ig_pulse` tab
2. Pulls per-post metrics for posts published last week → `ig_stars` tab
3. Pulls GA4 website metrics (users, sessions, acquisition, engagement, devices, location) → `web_pulse` tab
4. Sends a weekly email with both Instagram and website data + AI-generated insights

## Repo structure

```
.
├── .github/
│   └── workflows/
│       └── weekly_pipeline.yml
├── src/
│   ├── main.py              # Entry point
│   ├── ig_collector.py      # Instagram Graph API
│   ├── ga4_collector.py     # Google Analytics 4 Data API
│   ├── sheets.py            # Google Sheets helpers
│   ├── email_digest.py      # Weekly email with AI insights
│   └── config.py            # Centralised config
├── scripts/
│   └── ig_auth.py           # One-time Instagram OAuth setup
├── requirements.txt
├── .env.example
├── README.md
├── SETUP.md
└── MAINTENANCE.md
```

## Tabs

| Tab | Source | Notes |
|-----|--------|-------|
| `ig_pulse` | Instagram Graph API | Weekly account metrics |
| `ig_stars` | Instagram Graph API | Per-post metrics |
| `web_pulse` | Google Analytics 4 | Weekly website metrics |

## Quick reference — credentials

| Secret | Source |
|--------|--------|
| `IG_APP_ID` / `IG_APP_SECRET` | Meta Developer app (reuse from repo 1) |
| `IG_ACCESS_TOKEN` | Run `scripts/ig_auth.py` for this account |
| `IG_ACCOUNT_ID` | Output of `scripts/ig_auth.py` |
| `GA4_PROPERTY_ID` | GA4 Admin → Property Settings |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | New Google Cloud project service account |
| `GOOGLE_SPREADSHEET_ID` | From sheet URL |
| `EMAIL_SENDER/PASSWORD/RECIPIENT` | Gmail + App Password |
| `GOOGLE_AI_API_KEY` | Google AI Studio (reuse from repo 1) |

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in credentials

python src/main.py
```

See `SETUP.md` for full setup instructions including GA4 conversion configuration.
