# B2B Analytics Pipeline

Automated weekly data collection for a B2B service business.
Pulls Instagram performance data and Google Analytics 4 website metrics,
appends to Google Sheets, and sends a weekly email digest with AI insights.

## What this does

**Every Monday at 8AM UTC** the weekly pipeline:
1. Pulls last week's Instagram account metrics → `ig_pulse` tab
2. Pulls per-post metrics for posts published last week → `ig_stars` tab
3. Pulls GA4 website metrics (users, sessions, acquisition, engagement, devices, location) → `web_pulse` tab
4. Sends a weekly email with Instagram + website data and AI-generated insights

**Quarterly and annually** the review pipeline:
- **March 31** — Q1 review email (Jan–Mar)
- **June 30** — Q2 review email (Apr–Jun)
- **September 30** — Q3 review email (Jul–Sep)
- **December 31** — Q4 review email (Oct–Dec) + Annual review email (full year)

Review emails include aggregated totals, top performing posts, website performance summary, and AI-generated strategic insights with a B2B lens.

## Repo structure

```
.
├── .github/
│   └── workflows/
│       └── weekly_pipeline.yml   # Weekly + quarterly + annual schedules
├── src/
│   ├── main.py                   # Entry point — weekly pipeline
│   ├── review_runner.py          # Entry point — quarterly and annual reviews
│   ├── ig_collector.py           # Instagram Graph API logic
│   ├── ga4_collector.py          # Google Analytics 4 Data API logic
│   ├── sheets.py                 # Google Sheets read/write helpers
│   ├── email_digest.py           # Weekly email with AI insights (Gemini)
│   ├── review_digest.py          # Quarterly and annual review emails
│   └── config.py                 # Centralised config — reads from env vars
├── scripts/
│   └── ig_auth.py                # One-time Instagram OAuth setup
├── requirements.txt
├── .env.example
├── README.md
├── SETUP.md
└── MAINTENANCE.md
```

## Tabs

| Tab | Source | Notes |
|-----|--------|-------|
| `ig_pulse` | Instagram Graph API | Weekly account-level metrics |
| `ig_stars` | Instagram Graph API | Per-post metrics |
| `web_pulse` | Google Analytics 4 | Weekly website metrics |

## Quick reference — credentials

| Secret | Source |
|--------|--------|
| `IG_APP_ID` / `IG_APP_SECRET` | Meta Developer app (reuse from repo 1) |
| `IG_ACCESS_TOKEN` | Run `scripts/ig_auth.py` for this account |
| `IG_ACCOUNT_ID` | Output of `scripts/ig_auth.py` |
| `GA4_PROPERTY_ID` | GA4 Admin → Property Settings (9-10 digit number) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | New Google Cloud project service account JSON |
| `GOOGLE_SPREADSHEET_ID` | From sheet URL between `/d/` and `/edit` |
| `EMAIL_SENDER` / `EMAIL_PASSWORD` / `EMAIL_RECIPIENT` | Gmail + App Password |
| `GOOGLE_AI_API_KEY` | Google AI Studio (reuse from repo 1) |

## Running locally

```bash
pip3 install -r requirements.txt
cp .env.example .env
# fill in credentials

python3 src/main.py                                        # weekly pipeline
python3 src/review_runner.py --quarterly --q 1 --year 2026 # specific quarterly review
python3 src/review_runner.py --annual --year 2026          # annual review
python3 src/review_runner.py --all                         # both (Dec 31 simulation)
```

## Schedule

| Job | When | What |
|-----|------|------|
| Weekly pipeline | Every Monday 8AM UTC | IG + GA4 + email digest |
| Q1 review | March 31 | Jan–Mar summary |
| Q2 review | June 30 | Apr–Jun summary |
| Q3 review | September 30 | Jul–Sep summary |
| Q4 + Annual | December 31 | Oct–Dec + full year |

See `SETUP.md` for first-time setup and `MAINTENANCE.md` for ongoing maintenance.