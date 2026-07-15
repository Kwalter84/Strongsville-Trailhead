# The Strongsville Trailhead — Automated Weekly Newsletter

A fully automated system that finds genuinely positive local news and family/kids
events for Strongsville, OH, curates it with Claude, and emails it to your
subscriber list every Friday — no manual work once it's set up.

## How it works

```
Signup page (signup.html)
        │
        ▼
Google Sheet + Apps Script  ──(subscriber list)──►  Python script
        ▲                                                  │
        │                                       Google News RSS (Strongsville)
        │                                                  │
        │                                          Claude API (curates &
        │                                           writes the newsletter)
        │                                                  │
        │                                                  ▼
        └──────────────  GitHub Actions (runs weekly)  ──►  SendGrid ──► inboxes
```

## One-time setup (about 30–45 minutes)

### 1. Subscriber list & signup page
1. Create a new Google Sheet. Name the first tab `Subscribers`, header row: `Email | SignupDate | Status`.
2. In the Sheet: **Extensions → Apps Script**, paste in `apps_script/Code.gs`.
3. Edit `SECRET_KEY` in that file to any random string.
4. **Deploy → New deployment → Web app** → Execute as "Me", access "Anyone". Copy the URL.
5. Open `signup.html`, paste that URL into `APPS_SCRIPT_URL`.
6. Host `signup.html` anywhere free: GitHub Pages, Netlify, or Google Sites. This is the page you'll share/link to get subscribers.

### 2. Email sending (SendGrid)
1. Create a free SendGrid account (100 emails/day free tier — plenty to start).
2. Verify a sender email address (Settings → Sender Authentication).
3. Create an API key (Settings → API Keys → Full Access).

### 3. Claude API
1. Get an API key at console.anthropic.com.

### 4. Put it all on GitHub so it runs automatically
1. Create a new **private** GitHub repo, push this whole folder to it.
2. Go to **Settings → Secrets and variables → Actions** and add:
   - `ANTHROPIC_API_KEY`
   - `SENDGRID_API_KEY`
   - `SENDER_EMAIL` (the address you verified in SendGrid)
   - `APPS_SCRIPT_URL`
   - `APPS_SCRIPT_SECRET` (same string as `SECRET_KEY` in Code.gs)
3. That's it — `.github/workflows/weekly-newsletter.yml` will run automatically every Friday at 8am ET.

### Test it before Friday
Go to the **Actions** tab in your repo → "Weekly Strongsville Newsletter" → **Run workflow**.
This triggers it immediately so you can check your inbox and fix anything before it goes live.

## What the newsletter includes each week
- **Community Wins** — good local news, civic wins, volunteering
- **Work & Local Business** — new businesses, local economic good news
- **Family & Kids Corner** — actual events happening that week
- **School & Youth Achievements** — student/school/youth sports shoutouts
- **Weekend Ideas for Young Families** — Claude-written, evergreen local suggestions (parks, library storytimes, rec center, etc.)

## Ideas to grow engagement with young families
These aren't built yet, but are natural next additions once the base system is running:
- **"Strongsville Star Kid" shoutout** — a simple Google Form where parents nominate a kid; feature one per week
- **Referral rewards** — track signups per referral link, offer a small local-business gift card at milestones (ask a local coffee shop/ice cream place to sponsor)
- **Themed seasonal issues** — a Halloween trick-or-treat map issue, a "first day of school" issue, a summer splash-pad guide
- **Reply-to-submit** — let readers reply directly to the email with tips/events; route replies to your inbox instead of a no-reply address
- **A "free this weekend" ticker** — a dedicated line at the top listing only $0-cost family activities

## Editing the design
- `signup.html` — the public signup page (self-contained, no dependencies)
- `newsletter_generator.py` → `build_html()` — the email template. Colors/fonts match the signup page (pine green `#153328`, gold `#D9A441`, cream `#F7F1E3`).

## Costs at this scale
- Google Sheets/Apps Script: free
- SendGrid: free up to 100 emails/day
- Claude API: roughly a few cents per week (one call, ~4000 tokens)
- GitHub Actions: free for public/private repos at this usage level
