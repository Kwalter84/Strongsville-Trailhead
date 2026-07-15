# Building The Strongsville Trailhead — Full Step-by-Step Guide

This walks through every account and click needed to go from zero to a live,
automated weekly newsletter. Budget about 45–60 minutes total. Everything is
free at this scale.

You'll be setting up 5 things, in this order:
1. Google Sheet + Apps Script (your subscriber database + tip inbox)
2. Google Form (the "submit a tip" form, for Facebook/word-of-mouth finds)
3. SendGrid (actually sends the emails)
4. Anthropic API key (Claude curates and writes the newsletter)
5. GitHub (hosts the code and runs it automatically every week)

---

## Part 1 — Google Sheet + Apps Script (subscriber list & tip inbox)

1. Go to **sheets.google.com** and create a new blank spreadsheet. Name it "Strongsville Trailhead Data".
2. Rename the first tab (bottom left) to `Subscribers`. In row 1, add headers: `Email`, `SignupDate`, `Status`.
3. Click the `+` to add a second tab. Name it `Tips`. In row 1, add headers: `Timestamp`, `Tip`, `Link`, `Submitted By`.
4. Go to **Extensions → Apps Script**. This opens a code editor tied to your sheet.
5. Delete the placeholder `myFunction() {}` code that's there.
6. Open the `apps_script/Code.gs` file I gave you, copy the whole thing, and paste it into the Apps Script editor.
7. In the pasted code, find `const SECRET_KEY = "CHANGE_ME_TO_A_RANDOM_STRING";` and replace the string with something random you make up (e.g. a long password). Write it down — you'll need it twice more.
8. Click the **Save** icon (or Ctrl/Cmd+S).
9. Click **Deploy → New deployment**.
   - Click the gear icon next to "Select type" → choose **Web app**.
   - Description: "Trailhead backend" (or anything).
   - Execute as: **Me**.
   - Who has access: **Anyone**.
   - Click **Deploy**.
10. It'll ask you to authorize — click through the Google permission prompts (this is normal for your own script).
11. Copy the **Web app URL** it gives you. This is your `APPS_SCRIPT_URL`. Save it somewhere.

✅ Checkpoint: You now have a live backend URL and a secret key.

---

## Part 2 — Google Form for tips (Facebook finds & word-of-mouth)

Since Facebook doesn't allow pulling content from Pages/Groups you don't own,
this form is how those finds get into the newsletter — readers forward what
they see, and it feeds the same pipeline as the RSS sources.

1. Go to **forms.google.com** and create a new form. Title it "Strongsville Trailhead — Submit a Tip".
2. Add 3 questions:
   - Short answer: **"What's the good news or event?"** (required)
   - Short answer: **"Link (optional — Facebook post, article, event page, etc.)"**
   - Short answer: **"Your name (optional)"**
3. Click the **Responses** tab at the top → click the green Sheets icon → **Select existing spreadsheet** → choose your "Strongsville Trailhead Data" sheet → it will create a new response tab automatically.
4. This auto-created tab won't be named exactly `Tips` — rename it to `Tips` (right-click the tab → Rename), and make sure the column order matches: `Timestamp`, `Tip`, `Link`, `Submitted By`. If the Form's own headers differ, just relabel row 1 to match, or reorder the Form's questions to match this order before people start submitting.
5. Click **Send** (top right) → click the link icon → copy the form's public URL.
6. Open `signup.html`, find `PASTE_YOUR_GOOGLE_FORM_URL_HERE`, and paste this URL in.

✅ Checkpoint: Tips submitted via the form now land directly in your Tips sheet, and your Apps Script backend (Part 1) can already read them.

---

## Part 3 — SendGrid (email sending)

1. Go to **sendgrid.com** and sign up for a free account (100 emails/day free — plenty to start).
2. Verify your email address when prompted.
3. Go to **Settings → Sender Authentication**. Either:
   - Verify a **Single Sender** (fastest — just verify one email address you own), or
   - Set up full domain authentication if you have your own domain (better long-term deliverability, optional for now).
4. Go to **Settings → API Keys → Create API Key**. Choose **Full Access**. Copy the key immediately — SendGrid only shows it once.

✅ Checkpoint: You have a `SENDGRID_API_KEY` and a verified `SENDER_EMAIL`.

---

## Part 4 — Anthropic API key (Claude)

1. Go to **console.anthropic.com** and create an account.
2. Go to **API Keys** → **Create Key**. Copy it.
3. Add a small amount of credit (a few dollars covers many months at this usage level — one call of ~4,000 tokens per week).

✅ Checkpoint: You have an `ANTHROPIC_API_KEY`.

---

## Part 5 — GitHub (hosting + automatic weekly run)

1. Go to **github.com** and create a free account if you don't have one.
2. Click **New repository**. Name it `strongsville-trailhead`. Set it to **Private**. Create it.
3. Upload all the project files (drag-and-drop works on the repo's main page, or use `git push` if you're comfortable with git) — keep the folder structure intact, especially `.github/workflows/weekly-newsletter.yml`.
4. Go to **Settings → Secrets and variables → Actions → New repository secret**. Add each of these one at a time:
   - `ANTHROPIC_API_KEY` → from Part 4
   - `SENDGRID_API_KEY` → from Part 3
   - `SENDER_EMAIL` → the address you verified in Part 3
   - `APPS_SCRIPT_URL` → from Part 1
   - `APPS_SCRIPT_SECRET` → the random string you set in Part 1

✅ Checkpoint: Your code and secrets are in place. The workflow is scheduled to run every Friday at 8am ET automatically — you don't need to do anything else for it to keep running.

---

## Part 6 — Host the signup page

`signup.html` needs a public URL so you can share it. Easiest free option:
1. In the same GitHub repo, go to **Settings → Pages**.
2. Under "Source," choose the branch (`main`) and root folder → **Save**.
3. GitHub gives you a URL like `https://yourusername.github.io/strongsville-trailhead/signup.html`. That's shareable anywhere — Facebook groups, flyers, the City newsletter, etc.

---

## Part 7 — Test before it goes live

1. In your GitHub repo, go to the **Actions** tab → click "Weekly Strongsville Newsletter" → **Run workflow** → **Run workflow** (this triggers it manually).
2. Watch it run (takes 1–2 minutes). If it fails, click into the failed step to see the error — most issues are a typo'd secret or a missing sheet tab name.
3. Sign yourself up via the live `signup.html` page first, so the test send has somewhere to go.
4. Check your inbox.

Once that works, share the signup link and let it run itself every Friday.

---

## Quick reference — all 5 secrets you'll need

| Secret | Where you got it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `SENDGRID_API_KEY` | SendGrid → Settings → API Keys |
| `SENDER_EMAIL` | The address you verified in SendGrid |
| `APPS_SCRIPT_URL` | Apps Script → Deploy → Web app URL |
| `APPS_SCRIPT_SECRET` | The random string you made up in Code.gs |

## Troubleshooting
- **"Unauthorized" from Apps Script** → your `APPS_SCRIPT_SECRET` GitHub secret doesn't match `SECRET_KEY` in Code.gs exactly.
- **No subscribers found** → make sure the Subscribers sheet's `Status` column says exactly `active` (lowercase) for each row.
- **Newsletter comes back empty** → normal some weeks if genuinely nothing positive happened; check `latest_issue.html` in the workflow's uploaded artifact to see what Claude selected (or didn't).
- **SendGrid 403 error** → your sender email isn't verified yet (Part 3, step 3).
