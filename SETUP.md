# Setup Guide — B2B Analytics Pipeline

Complete first-time setup for the B2B Instagram + Google Analytics pipeline.
Follow steps in order.

---

## Prerequisites

- Python 3.11+
- Instagram Business account (separate from repo 1)
- GA4 already tracking on your website
- A Gmail account with 2-Step Verification enabled
- A GitHub account

---

## Step 1 — Instagram API

The Meta app setup is identical to repo 1. You can reuse the **same Meta app**
since one app supports multiple Instagram accounts. You just need a separate
access token and account ID for this second Instagram account.

### 1.1 Add this Instagram account as a tester
1. Go to your existing Meta app → App Roles → Instagram Testers
2. Add your second Instagram account
3. Accept the invite at **instagram.com/accounts/manage_access/**

### 1.2 Generate access token (manual OAuth flow)

The redirect URI `https://localhost/` should already be saved from repo 1 setup.

Open this URL in your browser (use the same App ID as repo 1):
```
https://api.instagram.com/oauth/authorize?client_id=YOUR_APP_ID&redirect_uri=https://localhost/&scope=instagram_business_basic,instagram_business_manage_insights&response_type=code
```

Log in with **this account's** Instagram. Copy the code from the redirect URL.

Exchange for short-lived token:
```bash
curl -X POST "https://api.instagram.com/oauth/access_token" \
  -d "client_id=YOUR_APP_ID" \
  -d "client_secret=YOUR_APP_SECRET" \
  -d "grant_type=authorization_code" \
  -d "redirect_uri=https://localhost/" \
  -d "code=YOUR_CODE"
```

Exchange for long-lived token:
```bash
curl "https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=YOUR_APP_SECRET&access_token=YOUR_SHORT_LIVED_TOKEN"
```

Get your account ID:
```bash
curl "https://graph.instagram.com/me?fields=id,username&access_token=YOUR_LONG_LIVED_TOKEN"
```

Save as `IG_ACCESS_TOKEN` and `IG_ACCOUNT_ID`.

---

## Step 2 — Google Analytics 4 setup

### 2.1 Find your GA4 Property ID
1. Go to [analytics.google.com](https://analytics.google.com)
2. Click the **Admin** gear icon (bottom left)
3. Under **Property**, click **Property Settings**
4. Your **Property ID** is the 9-10 digit number at the top right
5. Save as `GA4_PROPERTY_ID` — just the number, no "properties/" prefix

### 2.2 Set up GA4 Conversions (highly recommended for B2B)

Conversions tell you when someone takes a meaningful action on your site.
For a B2B service business, the most valuable conversions are:

**Contact form submission:**
1. In GA4, go to **Admin → Events**
2. Find the event that fires when your form submits
   (common names: `form_submit`, `generate_lead`, `contact`)
3. Click the toggle to mark it as a **Conversion**

**Contact button click / phone click:**
1. In GA4 go to **Admin → Events → Create Event**
2. Create a new event that triggers when someone clicks your contact CTA
3. Mark it as a Conversion

**If you don't see form events yet:**
This means your form platform isn't sending events to GA4. Most platforms
(Squarespace, Wix, Webflow, Typeform, etc.) have a GA4 integration — check
your form platform's settings to enable GA4 event tracking.

> Once conversions are set up, add them to `src/ga4_collector.py` —
> see comments in that file for where to add conversion metrics.

### 2.3 Grant service account access to GA4
1. In GA4, go to **Admin → Account Access Management** (top of left column)
2. Click **+** → **Add users**
3. Enter your service account email
   (from your service_account.json `client_email` field)
4. Set role to **Viewer**
5. Click **Add**

> ⚠️ This is the step people most often miss. Without it you'll get a
> permission error when the pipeline tries to read GA4 data.

---

## Step 3 — Google Cloud (new project, separate from repo 1)

### 3.1 Create a new project
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown → **New Project** → name it (e.g. "B2B Analytics") → Create
3. Make sure the new project is selected

### 3.2 Enable APIs
1. Search **"Google Sheets API"** → Enable
2. Search **"Google Drive API"** → Enable
3. Search **"Google Analytics Data API"** → Enable ← new for this repo

### 3.3 Create a Service Account
1. Go to **APIs & Services → Credentials → + Create Credentials → Service Account**
2. Name it (e.g. "analytics-reader") → **Create and Continue** → skip roles → **Done**

### 3.4 Download JSON key
1. Click the service account → **Keys** tab → **Add Key → Create New Key → JSON**
2. Save the downloaded file — this is your `GOOGLE_SERVICE_ACCOUNT_JSON`

### 3.5 Share your Google Sheet
Find `client_email` in the JSON file and share your Google Sheet with that
email address (Editor access).

### 3.6 Grant GA4 access
Use the same `client_email` to add the service account as a Viewer in GA4
(see Step 2.3 above).

---

## Step 4 — Gmail App Password

Reuse your existing App Password from repo 1, or create a new one:
1. [myaccount.google.com](https://myaccount.google.com) → Security → App Passwords
2. Create a new one named "B2B Analytics Pipeline"
3. Save the 16-char password (no spaces)

---

## Step 5 — Google AI Studio

Reuse your existing `GOOGLE_AI_API_KEY` from repo 1.

---

## Step 6 — Google Sheet tabs

Create a Google Sheet with exactly these three tab names:
- `ig_pulse`
- `ig_stars`
- `web_pulse`

Headers are written automatically on the first run.

---

## Step 7 — GitHub Setup

### 7.1 Create a new private repo
```bash
cd your-repo2-folder
git init
git add .
git commit -m "Initial pipeline setup"
git branch -M main
git remote add origin https://github.com/YOURUSERNAME/b2b-analytics.git
git push -u origin main
```

### 7.2 Move workflow file
Make sure `weekly_pipeline.yml` is in `.github/workflows/`:
```bash
mkdir -p .github/workflows
mv weekly_pipeline.yml .github/workflows/
git add .github/workflows/weekly_pipeline.yml
git commit -m "Add GitHub Actions workflow"
git push
```

### 7.3 Add GitHub Secrets
Go to repo → **Settings → Secrets and variables → Actions**:

```
IG_APP_ID           ← same as repo 1
IG_APP_SECRET       ← same as repo 1
IG_ACCESS_TOKEN     ← NEW token for this account
IG_ACCOUNT_ID       ← NEW account ID for this account
GA4_PROPERTY_ID     ← your GA4 property ID
GOOGLE_SERVICE_ACCOUNT_JSON  ← NEW service account JSON (different project)
GOOGLE_SPREADSHEET_ID        ← this repo's spreadsheet ID
EMAIL_SENDER        ← same Gmail as repo 1 is fine
EMAIL_PASSWORD      ← same App Password is fine
EMAIL_RECIPIENT     ← where to send the digest
GOOGLE_AI_API_KEY   ← same as repo 1
```

### 7.4 Test
Go to **Actions → Weekly Analytics Pipeline → Run workflow → Run workflow**
and watch the logs.

---

## Adding conversions to the pipeline later

Once GA4 conversions are set up and tracking, add them to `src/ga4_collector.py`:

In `collect_web_pulse()`, add to the `_get_user_metrics` call or create a new
`_get_conversions()` function using the `conversions` metric and filtering by
`eventName`. Then add the new columns to `WEB_PULSE_HEADERS`.

See the Google Analytics Data API docs for the exact metric names.

---

## Step 8 — Test the review emails

Once the weekly pipeline is working, test the reviews:

```bash
# Current quarter
python3 src/review_runner.py --quarterly

# Current year
python3 src/review_runner.py --annual

# Both at once (simulates Dec 31)
python3 src/review_runner.py --all

# Specific quarter/year
python3 src/review_runner.py --quarterly --q 1 --year 2026
python3 src/review_runner.py --annual --year 2026
```

You can also trigger from GitHub Actions → Run workflow → select mode dropdown.

> Review emails read all historical data from your Google Sheet.
> The more weeks of data in the sheet, the more meaningful the insights.